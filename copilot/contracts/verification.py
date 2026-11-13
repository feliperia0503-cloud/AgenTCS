"""Casos de prueba neutrales, oráculos y reporte de equivalencia.

Formato de intercambio entre runners de origen (expected.json) y harness de destino (actual.json).
Decimales SIEMPRE como string para no perder precisión entre lenguajes.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_floats(value: Any, path: str = "") -> None:
    if isinstance(value, float):
        raise ValueError(f"{path or 'valor'}: usar string para decimales, no float ({value!r})")
    if isinstance(value, dict):
        for k, v in value.items():
            _reject_floats(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _reject_floats(v, f"{path}[{i}]")


class Case(BaseModel):
    id: str
    input: dict[str, Any]
    tags: list[str] = []          # "borde", "invalido", "redondeo", "BR-003"...
    description: str = ""

    @field_validator("input")
    @classmethod
    def _no_floats(cls, v: dict[str, Any]) -> dict[str, Any]:
        _reject_floats(v)
        return v


class CaseError(BaseModel):
    code: str
    message: str = ""


class CaseOutput(BaseModel):
    id: str
    output: dict[str, Any] | list[dict[str, Any]] | None = None
    error: CaseError | None = None

    @field_validator("output")
    @classmethod
    def _no_floats(cls, v: Any) -> Any:
        _reject_floats(v)
        return v


class OracleLevel(StrEnum):
    A = "A"   # legacy ejecutado
    B = "B"   # pares E/S provistos por el cliente
    C = "C"   # implementación de referencia desde la spec + valores calculados a mano


class Difference(BaseModel):
    case_id: str
    field: str                    # "cuotas[3].interes", "error.code", "<faltante>"
    expected: Any
    actual: Any
    rule_ids: list[str] = []


class VerificationReport(BaseModel):
    source_language: str
    target_language: str
    oracle_level: OracleLevel
    oracle_description: str
    total: int
    passed: int
    differences: list[Difference] = []
    coverage_lines: float | None = None      # 0..100
    coverage_branches: float | None = None
    critical_findings: int | None = None
    max_complexity: int | None = None
    similarity: float | None = None          # 0..1, métrica del motor de autocorrección (ADR-005)
    attempt: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def equivalence_pct(self) -> float:
        return 100.0 * self.passed / self.total if self.total else 0.0

    def gate_failures(self) -> list[str]:
        """Quality gates del reto (sección 3.7). Lista vacía = pasa."""
        fails = []
        if self.total == 0:
            fails.append("no hay casos de equivalencia")
        if self.passed != self.total:
            fails.append(f"equivalencia {self.equivalence_pct:.1f}% (< 100%)")
        if self.coverage_lines is not None and self.coverage_lines < 80:
            fails.append(f"cobertura de líneas {self.coverage_lines:.1f}% (< 80%)")
        if self.coverage_branches is not None and self.coverage_branches < 70:
            fails.append(f"cobertura de ramas {self.coverage_branches:.1f}% (< 70%)")
        if self.critical_findings:
            fails.append(f"{self.critical_findings} hallazgos críticos")
        if self.max_complexity is not None and self.max_complexity > 10:
            fails.append(f"complejidad máxima {self.max_complexity} (> 10)")
        return fails
