"""Registro de packs de lenguaje. El núcleo pide adaptadores por id y nunca importa un pack concreto."""
from __future__ import annotations

from copilot.contracts import SourceAdapter, TargetAdapter


class PackNotAvailable(Exception):
    def __init__(self, kind: str, pack_id: str, available: list[str]):
        super().__init__(f"No hay pack de {kind} '{pack_id}'")
        self.kind, self.pack_id, self.available = kind, pack_id, available


def _targets() -> dict[str, TargetAdapter]:
    from .csharp.adapter import CSharpTarget
    from .java.adapter import JavaTarget
    from .python.adapter import PythonTarget
    from .typescript.adapter import TypeScriptTarget
    return {"java": JavaTarget(), "csharp": CSharpTarget(), "typescript": TypeScriptTarget(), "python": PythonTarget()}


def _sources() -> dict[str, SourceAdapter]:
    return {}   # los packs de origen (cobol, plsql...) se registran aquí cuando existan


def get_target(pack_id: str) -> TargetAdapter:
    targets = _targets()
    if pack_id not in targets:
        raise PackNotAvailable("destino", pack_id, sorted(targets))
    return targets[pack_id]


def get_source(pack_id: str | None) -> SourceAdapter | None:
    """Devuelve el pack de origen o None (el motor usa entonces el segmentador genérico y oráculo B/C)."""
    return _sources().get(pack_id or "")


def available_targets() -> list[str]:
    return sorted(_targets())
