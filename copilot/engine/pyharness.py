"""Arnés de ejecución para código Python (destino 'python' y oráculo de referencia nivel C).

El módulo objetivo expone `run(input: dict) -> dict | list | {"error": {"code", "message"}}`.
El arnés lee cases.json, ejecuta cada caso aislando excepciones y escribe actual.json con
decimales como string (contrato CaseOutput).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from copilot.contracts import CaseOutput

from .sandbox import ProcResult, run_cmd

HARNESS_FILE = "_agentcs_harness.py"

_TEMPLATE = '''import json, sys, importlib
from decimal import Decimal

def _norm(v):
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return v

def main(cases_path, out_path):
    target = importlib.import_module("__MODULE__")
    out = []
    for case in json.load(open(cases_path, encoding="utf-8")):
        try:
            result = target.run(case["input"])
            if isinstance(result, dict) and "error" in result and result["error"]:
                err = result["error"]
                out.append({"id": case["id"], "error": {"code": str(err.get("code", "")),
                                                          "message": str(err.get("message", ""))}})
            else:
                out.append({"id": case["id"], "output": _norm(result)})
        except Exception as exc:
            out.append({"id": case["id"], "error": {"code": "EXEC_ERROR", "message": type(exc).__name__ + ": " + str(exc)[:200]}})
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
'''


class HarnessError(Exception):
    """El arnés no pudo correr (import fallido, error de sintaxis...). Es retroalimentación válida."""

    def __init__(self, result: ProcResult):
        super().__init__(result.tail())
        self.result = result


def harness_source(module: str) -> str:
    return _TEMPLATE.replace("__MODULE__", module)


def run_python_module(workdir: Path, module: str, cases: list, timeout: float | None = None) -> list[CaseOutput]:
    (workdir / HARNESS_FILE).write_text(harness_source(module), encoding="utf-8")
    (workdir / "cases.json").write_text(json.dumps([c.model_dump() for c in cases], ensure_ascii=False),
                                        encoding="utf-8")
    actual = workdir / "actual.json"
    actual.unlink(missing_ok=True)
    kwargs = {"timeout": timeout} if timeout else {}
    result = run_cmd([sys.executable, HARNESS_FILE, "cases.json", "actual.json"], workdir, **kwargs)
    if not result.ok or not actual.is_file():
        raise HarnessError(result)
    return [CaseOutput.model_validate(o) for o in json.loads(actual.read_text(encoding="utf-8"))]
