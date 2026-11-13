"""Runner de ORIGEN para PL/SQL: ejecuta el script legacy en Oracle real (oráculo nivel A).

Flujo por intento (todo determinista salvo el bloque anónimo que escribe el LLM):
  1. Esquema temporal nuevo (usuario AGENTCS_<hex>) con permisos mínimos.
  2. setup_sql opcional del LLM: SOLO `CREATE TABLE`/`CREATE SEQUENCE` para dependencias ausentes.
  3. Script legacy TAL CUAL (dividido como SQL*Plus: `/` cierra bloques PL/SQL, `;` cierra SQL). Lo único
     que se transforma es el prefijo de esquema (`BANCO.CUENTAS` -> `CUENTAS`), y se declara.
  4. Verificación de USER_ERRORS: si un objeto no compila, vuelve como retroalimentación.
  5. Por caso: DELETE de las tablas conocidas, INSERT de las filas de input["_tablas"], bloque anónimo con
     binds (:<entrada>) que invoca la rutina legacy e imprime `@@campo=valor` por DBMS_OUTPUT, ROLLBACK.
  6. Al final se elimina el esquema.

Credenciales: ORACLE_DSN, ORACLE_ADMIN_USER (system) y ORACLE_PASSWORD vienen del entorno; nunca llegan al
LLM ni a los logs. Sin Oracle disponible, build() falla rápido y el oráculo baja a nivel B/C declarándolo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from copilot.contracts import BuildResult, Case, CaseOutput, NeutralType, Phase, SourceFile, Spec, TypeKind
from copilot.engine.llm import LLMClient, LLMError, complete_json
from copilot.engine.prompts import COMMON, numbered

from .sql_scripts import TEST_DATA, file_roles, install_order
from .source_runner import HarnessFailure, HarnessPlan, OutputField, parse_driver, to_case_output

TABLES_KEY = "_tablas"
MAX_ATTEMPTS = int(os.environ.get("AGENTCS_HARNESS_ATTEMPTS", "3"))
CALL_TIMEOUT_MS = int(os.environ.get("AGENTCS_ORACLE_CALL_TIMEOUT_MS", "20000"))
MAX_BLOCK_CHARS = 12_000
MAX_CODE_CHARS = 60_000

_SQLPLUS = re.compile(r"^\s*(SET|PROMPT|SPOOL|SHOW|SHO|EXIT|QUIT|WHENEVER|DEFINE|UNDEFINE|COLUMN|COL|TTITLE|"
                      r"BTITLE|REM|REMARK|CONNECT|CONN|DESC|DESCRIBE|CLEAR|BREAK|COMPUTE|PAUSE|@@?)\b", re.I)
_PLSQL_START = re.compile(r"^\s*(DECLARE|BEGIN|CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?"
                          r"(FUNCTION|PROCEDURE|PACKAGE|TRIGGER|TYPE|LIBRARY)\b)", re.I)
_EXEC = re.compile(r"^\s*EXEC(UTE)?\s+(.+?);?\s*$", re.I)
_SCHEMA_DECL = re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?(?:GLOBAL\s+TEMPORARY\s+)?"
                          r"(?:TABLE|VIEW|SEQUENCE|FUNCTION|PROCEDURE|PACKAGE(?:\s+BODY)?|TRIGGER|TYPE(?:\s+BODY)?|INDEX)"
                          r"\s+\"?(\w+)\"?\s*\.", re.I)
_ROUTINE = re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?"
                      r"(?:FUNCTION|PROCEDURE|PACKAGE(?:\s+BODY)?)\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?", re.I)
_FORBIDDEN_IN_BLOCK = re.compile(r"\b(CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|EXECUTE\s+IMMEDIATE|DBMS_SQL|"
                                 r"INSERT|UPDATE|DELETE|MERGE)\b", re.I)
_ALLOWED_SETUP = re.compile(r"^\s*CREATE\s+(TABLE|SEQUENCE)\s+\w+", re.I)
_IGNORABLE = ("ORA-00942", "ORA-01418", "ORA-02289", "ORA-04043", "ORA-04080", "ORA-01434", "ORA-00955")


# ---------------------------------------------------------------- script SQL*Plus -> sentencias
def strip_schema_prefixes(script: str) -> tuple[str, list[str]]:
    """BANCO.CUENTAS -> CUENTAS para los esquemas que el propio script declara (transformación mecánica)."""
    schemas = sorted({m.upper() for m in _SCHEMA_DECL.findall(script)} - {"SYS", "PUBLIC"})
    for schema in schemas:
        script = re.sub(rf"\"?\b{schema}\b\"?\s*\.\s*(?=\"?\w)", "", script, flags=re.I)
    return script, schemas


def _between(line: str, in_comment: bool) -> tuple[bool, bool]:
    """Fuera de una sentencia: ¿se descarta la línea? (comentarios, líneas vacías, comandos SQL*Plus)."""
    stripped = line.strip()
    if in_comment:
        return True, "*/" not in stripped
    if stripped.startswith("/*"):
        return True, "*/" not in stripped[2:]
    return (not stripped or stripped.startswith("--") or bool(_SQLPLUS.match(line))), False


def split_script(script: str) -> list[str]:
    """Divide como SQL*Plus: `/` cierra bloques PL/SQL, `;` cierra SQL. Los comentarios de bloque y de
    línea ENTRE sentencias se descartan, para que no oculten comandos SQL*Plus ni el inicio de un bloque."""
    statements: list[str] = []
    buf: list[str] = []
    plsql = in_comment = False
    for line in script.splitlines():
        stripped = line.strip()
        if not buf:
            skip, in_comment = _between(line, in_comment)
            if skip:
                continue
            if m := _EXEC.match(line):
                statements.append(f"BEGIN {m.group(2).rstrip(';')}; END;")
                continue
            plsql = bool(_PLSQL_START.match(line))
        if stripped == "/":
            if buf:
                statements.append(_finish(buf, plsql))
            buf, plsql = [], False
            continue
        buf.append(line)
        if not plsql and stripped.endswith(";"):
            statements.append(_finish(buf, plsql))
            buf = []
    if buf and "".join(buf).strip():
        statements.append(_finish(buf, plsql))
    return [s for s in statements if s]


def _finish(buf: list[str], plsql: bool) -> str:
    text = "\n".join(buf).strip()
    return text if plsql else text.rstrip(";").strip()


def routine_names(files: list[SourceFile]) -> set[str]:
    return {m.upper() for f in files for m in _ROUTINE.findall(f.content)}


# ---------------------------------------------------------------- plan del LLM
class OraclePlan(BaseModel):
    block: str = Field(description="Bloque anónimo PL/SQL (DECLARE/BEGIN ... END;) que invoca la rutina legacy")
    setup_sql: list[str] = []          # solo CREATE TABLE / CREATE SEQUENCE de dependencias ausentes
    outputs: list[OutputField] = []    # formato de cada salida (plain | implied)
    notes: str = ""


def validate_plan(plan: OraclePlan, files: list[SourceFile], spec: Spec) -> None:
    problems = []
    block = plan.block.strip()
    if not re.match(r"^(DECLARE|BEGIN)\b", block, re.I) or not block.rstrip().endswith(";"):
        problems.append("block debe ser un bloque anónimo DECLARE/BEGIN ... END;")
    if len(block) > MAX_BLOCK_CHARS:
        problems.append(f"block debe ser mínimo (máx. {MAX_BLOCK_CHARS} caracteres)")
    if m := _FORBIDDEN_IN_BLOCK.search(_strip_comments_and_strings(block)):
        problems.append(f"block no puede usar {m.group(1).upper()}: la plataforma carga los datos y el legacy hace el resto")
    names = routine_names(files)
    if names and not any(re.search(rf"\b{n}\b", block, re.I) for n in names):
        problems.append(f"block debe invocar alguna rutina legacy: {sorted(names)}")
    if bad := [s[:60] for s in plan.setup_sql if not _ALLOWED_SETUP.match(s)]:
        problems.append(f"setup_sql solo admite CREATE TABLE / CREATE SEQUENCE: {bad}")
    outputs = {f.name for f in spec.io.outputs}
    if bad := [o.name for o in plan.outputs if o.name not in outputs]:
        problems.append(f"salidas desconocidas: {bad}; válidas: {sorted(outputs)}")
    if problems:
        raise HarnessFailure("Plan inválido:\n- " + "\n- ".join(problems))


def _strip_comments_and_strings(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def block_binds(block: str) -> list[str]:
    """Nombres de bind (:nombre) usados en el bloque, sin duplicados y sin literales."""
    found = re.findall(r"(?<![:\w]):([A-Za-z_]\w*)", _strip_comments_and_strings(block))
    return list(dict.fromkeys(found))


# ---------------------------------------------------------------- conversión de valores
def to_db(value: Any, t: NeutralType | None) -> Any:
    if value is None or t is None:
        return value
    try:
        if t.kind in (TypeKind.DECIMAL, TypeKind.FLOAT):
            return Decimal(str(value))
        if t.kind == TypeKind.INTEGER:
            return int(Decimal(str(value)))
        if t.kind == TypeKind.DATE and isinstance(value, str):
            return dt.date.fromisoformat(value[:10])
        if t.kind == TypeKind.DATETIME and isinstance(value, str):
            return dt.datetime.fromisoformat(value)
        if t.kind == TypeKind.BOOLEAN:
            return 1 if value in (True, 1, "1", "true", "S", "Y") else 0
    except (InvalidOperation, ValueError):
        return value      # inválido a propósito: que el legacy decida
    return value


def table_types(spec: Spec) -> dict[str, dict[str, NeutralType]]:
    return {e.name.upper(): {f.name.upper(): f.type for f in e.fields} for e in spec.entities if e.kind == "tabla"}


# ---------------------------------------------------------------- acceso a Oracle (aislado para pruebas)
class OracleSession(Protocol):
    def execute(self, sql: str, binds: dict[str, Any] | None = None) -> None: ...
    def query(self, sql: str, binds: dict[str, Any] | None = None) -> list[tuple]: ...
    def run_block(self, block: str, binds: dict[str, Any]) -> str: ...      # devuelve DBMS_OUTPUT
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class FixtureError(HarnessFailure):
    """Los datos de prueba del caso no caben en el esquema real (CHECK, tipo, tabla inexistente)."""


class OracleError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class Database(Protocol):
    def admin_check(self) -> None: ...
    def create_schema(self) -> tuple[str, OracleSession]: ...
    def drop_schema(self, name: str) -> None: ...


@dataclass
class OracledbDatabase:
    """Implementación real con python-oracledb (modo thin: sin cliente Oracle instalado)."""
    dsn: str
    admin_user: str
    admin_password: str = field(repr=False)

    @classmethod
    def from_env(cls) -> OracledbDatabase | None:
        dsn, pwd = os.environ.get("ORACLE_DSN"), os.environ.get("ORACLE_PASSWORD")
        if not dsn or not pwd:
            return None
        return cls(dsn, os.environ.get("ORACLE_ADMIN_USER", "system"), pwd)

    def _connect(self, user: str, password: str):
        import oracledb
        conn = oracledb.connect(user=user, password=password, dsn=self.dsn, tcp_connect_timeout=5)
        conn.call_timeout = CALL_TIMEOUT_MS
        return conn

    def admin_check(self) -> None:
        with self._connect(self.admin_user, self.admin_password) as conn:
            conn.cursor().execute("SELECT 1 FROM dual")

    def create_schema(self) -> tuple[str, OracleSession]:
        name, pwd = f"AGENTCS_{secrets.token_hex(4).upper()}", "P" + secrets.token_hex(12)
        with self._connect(self.admin_user, self.admin_password) as conn:
            cur = conn.cursor()
            cur.execute(f'CREATE USER {name} IDENTIFIED BY "{pwd}" QUOTA UNLIMITED ON USERS')
            cur.execute(f"GRANT CREATE SESSION, CREATE TABLE, CREATE PROCEDURE, CREATE SEQUENCE, CREATE VIEW, "
                        f"CREATE TRIGGER, CREATE TYPE, CREATE SYNONYM TO {name}")
        return name, _OracledbSession(self._connect(name, pwd))

    def drop_schema(self, name: str) -> None:
        try:
            with self._connect(self.admin_user, self.admin_password) as conn:
                conn.cursor().execute(f"DROP USER {name} CASCADE")
        except Exception:   # noqa: BLE001 — limpieza best-effort, nunca rompe la verificación
            pass


class _OracledbSession:
    def __init__(self, conn):
        self.conn = conn
        cur = conn.cursor()
        cur.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'")
        cur.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD'")

    def _wrap(self, fn, *args):
        import oracledb
        try:
            return fn(*args)
        except oracledb.DatabaseError as exc:
            err = exc.args[0]
            raise OracleError(getattr(err, "code", 0), getattr(err, "message", str(exc))) from None

    def execute(self, sql, binds=None):
        self._wrap(self.conn.cursor().execute, sql, binds or {})

    def query(self, sql, binds=None):
        cur = self.conn.cursor()
        self._wrap(cur.execute, sql, binds or {})
        return cur.fetchall()

    def run_block(self, block, binds):
        cur = self.conn.cursor()
        cur.callproc("dbms_output.enable", [None])
        error = None
        try:
            self._wrap(cur.execute, block, binds)
        except OracleError as exc:
            error = exc
        lines_var = cur.arrayvar(str, 1000, 32767)
        count_var = cur.var(int)
        out = []
        while True:
            count_var.setvalue(0, 1000)
            cur.callproc("dbms_output.get_lines", (lines_var, count_var))
            n = count_var.getvalue()
            out += [ln or "" for ln in lines_var.getvalue()[:n]]
            if n < 1000:
                break
        if error is not None:
            error.output = "\n".join(out)
            raise error
        return "\n".join(out)

    def rollback(self):
        self.conn.rollback()

    def close(self):
        try:
            self.conn.close()
        except Exception:   # noqa: BLE001
            pass


# ---------------------------------------------------------------- prompt del arnés
HARNESS_SYSTEM = f"""{COMMON}
Eres el agente de Caracterización para PL/SQL. NO migras: logras que el PL/SQL legacy se EJECUTE tal cual en
Oracle para capturar su comportamiento real (golden master). La plataforma ya:
- creó un esquema vacío y ejecutó el script legacy completo (tablas, paquetes, funciones, triggers);
- antes de cada caso borra las tablas e inserta las filas de input["_tablas"] (estado inicial de la BD);
- ejecuta TU bloque anónimo con un bind por cada entrada de io.inputs, con el MISMO nombre (:monto, :canal...),
  ya convertido a NUMBER, VARCHAR2 o DATE; y hace ROLLBACK al final.
