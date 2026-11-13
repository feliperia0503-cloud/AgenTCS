"""Oráculo: el comportamiento esperado contra el que se compara el código migrado.

Nivel A: el legacy real ejecutado por el LegacyRunner del pack de origen.
Nivel B: pares entrada/salida provistos (sintéticos o anonimizados).
Nivel C: implementación de referencia en Python generada desde la Spec APROBADA, independiente del
         código migrado. Se declara siempre en el VerificationReport.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from copilot.contracts import Case, CaseOutput, LegacyRunner, OracleLevel, Phase, SourceFile, Spec

from .llm import LLMClient, LLMError, complete_json
from .prompts import ORACLE_SYSTEM
from .pyharness import HarnessError, run_python_module
from .sandbox import SandboxError, write_files


@dataclass
class OracleResult:
    level: OracleLevel
    description: str
    outputs: list[CaseOutput]
    reference_code: str | None = None


class ReferenceResponse(BaseModel):
    code: str


def _level_a(runner: LegacyRunner, spec: Spec, files: list[SourceFile], cases: list[Case], workdir: Path,
             llm: LLMClient | None) -> OracleResult:
    if hasattr(runner, "bind"):          # runners genéricos: el LLM escribe el arnés del legacy
        runner = runner.bind(llm)
    build = runner.build(files, workdir)
    if not build.ok:
        raise LLMError("LEGACY_BUILD_FAILED", build.log or "El código legacy no compiló en el sandbox.",
                       "Revisa dependencias (copybooks, includes) o usa pares E/S (nivel B).")
    outputs = runner.run(spec, cases, workdir)
    harness = runner.harness_code() if hasattr(runner, "harness_code") else None
    attempts = getattr(runner, "attempts", 0)
    detail = f" Arnés de ejecución generado y verificado en {attempts} intento(s)." if attempts else ""
    return OracleResult(OracleLevel.A, "Legacy ejecutado en el sandbox sin modificar (comportamiento real)." + detail,
                        outputs, harness)


def _level_b(provided: list[CaseOutput], cases: list[Case]) -> OracleResult:
    by_id = {o.id: o for o in provided}
    missing = [c.id for c in cases if c.id not in by_id]
    if missing:
        raise LLMError("ORACLE_PAIRS_INCOMPLETE", f"Faltan salidas esperadas para {len(missing)} caso(s).",
                       "Completa el archivo de pares E/S o deja que el motor use el oráculo de referencia.")
    return OracleResult(OracleLevel.B, "Pares entrada/salida provistos por el cliente.", [by_id[c.id] for c in cases])


def _level_c(llm: LLMClient, spec: Spec, cases: list[Case], workdir: Path) -> OracleResult:
    payload = spec.model_dump(mode="json", include={"program", "source_language", "rules", "io", "entities"})
    for r in payload["rules"]:
        r["source"].pop("snippet", None)
    prompt = (f"Especificación APROBADA:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
              'Responde con {"code": "<archivo reference.py completo>"}.')
    ref = complete_json(llm, ORACLE_SYSTEM, prompt, ReferenceResponse, agent="oracle", phase=Phase.VERIFICACION)
    write_files(workdir, {"reference.py": ref.code})
    try:
        outputs = run_python_module(workdir, "reference", cases)
    except HarnessError as exc:
        raise LLMError("ORACLE_FAILED", "La implementación de referencia no se pudo ejecutar.",
                       "Reintenta la verificación; si persiste, revisa la especificación.") from exc
    return OracleResult(OracleLevel.C, "Implementación de referencia independiente generada desde la "
                        "especificación aprobada (Python + Decimal).", outputs, ref.code)


def compute_expected(spec: Spec, cases: list[Case], *, workdir: Path, llm: LLMClient | None = None,
                     runner: LegacyRunner | None = None, files: list[SourceFile] | None = None,
                     provided: list[CaseOutput] | None = None) -> OracleResult:
    """Nivel A si el legacy se puede ejecutar; si no, B (pares provistos) o C, declarando por qué."""
    workdir.mkdir(parents=True, exist_ok=True)
    fallback = ""
    if runner is not None and files:
        try:
            return _level_a(runner, spec, files, cases, workdir / "legacy", llm)
        except (LLMError, HarnessError, SandboxError, OSError, ValueError) as exc:
            reason = exc.message if isinstance(exc, LLMError) else f"{type(exc).__name__}: {str(exc)[:300]}"
            fallback = f"Nivel A no disponible ({reason}). "
    if provided:
        result = _level_b(provided, cases)
    elif llm is None:
        raise LLMError("NO_ORACLE", "No hay forma de obtener resultados esperados.",
                       "Configura un pack de origen con runner, pares E/S o un LLM para la referencia.")
    else:
        result = _level_c(llm, spec, cases, workdir)
    if fallback:
        result.description = fallback + result.description
    return result
