"""Runner genérico de ORIGEN: ejecuta el legacy real para obtener el golden master (oráculo nivel A).

Funciona para cualquier lenguaje con compilador o intérprete en el contenedor. El pack solo declara sus
comandos en pack.yaml; el LLM escribe un ARNÉS mínimo (o usa el programa tal cual) y la plataforma hace
todo lo determinista:

    cases.json ──► líneas por stdin ──► [legacy SIN modificar + arnés] ──► stdout ──► CaseOutput

Protocolo de salida del arnés (modo "driver"), una línea por dato:
    @@<campo>=<valor>        un campo de salida
    @@ROW                    separador de filas (salidas tipo lista)
    @@ERROR=<código>|<msj>   error de negocio
Las demás líneas (DISPLAY/echo del propio legacy) se ignoran.

Modo "direct": el legacy ya lee de stdin y escribe en stdout; el plan declara expresiones regulares para
leer cada campo y cada código de error.

Salvaguardas deterministas: el arnés no puede sobrescribir archivos legacy, debe usar al menos un archivo
legacy, tiene tamaño acotado y los flags de compilación pasan por la lista blanca del pack. Si tras varios
intentos no se logra ejecutar, se lanza LLMError y el oráculo baja a nivel B/C declarándolo.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field

from copilot.contracts import (
    BuildResult, Case, CaseError, CaseOutput, NeutralType, Phase, SourceFile, Spec, TypeKind,
)
from copilot.engine.llm import LLMClient, LLMError, complete_json
from copilot.engine.prompts import COMMON, numbered
from copilot.engine.sandbox import SandboxError, resolve, run_cmd, write_files

MAX_ATTEMPTS = int(os.environ.get("AGENTCS_HARNESS_ATTEMPTS", "3"))
CASE_TIMEOUT = float(os.environ.get("AGENTCS_HARNESS_CASE_TIMEOUT", "15"))
MAX_HARNESS_FILES = 3
MAX_HARNESS_CHARS = 30_000
MAX_CODE_CHARS = 60_000
PREFIX = "@@"


# ---------------------------------------------------------------- configuración del pack
@dataclass(frozen=True)
class RunnerConfig:
    """Sección `runner` de pack.yaml."""
    tools: list[str]
    build: list[str]
    run: list[str]
    compile_extensions: list[str] = field(default_factory=list)
    include_args: list[str] = field(default_factory=list)       # p. ej. ["-I{dir}"] por carpeta
    allowed_flags: list[str] = field(default_factory=list)      # expresiones regulares
    harness_hint: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunnerConfig:
        return cls(tools=list(d.get("tools", [])), build=list(d.get("build", [])), run=list(d["run"]),
                   compile_extensions=[e.lower() for e in d.get("compile_extensions", [])],
                   include_args=list(d.get("include_args", [])), allowed_flags=list(d.get("allowed_flags", [])),
                   harness_hint=str(d.get("harness_hint", "")).strip())


# ---------------------------------------------------------------- plan que propone el LLM
class InputField(BaseModel):
    name: str
    format: Literal["plain", "implied"] = "plain"   # implied: dígitos sin punto (PIC 9(n)V99)
    width: int | None = Field(default=None, ge=1, le=64)


class OutputField(BaseModel):
    name: str
    format: Literal["plain", "implied"] = "plain"
    pattern: str | None = None                       # solo modo direct: regex con UN grupo


class ErrorPattern(BaseModel):
    pattern: str                                     # solo modo direct
    code: str


class HarnessPlan(BaseModel):
    mode: Literal["driver", "direct"]
    entry: str                                       # archivo principal a compilar/ejecutar
    files: dict[str, str] = {}                       # archivos NUEVOS del arnés (nunca legacy)
    compile: list[str] = []                          # vacío = todos los compilables
    flags: list[str] = []
    inputs: list[InputField]
    outputs: list[OutputField] = []
    errors: list[ErrorPattern] = []
    notes: str = ""


class HarnessFailure(Exception):
    """Fallo del arnés (no del legacy): se devuelve al LLM como retroalimentación."""


# ---------------------------------------------------------------- conversión determinista
def _field_types(fields: list[Any]) -> dict[str, NeutralType]:
    return {f.name: f.type for f in fields}


def render_stdin(plan: HarnessPlan, case: Case, types: dict[str, NeutralType]) -> str:
    lines = []
    for f in plan.inputs:
        value = case.input.get(f.name)
        lines.append(_encode(value, f, types.get(f.name)))
    return "\n".join(lines) + "\n"


def _encode(value: Any, f: InputField, t: NeutralType | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "1" if value else "0"
    elif f.format == "implied" and t is not None and t.kind == TypeKind.DECIMAL:
        digits = int((Decimal(str(value)) * (Decimal(10) ** (t.scale or 0))).to_integral_value())
        text = str(abs(digits)).zfill(f.width or 0)
        return ("-" + text) if digits < 0 else text
    else:
        text = str(value)
    return text.zfill(f.width) if f.width and f.format == "implied" else text


def normalize(raw: str, t: NeutralType | None, fmt: str = "plain") -> Any:
    """Texto del legacy -> valor neutral (decimales como string con la escala del tipo)."""
    s = raw.strip()
    if t is None or t.kind in (TypeKind.STRING, TypeKind.ENUM):
        return raw.rstrip()
    if t.kind == TypeKind.BOOLEAN:
        return s.upper() in {"1", "TRUE", "T", "Y", "S", "SI", "YES"}
    sign = ""
    if s.endswith(("-", "+")):                       # signo al final (PIC ...-)
        sign, s = ("-" if s[-1] == "-" else ""), s[:-1]
    if s.startswith(("-", "+")):
        sign, s = ("-" if s[0] == "-" else sign), s[1:]
    s = s.replace(" ", "").replace(",", "").replace("$", "")
    try:
        number = Decimal(sign + s) if s else Decimal(0)
    except InvalidOperation as exc:
        raise HarnessFailure(f"valor no numérico {raw!r}") from exc
    if t.kind == TypeKind.INTEGER:
        return int(number)
    if t.kind == TypeKind.DECIMAL:
        scale = t.scale or 0
        if fmt == "implied":
            number = number.scaleb(-scale)
        if number.as_tuple().exponent >= -scale:     # solo rellena ceros; nunca redondea
            number = number.quantize(Decimal(10) ** -scale)
        return format(number, "f")
    return s


def parse_driver(stdout: str, spec: Spec, plan: HarnessPlan) -> CaseOutput | dict:
    out_types = _field_types(spec.io.outputs)
    formats = {o.name: o.format for o in plan.outputs}
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    seen = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith(PREFIX):
            continue
        seen = True
        body = line[len(PREFIX):]
        if body.startswith("ERROR="):
            code, _, msg = body[6:].partition("|")
            return {"error": (code.strip(), msg.strip())}
        if body == "ROW":
            if current:
                rows.append(current)
            current = {}
            continue
        name, sep, value = body.partition("=")
        if not sep or name.strip() not in out_types:
            continue
        current[name.strip()] = normalize(value, out_types[name.strip()], formats.get(name.strip(), "plain"))
    if current:
        rows.append(current)
    if not seen:
        raise HarnessFailure("el arnés no imprimió ninguna línea @@")
    return {"rows": rows}


def parse_direct(stdout: str, spec: Spec, plan: HarnessPlan) -> dict:
    for e in plan.errors:
        if re.search(e.pattern, stdout, re.MULTILINE):
            return {"error": (e.code, "")}
    out_types = _field_types(spec.io.outputs)
    columns: dict[str, list[Any]] = {}
    for o in plan.outputs:
        if not o.pattern:
            continue
        found = re.findall(o.pattern, stdout, re.MULTILINE)
        columns[o.name] = [normalize(v if isinstance(v, str) else v[0], out_types.get(o.name), o.format)
                           for v in found]
    if not columns or not any(columns.values()):
        raise HarnessFailure("ninguna expresión regular de salida encontró valores en stdout")
    n = max(len(v) for v in columns.values())
    rows = [{k: v[i] for k, v in columns.items() if i < len(v)} for i in range(n)]
    return {"rows": rows}


def to_case_output(case_id: str, parsed: dict, spec: Spec) -> CaseOutput:
    if "error" in parsed:
        code, msg = parsed["error"]
        known = {e.code: e.message for e in spec.io.errors}
        return CaseOutput(id=case_id, error=CaseError(code=code, message=known.get(code, msg)))
    rows = parsed["rows"]
    if spec.io.output_is_list:
        return CaseOutput(id=case_id, output=rows)
    if not rows:
        raise HarnessFailure("no se obtuvo ningún campo de salida")
    return CaseOutput(id=case_id, output=rows[-1])


# ---------------------------------------------------------------- validación del plan
def _norm(path: str) -> str:
    return str(PurePosixPath(path.replace("\\", "/"))).lower()


def validate_plan(plan: HarnessPlan, files: list[SourceFile], spec: Spec, cfg: RunnerConfig) -> None:
    problems = (_check_files(plan, files) + _check_mode(plan, files, cfg) + _check_flags(plan, cfg)
                + _check_fields(plan, spec) + _check_patterns(plan))
    if problems:
        raise HarnessFailure("Plan de arnés inválido:\n- " + "\n- ".join(problems))


def _check_files(plan: HarnessPlan, files: list[SourceFile]) -> list[str]:
    legacy = {_norm(f.path) for f in files}
    known = legacy | {_norm(p) for p in plan.files}
    problems = []
    if clash := [p for p in plan.files if _norm(p) in legacy]:
        problems.append(f"el arnés no puede sobrescribir archivos legacy: {clash}")
    if len(plan.files) > MAX_HARNESS_FILES or sum(len(c) for c in plan.files.values()) > MAX_HARNESS_CHARS:
        problems.append(f"el arnés debe ser mínimo (máx. {MAX_HARNESS_FILES} archivos y {MAX_HARNESS_CHARS} caracteres)")
    if _norm(plan.entry) not in known:
        problems.append(f"entry '{plan.entry}' no existe")
    if missing := [p for p in plan.compile if _norm(p) not in known]:
        problems.append(f"archivos de compile inexistentes: {missing}")
    return problems


def _check_mode(plan: HarnessPlan, files: list[SourceFile], cfg: RunnerConfig) -> list[str]:
    if plan.mode == "driver":
        return [] if _uses_legacy(plan, files, cfg) else [
            "el arnés debe usar el código legacy (inclúyelo en compile o refiérelo por su nombre)"]
    problems = []
    if plan.files or _norm(plan.entry) not in {_norm(f.path) for f in files}:
        problems.append("en modo direct no hay archivos de arnés y entry debe ser un archivo legacy")
    if not any(o.pattern for o in plan.outputs) and not plan.errors:
        problems.append("en modo direct cada salida necesita 'pattern'")
    return problems


def _check_flags(plan: HarnessPlan, cfg: RunnerConfig) -> list[str]:
    bad = [f for f in plan.flags if not any(re.fullmatch(p, f) for p in cfg.allowed_flags)]
    return [f"flags no permitidos: {bad} (permitidos: {cfg.allowed_flags or 'ninguno'})"] if bad else []


def _check_fields(plan: HarnessPlan, spec: Spec) -> list[str]:
    inputs = {f.name for f in spec.io.inputs}
    outputs = {f.name for f in spec.io.outputs}
    problems = []
    if bad := [f.name for f in plan.inputs if f.name not in inputs]:
        problems.append(f"entradas desconocidas: {bad}; válidas: {sorted(inputs)}")
    if bad := [f.name for f in plan.outputs if f.name not in outputs]:
        problems.append(f"salidas desconocidas: {bad}; válidas: {sorted(outputs)}")
    return problems


def _check_patterns(plan: HarnessPlan) -> list[str]:
    problems = []
    for p in [o.pattern for o in plan.outputs if o.pattern] + [e.pattern for e in plan.errors]:
        try:
            re.compile(p)
        except re.error as exc:
            problems.append(f"regex inválida {p!r}: {exc}")
    return problems


def _uses_legacy(plan: HarnessPlan, files: list[SourceFile], cfg: RunnerConfig) -> bool:
    """Heurística determinista: el arnés compila un archivo legacy o lo referencia por su nombre.
    Las líneas del protocolo (@@campo=) no cuentan, para que un nombre de campo no la engañe."""
    legacy = {_norm(f.path) for f in files}
    if cfg.compile_extensions:
        compiled = plan.compile or [f.path for f in files if Path(f.path).suffix.lower() in cfg.compile_extensions]
        return any(_norm(p) in legacy for p in compiled)
    text = re.sub(r"@@\w+\s*=?", " ", "\n".join(plan.files.values())).lower()
    for f in files:
        name, stem = Path(f.path).name.lower(), Path(f.path).stem.lower()
        if name in text or re.search(rf"\b{re.escape(stem)}\b", text):
            return True
    return False


# ---------------------------------------------------------------- comandos
def _compile_list(plan: HarnessPlan, files: list[SourceFile], cfg: RunnerConfig) -> list[str]:
    if plan.compile:
        chosen = list(plan.compile)
    else:
        chosen = [f.path for f in files if Path(f.path).suffix.lower() in cfg.compile_extensions]
        chosen += [p for p in plan.files if Path(p).suffix.lower() in cfg.compile_extensions]
    entry = next((c for c in chosen if _norm(c) == _norm(plan.entry)), plan.entry)
    return [entry] + [c for c in dict.fromkeys(chosen) if _norm(c) != _norm(plan.entry)]


def expand(template: list[str], *, plan: HarnessPlan, files: list[SourceFile], cfg: RunnerConfig) -> list[str]:
    compile_list = _compile_list(plan, files, cfg)
    dirs = sorted({str(PurePosixPath(f.path.replace("\\", "/")).parent) for f in files} | {"."})
    includes = [a.replace("{dir}", d) for d in dirs for a in cfg.include_args]
    entry = PurePosixPath(plan.entry.replace("\\", "/"))
    values = {"{flags}": list(plan.flags), "{others}": compile_list[1:], "{all}": compile_list,
              "{includes}": includes}
    out: list[str] = []
    for arg in template:
        if arg in values:
            out.extend(values[arg])
        else:
            out.append(arg.replace("{entry}", str(entry)).replace("{entry_stem}", entry.stem))
    return out


# ---------------------------------------------------------------- prompt
HARNESS_SYSTEM = f"""{COMMON}
Eres el agente de Caracterización. Tu trabajo NO es migrar: es lograr que el programa legacy se EJECUTE tal
cual está para capturar su comportamiento real (golden master). Escribes un arnés mínimo en el MISMO
lenguaje del legacy, o indicas cómo ejecutar el legacy directamente.