Tu bloque:
- invoca la rutina de entrada legacy (función, procedimiento o paquete.rutina) con esos binds, SIN reimplementar
  ni copiar su lógica. Prohibido INSERT/UPDATE/DELETE/MERGE/DDL/EXECUTE IMMEDIATE: los datos los carga la
  plataforma y el resto lo hace el legacy. Puedes usar SELECT ... INTO para LEER el estado final de las tablas.
- imprime cada salida con DBMS_OUTPUT.PUT_LINE('@@<campo>=' || TO_CHAR(valor)) usando los nombres EXACTOS de
  io.outputs (fechas con TO_CHAR(f,'YYYY-MM-DD')). Si output_is_list (p. ej. un proceso por lotes), después de
  invocar la rutina recorre los resultados con FOR r IN (SELECT ... ORDER BY <clave>) LOOP e imprime '@@ROW'
  y luego cada campo de esa fila. Está bien que el legacy haga COMMIT: la plataforma restaura la base por caso.
- errores de negocio: captura la excepción e imprime '@@ERROR=<código de io.errors>|' || SQLERRM. Si el
  legacy usa RAISE_APPLICATION_ERROR, mapea SQLCODE al código del contrato.
- setup_sql: SOLO si el script referencia tablas o secuencias que NO crea, decláralas con CREATE TABLE /
  CREATE SEQUENCE mínimos (sin datos ni lógica).
