"""Interfaces de los adaptadores de lenguaje (packs). El núcleo solo conoce estas interfaces.

Un pack vive en copilot/languages/<id>/ con pack.yaml + adapter.py. Ver skill `language-adapters`.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .analysis import AnalysisResult, SourceFile
from .spec import Spec
from .types import NeutralType
from .verification import Case, CaseOutput, OracleLevel


class PackRole(StrEnum):
    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"


class PackInfo(BaseModel):
    """Contenido de pack.yaml."""
    id: str                         # cobol, plsql, csharp-legacy, java, typescript, csharp, python
    name: str                       # "COBOL (GnuCOBOL)", "Java 21 + Spring Boot 3"
    role: PackRole
    extensions: list[str] = []      # [".cbl", ".cob", ".cpy"]
    version: str = "0.1.0"
    oracle_level: OracleLevel | None = None   # solo origen: nivel máximo que su runner puede dar


class BuildResult(BaseModel):
    ok: bool
    log: str = ""
    duration_s: float = 0.0


class TestResult(BaseModel):
    passed: int
    failed: int
    coverage_lines: float | None = None
    coverage_branches: float | None = None
    log: str = ""


class QualityFinding(BaseModel):
    tool: str                       # pmd, eslint, roslyn, ruff, semgrep, gitleaks, archunit...
    severity: str                   # CRITICAL, MAJOR, MINOR
    file: str
    line: int | None = None
    message: str


class QualityReport(BaseModel):
    findings: list[QualityFinding] = []
    max_complexity: int | None = None

    @property
    def critical(self) -> int:
        return sum(f.severity == "CRITICAL" for f in self.findings)


@runtime_checkable
class LegacyRunner(Protocol):
    """Ejecuta el legacy para obtener el golden master (oráculo nivel A)."""
    def build(self, files: list[SourceFile], workdir: Path) -> BuildResult: ...
    def run(self, spec: Spec, cases: list[Case], workdir: Path) -> list[CaseOutput]: ...


@runtime_checkable
class SourceAdapter(Protocol):
    info: PackInfo
    runner: LegacyRunner | None     # None => oráculo nivel B o C

    def detect(self, files: list[SourceFile]) -> float: ...                 # 0..1
    def parse(self, files: list[SourceFile]) -> AnalysisResult: ...
    def classify(self, analysis: AnalysisResult, files: list[SourceFile]) -> AnalysisResult: ...
    def to_neutral_type(self, declaration: str) -> NeutralType: ...
    def knowledge(self) -> str: ...  # semántica del lenguaje para el prompt del extractor


@runtime_checkable
class TargetAdapter(Protocol):
    info: PackInfo

    def from_neutral_type(self, t: NeutralType) -> str: ...
    def conventions(self) -> str: ...   # reglas de arquitectura/estilo para el prompt del desarrollador
    def scaffold(self, spec: Spec, out: Path) -> None: ...
    def build(self, project: Path) -> BuildResult: ...
    def test(self, project: Path) -> TestResult: ...
    def run_harness(self, project: Path, cases: list[Case]) -> list[CaseOutput]: ...
    def quality(self, project: Path) -> QualityReport: ...
