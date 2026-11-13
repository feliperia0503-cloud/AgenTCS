"""'Sugerir configuración': analiza el código legacy real y recomienda lenguaje, framework y
arquitectura destino, restringidos al catálogo (catalog.py).

El inventario (lenguajes, archivos, líneas) es determinista; el LLM solo razona la recomendación.
Todo el código pasa por el sanitizador antes de llegar al LLM.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from copilot.contracts import Phase, SourceFile
from copilot.engine.llm import LLMClient, complete_json
from copilot.engine.prompts import COMMON
from copilot.security import Sanitizer

from . import catalog, sources

MAX_PROMPT_CHARS = 45_000
MAX_LINES_PER_FILE = 160


class Alternative(BaseModel):
    language: str
    framework: str
    architecture: str
    reason: str


class Suggestion(BaseModel):
    source_summary: str = Field(description="Qué hace el sistema legacy, en lenguaje de negocio (2-3 frases)")
    language: str
    framework: str
    architecture: str
    rationale: str
    risks: list[str] = []
    confidence: float = Field(ge=0, le=1)
    alternatives: list[Alternative] = []

    @model_validator(mode="after")
    def _in_catalog(self) -> Suggestion:
        for opt in [self, *self.alternatives]:
            problem = catalog.is_valid(opt.language, opt.framework, opt.architecture)
            if problem:
                raise ValueError(problem)
        return self


SYSTEM = f"""{COMMON}
Eres el Arquitecto de modernización de AgenTCS. Analizas una muestra del código legacy (puede ser COBOL,
PL/SQL, Delphi, RPG, VB6, C#, Java antiguo u otro) y su inventario, y recomiendas la tecnología destino de
MENOR RIESGO para migrarlo preservando el comportamiento.
Criterios: equivalencia funcional y precisión decimal, ecosistema y talento disponible en banca/seguros,
afinidad con el origen (p. ej. .NET Framework → C#, Delphi de escritorio → C#), naturaleza del sistema
(batch, transaccional en línea, eventos) y despliegue en contenedores. Elige SOLO claves del catálogo.
Sé concreto: menciona lo que viste en el código. Riesgos: 2 a 4, específicos. Alternativas: 1 o 2."""


def _priority(f: SourceFile) -> tuple[int, int]:
    _, _, logic = sources.language_of(f.path)
    return (0 if logic else 1, -len(f.lines))


def sample(files: list[SourceFile]) -> str:
    blocks, used = [], 0
    for f in sorted(files, key=_priority):
        body = "\n".join(f.lines[:MAX_LINES_PER_FILE])
        cut = ", recortado" if len(f.lines) > MAX_LINES_PER_FILE else ""
        block = f"=== {f.path} ({len(f.lines)} líneas{cut}) ===\n{body}"
        if used + len(block) > MAX_PROMPT_CHARS:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def suggest(llm: LLMClient, raw: list[tuple[str, str]]) -> dict:
    files, findings = Sanitizer().sanitize_files(raw)
    inv = sources.inventory(raw)
    prompt = (f"Catálogo permitido (usa las claves):\n{catalog.compact()}\n\nInventario:\n{inv}\n\n"
              f"Muestra del código (sanitizado):\n{sample(files)}\n\n"
              f"Responde con un JSON que cumpla este esquema:\n{Suggestion.model_json_schema()}")
    rec = complete_json(llm, SYSTEM, prompt, Suggestion, agent="advisor", phase=Phase.INGESTA)
    lang = catalog.LANGUAGES[rec.language]
    return {"suggestion": rec.model_dump(), "inventory": inv, "sanitized_findings": len(findings),
            "source_language": sources.dominant_language(raw),
            "labels": {"language": lang["label"], "framework": lang["frameworks"][rec.framework],
                       "architecture": catalog.ARCHITECTURES[rec.architecture]},
            "files": [Path(p).as_posix() for p, _ in raw[:50]]}
