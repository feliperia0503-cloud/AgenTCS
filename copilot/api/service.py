"""Lógica de la API independiente del framework web (FastAPI solo la expone).

Errores: ServiceError con código estable, mensaje y acción sugerida (el reto pide mensajes de
error con acción para el usuario y sin exponer datos).
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

from copilot.contracts import (
    Phase, PhaseStatus, RuleStatus, RunMode, RunState, Spec,
)
from copilot.security import Sanitizer

from . import demo

log = logging.getLogger("agentcs.api")

OUTPUT_DIR = Path(os.environ.get("AGENTCS_OUTPUT", "output")) / "runs"
DEFAULT_MODE = RunMode(os.environ.get("AGENTCS_MODE", RunMode.DEMO.value))

MAX_FILES = 20
MAX_FILE_BYTES = 2 * 1024 * 1024

# Catálogo de packs. Cuando existan copilot/languages/*/pack.yaml, se leerá de ahí.
SOURCES = [
    {"id": "cobol", "name": "COBOL (GnuCOBOL)", "extensions": [".cbl", ".cob", ".cpy"], "oracle_level": "A", "status": "en construcción"},
    {"id": "plsql", "name": "PL/SQL (Oracle)", "extensions": [".pks", ".pkb", ".sql", ".prc", ".fnc", ".trg"], "oracle_level": "A", "status": "planeado"},
    {"id": "csharp-legacy", "name": "C# / VB.NET (.NET Framework)", "extensions": [".cs", ".vb"], "oracle_level": "A", "status": "planeado"},
    {"id": "java-legacy", "name": "Java legacy (1.4–6)", "extensions": [".java"], "oracle_level": "A", "status": "planeado"},
    {"id": "rpg", "name": "RPG (IBM i)", "extensions": [".rpg", ".rpgle", ".sqlrpgle"], "oracle_level": "C", "status": "planeado"},
]
TARGETS = [
    {"id": "python", "name": "Python 3.12", "status": "disponible (motor real)"},
    {"id": "java", "name": "Java 21 + Spring Boot 3", "status": "en construcción"},
    {"id": "typescript", "name": "TypeScript + Node 20", "status": "planeado"},
    {"id": "csharp", "name": "C# .NET 8", "status": "planeado"},
]
_EXT_TO_SOURCE = {ext: s["id"] for s in SOURCES for ext in s["extensions"]}


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str, action: str):
        super().__init__(message)
        self.status, self.code, self.message, self.action = status, code, message, action

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "action": self.action}


class RunStore:
    """Estado en memoria + copia en disco (output/runs/<id>/state.json) para no perderlo al reiniciar."""

    def __init__(self, root: Path = OUTPUT_DIR):
        self.root = root
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def save(self, state: RunState) -> None:
        with self._lock:
            self._runs[state.run_id] = state
            folder = self.root / state.run_id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "state.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def get(self, run_id: str) -> RunState:
        with self._lock:
            if run_id in self._runs:
                return self._runs[run_id]
        path = self.root / run_id / "state.json"
        if path.is_file() and run_id.isalnum():
            state = RunState.model_validate_json(path.read_text(encoding="utf-8"))
            with self._lock:
                self._runs[run_id] = state
            return state
        raise ServiceError(404, "RUN_NOT_FOUND", f"No existe la ejecución {run_id}.",
                           "Crea una nueva ejecución desde la pantalla de migración.")


class CopilotService:
    def __init__(self, store: RunStore | None = None, mode: RunMode = DEFAULT_MODE,
                 engine_factory: Callable[[], object] | None = None, background: bool = True):
        self.store = store or RunStore()
        self.mode = mode
        self.background = background
        self._engine_factory = engine_factory
        self._engine = None

    # ---------------------------------------------------------------- catálogo
    def languages(self) -> dict:
        return {"sources": SOURCES, "targets": TARGETS, "mode": self.mode.value}

    # ---------------------------------------------------------------- ejecuciones
    def create_run(self, files: list[tuple[str, bytes]], target_language: str,
                   source_language: str | None = None, domain: str | None = None,
                   demo_mode: bool | None = None) -> RunState:
        if target_language not in {t["id"] for t in TARGETS}:
            raise ServiceError(422, "TARGET_NOT_SUPPORTED", f"El destino '{target_language}' no está disponible.",
                               "Elige un destino de la lista: " + ", ".join(t["id"] for t in TARGETS) + ".")
        run_id = uuid.uuid4().hex[:12]
        use_demo = self.mode == RunMode.DEMO if demo_mode is None else demo_mode
        if use_demo and not files:
            state = demo.build_demo_run(run_id, target_language)
            self.store.save(state)
            return state
        decoded = self._validate_files(files)
        if source_language is None:
            source_language = self._detect(decoded)
        sanitized, findings = Sanitizer().sanitize_files(decoded)
        for f in sanitized:
            f.language = source_language
        state = RunState(run_id=run_id, mode=RunMode.REAL, source_language=source_language,
                         target_language=target_language, domain=domain, files=sanitized,
                         sanitization=findings)
        state.start(Phase.INGESTA)
        state.finish(Phase.INGESTA, ok=True,
                     message=f"{len(sanitized)} archivo(s) {source_language} · {len(findings)} dato(s) sensible(s) enmascarado(s)")
        self.store.save(state)
        self._dispatch(self._analyze, state)
        return state

    def get_run(self, run_id: str) -> RunState:
        return self.store.get(run_id)

    # ---------------------------------------------------------------- HITL
    def decide_rule(self, run_id: str, rule_id: str, action: str, by: str,
                    comment: str | None = None, changes: dict | None = None) -> RunState:
        state = self._require_review_phase(run_id)
        try:
            rule = state.spec.rule(rule_id)
        except StopIteration:
            raise ServiceError(404, "RULE_NOT_FOUND", f"La regla {rule_id} no existe en esta ejecución.",
                               "Recarga la lista de reglas.") from None
        if not by.strip():
            raise ServiceError(422, "REVIEWER_REQUIRED", "Falta el nombre de quien revisa.",
                               "Indica tu nombre para dejar trazabilidad de la decisión.")
        allowed = {"condition", "action", "description", "assumptions", "decision_table", "name"}
        changes = changes or {}
        if bad := set(changes) - allowed:
            raise ServiceError(422, "INVALID_CHANGES", f"No se pueden modificar: {', '.join(sorted(bad))}.",
                               f"Solo se pueden ajustar: {', '.join(sorted(allowed))}.")
        try:
            if action == "approve":
                new = rule.approve(by=by, comment=comment)
            elif action == "adjust":
                if not comment:
                    raise ServiceError(422, "COMMENT_REQUIRED", "Ajustar una regla requiere un comentario.",
                                       "Explica qué cambiaste y por qué.")
                new = rule.adjust(by=by, comment=comment, **changes)
            elif action == "reject":
                if not comment:
                    raise ServiceError(422, "COMMENT_REQUIRED", "Rechazar una regla requiere un comentario.",
                                       "Explica por qué la regla no es válida.")
                new = rule.reject(by=by, comment=comment)
            else:
                raise ServiceError(422, "INVALID_ACTION", f"Acción desconocida: {action}.",
                                   "Usa approve, adjust o reject.")
        except ValueError as exc:   # validación del contrato (p. ej. confianza baja sin comentario)
            msg = str(exc.errors()[0]["msg"]) if hasattr(exc, "errors") else str(exc)
            raise ServiceError(422, "RULE_VALIDATION", msg.removeprefix("Value error, "),
                               "Agrega un comentario que justifique la decisión.") from None
        state.update_spec(state.spec.replace_rule(new))
        pending = len(state.spec.pending)
        state.wait_for_human(Phase.VALIDACION_HUMANA,
                             f"{pending} regla(s) pendiente(s)" if pending else "Todas las reglas revisadas: lista para aprobar")
        self.store.save(state)
        return state

    def approve_spec(self, run_id: str, by: str) -> RunState:
        state = self._require_review_phase(run_id)
        if not state.spec.is_fully_reviewed:
            ids = ", ".join(r.id for r in state.spec.pending)
            raise ServiceError(409, "RULES_PENDING", f"Faltan reglas por revisar: {ids}.",
                               "Aprueba, ajusta o rechaza cada regla antes de continuar.")
        if not state.spec.active_rules:
            raise ServiceError(409, "NO_ACTIVE_RULES", "Todas las reglas fueron rechazadas.",
                               "Aprueba al menos una regla para generar código.")
        if state.mode == RunMode.REAL:
            self._require_target_pack(state.target_language)
        state.approved_by = by
        if state.mode == RunMode.DEMO:
            demo.complete_demo_run(state)
            self.store.save(state)
            return state
        state.finish(Phase.VALIDACION_HUMANA, ok=True, message=f"Especificación aprobada por {by}")
        self.store.save(state)
        self._dispatch(self._generate, state)
        return state

    # ---------------------------------------------------------------- motor real (ADR-005)
    def _get_engine(self):
        if self._engine is None:
            if self._engine_factory is None:
                from copilot.engine.pipeline import Engine
                self._engine_factory = Engine.from_env
            self._engine = self._engine_factory()
        return self._engine

    def _dispatch(self, job: Callable[[RunState], None], state: RunState) -> None:
        if self.background:
            threading.Thread(target=job, args=(state,), daemon=True, name=f"agentcs-{state.run_id}").start()
        else:
            job(state)

    def _analyze(self, state: RunState) -> None:
        self._guarded(state, lambda engine: engine.analyze(state, self.store.save))

    def _generate(self, state: RunState) -> None:
        self._guarded(state, lambda engine: engine.generate_and_verify(state, self.store.save))

    def _guarded(self, state: RunState, work: Callable[[object], None]) -> None:
        """Ejecuta una etapa del motor; cualquier fallo queda en la fase en curso con acción sugerida."""
        from copilot.engine.llm import LLMError
        try:
            work(self._get_engine())
        except LLMError as exc:
            self._fail_current(state, f"{exc.message} Acción: {exc.action}")
        except Exception:   # noqa: BLE001 — nunca exponer trazas ni datos del usuario
            log.exception("Fallo inesperado en el motor (run %s)", state.run_id)
            self._fail_current(state, "Error inesperado en el motor. Acción: reintenta; si persiste, revisa los registros de la API.")

    def _fail_current(self, state: RunState, message: str) -> None:
        running = [p for p in Phase if state.phases[p].status == PhaseStatus.EN_CURSO]
        pending = [p for p in Phase if state.phases[p].status == PhaseStatus.PENDIENTE]
        phase = (running or pending or [Phase.EMPAQUETADO])[0]
        state.finish(phase, ok=False, message=message)
        state.errors.append(message)
        self.store.save(state)

    @staticmethod
    def _require_target_pack(target: str) -> None:
        from copilot.languages.registry import PackNotAvailable, get_target
        try:
            get_target(target)
        except PackNotAvailable as exc:
            raise ServiceError(422, "TARGET_PACK_MISSING",
                               f"El motor real aún no tiene el pack de destino '{target}'.",
                               f"Usa un destino disponible ({', '.join(exc.available)}) o el modo demo.") from None

    # ---------------------------------------------------------------- resultados
    def verification(self, run_id: str) -> dict:
        state = self.get_run(run_id)
        if state.verification is None:
            raise ServiceError(409, "NOT_VERIFIED", "Esta ejecución aún no tiene verificación.",
                               "Aprueba la especificación para generar y verificar el código.")
        return {"current": state.verification.model_dump(mode="json"),
                "history": [v.model_dump(mode="json") for v in state.verification_history],
                "gate_failures": state.verification.gate_failures()}

    def package(self, run_id: str) -> bytes:
        state = self.get_run(run_id)
        if state.phases[Phase.EMPAQUETADO].status != PhaseStatus.APROBADA or state.spec is None:
            raise ServiceError(409, "PACKAGE_NOT_READY", "El paquete aún no está listo.",
                               "Espera a que termine la verificación.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("README.md", _package_readme(state))
            z.writestr("docs/business-rules.json", state.spec.model_dump_json(indent=2))
            z.writestr("docs/traceability-matrix.md", _traceability(state.spec))
            z.writestr("docs/sanitization.json", json.dumps(
                [f.model_dump() for f in state.sanitization], indent=2, ensure_ascii=False))
            z.writestr("reports/analysis.json", state.analysis.model_dump_json(indent=2) if state.analysis else "{}")
            z.writestr("reports/equivalence-report.json", json.dumps(
                self.verification(run_id), indent=2, ensure_ascii=False))
            z.writestr("tests/cases.json", json.dumps([c.model_dump() for c in state.cases], indent=2, ensure_ascii=False))
            z.writestr("tests/expected.json", json.dumps([o.model_dump() for o in state.expected], indent=2, ensure_ascii=False))
            for path, content in state.generated_files.items():
                z.writestr(path, content)
        return buf.getvalue()

    # ---------------------------------------------------------------- utilidades
    def _require_review_phase(self, run_id: str) -> RunState:
        state = self.get_run(run_id)
        if state.spec is None:
            raise ServiceError(409, "SPEC_NOT_READY", "La especificación todavía no está lista.",
                               "Espera a que termine la extracción de reglas.")
        if state.phases[Phase.VALIDACION_HUMANA].status != PhaseStatus.ESPERANDO_HUMANO:
            raise ServiceError(409, "REVIEW_CLOSED", "La revisión de reglas ya se cerró para esta ejecución.",
                               "Crea una nueva ejecución si necesitas cambiar reglas.")
        return state

    @staticmethod
    def _validate_files(files: list[tuple[str, bytes]]) -> list[tuple[str, str]]:
        if not files:
            raise ServiceError(422, "NO_FILES", "No se recibió ningún archivo legacy.",
                               "Adjunta al menos un archivo de código fuente.")
        if len(files) > MAX_FILES:
            raise ServiceError(422, "TOO_MANY_FILES", f"Se recibieron {len(files)} archivos (máximo {MAX_FILES}).",
                               "Sube solo el programa a migrar y sus dependencias directas.")
        out = []
        for name, data in files:
            safe = Path(name).name   # sin rutas: evita path traversal
            if len(data) > MAX_FILE_BYTES:
                raise ServiceError(413, "FILE_TOO_LARGE", f"{safe} supera {MAX_FILE_BYTES // 1024 // 1024} MB.",
                                   "Divide el programa o sube solo la rutina a migrar.")
            if b"\x00" in data[:4096]:
                raise ServiceError(422, "BINARY_FILE", f"{safe} parece un archivo binario.",
                                   "Sube el código fuente en texto (no compilados ni comprimidos).")
            for enc in ("utf-8", "cp1252", "latin-1"):
                try:
                    out.append((safe, data.decode(enc)))
                    break
                except UnicodeDecodeError:
                    continue
        return out

    @staticmethod
    def _detect(files: list[tuple[str, str]]) -> str:
        found = {_EXT_TO_SOURCE.get(Path(n).suffix.lower()) for n, _ in files} - {None}
        if len(found) == 1:
            return found.pop()
        raise ServiceError(422, "LANGUAGE_UNKNOWN",
                           "No se pudo identificar un único lenguaje de origen por la extensión.",
                           "Indica el lenguaje de origen manualmente en la configuración.")


def _traceability(spec: Spec) -> str:
    rows = ["| Regla | Nombre | Legacy | Estado | Revisor | Comentario |", "|---|---|---|---|---|---|"]
    for r in spec.rules:
        rev = r.review
        rows.append(f"| {r.id} | {r.name} | {r.source.file}:{r.source.lines[0]}–{r.source.lines[1]} · "
                    f"{r.source.unit} | {r.status} | {rev.by if rev else ''} | {(rev.comment or '') if rev else ''} |")
    return "# Matriz de trazabilidad\n\n" + "\n".join(rows) + "\n"


def _package_readme(state: RunState) -> str:
    v = state.verification
    active = sum(r.status in (RuleStatus.APROBADA, RuleStatus.AJUSTADA) for r in state.spec.rules)
    return (f"# Paquete de migración · {state.spec.program}\n\n"
            f"- Origen → destino: {state.source_language} → {state.target_language}\n"
            f"- Modo: {state.mode.value}\n"
            f"- Reglas activas: {active} de {len(state.spec.rules)} (aprobó: {state.approved_by})\n"
            f"- Equivalencia: {v.passed}/{v.total} casos · oráculo nivel {v.oracle_level}\n"
            f"- Intentos de generación: {state.generation_attempts}\n")
