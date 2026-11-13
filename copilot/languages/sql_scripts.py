"""Soporte determinista para scripts SQL/PL/SQL entregados como archivos sueltos.

Un sistema PL/SQL real llega como varios scripts con papeles distintos:
  codigo         DDL y objetos PL/SQL (tablas, secuencias, paquetes, funciones, triggers).
  configuracion  INSERTs de parametrización que forman parte del sistema (se instalan con el código).
  datos_prueba   INSERTs del escenario de prueba (no se instalan: son el estado inicial de los casos).
  ejecucion      Bloques anónimos / EXEC que invocan la rutina de entrada (indican cómo se ejecuta).

También convierte los INSERT de configuración y de prueba en filas `_tablas` tipadas, leyendo el orden y
el tipo de las columnas del DDL. Nada de esto usa el LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any

from copilot.contracts import SourceFile

CODE, CONFIG, TEST_DATA, EXECUTION = "codigo", "configuracion", "datos_prueba", "ejecucion"
ROLE_LABELS = {CODE: "Código", CONFIG: "Configuración del sistema", TEST_DATA: "Datos de prueba",
               EXECUTION: "Script de ejecución"}
_TEST_PATH = re.compile(r"(^|[/_\-.])(prueba|pruebas|test|tests|datos|data|fixture|fixtures|ejemplo|demo|evaluacion)"
                        r"([/_\-.]|$)", re.I)
_DML = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE|COMMIT|ROLLBACK|ALTER\s+SESSION|SAVEPOINT)\b", re.I)
_ANON = re.compile(r"^\s*(DECLARE|BEGIN)\b", re.I)
_DDL_TABLE = re.compile(r"^\s*CREATE\s+(GLOBAL\s+TEMPORARY\s+)?TABLE\b", re.I)


# ---------------------------------------------------------------- roles y orden
def _statements(content: str) -> list[str]:
    from .oracle_runner import split_script   # import diferido: evita ciclo
    return split_script(content)


def file_role(path: str, content: str) -> str:
    statements = [s for s in _statements(content) if s.strip()]
    if statements and all(_ANON.match(s) for s in statements):
        return EXECUTION
    if statements and all(_DML.match(s) for s in statements):
        return TEST_DATA if _TEST_PATH.search(PurePosixPath(path.replace("\\", "/")).as_posix()) else CONFIG
    return CODE


def file_roles(files: list[SourceFile]) -> dict[str, str]:
    return {f.path: file_role(f.path, f.content) for f in files}


def _natural(path: str) -> list[Any]:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path)]


def install_order(files: list[SourceFile]) -> list[SourceFile]:
    """Código y configuración en el orden de instalación: tablas, luego configuración, luego PL/SQL.
    Dentro de cada grupo se respeta la numeración de los archivos (01_, 02_...)."""
    roles = file_roles(files)

    def rank(f: SourceFile) -> int:
        if roles[f.path] == CONFIG:
            return 1
        statements = _statements(f.content)
        return 0 if statements and _DDL_TABLE.match(statements[0]) else 2

    chosen = [f for f in files if roles[f.path] in (CODE, CONFIG)]
    return sorted(chosen, key=lambda f: (rank(f), _natural(f.path)))


# ---------------------------------------------------------------- DDL -> columnas tipadas
@dataclass
class Column:
    name: str
    kind: str                  # number | text | date
    scale: int | None = None
    default: Any = None


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name.lower()), None)


_CREATE_TABLE = re.compile(r"CREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?\s*\((.*)\)",
                           re.I | re.S)
_CONSTRAINT = re.compile(r"^\s*(CONSTRAINT|PRIMARY|UNIQUE|CHECK|FOREIGN)\b", re.I)


def split_top_level(text: str, sep: str = ",") -> list[str]:
    parts, depth, buf, quoted = [], 0, [], False
    for ch in text:
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        if ch == sep and depth == 0 and not quoted:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _column(definition: str) -> Column | None:
    m = re.match(r"\"?(\w+)\"?\s+(\w+)\s*(\(([^)]*)\))?(.*)$", definition.strip(), re.S)
    if not m:
        return None
    name, typ, args, rest = m.group(1).lower(), m.group(2).upper(), m.group(4), m.group(5)
    if typ in ("NUMBER", "NUMERIC", "DECIMAL", "INTEGER", "INT", "SMALLINT", "FLOAT", "BINARY_DOUBLE"):
        scale = None
        if args and "," in args:
            scale = int(args.split(",")[1].strip() or 0)
        elif typ in ("INTEGER", "INT", "SMALLINT") or (args and args.strip().isdigit()):
            scale = 0
        kind = "number"
    elif typ in ("DATE", "TIMESTAMP"):
        kind, scale = "date", None
    else:
        kind, scale = "text", None
    default = None
    if d := re.search(r"\bDEFAULT\s+('(?:[^']|'')*'|-?\d+(?:\.\d+)?)", rest, re.I):
        default = _literal(d.group(1))
    return Column(name, kind, scale, default)


def parse_tables(files: list[SourceFile]) -> dict[str, Table]:
    tables: dict[str, Table] = {}
    for f in files:
        for stmt in _statements(f.content):
            body = re.sub(r"--[^\n]*", "", stmt)
            if not (m := _CREATE_TABLE.search(body)):
                continue
            table = Table(m.group(1).lower())
            for part in split_top_level(m.group(2)):
                if not _CONSTRAINT.match(part) and (col := _column(part)):
                    table.columns.append(col)
            tables[table.name] = table
    return tables


# ---------------------------------------------------------------- INSERT -> filas
_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(?:\"?\w+\"?\.)?\"?(\w+)\"?\s*(\(([^)]*)\))?\s*VALUES\s*\((.*)\)\s*$",
                     re.I | re.S)
_SKIP = object()


def _literal(token: str) -> Any:
    t = token.strip()
    if t.upper() == "NULL":
        return None
    if t.startswith("'") and t.endswith("'"):
        return t[1:-1].replace("''", "'")
    if m := re.fullmatch(r"(?:DATE|TIMESTAMP)\s*'([^']+)'", t, re.I):
        return m.group(1)[:10]
    if m := re.fullmatch(r"TO_DATE\s*\(\s*'([^']+)'\s*(?:,\s*'([^']+)'\s*)?\)", t, re.I):
        return _to_iso(m.group(1), m.group(2))
    try:
        return Decimal(t)
    except InvalidOperation:
        return _SKIP           # expresión no literal (SYSDATE, secuencias, funciones)


def _to_iso(value: str, fmt: str | None) -> str:
    fmt = (fmt or "YYYY-MM-DD").upper()
    if fmt.startswith("DD/MM/YYYY") or fmt.startswith("DD-MM-YYYY"):
        d, mth, y = re.split(r"[/-]", value[:10])
        return f"{y}-{mth}-{d}"
    return value[:10]


def _typed(value: Any, col: Column | None) -> Any:
    if value is None or col is None:
        return str(value) if isinstance(value, Decimal) else value
    if col.kind == "number":
        number = Decimal(str(value))
        if col.scale == 0:
            return int(number)
        if col.scale:
            return format(number.quantize(Decimal(10) ** -col.scale), "f")
        return format(number.normalize(), "f") if number == number.to_integral_value() else format(number, "f")
    return str(value) if not isinstance(value, str) else value


@dataclass
class Dataset:
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)   # sentencias que no se pudieron convertir


def parse_dataset(files: list[SourceFile], tables: dict[str, Table]) -> Dataset:
    data = Dataset()
    for f in files:
        for stmt in _statements(f.content):
            if not (m := _INSERT.match(re.sub(r"--[^\n]*", "", stmt))):
                continue
            name = m.group(1).lower()
            table = tables.get(name)
            values = [_literal(v) for v in split_top_level(m.group(4))]
            cols = ([c.strip().strip('"').lower() for c in m.group(3).split(",")] if m.group(3)
                    else [c.name for c in table.columns] if table else [])
            if not cols or len(cols) != len(values) or any(v is _SKIP for v in values):
                data.skipped.append(f"{f.path}: {stmt[:90]}")
                continue
            row = {c: _typed(v, table.column(c) if table else None) for c, v in zip(cols, values)}
            for col in (table.columns if table else []):
                if col.default is not None:   # solo DEFAULT literales; USER/SYSDATE los pone Oracle al insertar
                    row.setdefault(col.name, _typed(col.default, col))
            data.rows.setdefault(name, []).append(row)
    return data


def base_dataset(files: list[SourceFile]) -> Dataset:
    """Estado inicial de la base: configuración del sistema + datos de prueba, con tipos del DDL."""
    roles = file_roles(files)
    tables = parse_tables([f for f in files if roles[f.path] == CODE])
    ordered = sorted((f for f in files if roles[f.path] in (CONFIG, TEST_DATA)),
                     key=lambda f: (roles[f.path] != CONFIG, _natural(f.path)))
    data = parse_dataset(ordered, tables)
    for name in tables:                      # tablas sin filas también existen (vacías)
        data.rows.setdefault(name, [])
    return data


def execution_scripts(files: list[SourceFile]) -> list[SourceFile]:
    roles = file_roles(files)
    return [f for f in files if roles[f.path] == EXECUTION]
