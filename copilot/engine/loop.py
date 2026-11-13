"""Bucle de autocorrección: generar → compilar → ejecutar → comparar → retroalimentar → repetir.

Se detiene con equivalencia total, por meseta (PATIENCE intentos sin mejorar), por MAX_ATTEMPTS o por
presupuesto de tokens, y devuelve SIEMPRE la mejor versión obtenida, no la última. Ver ADR-005.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from copilot.contracts import (
    Case, CaseOutput, OracleLevel, Spec, TargetAdapter, VerificationReport,
)
from copilot.verification import compare, failing_cases

from .generator import generate_project
from .lessons import LessonStore, learn
from .llm import LLMClient, LLMError
from .pyharness import HarnessError
from .sandbox import SandboxError, write_files

CASES_WEIGHT, FIELDS_WEIGHT = 0.7, 0.3


@dataclass
class LoopConfig:
    max_attempts: int = int(os.environ.get("AGENTCS_MAX_ATTEMPTS", "5"))
    patience: int = int(os.environ.get("AGENTCS_PATIENCE", "2"))
    token_budget: int = int(os.environ.get("AGENTCS_TOKEN_BUDGET", "600000"))
    max_feedback_cases: int = 8


@dataclass
class AttemptRecord:
    attempt: int
    compiled: bool
    passed: int
    total: int
    similarity: float
    error: str | None = None


@dataclass
class LoopResult:
    best_files: dict[str, str]
    best_report: VerificationReport
    best_score: float
    best_attempt: int
    attempts: list[AttemptRecord] = field(default_factory=list)
    stop_reason: str = ""


AttemptCallback = Callable[[AttemptRecord, VerificationReport, dict[str, str]], None]


# ---------------------------------------------------------------- métrica
def _fields(o: CaseOutput) -> int:
    if o.error is not None:
        return 1
    if isinstance(o.output, list):
        return max(1, sum(len(row) for row in o.output))
    return max(1, len(o.output or {}))


def similarity(report: VerificationReport, expected: list[CaseOutput]) -> float:
    """0.7 × casos equivalentes/total + 0.3 × campos iguales/campos comparados (crédito parcial)."""
    if not expected:
        return 0.0
    per_case = {o.id: _fields(o) for o in expected}
    total_fields = sum(per_case.values())
    bad_by_case: dict[str, int] = {}
    for d in report.differences:
        bad_by_case[d.case_id] = bad_by_case.get(d.case_id, 0) + 1
    bad = sum(min(n, per_case.get(cid, n)) for cid, n in bad_by_case.items())
    score = CASES_WEIGHT * report.passed / len(expected) + FIELDS_WEIGHT * (total_fields - bad) / total_fields
    return round(score, 4)


# ---------------------------------------------------------------- retroalimentación
def build_feedback(report: VerificationReport, spec: Spec, cases: list[Case], regressions: set[str],
                   max_cases: int) -> str:
    by_case = failing_cases(report)
    inputs = {c.id: c.input for c in cases}
    by_rule: dict[str, list[str]] = {}
    for cid in list(by_case)[:max_cases]:
        diffs = by_case[cid]
        rule = next((r for d in diffs for r in d.rule_ids), "sin-regla")
        lines = [f"  - Caso {cid}{' (REGRESIÓN: antes pasaba)' if cid in regressions else ''} · entrada {inputs.get(cid)}"]
        lines += [f"      campo {d.field}: esperado {d.expected!r}, obtenido {d.actual!r}" for d in diffs[:6]]
        by_rule.setdefault(rule, []).extend(lines)
    out = [f"{report.passed}/{report.total} casos equivalentes. Diferencias agrupadas por regla:"]
    for rule_id, lines in by_rule.items():
        rule = next((r for r in spec.rules if r.id == rule_id), None)
        header = f"* {rule_id}: {rule.name} — {rule.action}" if rule else f"* {rule_id}"
        out += [header, *lines]
    if len(by_case) > max_cases:
        out.append(f"(y {len(by_case) - max_cases} caso(s) más con diferencias)")
    return "\n".join(out)


def _failure_report(spec: Spec, cases: list[Case], expected: list[CaseOutput], attempt: int,
                    target: str, level: OracleLevel, desc: str) -> VerificationReport:
    return compare(spec, cases, expected, [], target_language=target, oracle_level=level,
                   oracle_description=desc, attempt=attempt)


# ---------------------------------------------------------------- bucle
@dataclass
class SelfCorrectingLoop:
    llm: LLMClient
    target: TargetAdapter
    workdir: Path
    config: LoopConfig = field(default_factory=LoopConfig)
    lessons: LessonStore | None = None
    on_attempt: AttemptCallback | None = None

    def run(self, spec: Spec, cases: list[Case], expected: list[CaseOutput], *,
            oracle_level: OracleLevel, oracle_description: str) -> LoopResult:
        pair = f"{spec.source_language}→{self.target.info.id}"
        lessons = self.lessons.relevant(pair, ["redondeo", "validacion"]) if self.lessons else []
        files: dict[str, str] | None = None
        feedback: str | None = None
        best: LoopResult | None = None
        best_passed: set[str] = set()
        no_improve = 0
        records: list[AttemptRecord] = []
        stop = "max_intentos"

        for attempt in range(1, self.config.max_attempts + 1):
            previous_feedback = feedback
            files, report, error = self._attempt(spec, cases, expected, attempt, files, feedback, lessons,
                                                 oracle_level, oracle_description)
            score = similarity(report, expected) if error is None else 0.0
            report = report.model_copy(update={"similarity": score})
            record = AttemptRecord(attempt, error is None, report.passed, report.total, score, error)
            records.append(record)
            if self.on_attempt:
                self.on_attempt(record, report, dict(files or {}))

            failing = set(failing_cases(report))
            if best is None or score > best.best_score:
                if best is not None and self.lessons and previous_feedback:
                    learn(self.llm, self.lessons, pair, previous_feedback,
                          f"La similitud subió de {best.best_score:.2f} a {score:.2f} en el intento {attempt}.")
                best = LoopResult(dict(files or {}), report, score, attempt)
                best_passed = {c.id for c in cases} - failing
                no_improve = 0
            else:
                no_improve += 1

            reason = self._stop_reason(report, error, no_improve)
            if reason:
                stop = reason
                break
            feedback = error or build_feedback(report, spec, cases, failing & best_passed,
                                               self.config.max_feedback_cases)

        if best is None:   # imposible con max_attempts >= 1; protege contra configuraciones inválidas
            raise ValueError("max_attempts debe ser >= 1")
        best.attempts, best.stop_reason = records, stop
        return best

    def _stop_reason(self, report: VerificationReport, error: str | None, no_improve: int) -> str | None:
        if error is None and report.passed == report.total:
            return "equivalencia_total"
        if no_improve >= self.config.patience:
            return "meseta"
        if getattr(self.llm, "tokens_used", 0) >= self.config.token_budget:
            return "presupuesto"
        return None

    def _attempt(self, spec: Spec, cases: list[Case], expected: list[CaseOutput], attempt: int,
                 files: dict[str, str] | None, feedback: str | None, lessons: list[str],
                 level: OracleLevel, desc: str) -> tuple[dict[str, str] | None, VerificationReport, str | None]:
        fail = _failure_report(spec, cases, expected, attempt, self.target.info.id, level, desc)
        try:
            files = generate_project(self.llm, spec, self.target, attempt=attempt, previous=files,
                                     feedback=feedback, lessons=lessons)
        except LLMError as exc:
            return files, fail, f"El generador no produjo una respuesta válida: {exc.message}"
        project = self.workdir / f"attempt-{attempt:02d}"
        try:
            write_files(project, files)
        except SandboxError as exc:
            return files, fail, f"Ruta inválida en el proyecto generado: {exc}"
        build = self.target.build(project)
        if not build.ok:
            return files, fail, f"El proyecto no compila. Errores:\n{build.log[-3000:]}"
        try:
            actual = self.target.run_harness(project, cases)
        except HarnessError as exc:
            return files, fail, f"El arnés de pruebas no pudo ejecutar el código. Salida:\n{str(exc)[-3000:]}"
        report = compare(spec, cases, expected, actual, target_language=self.target.info.id,
                         oracle_level=level, oracle_description=desc, attempt=attempt)
        return files, report, None
