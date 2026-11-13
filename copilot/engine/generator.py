"""Agente Desarrollador: Spec aprobada + convenciones del destino (+ retroalimentación) → proyecto."""
from __future__ import annotations

import json

from pydantic import BaseModel

from copilot.contracts import Phase, Spec, TargetAdapter

from .llm import LLMClient, complete_json
from .prompts import GENERATOR_SYSTEM

MAX_FILE_CHARS = 60_000


class ProjectResponse(BaseModel):
    files: dict[str, str]
    notes: str = ""


def spec_for_prompt(spec: Spec) -> str:
    rules = spec.active_rules or spec.rules
    payload = {
        "programa": spec.program, "lenguaje_origen": spec.source_language, "dominio": spec.domain,
        "contrato": spec.io.model_dump(mode="json"),
        "entidades": [e.model_dump(mode="json") for e in spec.entities],
        "reglas": [{"id": r.id, "nombre": r.name, "categoria": r.category.value, "descripcion": r.description,
                    "condicion": r.condition, "accion": r.action,
                    "tipo_resultado": r.result_type.describe() if r.result_type else None,
                    "origen": f"{r.source.file}:{r.source.lines[0]}-{r.source.lines[1]} ({r.source.unit})",
                    "codigo_legacy": r.source.snippet, "supuestos": r.assumptions,
                    "revision": r.review.comment if r.review else None} for r in rules],
        "supuestos": spec.assumptions,
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _current_files(files: dict[str, str]) -> str:
    return "\n\n".join(f"=== {path} ===\n{content[:MAX_FILE_CHARS]}" for path, content in sorted(files.items()))


def generate_project(llm: LLMClient, spec: Spec, target: TargetAdapter, *, attempt: int,
                     previous: dict[str, str] | None = None, feedback: str | None = None,
                     lessons: list[str] | None = None) -> dict[str, str]:
    parts = [f"Destino: {target.info.name}\nConvenciones obligatorias:\n{target.conventions()}",
             f"Especificación aprobada (fuente de verdad):\n{spec_for_prompt(spec)}"]
    if lessons:
        parts.append("Lecciones aprendidas en migraciones anteriores de este par de lenguajes:\n"
                     + "\n".join(f"- {lesson}" for lesson in lessons))
    if previous:
        parts.append(f"Intento {attempt}. Versión actual del proyecto:\n{_current_files(previous)}")
        parts.append(f"Retroalimentación de las pruebas de equivalencia contra el legacy:\n{feedback}\n\n"
                     "Corrige la causa raíz. Devuelve SOLO los archivos que cambian (contenido completo).")
    else:
        parts.append("Genera el proyecto completo.")
    parts.append(f"Formato de respuesta (JSON Schema):\n{json.dumps(ProjectResponse.model_json_schema())}")
    resp = complete_json(llm, GENERATOR_SYSTEM, "\n\n".join(parts), ProjectResponse,
                         agent="generator", phase=Phase.GENERACION)
    files = dict(previous or {})
    for path, content in resp.files.items():
        if content == "":
            files.pop(path, None)
        else:
            files[path] = content
    return files
