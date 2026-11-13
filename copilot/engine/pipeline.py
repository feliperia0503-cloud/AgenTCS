"""Orquestación del motor sobre un RunState: análisis + extracción (antes del HITL) y
casos + oráculo + bucle de autocorrección + empaquetado (después del HITL)."""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from copilot.contracts import AnalysisResult, CaseOutput, Phase, RunState, SourceFile, VerificationReport
from copilot.languages.registry import get_source, get_target

from .extractor import extract_spec
from .lessons import LessonStore
from .llm import AnthropicLLM, LLMClient
from .loop import AttemptRecord, LoopConfig, LoopResult, SelfCorrectingLoop
from .oracle import compute_expected
from .segmenter import segment
from .test_generator import generate_cases

Save = Callable[[RunState], None]
EXTRACTION_BUDGET = int(os.environ.get("AGENTCS_EXTRACTION_CHARS", "120000"))


def _program_name(state: RunState) -> str:
    ref = (state.source_ref or "").rstrip("/").split("/")[-1].removesuffix(".git")
    for suffix in (".zip", ".tar.gz", ".tgz", ".tar"):
        ref = ref.removesuffix(suffix)
    return (ref or Path(state.files[0].path).stem).upper()


def select_for_extraction(files: list[SourceFile], analysis: AnalysisResult) -> tuple[list[SourceFile], str | None]:
    """Si el código supera el presupuesto, prioriza los archivos con más lógica (complejidad por unidad)."""
    total = sum(len(f.content) for f in files)
    if total <= EXTRACTION_BUDGET:
        return files, None
    weight: dict[str, int] = {}
    for u in analysis.units:
        weight[u.file] = weight.get(u.file, 0) + u.complexity
    ranked = sorted(files, key=lambda f: (-weight.get(f.path, 0) / max(len(f.content), 1) * 1000, f.path))
    chosen, used = [], 0
    for f in ranked:
        if used + len(f.content) <= EXTRACTION_BUDGET or not chosen:
            chosen.append(f)
            used += len(f.content)
    note = (f"Se analizaron {len(chosen)} de {len(files)} archivos (los de mayor densidad de lógica) por el "
            f"presupuesto de contexto; el resto queda pendiente para una siguiente iteración.")
    return chosen, note


