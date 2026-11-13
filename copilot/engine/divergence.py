"""Reglas agregadas por el experto durante la revisión humana (HITL).

- documenta_legacy: el legacy YA lo hace y el extractor no lo vio. La equivalencia con el legacy se mantiene.
- cambio_negocio: comportamiento NUEVO aprobado por el negocio. Los casos que lo ejercitan se apartan del
  legacy a propósito: se separan como divergencia intencional y no cuentan como fallo de equivalencia.
"""
from __future__ import annotations

from copilot.contracts import Case, Spec

LEGACY_DOC = "Origen: experto de negocio — documenta un comportamiento que el legacy ya tiene"
BUSINESS_CHANGE = "CAMBIO DE NEGOCIO: el código migrado se aparta del legacy a propósito"
RULE_ORIGINS = {"documenta_legacy": LEGACY_DOC, "cambio_negocio": BUSINESS_CHANGE}


def change_rule_ids(spec: Spec) -> set[str]:
    return {r.id for r in spec.active_rules if BUSINESS_CHANGE in r.assumptions}


def split_divergent(spec: Spec, cases: list[Case]) -> tuple[list[Case], list[Case]]:
    """(casos comparables con el legacy, casos que ejercitan un cambio de negocio aprobado)."""
    changes = change_rule_ids(spec)
    divergent = [c for c in cases if changes & set(c.tags)]
    return [c for c in cases if c not in divergent], divergent
