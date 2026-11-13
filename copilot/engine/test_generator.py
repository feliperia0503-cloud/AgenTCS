"""Agente QA: casos de caracterización a partir de la Spec.

Combina casos propuestos por el LLM con casos deterministas: fronteras de cada condición numérica
(umbral exacto y ± la unidad mínima del tipo) y extremos de cada tipo. Los valores esperados NO se
inventan aquí: los produce el oráculo (oracle.py).
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from copilot.contracts import Case, NeutralType, Phase, Spec, TypeKind

from .llm import LLMClient, complete_json
from .prompts import TESTS_SYSTEM

MAX_CASES = 40
_COMPARISON = re.compile(r"\b([A-Za-z_]\w*)\s*(>=|<=|==|!=|<>|>|<|=)\s*(-?\d+(?:\.\d+)?)")


class CaseDraft(BaseModel):
    description: str = ""
    input: dict[str, Any]
    rule_ids: list[str] = []
    kind: str = "tipico"


class CasesResponse(BaseModel):
    cases: list[CaseDraft]


def _format(value: Any, t: NeutralType) -> Any:
    """Normaliza un valor de entrada al formato del contrato (decimales como string)."""
    if value is None:
        return None
    if t.kind == TypeKind.DECIMAL:
        try:
            return format(Decimal(str(value)), "f")
        except InvalidOperation:
            return str(value)   # inválido a propósito: lo juzga el oráculo
    if t.kind == TypeKind.INTEGER:
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return str(value)
    if t.kind == TypeKind.FLOAT:
        return str(value)
    return value


def _normalize(raw: dict[str, Any], types: dict[str, NeutralType]) -> dict[str, Any]:
    return {k: _format(v, types[k]) if k in types else (str(v) if isinstance(v, float) else v)
            for k, v in raw.items()}


def _unit(t: NeutralType) -> Decimal:
    return Decimal(1).scaleb(-(t.scale or 0)) if t.kind == TypeKind.DECIMAL else Decimal(1)


def _num(t: NeutralType, value: Decimal) -> Any:
    if t.kind == TypeKind.DECIMAL:
        return format(value.quantize(_unit(t)), "f")
    return int(value)


def boundary_cases(spec: Spec, base: dict[str, Any]) -> list[tuple[dict[str, Any], list[str], str]]:
    """Variantes del caso base en el umbral de cada condición y en ± la unidad mínima del tipo."""
    types = {f.name: f.type for f in spec.io.inputs}
    out = []
    for rule in spec.active_rules or spec.rules:
        for var, _op, number in _COMPARISON.findall(rule.condition or ""):
            t = types.get(var)
            if t is None or t.kind not in (TypeKind.DECIMAL, TypeKind.INTEGER):
                continue
            threshold, unit = Decimal(number), _unit(t)
            for value in (threshold - unit, threshold, threshold + unit):
                out.append(({**base, var: _num(t, value)}, [rule.id], f"Frontera de {rule.id}: {var}={value}"))
    for name, t in types.items():
        if t.kind == TypeKind.DECIMAL and t.precision is not None:
            top = Decimal(10) ** (t.precision - (t.scale or 0)) - _unit(t)
            out.append(({**base, name: _num(t, top)}, [], f"Máximo de {name}"))
            out.append(({**base, name: _num(t, Decimal(0))}, [], f"Cero en {name}"))
    return out


def generate_cases(llm: LLMClient, spec: Spec, max_cases: int = MAX_CASES) -> list[Case]:
    payload = {"io": spec.io.model_dump(mode="json"),
               "reglas": [{"id": r.id, "nombre": r.name, "condicion": r.condition, "accion": r.action,
                           "tipo_resultado": r.result_type.describe() if r.result_type else None}
                          for r in (spec.active_rules or spec.rules)]}
    prompt = (f"Especificación aprobada:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
              f"Devuelve entre 8 y 20 casos con este JSON Schema:\n"
              f"{json.dumps(CasesResponse.model_json_schema(), ensure_ascii=False)}")
    drafts = complete_json(llm, TESTS_SYSTEM, prompt, CasesResponse, agent="tests", phase=Phase.VERIFICACION).cases
    types = {f.name: f.type for f in spec.io.inputs}
    candidates = [(_normalize(d.input, types), d.rule_ids + [d.kind], d.description) for d in drafts]
    base = next((c[0] for c in candidates if "tipico" in c[1]), candidates[0][0] if candidates else None)
    if base is not None:
        candidates += [(inp, tags + ["borde"], desc) for inp, tags, desc in boundary_cases(spec, base)]
    cases, seen = [], set()
    for inp, tags, desc in candidates:
        key = json.dumps(inp, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        cases.append(Case(id=f"C{len(cases) + 1:03d}", input=inp, tags=sorted(set(tags)), description=desc))
        if len(cases) >= max_cases:
            break
    return cases
