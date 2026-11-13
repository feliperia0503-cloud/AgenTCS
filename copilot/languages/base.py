"""Base común de los packs de DESTINO. Cada pack define su punto de entrada, su arnés de verificación
(lee cases.json, llama al punto de entrada, escribe actual.json) y los comandos de build/ejecución.

Regla compartida: el código propio del framework (controladores, configuración, inyección) vive SOLO en
carpetas `infrastructure/`, que no se compilan en la verificación de equivalencia (sus dependencias no
están disponibles sin red). El núcleo de dominio y el punto de entrada no pueden depender de ellas.
"""
from __future__ import annotations

import json
from pathlib import Path

from copilot.contracts import BuildResult, Case, CaseOutput, QualityReport, Spec, TestResult
from copilot.engine.pyharness import HarnessError
from copilot.engine.sandbox import ProcResult, resolve

INFRA_DIRS = {"infrastructure", "Infrastructure"}

COMMON_RULES = """Reglas comunes a todo destino:
- El código específico del framework elegido (controladores, endpoints, configuración, inyección de
  dependencias, ORM) va SOLO dentro de carpetas llamadas `infrastructure/`. Esas carpetas NO se compilan en
  la verificación de equivalencia; el dominio, la aplicación y el punto de entrada NO pueden importarlas.
- El punto de entrada de verificación delega en la capa de aplicación; no contiene lógica de negocio.
- Decimales exactos con escala y modo de redondeo del tipo neutral; nunca punto flotante para dinero.
- Errores de negocio: devuelve {"error": {"code": "<código>", "message": "<mensaje>"}} con el MISMO
  código y mensaje del legacy (no lances excepciones para errores de negocio).
- Comentario de trazabilidad en cada regla: `Regla BR-xxx · archivo:líneas`.
- Acceso a datos: si `input` trae la clave "_tablas" ({"TABLA": [filas como mapas columna→valor]}), define en
  el dominio un PUERTO (interfaz de repositorio) y, en el punto de entrada, un adaptador EN MEMORIA cargado
  desde "_tablas" (decimales como string). El adaptador real de base de datos va en `infrastructure/`. Las
  consultas en memoria replican la semántica del SQL legacy (filtros, orden, sumas, NULL, sin filas).
- No escribas el arnés de pruebas ni un método main/Program: los provee la plataforma."""


def is_infra(path: Path, root: Path) -> bool:
    return any(part in INFRA_DIRS for part in path.relative_to(root).parts[:-1])


def sources(root: Path, suffix: str, exclude: set[str] = frozenset()) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob(f"*{suffix}")
                  if not is_infra(p, root) and p.name not in exclude
                  and not any(part in {"build", "out", "dist", "bin", "obj", "node_modules"}
                              for part in p.relative_to(root).parts[:-1]))


def write_cases(root: Path, cases: list[Case]) -> None:
    (root / "cases.json").write_text(json.dumps([c.model_dump() for c in cases], ensure_ascii=False), encoding="utf-8")
    (root / "actual.json").unlink(missing_ok=True)


def read_actual(root: Path, result: ProcResult) -> list[CaseOutput]:
    actual = root / "actual.json"
    if not result.ok or not actual.is_file():
        raise HarnessError(result)
    return [CaseOutput.model_validate(o) for o in json.loads(actual.read_text(encoding="utf-8"))]


def to_build(result: ProcResult) -> BuildResult:
    return BuildResult(ok=result.ok, log=result.tail())


class BaseTarget:
    tools: list[str] = []

    def missing_tools(self) -> list[str]:
        return [t for t in self.tools if resolve(t) is None]

    def scaffold(self, spec: Spec, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)

    def test(self, project: Path) -> TestResult:
        return TestResult(passed=0, failed=0, log="Pruebas nativas no configuradas: la equivalencia se mide con el arnés")

    def quality(self, project: Path) -> QualityReport:
        return QualityReport()
