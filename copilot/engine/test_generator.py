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
TABLES_KEY = "_tablas"
TABLE_KIND = "tabla"
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


def table_types(spec: Spec) -> dict[str, dict[str, NeutralType]]:
    """Columnas tipadas de cada tabla declarada en la Spec (Entity.kind == 'tabla')."""
    return {e.name.lower(): {f.name.lower(): f.type for f in e.fields} for e in spec.entities if e.kind == TABLE_KIND}


def _normalize_tables(raw: Any, tables: dict[str, dict[str, NeutralType]]) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for name, rows in raw.items():
        cols = tables.get(name.lower(), {})
        out[name.lower()] = ([_normalize({k.lower(): v for k, v in r.items()}, cols) for r in rows if isinstance(r, dict)]
                             if isinstance(rows, list) else [])
    return out


def _normalize(raw: dict[str, Any], types: dict[str, NeutralType],
               tables: dict[str, dict[str, NeutralType]] | None = None) -> dict[str, Any]:
    out = {k: _format(v, types[k]) if k in types else (str(v) if isinstance(v, float) else v)
           for k, v in raw.items() if k != TABLES_KEY}
    if tables or TABLES_KEY in raw:
        out[TABLES_KEY] = _normalize_tables(raw.get(TABLES_KEY), tables or {})
    return out


def with_base_tables(inp: dict[str, Any], base: dict[str, list[dict[str, Any]]] | None) -> dict[str, Any]:
    """Las tablas que el caso no menciona heredan el estado base (configuración + datos de prueba).
    Una tabla presente en el caso REEMPLAZA a la base (lista vacía = tabla vacía)."""
    if not base:
        return inp
    own = {k.lower(): v for k, v in (inp.get(TABLES_KEY) or {}).items()}
    return {**inp, TABLES_KEY: {**{k.lower(): v for k, v in base.items()}, **own}}


def _unit(t: NeutralType) -> Decimal:
    return Decimal(1).scaleb(-(t.scale or 0)) if t.kind == TypeKind.DECIMAL else Decimal(1)


def _num(t: NeutralType, value: Decimal) -> Any:
    if t.kind == TypeKind.DECIMAL:
        return format(value.quantize(_unit(t)), "f")
    return int(value)


def _with_column(base: dict[str, Any], table: str, column: str, value: Any) -> dict[str, Any]:
    """Copia del caso base con la columna cambiada en la PRIMERA fila de la tabla."""
    tables = {k: [dict(r) for r in v] for k, v in base.get(TABLES_KEY, {}).items()}
    tables[table][0][column] = value
    return {**base, TABLES_KEY: tables}


def _variants(base: dict[str, Any], var: str, types: dict[str, NeutralType],
              tables: dict[str, dict[str, NeutralType]]):
    """Dónde vive la variable de la condición: parámetro de entrada o columna de una tabla con filas."""
    if var in types:
        return types[var], lambda v: {**base, var: v}
    rows = base.get(TABLES_KEY, {})
    for table, cols in tables.items():
        col = next((c for c in cols if c.lower() == var.lower()), None)
        if col and rows.get(table):
            return cols[col], lambda v, t=table, c=col: _with_column(base, t, c, v)
    return None, None


def boundary_cases(spec: Spec, base: dict[str, Any]) -> list[tuple[dict[str, Any], list[str], str]]:
    """Variantes del caso base en el umbral de cada condición y en ± la unidad mínima del tipo.
    La variable puede ser un parámetro o una columna de tabla (frecuente en PL/SQL)."""
    types = {f.name: f.type for f in spec.io.inputs}
    tables = table_types(spec)
    out = []
    for rule in spec.active_rules or spec.rules:
        for var, _op, number in _COMPARISON.findall(rule.condition or ""):
            t, make = _variants(base, var, types, tables)
            if t is None or t.kind not in (TypeKind.DECIMAL, TypeKind.INTEGER):
                continue
            threshold, unit = Decimal(number), _unit(t)
            for value in (threshold - unit, threshold, threshold + unit):
                out.append((make(_num(t, value)), [rule.id], f"Frontera de {rule.id}: {var}={value}"))
    for name, t in types.items():
        if t.kind == TypeKind.DECIMAL and t.precision is not None:
            top = Decimal(10) ** (t.precision - (t.scale or 0)) - _unit(t)
            out.append(({**base, name: _num(t, top)}, [], f"Máximo de {name}"))
            out.append(({**base, name: _num(t, Decimal(0))}, [], f"Cero en {name}"))
    return out


OFFICIAL = "oficial"


def _prompt(spec: Spec, tables: dict[str, dict[str, NeutralType]], base: dict[str, list] | None,
            run_scripts: list[str]) -> str:
    payload = {"io": spec.io.model_dump(mode="json"),
               "tablas": {name: {c: t.describe() for c, t in cols.items()} for name, cols in tables.items()},
               "reglas": [{"id": r.id, "nombre": r.name, "condicion": r.condition, "accion": r.action,
                           "tipo_resultado": r.result_type.describe() if r.result_type else None}
                          for r in (spec.active_rules or spec.rules)]}
    parts = [f"Especificación aprobada:\n{json.dumps(payload, ensure_ascii=False)}"]
    if base:
        parts.append("Estado BASE de la base de datos (configuración del sistema + datos de prueba del cliente). "
                     "Cada caso hereda estas tablas; en input._tablas incluye SOLO las tablas que tu caso cambia "
                     "(la tabla que incluyas reemplaza completa a la base; usa ids nuevos para filas nuevas):\n"
                     f"{json.dumps(base, ensure_ascii=False)[:30000]}")
    if run_scripts:
        parts.append("Scripts de ejecución provistos por el cliente. El PRIMER caso debe tener kind \"oficial\": "
                     "reproduce EXACTAMENTE esa ejecución (mismos parámetros) sobre el estado base, sin _tablas:\n"
                     + "\n---\n".join(run_scripts))
    parts.append("Devuelve entre 8 y 20 casos con este JSON Schema:\n"
                 f"{json.dumps(CasesResponse.model_json_schema(), ensure_ascii=False)}")
    return "\n\n".join(parts)


def generate_cases(llm: LLMClient, spec: Spec, max_cases: int = MAX_CASES, *,
                   base_tables: dict[str, list[dict[str, Any]]] | None = None,
                   run_scripts: list[str] | None = None) -> list[Case]:
    """Casos del LLM + fronteras deterministas. Con base_tables, el caso oficial (si hay script de ejecución)
    va primero y todos los casos heredan las tablas que no cambian."""
    tables = table_types(spec)
    prompt = _prompt(spec, tables, base_tables, run_scripts or [])
    drafts = complete_json(llm, TESTS_SYSTEM, prompt, CasesResponse, agent="tests", phase=Phase.VERIFICACION).cases
    drafts.sort(key=lambda d: d.kind != OFFICIAL)
    types = {f.name: f.type for f in spec.io.inputs}
    candidates = [(with_base_tables(_normalize(d.input, types, tables), base_tables), d.rule_ids + [d.kind],
                   d.description or ("Ejecución provista por el cliente" if d.kind == OFFICIAL else ""))
                  for d in drafts]
    base = next((c[0] for c in candidates if OFFICIAL in c[1] or "tipico" in c[1]),
                candidates[0][0] if candidates else None)
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
