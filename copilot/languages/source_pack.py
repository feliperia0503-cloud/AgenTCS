"""Pack de ORIGEN declarativo: un lenguaje legacy = pack.yaml + knowledge.md, sin código Python.

pack.yaml (role: source):
    id, name, extensions, aliases (otros ids que detecta la ingesta), oracle_level (A si tiene runner)
    runner: tools, build, run, compile_extensions, include_args, allowed_flags, harness_hint
knowledge.md: semántica y trampas del lenguaje; se inyecta en el prompt del extractor.

El análisis estructural usa el segmentador genérico (confianza reducida y declarada); un pack puede
reemplazarlo más adelante con un parser propio sin tocar el motor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from copilot.contracts import (
    AnalysisResult, NeutralType, OracleLevel, PackInfo, PackRole, SourceFile,
)
from copilot.engine.segmenter import segment

from .oracle_runner import OracleLegacyRunner
from .source_runner import GenericLegacyRunner, RunnerConfig

PACKS_DIR = Path(__file__).parent


@dataclass
class DeclarativeSource:
    info: PackInfo
    runner: GenericLegacyRunner | OracleLegacyRunner | None
    aliases: list[str]
    knowledge_text: str
    support: str | None = None      # soporte determinista adicional (p. ej. sql_scripts)

    @classmethod
    def load(cls, folder: Path) -> DeclarativeSource | None:
        meta_path = folder / "pack.yaml"
        if not meta_path.is_file():
            return None
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if meta.get("role") not in ("source", "both"):
            return None
        runner_cfg = meta.get("runner")
        info = PackInfo(id=meta["id"], name=meta["name"], role=PackRole(meta["role"]),
                        extensions=meta.get("extensions", []), version=str(meta.get("version", "0.1.0")),
                        oracle_level=OracleLevel.A if runner_cfg else OracleLevel.C)
        runner = _make_runner(info, runner_cfg)
        knowledge = folder / "knowledge.md"
        return cls(info=info, runner=runner, aliases=list(meta.get("aliases", [])),
                   knowledge_text=knowledge.read_text(encoding="utf-8") if knowledge.is_file() else "",
                   support=meta.get("support"))

    # --- SourceAdapter
    def detect(self, files: list[SourceFile]) -> float:
        if not files:
            return 0.0
        exts = {e.lower() for e in self.info.extensions}
        return sum(Path(f.path).suffix.lower() in exts for f in files) / len(files)

    def parse(self, files: list[SourceFile]) -> AnalysisResult:
        return segment(files, self.info.id)

    def classify(self, analysis: AnalysisResult, files: list[SourceFile]) -> AnalysisResult:
        return analysis

    def to_neutral_type(self, declaration: str) -> NeutralType:
        try:
            return NeutralType.parse(declaration)
        except ValueError:
            size = re.search(r"\d+", declaration)
            return NeutralType.parse(f"string({size.group() if size else 255})")

    def knowledge(self) -> str:
        return self.knowledge_text

    # --- capacidades opcionales que el motor consulta con hasattr/getattr
    def file_roles(self, files: list[SourceFile]) -> dict[str, str]:
        """Papel de cada archivo: codigo | configuracion | datos_prueba | ejecucion."""
        if self.support == "sql_scripts":
            from . import sql_scripts
            return sql_scripts.file_roles(files)
        return {f.path: "codigo" for f in files}

    def base_tables(self, files: list[SourceFile]) -> dict[str, list[dict]] | None:
        """Estado inicial de la base (configuración + datos de prueba) como filas tipadas, si aplica."""
        if self.support != "sql_scripts":
            return None
        from . import sql_scripts
        data = sql_scripts.base_dataset(files)
        return data.rows if any(data.rows.values()) else None

    def runtime_available(self) -> bool:
        return self.runner is not None and not self.runner.missing_tools()


def _make_runner(info: PackInfo, cfg: dict | None):
    if not cfg:
        return None
    if cfg.get("kind") == "oracle":
        return OracleLegacyRunner(info.id, info.name)
    return GenericLegacyRunner(info.id, info.name, RunnerConfig.from_dict(cfg))


def load_source_packs(root: Path = PACKS_DIR) -> dict[str, DeclarativeSource]:
    packs: dict[str, DeclarativeSource] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        pack = DeclarativeSource.load(folder)
        if pack is None:
            continue
        for key in [pack.info.id, *pack.aliases]:
            packs.setdefault(key, pack)
    return packs