Reglas obligatorias:
- NUNCA modifiques ni copies la lógica de negocio del legacy dentro del arnés. El arnés solo: lee las
  entradas, invoca el código legacy existente y escribe las salidas. Si reimplementas lógica, la prueba de
  equivalencia queda invalidada.
- No sobrescribas archivos legacy; tus archivos tienen nombres nuevos (prefijo agentcs_).
- Entradas: la plataforma envía por stdin UNA línea por campo, en el orden de "inputs". Formato "plain":
  el valor tal cual (decimales con punto, p. ej. 1234.50). Formato "implied": solo dígitos con la escala
  implícita del tipo y relleno de ceros hasta "width" (útil para campos numéricos sin punto decimal).
- Modo "driver": tu arnés imprime en stdout, una por línea:
    @@<campo>=<valor>         por cada campo de salida (nombres EXACTOS de io.outputs)
    @@ROW                     antes de cada fila si output_is_list es true
    @@ERROR=<código>|<mensaje> si el legacy señala un error de negocio (códigos de io.errors)
  Imprime los decimales con punto decimal y todos sus dígitos; si tu lenguaje solo puede imprimir dígitos
  sin punto, declara ese campo con format "implied". Otras líneas de salida se ignoran.
- Modo "direct" (sin archivos de arnés): solo si el legacy YA lee sus entradas de stdin; declara para cada
  salida una regex "pattern" con UN grupo de captura sobre stdout, y en "errors" regex -> código.
