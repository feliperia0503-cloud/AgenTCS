"""Agente Extractor: código legacy (sanitizado) + análisis → Spec neutral con reglas trazables.

El LLM propone; la validación determinista decide: líneas inexistentes descartan la regla, el snippet se
toma del archivo real y si las variables citadas no aparecen en esas líneas, baja la confianza.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator

from copilot.contracts import (
    AnalysisResult, DataField, Entity, ErrorCode, IOContract, NeutralType, Phase, Rule, RuleCategory, SourceFile,
    SourceRef, Spec,
)

from .llm import LLMClient, complete_json
from .prompts import EXTRACTOR_SYSTEM, numbered

MISSING_VARS_FACTOR = 0.8
TABLE_KIND = "tabla"   # Entity.kind de las tablas cuyos datos viajan en input['_tablas']


def _check_type(v: str | None) -> str | None:
    if v is not None:
        NeutralType.parse(v)   # lanza si el tipo no es válido -> el LLM recibe el error y reintenta
    return v


class FieldDraft(BaseModel):
    name: str
    type: str
    legacy_name: str | None = None
    description: str = ""

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        return _check_type(v) or v


class RuleDraft(BaseModel):
    name: str
    category: RuleCategory
    description: str
    condition: str | None = None
    action: str
    file: str
    unit: str
    start_line: int
    end_line: int
    variables: dict[str, str] = {}
    result_type: str | None = None
    confidence: float = Field(ge=0, le=1)
    confidence_reason: str
    assumptions: list[str] = []
    gherkin: str | None = None

    @field_validator("result_type")
    @classmethod
    def _valid_result_type(cls, v: str | None) -> str | None:
        return _check_type(v)


class TableDraft(BaseModel):
    """Tabla de base de datos que la rutina lee o modifica (sus datos viajan en input['_tablas'])."""
    name: str
    access: str = "lectura"          # lectura | escritura | lectura_escritura
    columns: list[FieldDraft]
    description: str = ""


class DeadCodeDraft(BaseModel):
    file: str
    unit: str
    start_line: int
    end_line: int
    reason: str


class ExcludedDraft(BaseModel):
    name: str
    reason: str


class ExtractionResponse(BaseModel):
    operation: str
    inputs: list[FieldDraft]
    outputs: list[FieldDraft]
    output_is_list: bool = False
    errors: list[ErrorCode] = []
    rules: list[RuleDraft]
    tables: list[TableDraft] = []
    dead_code: list[DeadCodeDraft] = []
    excluded_outputs: list[ExcludedDraft] = []
    assumptions: list[str] = []


def _prompt(files: list[SourceFile], analysis: AnalysisResult, knowledge: str, domain: str | None) -> str:
    units = [{"unidad": u.name, "archivo": u.file, "lineas": [u.start_line, u.end_line],
              "clasificacion": u.classification.value, "notas": u.notes} for u in analysis.units]
    schema = json.dumps(ExtractionResponse.model_json_schema(), ensure_ascii=False)
    return (f"Lenguaje origen: {analysis.language} ({analysis.dialect or 'dialecto no especificado'})\n"
            f"Dominio: {domain or 'no indicado'}\n\n"
            f"Conocimiento del lenguaje:\n{knowledge or '(sin pack de origen: usa tu conocimiento general)'}\n\n"
            f"Unidades detectadas por el análisis estático:\n{json.dumps(units, ensure_ascii=False)}\n\n"
            f"Código (numerado):\n{numbered(files)}\n\n"
            f"Devuelve un JSON que cumpla este JSON Schema:\n{schema}")


def _validate(draft: RuleDraft, files: dict[str, SourceFile], penalty: float) -> tuple[SourceRef, float, list[str]] | None:
    f = files.get(draft.file)
    if f is None or not 1 <= draft.start_line <= draft.end_line <= len(f.lines):
        return None
    lines = f.lines[draft.start_line - 1:draft.end_line]
    snippet = "\n".join(lines)
    confidence, notes = draft.confidence * (1 - penalty), []
    missing = [v for v in draft.variables.values() if v and v.lower() not in snippet.lower()]
    if missing:
        confidence *= MISSING_VARS_FACTOR
        notes.append(f"Variables no visibles en las líneas citadas: {', '.join(missing)}")
    src = SourceRef(file=draft.file, unit=draft.unit, lines=(draft.start_line, draft.end_line), snippet=snippet)
    return src, round(confidence, 3), notes


def _field(d: FieldDraft) -> DataField:
    return DataField(name=d.name, type=NeutralType.parse(d.type), description=d.description, legacy_name=d.legacy_name)


@dataclass
class Findings:
    """Hallazgos de la extracción que no son reglas: código muerto y salidas excluidas de la comparación."""
    dead_code: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)


def _dead_code(drafts: list[DeadCodeDraft], files: dict[str, SourceFile]) -> list[dict]:
    """Solo se conserva el código muerto cuyas líneas existen (validación determinista, como las reglas)."""
    out = []
    for d in drafts:
        f = files.get(d.file)
        if f is None or not 1 <= d.start_line <= d.end_line <= len(f.lines):
            continue
        out.append({"file": d.file, "unit": d.unit, "lines": [d.start_line, d.end_line], "reason": d.reason,
                    "snippet": "\n".join(f.lines[d.start_line - 1:min(d.end_line, d.start_line + 7)])})
    return out


def extract_spec(llm: LLMClient, files: list[SourceFile], analysis: AnalysisResult, *,
                 program: str, knowledge: str = "", domain: str | None = None) -> Spec:
    return extract(llm, files, analysis, program=program, knowledge=knowledge, domain=domain)[0]


def extract(llm: LLMClient, files: list[SourceFile], analysis: AnalysisResult, *,
            program: str, knowledge: str = "", domain: str | None = None) -> tuple[Spec, Findings]:
    resp = complete_json(llm, EXTRACTOR_SYSTEM, _prompt(files, analysis, knowledge, domain),
                         ExtractionResponse, agent="extractor", phase=Phase.EXTRACCION)
    by_path = {f.path: f for f in files}
    rules, discarded = [], []
    for draft in resp.rules:
        checked = _validate(draft, by_path, analysis.confidence_penalty)
        if checked is None:
            discarded.append(f"Regla descartada por líneas inválidas: {draft.name} ({draft.file}:{draft.start_line}-{draft.end_line})")
            continue
        src, confidence, notes = checked
        rules.append(Rule(
            id=f"BR-{len(rules) + 1:03d}", name=draft.name, category=draft.category, description=draft.description,
            condition=draft.condition, action=draft.action, source=src, variables=draft.variables,
            result_type=NeutralType.parse(draft.result_type) if draft.result_type else None,
            confidence=confidence, confidence_reason=draft.confidence_reason,
            assumptions=draft.assumptions + notes, gherkin=draft.gherkin))
    io = IOContract(operation=resp.operation, inputs=[_field(d) for d in resp.inputs],
                    outputs=[_field(d) for d in resp.outputs], errors=resp.errors, output_is_list=resp.output_is_list)
    tables = [Entity(name=t.name, kind=TABLE_KIND, fields=[_field(c) for c in t.columns],
                     description=f"{t.access}: {t.description}".strip(": "))
              for t in resp.tables if t.columns]
    findings = Findings(dead_code=_dead_code(resp.dead_code, by_path),
                        excluded=[{"name": e.name, "reason": e.reason} for e in resp.excluded_outputs])
    notes = ([f"Código muerto (no se migra): {d['file']}:{d['lines'][0]}–{d['lines'][1]} · {d['unit']} — {d['reason']}"
              for d in findings.dead_code]
             + [f"Excluido de la comparación: {e['name']} — {e['reason']}" for e in findings.excluded])
    spec = Spec(program=program, source_language=analysis.language, domain=domain, rules=rules, io=io,
                entities=tables, assumptions=resp.assumptions + notes + discarded)
    return spec, findings
