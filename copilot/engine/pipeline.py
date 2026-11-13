"""Orquestación del motor sobre un RunState: análisis + extracción (antes del HITL) y
casos + oráculo + bucle de autocorrección + empaquetado (después del HITL)."""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from copilot.contracts import CaseOutput, Phase, RunState, VerificationReport
from copilot.languages.registry import get_source, get_target

from .extractor import extract_spec
from .lessons import LessonStore
from .llm import AnthropicLLM, LLMClient
from .loop import AttemptRecord, LoopConfig, LoopResult, SelfCorrectingLoop
from .oracle import compute_expected
from .segmenter import segment
from .test_generator import generate_cases

Save = Callable[[RunState], None]


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
        spec = extract_spec(self.llm, state.files, analysis, program=Path(state.files[0].path).stem.upper(),
                            knowledge=source.knowledge() if source else "", domain=state.domain)
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
        state.design = {"target": target.info.name, "style": "arquitectura limpia según convenciones del pack destino"}
        state.finish(Phase.DISENO, ok=True, message=f"Convenciones de {target.info.name} aplicadas")

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

        loop = SelfCorrectingLoop(self.llm, target, run_dir / "attempts", self.config, self.lessons, on_attempt)
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