Responde SOLO con JSON: {{"block": "DECLARE ... BEGIN ... END;", "setup_sql": [],
 "outputs": [{{"name": "...", "format": "plain"}}], "notes": "<cómo conectaste el legacy>"}}"""


def _prompt(spec: Spec, files: list[SourceFile], cases: list[Case], feedback: str | None) -> str:
    roles = file_roles(files)
    shown = [f for f in files if roles.get(f.path) != TEST_DATA]
    code = numbered(shown)
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS] + "\n... (código truncado por tamaño)"
    payload = {"io": spec.io.model_dump(mode="json"),
               "tablas": {t: {c: ty.describe() for c, ty in cols.items()} for t, cols in table_types(spec).items()}}
    sample = [{k: v for k, v in c.input.items() if k != TABLES_KEY} for c in cases[:3]]
    parts = [f"Contrato aprobado:\n{json.dumps(payload, ensure_ascii=False)}",
             f"Papel de cada archivo: {json.dumps(roles, ensure_ascii=False)} (los datos de prueba NO se muestran: "
             "la plataforma los carga como input._tablas antes de cada caso).",
             f"Ejemplos de parámetros de entrada (sin _tablas):\n{json.dumps(sample, ensure_ascii=False)[:3000]}",
             f"Script(s) legacy (numerados):\n{code}"]
    if feedback:
        parts.append(f"Tu intento anterior falló. Corrígelo:\n{feedback}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- runner
@dataclass
class OracleLegacyRunner:
    pack_id: str
    pack_name: str
    llm: LLMClient | None = None
    database: Database | None = None
    files: list[SourceFile] = field(default_factory=list)
    plan: OraclePlan | None = None
    attempts: int = 0
    notes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def bind(self, llm: LLMClient | None) -> OracleLegacyRunner:
        return replace(self, llm=llm, files=[], plan=None, attempts=0, notes=[], skipped=[],
                       database=self.database or OracledbDatabase.from_env())

    def missing_tools(self) -> list[str]:
        if self.database is not None or OracledbDatabase.from_env() is not None:
            return []
        return ["Oracle (ORACLE_DSN y ORACLE_PASSWORD; docker compose --profile oracle)"]

    def build(self, files: list[SourceFile], workdir: Path) -> BuildResult:
        self.files = list(files)
        if self.database is None:
            return BuildResult(ok=False, log="Oracle no configurado (usa docker compose --profile oracle).")
        try:
            self.database.admin_check()
        except Exception as exc:   # noqa: BLE001 — cualquier fallo de conexión = sin nivel A
            return BuildResult(ok=False, log=f"Oracle no disponible en este momento ({type(exc).__name__}).")
        return BuildResult(ok=True, log="Oracle disponible")

    def run(self, spec: Spec, cases: list[Case], workdir: Path) -> list[CaseOutput]:
        if self.llm is None or self.database is None:
            raise LLMError("HARNESS_NO_LLM", "No hay LLM u Oracle para ejecutar el PL/SQL legacy.",
                           "Configura ANTHROPIC_API_KEY y el perfil oracle, o usa pares E/S (nivel B).")
        feedback: str | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.attempts = attempt
            try:
                plan = complete_json(self.llm, HARNESS_SYSTEM, _prompt(spec, self.files, cases, feedback),
                                     OraclePlan, agent="legacy_harness", phase=Phase.VERIFICACION)
                validate_plan(plan, self.files, spec)
                outputs = self._execute(plan, spec, cases)
                self.plan = plan
                return outputs
            except HarnessFailure as exc:
                feedback = str(exc)[-4000:]
        raise LLMError("LEGACY_HARNESS_FAILED",
                       f"No se logró ejecutar el PL/SQL en Oracle tras {MAX_ATTEMPTS} intento(s).",
                       "Revisa dependencias del script (otros esquemas, db links) o provee pares E/S (nivel B).")

    # ------------------------------------------------------------ un intento completo
    def _execute(self, plan: OraclePlan, spec: Spec, cases: list[Case]) -> list[CaseOutput]:
        schema, session = self.database.create_schema()
        try:
            tables, seeded = self._install(session, plan, spec)
            return self._run_cases(session, plan, spec, cases, tables, seeded)
        finally:
            session.close()
            self.database.drop_schema(schema)

    def _install(self, session: OracleSession, plan: OraclePlan, spec: Spec) -> tuple[list[str], set[str]]:
        """Instala código y configuración (no datos de prueba ni scripts de ejecución) en orden.
        Devuelve las tablas del esquema y las que quedaron con filas de configuración (semilla)."""
        for ddl in plan.setup_sql:
            self._try(session, ddl.strip().rstrip(";"), "setup_sql")
        warnings, self.notes = [], []
        for f in install_order(self.files):
            script, schemas = strip_schema_prefixes(f.content)
            if schemas:
                self.notes.append(f"{f.path}: se quitó el prefijo de esquema {', '.join(schemas)}")
            for stmt in split_script(script):
                warnings += self._try(session, stmt, f.path, fatal=False)
        session.execute("COMMIT")
        invalid = session.query("SELECT name, type, line, text FROM user_errors WHERE attribute = 'ERROR' "
                                "ORDER BY name, sequence")
        if invalid:
            detail = "\n".join(f"{n} ({t}) línea {ln}: {txt.strip()}" for n, t, ln, txt in invalid[:15])
            raise HarnessFailure("El PL/SQL legacy no compiló en Oracle (si faltan tablas o secuencias externas, "
                                 f"decláralas en setup_sql):\n{detail}\nOtros avisos:\n" + "\n".join(warnings[:10]))
        tables = [r[0] for r in session.query("SELECT table_name FROM user_tables")]
        seeded = {t for t in tables if session.query(f"SELECT COUNT(*) FROM {t}")[0][0] > 0}
        for table, constraint in session.query("SELECT table_name, constraint_name FROM user_constraints "
                                               "WHERE constraint_type = 'R'"):
            self._try(session, f"ALTER TABLE {table} DISABLE CONSTRAINT {constraint}", "fixtures", fatal=False)
        return tables, seeded

    @staticmethod
    def _try(session: OracleSession, sql: str, origin: str, fatal: bool = True) -> list[str]:
        try:
            session.execute(sql)
        except OracleError as exc:
            msg = f"{origin}: ORA-{abs(exc.code):05d} {exc.message.splitlines()[0][:200]} en «{sql[:80]}»"
            if any(code in exc.message for code in _IGNORABLE) or not fatal:
                return [msg]
            raise HarnessFailure(msg) from None
        return []

    def _run_cases(self, session: OracleSession, plan: OraclePlan, spec: Spec, cases: list[Case],
                   tables: list[str], seeded: set[str]) -> list[CaseOutput]:
        in_types = {f.name.lower(): f.type for f in spec.io.inputs}
        col_types = table_types(spec)
        binds_used = block_binds(plan.block)
        driver = HarnessPlan(mode="driver", entry="-", inputs=[], outputs=plan.outputs)
        outputs, failures, self.skipped = [], [], []
        for case in cases:
            try:
                try:
                    self._load_fixtures(session, case, tables, seeded, col_types)
                except FixtureError as exc:
                    self.skipped.append(f"{case.id}: {exc}")
                    continue
                binds = {b: to_db(_get(case.input, b), in_types.get(b.lower())) for b in binds_used}
                outputs.append(self._call(session, plan.block, binds, case.id, spec, driver))
            except HarnessFailure as exc:
                failures.append(f"caso {case.id} entrada {json.dumps(case.input, ensure_ascii=False)[:300]}: {exc}")
            finally:
                session.rollback()
        if failures:
            raise HarnessFailure(f"{len(failures)} de {len(cases)} caso(s) sin salida válida:\n" + "\n".join(failures[:4]))
        if not outputs:
            raise HarnessFailure("Ningún caso pudo cargar sus datos de prueba:\n" + "\n".join(self.skipped[:4]))
        return outputs

    @staticmethod
    def _call(session: OracleSession, block: str, binds: dict[str, Any], case_id: str, spec: Spec,
              driver: HarnessPlan) -> CaseOutput:
        try:
            text = session.run_block(block, binds)
        except OracleError as exc:
            # Excepción no capturada por el bloque: es el comportamiento del legacy (p. ej. RAISE_APPLICATION_ERROR)
            output = getattr(exc, "output", "")
            if "@@" in output:
                return to_case_output(case_id, parse_driver(output, spec, driver), spec)
            return to_case_output(case_id, {"error": (f"ORA-{abs(exc.code):05d}", exc.message)}, spec)
        return to_case_output(case_id, parse_driver(text, spec, driver), spec)

    def _load_fixtures(self, session: OracleSession, case: Case, tables: list[str], seeded: set[str],
                       col_types: dict[str, dict[str, NeutralType]]) -> None:
        """Deja la base en el estado del caso: las tablas del caso se reemplazan por sus filas; las tablas de
        configuración que el caso no menciona se conservan; el resto queda vacío."""
        data = {k.upper(): v for k, v in (case.input.get(TABLES_KEY) or {}).items()}
        present = {t.upper() for t in tables}
        if unknown := sorted(set(data) - present):
            raise FixtureError(f"tablas de _tablas inexistentes en el esquema: {unknown} (tablas: {sorted(present)})")
        for table in tables:
            if table.upper() in data or table.upper() not in seeded:
                self._try(session, f"DELETE FROM {table}", "fixtures")
        for table, rows in data.items():
            types = col_types.get(table, {})
            for row in rows:
                cols = list(row)
                sql = (f"INSERT INTO {table} ({', '.join(c.upper() for c in cols)}) "
                       f"VALUES ({', '.join(f':c{i}' for i in range(len(cols)))})")
                self._insert(session, sql, {f"c{i}": to_db(row[c], types.get(c.upper())) for i, c in enumerate(cols)})

    @staticmethod
    def _insert(session: OracleSession, sql: str, values: dict[str, Any]) -> None:
        try:
            session.execute(sql, values)
        except OracleError as exc:
            raise FixtureError(f"no se pudo cargar la fila de prueba: ORA-{abs(exc.code):05d} "
                                 f"{exc.message.splitlines()[0][:200]}") from None

    def harness_code(self) -> str | None:
        if self.plan is None:
            return None
        return json.dumps({**self.plan.model_dump(), "transformaciones": self.notes}, ensure_ascii=False, indent=2)


def _get(data: dict[str, Any], name: str) -> Any:
    lowered = {k.lower(): v for k, v in data.items()}
    return lowered.get(name.lower())