@dataclass
class Engine:
    llm: LLMClient
    lessons: LessonStore
    output_root: Path
    config: LoopConfig = field(default_factory=LoopConfig)

    @classmethod
    def from_env(cls, config: LoopConfig | None = None) -> Engine:
        out = Path(os.environ.get("AGENTCS_OUTPUT", "output"))
        return cls(AnthropicLLM(), LessonStore(out / "lessons.json"), out, config or LoopConfig())

    # ------------------------------------------------------------ antes del HITL
    def analyze(self, state: RunState, save: Save) -> None:
        self.llm.recorder = state.llm_calls.append
        source = get_source(state.source_language)
        state.start(Phase.ANALISIS)
        save(state)
        analysis = (source.classify(source.parse(state.files), state.files) if source
                    else segment(state.files, state.source_language or "desconocido"))
        state.analysis = analysis
        problems = analysis.check_against({f.path: f for f in state.files})
        how = "pack de origen" if source else "segmentador genérico (confianza reducida)"
        state.finish(Phase.ANALISIS, ok=not problems,
                     message="; ".join(problems) or f"{analysis.metrics.units} unidades inventariadas con {how}")
        state.start(Phase.EXTRACCION)
        save(state)
        selected, note = select_for_extraction(state.files, analysis)
        spec = extract_spec(self.llm, selected, analysis, program=_program_name(state),
                            knowledge=source.knowledge() if source else "", domain=state.domain)
        if note:
            spec = spec.model_copy(update={"assumptions": [note, *spec.assumptions]})
        state.update_spec(spec)
        dropped = sum(a.startswith("Regla descartada") for a in spec.assumptions)
        state.finish(Phase.EXTRACCION, ok=bool(spec.rules),
                     message=f"{len(spec.rules)} reglas con línea de origen y confianza"
                     + (f" · {dropped} descartada(s) por líneas inválidas" if dropped else ""))
        if spec.rules:
            low = sum(r.needs_attention for r in spec.rules)
            state.wait_for_human(Phase.VALIDACION_HUMANA, f"{len(spec.rules)} reglas por revisar ({low} con confianza baja)")
        save(state)

    # ------------------------------------------------------------ después del HITL
    def generate_and_verify(self, state: RunState, save: Save,
                            provided: list[CaseOutput] | None = None) -> LoopResult:
        self.llm.recorder = state.llm_calls.append
        target = get_target(state.target_language)
        run_dir = self.output_root / "runs" / state.run_id
        state.start(Phase.DISENO)
        state.design = {"target": target.info.name, "framework": state.target_framework,
                        "architecture": state.target_architecture}
        state.finish(Phase.DISENO, ok=True, message=f"{target.info.name} · {state.target_framework or 'núcleo puro'} · "
                                                    f"{state.target_architecture or 'hexagonal'}")

        state.start(Phase.GENERACION)
        state.start(Phase.VERIFICACION)
        state.phases[Phase.VERIFICACION].gate_message = "Generando casos de prueba y oráculo"
        save(state)
        state.cases = generate_cases(self.llm, state.spec)
        source = get_source(state.source_language)
        oracle = compute_expected(state.spec, state.cases, workdir=run_dir / "oracle", llm=self.llm,
                                  runner=source.runner if source else None, files=state.files, provided=provided)
        state.expected = oracle.outputs
        save(state)

        reports: list[VerificationReport] = []

        def on_attempt(rec: AttemptRecord, report: VerificationReport, files: dict[str, str]) -> None:
            reports.append(report)
            state.generation_attempts = rec.attempt
            state.set_verification(report)
            state.generated_files = files
            state.phases[Phase.GENERACION].gate_message = (
                f"Intento {rec.attempt}: {'compila' if rec.compiled else 'no compila'} · "
                f"{rec.passed}/{rec.total} casos · similitud {rec.similarity:.2f}")
            save(state)

        loop = SelfCorrectingLoop(self.llm, target, run_dir / "attempts", self.config, self.lessons, on_attempt,
                                  framework=state.target_framework, architecture=state.target_architecture)
        result = loop.run(state.spec, state.cases, state.expected,
                          oracle_level=oracle.level, oracle_description=oracle.description)
        self._finish(state, result, reports)
        save(state)
        return result

    @staticmethod
    def _finish(state: RunState, result: LoopResult, reports: list[VerificationReport]) -> None:
        state.generated_files = result.best_files
        state.verification = result.best_report
        state.verification_history = [r for r in reports if r.attempt != result.best_attempt]
        compiled = any(a.compiled for a in result.attempts)
        state.finish(Phase.GENERACION, ok=compiled,
                     message=f"{len(result.attempts)} intento(s) · mejor versión: intento {result.best_attempt}")
        fails = result.best_report.gate_failures()
        reasons = {"equivalencia_total": "equivalencia total", "meseta": "sin mejora (meseta)",
                   "max_intentos": "máximo de intentos", "presupuesto": "presupuesto de tokens"}
        state.finish(Phase.VERIFICACION, ok=not fails,
                     message=f"{result.best_report.passed}/{result.best_report.total} casos · similitud "
                             f"{result.best_score:.2f} · parada: {reasons.get(result.stop_reason, result.stop_reason)}"
                             + (f" · {'; '.join(fails)}" if fails else ""))
        state.start(Phase.EMPAQUETADO)
        state.finish(Phase.EMPAQUETADO, ok=True,
                     message=f"Paquete con la mejor versión (intento {result.best_attempt})")
