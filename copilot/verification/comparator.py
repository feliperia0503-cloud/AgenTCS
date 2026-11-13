"""Comparador neutral de equivalencia: expected (oráculo) vs actual (destino). Tolerancia cero.

No depende de ningún lenguaje: usa los tipos neutrales de spec.io.outputs.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from copilot.contracts import (
    Case, CaseOutput, Difference, NeutralType, OracleLevel, Spec, TypeKind, VerificationReport,
)

MISSING = "<faltante>"


def _equal(expected: Any, actual: Any, t: NeutralType | None) -> bool:
    if t is not None and t.kind == TypeKind.DECIMAL:
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except (InvalidOperation, ValueError):
            return False
    if t is not None and t.kind == TypeKind.INTEGER:
        try:
            return int(expected) == int(actual)
        except (TypeError, ValueError):
            return False
    if t is not None and t.kind == TypeKind.STRING and isinstance(expected, str) and isinstance(actual, str):
        return expected.rstrip() == actual.rstrip()   # relleno de ancho fijo del legacy
    return expected == actual


def _compare_row(case_id: str, prefix: str, exp: dict[str, Any], act: dict[str, Any],
                 types: dict[str, NeutralType], rules: list[str]) -> list[Difference]:
    diffs = []
    for name, e in exp.items():
        if name not in act:
            diffs.append(Difference(case_id=case_id, field=f"{prefix}{name}", expected=e, actual=MISSING, rule_ids=rules))
        elif not _equal(e, act[name], types.get(name)):
            diffs.append(Difference(case_id=case_id, field=f"{prefix}{name}", expected=e, actual=act[name], rule_ids=rules))
    for name in act.keys() - exp.keys():
        diffs.append(Difference(case_id=case_id, field=f"{prefix}{name}", expected=MISSING, actual=act[name], rule_ids=rules))
    return diffs


def compare_case(case: Case, expected: CaseOutput, actual: CaseOutput | None,
                 types: dict[str, NeutralType]) -> list[Difference]:
    rules = [t for t in case.tags if t.startswith("BR-")]
    cid = case.id
    if actual is None:
        return [Difference(case_id=cid, field="<caso>", expected="ejecutado", actual=MISSING, rule_ids=rules)]

    # Errores de negocio: mismo código y mensaje
    if expected.error or actual.error:
        e = expected.error.model_dump() if expected.error else None
        a = actual.error.model_dump() if actual.error else None
        if e is None or a is None or e["code"] != a["code"] or e["message"].strip() != a["message"].strip():
            return [Difference(case_id=cid, field="error", expected=e, actual=a, rule_ids=rules)]
        return []

    exp, act = expected.output, actual.output
    if isinstance(exp, list) or isinstance(act, list):
        if not (isinstance(exp, list) and isinstance(act, list)):
            return [Difference(case_id=cid, field="output", expected=type(exp).__name__, actual=type(act).__name__, rule_ids=rules)]
        diffs = []
        if len(exp) != len(act):
            diffs.append(Difference(case_id=cid, field="output.length", expected=len(exp), actual=len(act), rule_ids=rules))
        for i, (e_row, a_row) in enumerate(zip(exp, act)):
            diffs += _compare_row(cid, f"[{i}].", e_row, a_row, types, rules)
        return diffs
    return _compare_row(cid, "", exp or {}, act or {}, types, rules)


def compare(spec: Spec, cases: list[Case], expected: list[CaseOutput], actual: list[CaseOutput], *,
            target_language: str, oracle_level: OracleLevel, oracle_description: str,
            attempt: int = 1) -> VerificationReport:
    exp_by_id = {o.id: o for o in expected}
    act_by_id = {o.id: o for o in actual}
    types = spec.output_types()
    differences: list[Difference] = []
    passed = 0
    for case in cases:
        if case.id not in exp_by_id:
            raise ValueError(f"el oráculo no tiene resultado para el caso {case.id}")
        diffs = compare_case(case, exp_by_id[case.id], act_by_id.get(case.id), types)
        differences += diffs
        passed += not diffs
    return VerificationReport(
        source_language=spec.source_language, target_language=target_language,
        oracle_level=oracle_level, oracle_description=oracle_description,
        total=len(cases), passed=passed, differences=differences, attempt=attempt,
    )


def failing_cases(report: VerificationReport) -> dict[str, list[Difference]]:
    """Agrupa diferencias por caso: es lo que se devuelve al agente Desarrollador para reintentar."""
    out: dict[str, list[Difference]] = {}
    for d in report.differences:
        out.setdefault(d.case_id, []).append(d)
    return out
