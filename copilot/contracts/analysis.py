"""Resultado de la ingesta y del análisis estático (salida de un SourceAdapter)."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .types import NeutralType


class SourceFile(BaseModel):
    """Archivo legacy YA sanitizado. El contenido original con secretos nunca sale de la ingesta."""
    path: str
    content: str
    language: str | None = None   # id del pack (cobol, plsql, csharp-legacy...)
    dialect: str | None = None

    @property
    def lines(self) -> list[str]:
        return self.content.splitlines()


class SanitizationFinding(BaseModel):
    """Qué se enmascaró. Nunca guarda el valor original."""
    kind: str            # api_key, password, connection_string, email, document_id...
    file: str
    line: int
    placeholder: str     # p. ej. "<<SECRET_1>>"
    detector: str        # detect-secrets, regex:<nombre>, presidio...


class UnitKind(StrEnum):
    PROGRAM = "program"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    PACKAGE = "package"
    PROCEDURE = "procedure"
    FUNCTION = "function"
    TRIGGER = "trigger"
    CLASS = "class"
    METHOD = "method"
    BLOCK = "block"
    OTHER = "other"


class Classification(StrEnum):
    NEGOCIO = "NEGOCIO"
    INFRAESTRUCTURA = "INFRAESTRUCTURA"
    MIXTO = "MIXTO"
    DESCONOCIDO = "DESCONOCIDO"


class Variable(BaseModel):
    name: str
    declared_type: str | None = None        # texto original: "PIC S9(7)V99 COMP-3", "NUMBER(9,2)"
    neutral_type: NeutralType | None = None
    file: str
    line: int
    is_constant: bool = False
    initial_value: str | None = None


class Unit(BaseModel):
    """Unidad de código: párrafo COBOL, procedimiento PL/SQL, método C#..."""
    id: str                      # único: "<file>::<name>"
    name: str
    kind: UnitKind
    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    calls: list[str] = []        # ids o nombres de unidades invocadas (PERFORM, CALL, llamadas a método)
    reads: list[str] = []        # variables leídas
    writes: list[str] = []       # variables escritas
    classification: Classification = Classification.DESCONOCIDO
    complexity: int = Field(default=1, ge=1)
    notes: list[str] = []        # GO TO, REDEFINES, SQL dinámico, catch vacío...

    @model_validator(mode="after")
    def _lines(self) -> Unit:
        if self.end_line < self.start_line:
            raise ValueError(f"{self.id}: end_line < start_line")
        return self


class Dependency(BaseModel):
    kind: str                    # copybook, include, table, file, program, package, class, external
    name: str
    from_unit: str | None = None
    resolved: bool = False


class RiskItem(BaseModel):
    unit_id: str
    level: str                   # ALTO / MEDIO / BAJO
    reasons: list[str]


class Metrics(BaseModel):
    loc: int
    units: int
    avg_complexity: float
    max_complexity: int
    dead_units: list[str] = []


class AnalysisResult(BaseModel):
    language: str
    dialect: str | None = None
    parser: str                  # "tree-sitter:cobol", "regex:plsql", "generic"
    files: list[str]
    units: list[Unit]
    variables: list[Variable] = []
    dependencies: list[Dependency] = []
    metrics: Metrics
    risks: list[RiskItem] = []
    confidence_penalty: float = Field(default=0.0, ge=0, le=1)  # >0 si se usó el segmentador genérico

    def unit(self, unit_id: str) -> Unit:
        for u in self.units:
            if u.id == unit_id:
                return u
        raise KeyError(unit_id)

    def check_against(self, files: dict[str, SourceFile]) -> list[str]:
        """Verificación determinista: las líneas de cada unidad existen en su archivo."""
        errors = []
        for u in self.units:
            f = files.get(u.file)
            if f is None:
                errors.append(f"{u.id}: archivo {u.file} no existe")
            elif u.end_line > len(f.lines):
                errors.append(f"{u.id}: línea {u.end_line} fuera de {u.file} ({len(f.lines)} líneas)")
        return errors