- "flags": solo de la lista permitida del lenguaje. "compile": archivos a compilar (vacío = todos).
Responde SOLO con JSON:
{{"mode": "driver|direct", "entry": "<archivo principal>", "files": {{"<ruta>": "<contenido>"}},
  "compile": [], "flags": [], "inputs": [{{"name": "...", "format": "plain|implied", "width": null}}],
  "outputs": [{{"name": "...", "format": "plain|implied", "pattern": null}}],
  "errors": [{{"pattern": "...", "code": "..."}}], "notes": "<cómo conectaste el legacy>"}}"""


def _prompt(spec: Spec, files: list[SourceFile], cases: list[Case], cfg: RunnerConfig, pack_name: str,
            feedback: str | None) -> str:
    code = numbered(files)
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS] + "\n... (código truncado por tamaño)"
    io = spec.io.model_dump(mode="json")
    sample = [c.input for c in cases[:3]]
    parts = [f"Lenguaje legacy: {pack_name}.",
             f"Cómo se compila: {' '.join(cfg.build) or '(interpretado)'} · cómo se ejecuta: {' '.join(cfg.run)}",
             f"Flags permitidos (regex): {cfg.allowed_flags or 'ninguno'}",
             f"Indicaciones del lenguaje:\n{cfg.harness_hint}" if cfg.harness_hint else "",
             f"Contrato de E/S aprobado:\n{json.dumps(io, ensure_ascii=False)}",
             f"Ejemplos de entradas:\n{json.dumps(sample, ensure_ascii=False)}",
             f"Código legacy (numerado):\n{code}"]
    if feedback:
        parts.append(f"Tu arnés anterior falló. Corrígelo:\n{feedback}")
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------- runner
@dataclass
class GenericLegacyRunner:
    """Implementa LegacyRunner para cualquier lenguaje declarado en pack.yaml."""
    pack_id: str
    pack_name: str
    config: RunnerConfig
    llm: LLMClient | None = None
    files: list[SourceFile] = field(default_factory=list)
    plan: HarnessPlan | None = None
    attempts: int = 0

    def bind(self, llm: LLMClient) -> GenericLegacyRunner:
        return replace(self, llm=llm, files=[], plan=None, attempts=0)

    def missing_tools(self) -> list[str]:
        return [t for t in self.config.tools if resolve(t) is None]

    def build(self, files: list[SourceFile], workdir: Path) -> BuildResult:
        """Verifica la cadena de herramientas. La compilación real ocurre en run(), junto con el arnés."""
        self.files = list(files)
        if missing := self.missing_tools():
            return BuildResult(ok=False, log=f"Faltan herramientas para ejecutar {self.pack_name}: {', '.join(missing)}")
        return BuildResult(ok=True, log="Herramientas disponibles")

    def run(self, spec: Spec, cases: list[Case], workdir: Path) -> list[CaseOutput]:
        if self.llm is None:
            raise LLMError("HARNESS_NO_LLM", "No hay LLM para escribir el arnés del legacy.",
                           "Configura ANTHROPIC_API_KEY o usa pares E/S (nivel B).")
        feedback: str | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.attempts = attempt
            try:
                plan = complete_json(self.llm, HARNESS_SYSTEM,
                                     _prompt(spec, self.files, cases, self.config, self.pack_name, feedback),
                                     HarnessPlan, agent="legacy_harness", phase=Phase.VERIFICACION)
                validate_plan(plan, self.files, spec, self.config)
                outputs = self._execute(plan, spec, cases, workdir / f"harness-{attempt:02d}")
                self.plan = plan
                return outputs
            except HarnessFailure as exc:
                feedback = str(exc)[-4000:]
        raise LLMError("LEGACY_HARNESS_FAILED",
                       f"No se logró ejecutar el legacy tras {MAX_ATTEMPTS} intento(s) de arnés.",
                       "Revisa dependencias del legacy (copybooks, units, librerías) o provee pares E/S (nivel B).")

    def _execute(self, plan: HarnessPlan, spec: Spec, cases: list[Case], project: Path) -> list[CaseOutput]:
        try:
            write_files(project, {f.path: f.content for f in self.files})
            write_files(project, plan.files)
        except SandboxError as exc:
            raise HarnessFailure(f"ruta inválida: {exc}") from exc
        if self.config.build:
            build = run_cmd(expand(self.config.build, plan=plan, files=self.files, cfg=self.config), project)
            if not build.ok:
                raise HarnessFailure(f"No compila. Log:\n{build.tail()}")
        types = _field_types(spec.io.inputs)
        command = expand(self.config.run, plan=plan, files=self.files, cfg=self.config)
        parser = parse_driver if plan.mode == "driver" else parse_direct
        outputs, failures = [], []
        for case in cases:
            result = run_cmd(command, project, timeout=CASE_TIMEOUT, stdin=render_stdin(plan, case, types))
            try:
                if result.timed_out:
                    raise HarnessFailure("tiempo agotado (¿espera más líneas de stdin de las enviadas?)")
                outputs.append(to_case_output(case.id, parser(result.stdout, spec, plan), spec))
            except HarnessFailure as exc:
                failures.append(f"caso {case.id} entrada {case.input}: {exc}\n  stdout: {result.stdout[-600:]!r}"
                                f"\n  stderr: {result.stderr[-600:]!r}")
        if failures:
            raise HarnessFailure(f"{len(failures)} de {len(cases)} caso(s) sin salida válida:\n" + "\n".join(failures[:4]))
        return outputs

    def harness_code(self) -> str | None:
        if self.plan is None:
            return None
        return json.dumps(self.plan.model_dump(), ensure_ascii=False, indent=2)
