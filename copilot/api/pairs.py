"""Oráculo nivel B: pares entrada/salida esperados que aporta el usuario (sintéticos o anonimizados).

Formato (JSON, una lista):
    [{"id": "P01", "input": {"monto": "1000.00", "dias": 30}, "output": {"interes": "12.50"}},
     {"id": "P02", "input": {"monto": "0"}, "error": {"code": "E01", "message": "Monto inválido"}}]

- Decimales SIEMPRE como string (nunca float): se rechaza el archivo si trae floats.
- Cada par tiene `output` o `error`, no ambos. `id` es opcional (se numera P001, P002...).
- Al subirlos solo se valida la forma; contra el contrato de la especificación se validan al aprobarla,
  porque los nombres de los campos los define la extracción.
- Si el legacy se puede ejecutar (nivel A), los pares se usan como casos y manda la ejecución real.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from copilot.contracts import Case, CaseOutput, Spec

MAX_BYTES = 1024 * 1024
MAX_PAIRS = 500
FILE_NAME = "expected_pairs.json"


class PairsError(Exception):
    def __init__(self, status: int, code: str, message: str, action: str):
        super().__init__(message)
        self.status, self.code, self.message, self.action = status, code, message, action


def _fail(message: str, action: str = "Corrige el archivo y vuelve a subirlo.") -> PairsError:
    return PairsError(422, "PAIRS_INVALID", message, action)


def parse(name: str, data: bytes) -> list[tuple[Case, CaseOutput]]:
    """Valida la forma del archivo y devuelve (caso, salida esperada) por par."""
    if len(data) > MAX_BYTES:
        raise PairsError(413, "PAIRS_TOO_LARGE", "El archivo de pares supera 1 MB.", "Envía menos pares (máximo 500).")
    if not name.lower().endswith(".json"):
        raise _fail("Los pares deben venir en un archivo .json.", "Usa el formato descrito en samples/README.md.")
    try:
        raw = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail(f"El archivo no es JSON válido ({type(exc).__name__}).") from None
    if not isinstance(raw, list) or not raw:
        raise _fail("El archivo debe ser una lista JSON con al menos un par.")
    if len(raw) > MAX_PAIRS:
        raise PairsError(413, "PAIRS_TOO_LARGE", f"Hay {len(raw)} pares (máximo {MAX_PAIRS}).", "Reduce la cantidad de pares.")
    pairs: list[tuple[Case, CaseOutput]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("input"), dict):
            raise _fail(f"Par {i}: falta el objeto 'input'.")
        has_out, has_err = item.get("output") is not None, item.get("error") is not None
        if has_out == has_err:
            raise _fail(f"Par {i}: debe tener 'output' o 'error' (exactamente uno).")
        pid = str(item.get("id") or f"P{i:03d}")
        if pid in seen:
            raise _fail(f"Par {i}: el id {pid} está repetido.")
        seen.add(pid)
        try:
            case = Case(id=pid, input=item["input"], tags=["par-provisto"], description=str(item.get("description", "")))
            out = CaseOutput(id=pid, output=item.get("output"), error=item.get("error"))
        except ValidationError as exc:
            detail = exc.errors()[0]
            raise _fail(f"Par {i} ({pid}): {detail.get('msg', 'valor inválido')}.",
                        "Escribe los decimales como texto, por ejemplo \"1250.50\".") from None
        pairs.append((case, out))
    return pairs


def check_against(spec: Spec, pairs: list[tuple[Case, CaseOutput]]) -> list[str]:
    """Problemas de los pares frente al contrato aprobado (lista vacía si todo cuadra)."""
    inputs = {f.name for f in spec.io.inputs}
    required = {f.name for f in spec.io.inputs if f.required}
    outputs = {f.name for f in spec.io.outputs}
    codes = {e.code for e in spec.io.errors}
    problems: list[str] = []
    for case, out in pairs:
        keys = set(case.input)
        if extra := keys - inputs:
            problems.append(f"{case.id}: entradas desconocidas {sorted(extra)}")
        if missing := required - keys:
            problems.append(f"{case.id}: faltan entradas {sorted(missing)}")
        if out.error is not None:
            if codes and out.error.code not in codes:
                problems.append(f"{case.id}: código de error {out.error.code} no está en el contrato {sorted(codes)}")
            continue
        rows = out.output if isinstance(out.output, list) else [out.output or {}]
        if isinstance(out.output, list) != spec.io.output_is_list:
            problems.append(f"{case.id}: la salida debe ser {'una lista de filas' if spec.io.output_is_list else 'un objeto'}")
            continue
        for row in rows:
            if set(row) != outputs:
                problems.append(f"{case.id}: salidas {sorted(row)} ≠ contrato {sorted(outputs)}")
                break
    return problems


def contract_hint(spec: Spec) -> str:
    ins = ", ".join(f.name for f in spec.io.inputs)
    outs = ", ".join(f.name for f in spec.io.outputs)
    return f"Entradas esperadas: {ins}. Salidas esperadas: {outs}."


def save(folder: Path, pairs: list[tuple[Case, CaseOutput]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    payload = [{"case": c.model_dump(), "expected": o.model_dump()} for c, o in pairs]
    (folder / FILE_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(folder: Path) -> list[tuple[Case, CaseOutput]] | None:
    path = folder / FILE_NAME
    if not path.is_file():
        return None
    return [(Case.model_validate(p["case"]), CaseOutput.model_validate(p["expected"]))
            for p in json.loads(path.read_text(encoding="utf-8"))]
