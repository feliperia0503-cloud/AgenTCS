"""Pack de DESTINO 'python' (Python 3.12). Sirve como destino real y como destino de pruebas del
motor, porque no necesita compiladores externos."""
from __future__ import annotations

import sys
from pathlib import Path

from copilot.contracts import (
    BuildResult, Case, CaseOutput, NeutralType, PackInfo, PackRole, QualityReport, Spec, TestResult,
    TypeKind,
)
from copilot.engine.pyharness import run_python_module
from copilot.engine.sandbox import run_cmd

ENTRY_MODULE = "app"

CONVENTIONS = """Destino: Python 3.12, solo biblioteca estándar.
- Punto de entrada OBLIGATORIO: archivo `app.py` con `def run(input: dict) -> dict | list[dict]`.
  `input` trae los campos de io.inputs (decimales como string). Devuelve los campos de io.outputs
  (una lista de dicts si output_is_list). Para errores de negocio devuelve
  {"error": {"code": "<código>", "message": "<mensaje>"}} con el MISMO código y mensaje del legacy.
- NO escribas el arnés de pruebas: lo provee la plataforma (importa `app` y llama `run`).
- Arquitectura limpia: `domain/` (reglas y value objects, sin E/S), `application/` (caso de uso),
  y `app.py` como adaptador de entrada. Cada carpeta con `__init__.py`.
- Dinero y tasas: `decimal.Decimal`, nunca float. Calcula intermedios con `localcontext()` prec=34 y
  aplica escala y redondeo SOLO al asignar, con `quantize(Decimal(10) ** -escala, rounding=...)`
  usando el modo del tipo neutral (HALF_UP→ROUND_HALF_UP, DOWN→ROUND_DOWN, HALF_EVEN→ROUND_HALF_EVEN).
- Devuelve decimales como string con la escala exacta del tipo (p. ej. "15.00").
- Cada función que implemente una regla lleva un comentario `# Regla BR-xxx · archivo:líneas`.
- Funciones cortas (complejidad ≤ 10), nombres de dominio, sin except vacíos."""

_PY_TYPES = {TypeKind.DECIMAL: "Decimal", TypeKind.INTEGER: "int", TypeKind.FLOAT: "float",
             TypeKind.STRING: "str", TypeKind.DATE: "datetime.date", TypeKind.DATETIME: "datetime.datetime",
             TypeKind.BOOLEAN: "bool", TypeKind.ENUM: "str", TypeKind.RECORD: "dict"}


class PythonTarget:
    info = PackInfo(id="python", name="Python 3.12", role=PackRole.TARGET, extensions=[".py"])

    def from_neutral_type(self, t: NeutralType) -> str:
        if t.kind == TypeKind.LIST and t.item is not None:
            return f"list[{self.from_neutral_type(t.item)}]"
        return _PY_TYPES[t.kind]

    def conventions(self) -> str:
        return CONVENTIONS

    def scaffold(self, spec: Spec, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)

    def build(self, project: Path) -> BuildResult:
        files = [str(p.relative_to(project)) for p in project.rglob("*.py")]
        if not (project / f"{ENTRY_MODULE}.py").is_file():
            return BuildResult(ok=False, log=f"Falta el punto de entrada {ENTRY_MODULE}.py con def run(input).")
        result = run_cmd([sys.executable, "-m", "py_compile", *files], project)
        return BuildResult(ok=result.ok, log=result.tail())

    def test(self, project: Path) -> TestResult:
        if not (project / "tests").is_dir():
            return TestResult(passed=0, failed=0, log="Sin pruebas nativas")
        result = run_cmd([sys.executable, "-m", "pytest", "-q", "tests"], project)
        return TestResult(passed=int(result.ok), failed=int(not result.ok), log=result.tail())

    def run_harness(self, project: Path, cases: list[Case]) -> list[CaseOutput]:
        return run_python_module(project, ENTRY_MODULE, cases)

    def quality(self, project: Path) -> QualityReport:
        return QualityReport()
