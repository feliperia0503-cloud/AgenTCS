"""Especificación neutral: el pivote entre cualquier lenguaje origen y cualquier destino.

Es la "fuente de verdad" aprobada por el humano (Spec-Driven Development).
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .types import NeutralType

LOW_CONFIDENCE = 0.70


class RuleCategory(StrEnum):
    CALCULO = "CALCULO"
    VALIDACION = "VALIDACION"
    DECISION = "DECISION"
    CONSTANTE = "CONSTANTE"


class RuleStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADA = "APROBADA"
    AJUSTADA = "AJUSTADA"
    RECHAZADA = "RECHAZADA"


class SourceRef(BaseModel):
    file: str
    unit: str                      # párrafo, procedimiento, método...
    lines: tuple[int, int]
    snippet: str | None = None     # sintaxis original (solo aquí, el resto es neutral)

    @field_validator("lines")
    @classmethod
    def _order(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] < 1 or v[1] < v[0]:
            raise ValueError("lines debe ser (inicio, fin) con 1 <= inicio <= fin")
        return v


class Review(BaseModel):
    by: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    comment: str | None = None


class Rule(BaseModel):
    id: str = Field(pattern=r"^BR-\d{3,}$")
    name: str
    category: RuleCategory
    description: str                       # lenguaje de negocio
    condition: str | None = None           # pseudocódigo neutral
    action: str                            # pseudocódigo neutral
    decision_table: list[dict[str, Any]] | None = None
    source: SourceRef
    variables: dict[str, str] = {}         # nombre neutral -> nombre legacy
    result_type: NeutralType | None = None
    confidence: float = Field(ge=0, le=1)
    confidence_reason: str
    assumptions: list[str] = []
    gherkin: str | None = None
    status: RuleStatus = RuleStatus.PENDIENTE
    review: Review | None = None

    @model_validator(mode="after")
    def _review_rules(self) -> Rule:
        if self.status != RuleStatus.PENDIENTE and self.review is None:
            raise ValueError(f"{self.id}: una regla revisada requiere review")
        if (self.status in (RuleStatus.APROBADA, RuleStatus.AJUSTADA)
                and self.confidence < LOW_CONFIDENCE
                and not (self.review and self.review.comment)):
            raise ValueError(f"{self.id}: confianza < {LOW_CONFIDENCE} exige comentario del revisor")
        return self

    @property
    def needs_attention(self) -> bool:
        return self.confidence < LOW_CONFIDENCE

    # Transiciones HITL (devuelven una copia: el historial lo guarda RunState)
    def approve(self, by: str, comment: str | None = None) -> Rule:
        return self.model_validate({**self.model_dump(), "status": RuleStatus.APROBADA,
                                    "review": Review(by=by, comment=comment)})

    def adjust(self, by: str, comment: str, **changes: Any) -> Rule:
        return self.model_validate({**self.model_dump(), **changes, "status": RuleStatus.AJUSTADA,
                                    "review": Review(by=by, comment=comment)})

    def reject(self, by: str, comment: str) -> Rule:
        return self.model_validate({**self.model_dump(), "status": RuleStatus.RECHAZADA,
                                    "review": Review(by=by, comment=comment)})


class DataField(BaseModel):
    name: str                       # nombre de dominio (monto, tasa_anual)
    type: NeutralType
    description: str = ""
    legacy_name: str | None = None  # WS-MONTO, p_monto, txtMonto
    required: bool = True


class Entity(BaseModel):
    name: str
    kind: str = "entity"            # entity | value_object | aggregate
    description: str = ""
    fields: list[DataField]


class ErrorCode(BaseModel):
    """Errores de negocio que forman parte del contrato (mismo código y mensaje que el legacy)."""
    code: str
    message: str
    rule_id: str | None = None


class IOContract(BaseModel):
    """Contrato del caso de uso: lo que reciben runners de origen y harness de destino."""
    operation: str                  # nombre del caso de uso, p. ej. calcular_tabla_amortizacion
    inputs: list[DataField]
    outputs: list[DataField]
    errors: list[ErrorCode] = []
    output_is_list: bool = False    # p. ej. una fila por cuota


class Spec(BaseModel):
    program: str
    source_language: str
    domain: str | None = None
    version: int = 1
    rules: list[Rule]
    entities: list[Entity] = []
    io: IOContract
    assumptions: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _unique_ids(self) -> Spec:
        ids = [r.id for r in self.rules]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"ids de regla duplicados: {sorted(dup)}")
        return self

    def rule(self, rule_id: str) -> Rule:
        return next(r for r in self.rules if r.id == rule_id)

    def replace_rule(self, rule: Rule) -> Spec:
        return self.model_copy(update={"rules": [rule if r.id == rule.id else r for r in self.rules]})

    @property
    def pending(self) -> list[Rule]:
        return [r for r in self.rules if r.status == RuleStatus.PENDIENTE]

    @property
    def is_fully_reviewed(self) -> bool:
        return not self.pending

    @property
    def active_rules(self) -> list[Rule]:
        """Reglas que guían la generación de código (aprobadas o ajustadas)."""
        return [r for r in self.rules if r.status in (RuleStatus.APROBADA, RuleStatus.AJUSTADA)]

    def output_types(self) -> dict[str, NeutralType]:
        return {f.name: f.type for f in self.io.outputs}
