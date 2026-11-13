"""Estado de una ejecución del copiloto (estado del grafo LangGraph)."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .analysis import AnalysisResult, SanitizationFinding, SourceFile
from .spec import Spec
from .verification import Case, CaseOutput, VerificationReport


class Phase(IntEnum):
    INGESTA = 1
    ANALISIS = 2
    EXTRACCION = 3
    VALIDACION_HUMANA = 4
    DISENO = 5
    GENERACION = 6
    VERIFICACION = 7
    EMPAQUETADO = 8


class PhaseStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_CURSO = "EN_CURSO"
    ESPERANDO_HUMANO = "ESPERANDO_HUMANO"
    APROBADA = "APROBADA"     # pasó su quality gate
    FALLIDA = "FALLIDA"


class PhaseRecord(BaseModel):
    status: PhaseStatus = PhaseStatus.PENDIENTE
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_message: str = ""
    artifacts: list[str] = []          # rutas generadas en output/<run_id>/


class LLMCall(BaseModel):
    """Registro de gobierno: cada llamada al modelo (el prompt ya va sanitizado)."""
    phase: Phase
    agent: str
    prompt_hash: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_s: float = 0.0
    replayed: bool = False             # True si vino de la caché (modo replay)


def _now() -> datetime:
    return datetime.now(UTC)


class RunState(BaseModel):
    run_id: str
    source_language: str | None = None    # None => autodetectar
    target_language: str
    domain: str | None = None
    created_at: datetime = Field(default_factory=_now)

    files: list[SourceFile] = []
    sanitization: list[SanitizationFinding] = []
    analysis: AnalysisResult | None = None
    spec: Spec | None = None
    spec_history: list[Spec] = []         # versiones previas (trazabilidad del HITL)
    design: dict[str, Any] = {}           # modelo de dominio, OpenAPI, ADRs (rutas)
    project_path: str | None = None
    cases: list[Case] = []
    expected: list[CaseOutput] = []
    actual: list[CaseOutput] = []
    verification: VerificationReport | None = None
    generation_attempts: int = 0
    max_attempts: int = 3

    phases: dict[Phase, PhaseRecord] = Field(default_factory=lambda: {p: PhaseRecord() for p in Phase})
    llm_calls: list[LLMCall] = []
    errors: list[str] = []

    def start(self, phase: Phase) -> None:
        self.phases[phase] = PhaseRecord(status=PhaseStatus.EN_CURSO, started_at=_now())

    def finish(self, phase: Phase, ok: bool, message: str = "", artifacts: list[str] | None = None) -> None:
        rec = self.phases[phase]
        rec.status = PhaseStatus.APROBADA if ok else PhaseStatus.FALLIDA
        rec.finished_at = _now()
        rec.gate_message = message
        rec.artifacts.extend(artifacts or [])

    def wait_for_human(self, phase: Phase, message: str) -> None:
        rec = self.phases[phase]
        rec.status = PhaseStatus.ESPERANDO_HUMANO
        rec.gate_message = message

    def update_spec(self, new: Spec) -> None:
        if self.spec is not None:
            self.spec_history.append(self.spec)
        self.spec = new

    @property
    def elapsed_s(self) -> float:
        return (_now() - self.created_at).total_seconds()
