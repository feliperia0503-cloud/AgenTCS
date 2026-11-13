"""Oráculo nivel A para PL/SQL con tablas.

- Pruebas de la plataforma con un Oracle simulado (siempre corren): división del script, prefijos de esquema,
  validación del bloque, carga de filas, binds, protocolo, errores ORA y autocorrección.
- Prueba de integración contra Oracle REAL: se activa sola si ORACLE_DSN/ORACLE_PASSWORD apuntan a una base
  disponible (docker compose --profile oracle). Valores calculados a mano en samples/plsql/pkg_cartera_mora.sql.
"""
import datetime as dt
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from copilot.contracts import (
    Case, DataField, Entity, ErrorCode, IOContract, NeutralType as T, OracleLevel, Rule, RuleCategory, SourceFile,
    SourceRef, Spec,
)
from copilot.engine.oracle import compute_expected
from copilot.languages.oracle_runner import (
    OracleError, OracledbDatabase, OracleLegacyRunner, OraclePlan, block_binds, split_script, strip_schema_prefixes,
    validate_plan,
)
from copilot.languages.source_runner import HarnessFailure
from tests.test_engine import CORRECT, FakeLLM

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "plsql" / "pkg_cartera_mora.sql"
FILES = [SourceFile(path="pkg_cartera_mora.sql", content=SAMPLE.read_text(encoding="utf-8"), language="plsql")]

SPEC = Spec(
    program="PKG_CARTERA", source_language="plsql",
    rules=[Rule(id="BR-001", name="Mora", category=RuleCategory.CALCULO, description="interés de mora",
                action="interes = saldo * tasa / 360 * min(dias, 180)", confidence=0.9, confidence_reason="ok",
                source=SourceRef(file="pkg_cartera_mora.sql", unit="liquidar_mora", lines=(60, 61)))],
    io=IOContract(operation="liquidar_mora",
                  inputs=[DataField(name="credito_id", type=T.parse("integer(32)")),
                          DataField(name="fecha_corte", type=T(kind="date"))],
                  outputs=[DataField(name="interes_mora", type=T.parse("decimal(14,2,HALF_UP)")),
                           DataField(name="estado_final", type=T.parse("string(10)"))],
                  errors=[ErrorCode(code="ORA-20001", message="CREDITO NO EXISTE"),
                          ErrorCode(code="ORA-20002", message="CREDITO CASTIGADO")]),
    entities=[Entity(name="CLIENTES", kind="tabla", fields=[
                  DataField(name="cliente_id", type=T.parse("integer(32)")),
                  DataField(name="segmento", type=T.parse("string(10)"))]),
              Entity(name="CREDITOS", kind="tabla", fields=[
                  DataField(name="credito_id", type=T.parse("integer(32)")),
                  DataField(name="cliente_id", type=T.parse("integer(32)")),
                  DataField(name="saldo", type=T.parse("decimal(14,2,HALF_UP)")),
                  DataField(name="tasa_mora_anual", type=T.parse("decimal(7,4,HALF_UP)")),
                  DataField(name="fecha_vencimiento", type=T(kind="date")),
                  DataField(name="estado", type=T.parse("string(10)"))])])


def credit(cid, seg, saldo, tasa, vence, estado="VIGENTE"):
    return {"CLIENTES": [{"cliente_id": 10, "segmento": seg}],
            "CREDITOS": [{"credito_id": cid, "cliente_id": 10, "saldo": saldo, "tasa_mora_anual": tasa,
                          "fecha_vencimiento": vence, "estado": estado}]}


CASES = [  # (caso, esperado calculado a mano)
    (Case(id="R1", input={"credito_id": 1, "fecha_corte": "2026-02-15",
                          "_tablas": credit(1, "ESTANDAR", "1500000.00", "0.2400", "2026-01-01")}), ("45000.00", "MORA")),
    (Case(id="R2", input={"credito_id": 2, "fecha_corte": "2026-01-11",
                          "_tablas": credit(2, "PREMIUM", "123456.78", "0.1875", "2026-01-01")}), ("514.40", "VIGENTE")),
    (Case(id="R3", input={"credito_id": 3, "fecha_corte": "2026-01-06",       # 0.505 -> la ASIGNACIÓN redondea a .51
                          "_tablas": credit(3, "ESTANDAR", "101.00", "0.3600", "2026-01-01")}), ("0.51", "VIGENTE")),
    (Case(id="R4", input={"credito_id": 99, "fecha_corte": "2026-01-06",
                          "_tablas": credit(4, "ESTANDAR", "100.00", "0.1000", "2026-01-01")}), "ORA-20001"),
    (Case(id="R5", input={"credito_id": 5, "fecha_corte": "2026-01-06",
                          "_tablas": credit(5, "ORO", "100.00", "0.1000", "2026-01-01", "CASTIGADO")}), "ORA-20002"),
]

BLOCK = """DECLARE
  v_interes NUMBER;
  v_estado  VARCHAR2(10);
BEGIN
  v_interes := pkg_cartera.liquidar_mora(:credito_id, :fecha_corte);
  SELECT estado INTO v_estado FROM creditos WHERE credito_id = :credito_id;
  DBMS_OUTPUT.PUT_LINE('@@interes_mora=' || TO_CHAR(v_interes));
  DBMS_OUTPUT.PUT_LINE('@@estado_final=' || v_estado);
END;"""
GOOD_PLAN = json.dumps({"block": BLOCK, "outputs": [{"name": "interes_mora"}, {"name": "estado_final"}]})


# ---------------------------------------------------------------- Oracle simulado (emula pkg_cartera)
class FakeSession:
    def __init__(self, db):
        self.db, self.rows, self.log = db, {"CLIENTES": [], "CREDITOS": []}, []

    def execute(self, sql, binds=None):
        self.log.append((sql, binds))
        if sql.startswith("DELETE FROM "):
            self.rows[sql.split()[-1]] = []
        elif sql.startswith("INSERT INTO "):
            table, cols = sql.split()[2], sql[sql.index("(") + 1:sql.index(")")].split(", ")
            self.rows[table].append({c: binds[f"c{i}"] for i, c in enumerate(cols)})

    def query(self, sql, binds=None):
        if sql.startswith("SELECT COUNT(*) FROM "):
            return [(len(self.rows.get(sql.split()[-1], [])),)]
        if "user_errors" in sql:
            return self.db.compile_errors.pop(0) if self.db.compile_errors else []
        if "user_tables" in sql:
            return [("CLIENTES",), ("CREDITOS",)]
        return [("CREDITOS", "SYS_C001")]

    def run_block(self, block, binds):
        self.db.binds.append(binds)
        cred = next((c for c in self.rows["CREDITOS"] if c["CREDITO_ID"] == binds["credito_id"]), None)
        if cred is None:
            raise OracleError(20001, "ORA-20001: CREDITO NO EXISTE")
        if cred["ESTADO"] == "CASTIGADO":
            raise OracleError(20002, "ORA-20002: CREDITO CASTIGADO")
        seg = self.rows["CLIENTES"][0]["SEGMENTO"]
        dias = (binds["fecha_corte"] - cred["FECHA_VENCIMIENTO"]).days
        raw = cred["SALDO"] * cred["TASA_MORA_ANUAL"] / 360 * min(dias, 180)
        interes = raw.quantize(Decimal("0.01"), ROUND_HALF_UP)
        desc = {"PREMIUM": Decimal("0.20"), "ORO": Decimal("0.10")}.get(seg, Decimal(0))
        interes -= (interes * desc).quantize(Decimal("0.01"), rounding="ROUND_DOWN")
        estado = "MORA" if dias > 30 else cred["ESTADO"]
        return f"otra salida del legacy\n@@interes_mora={interes}\n@@estado_final={estado}"

    def rollback(self):
        pass

    def close(self):
        pass


class FakeDatabase:
    def __init__(self, compile_errors=None):
        self.compile_errors, self.binds, self.sessions, self.dropped = list(compile_errors or []), [], [], []

    def admin_check(self):
        pass

    def create_schema(self):
        s = FakeSession(self)
        self.sessions.append(s)
        return f"AGENTCS_{len(self.sessions)}", s

    def drop_schema(self, name):
        self.dropped.append(name)


def run(db, plans):
    llm = FakeLLM({"legacy_harness": plans, "oracle": [json.dumps({"code": CORRECT})]})
    runner = OracleLegacyRunner("plsql", "PL/SQL", database=db)
    result = compute_expected(SPEC, [c for c, _ in CASES], workdir=Path("/tmp/agentcs-oracle-test"), llm=llm,
                              runner=runner, files=FILES)
    return result, llm


def as_table(result):
    return {o.id: (o.error.code if o.error else (o.output["interes_mora"], o.output["estado_final"]))
            for o in result.outputs}


EXPECTED = {c.id: e for c, e in CASES}


# ---------------------------------------------------------------- flujo completo (simulado)
def test_plsql_with_tables_level_a_flow():
    db = FakeDatabase()
    result, _ = run(db, [GOOD_PLAN])
    assert result.level == OracleLevel.A
    assert as_table(result) == EXPECTED
    assert result.outputs[3].error.message == "CREDITO NO EXISTE"       # mensaje del contrato
    session = db.sessions[0]
    statements = [sql for sql, _ in session.log]
    assert any(s.startswith("CREATE OR REPLACE PACKAGE BODY pkg_cartera") for s in statements)
    assert "ALTER TABLE CREDITOS DISABLE CONSTRAINT SYS_C001" in statements    # filas de prueba sin FK
    first_insert = next(b for s, b in session.log if s.startswith("INSERT INTO CREDITOS"))
    assert first_insert["c2"] == Decimal("1500000.00") and first_insert["c4"] == dt.date(2026, 1, 1)
    assert set(db.binds[0]) == {"credito_id", "fecha_corte"}                    # solo los binds del bloque
    assert db.binds[0]["fecha_corte"] == dt.date(2026, 2, 15)
    assert db.dropped == ["AGENTCS_1"]                                          # esquema eliminado


def test_compile_errors_go_back_to_the_llm():
    db = FakeDatabase(compile_errors=[[("PKG_CARTERA", "PACKAGE BODY", 12, "PLS-00201: identifier 'TASAS' must be declared")]])
    result, llm = run(db, [GOOD_PLAN, GOOD_PLAN])
    assert result.level == OracleLevel.A and "2 intento(s)" in result.description
    feedback = llm.prompts("legacy_harness")[1]
    assert "no compiló" in feedback and "PLS-00201" in feedback and "setup_sql" in feedback


def test_without_oracle_falls_back_to_level_c(monkeypatch):
    monkeypatch.delenv("ORACLE_DSN", raising=False)
    llm = FakeLLM({"oracle": [json.dumps({"code": CORRECT})]})
    result = compute_expected(SPEC, [CASES[0][0]], workdir=Path("/tmp/agentcs-oracle-test2"), llm=llm,
                              runner=OracleLegacyRunner("plsql", "PL/SQL"), files=FILES)
    assert result.level == OracleLevel.C
    assert result.description.startswith("Nivel A no disponible (Oracle no configurado")


# ---------------------------------------------------------------- salvaguardas y SQL*Plus
def test_block_cannot_load_data_or_skip_the_legacy():
    bad = OraclePlan(block="BEGIN INSERT INTO creditos VALUES (1); DBMS_OUTPUT.PUT_LINE('@@interes_mora=1'); END;",
                     setup_sql=["CREATE OR REPLACE PROCEDURE x IS BEGIN NULL; END;"])
    with pytest.raises(HarnessFailure) as exc:
        validate_plan(bad, FILES, SPEC)
    msg = str(exc.value)
    assert "INSERT" in msg and "invocar alguna rutina legacy" in msg and "setup_sql solo admite" in msg
    validate_plan(OraclePlan(block=BLOCK.replace("FROM creditos", "FROM creditos /* UPDATE */")), FILES, SPEC)


def test_split_script_like_sqlplus():
    script = ("SET SERVEROUTPUT ON\nPROMPT creando\nCREATE TABLE t (x NUMBER);\nINSERT INTO t VALUES (1);\n"
              "CREATE OR REPLACE PROCEDURE p IS\nBEGIN\n  UPDATE t SET x = 2;\nEND;\n/\nEXEC p;\nSHOW ERRORS\n")
    assert split_script(script) == ["CREATE TABLE t (x NUMBER)", "INSERT INTO t VALUES (1)",
                                    "CREATE OR REPLACE PROCEDURE p IS\nBEGIN\n  UPDATE t SET x = 2;\nEND;",
                                    "BEGIN p; END;"]
    assert len(split_script(FILES[0].content)) == 4


def test_schema_prefix_is_removed_and_declared():
    script, schemas = strip_schema_prefixes("CREATE TABLE BANCO.cuentas (x NUMBER);\nSELECT * FROM banco.cuentas;")
    assert schemas == ["BANCO"] and "BANCO." not in script.upper()


def test_error_code_is_matched_to_the_contract_form():
    from copilot.languages.source_runner import to_case_output
    out = to_case_output("X", {"error": ("-20002", "ORA-20002: CREDITO CASTIGADO")}, SPEC)
    assert (out.error.code, out.error.message) == ("ORA-20002", "CREDITO CASTIGADO")


def test_binds_ignore_literals_and_assignments():
    assert block_binds("BEGIN v := f(:monto, ':falso'); -- :comentario\n x := :Canal; END;") == ["monto", "Canal"]


# ---------------------------------------------------------------- Oracle REAL (se activa sola)
def _oracle_ready() -> bool:
    db = OracledbDatabase.from_env()
    if db is None:
        return False
    try:
        db.admin_check()
        return True
    except Exception:   # noqa: BLE001
        return False


@pytest.mark.skipif(not _oracle_ready(), reason="requiere Oracle (docker compose --profile oracle)")
def test_real_oracle_level_a_with_tables():
    result, _ = run(OracledbDatabase.from_env(), [GOOD_PLAN])
    assert result.level == OracleLevel.A, result.description
    assert as_table(result) == EXPECTED


def test_dataset_from_scripts_keeps_oracle_defaults():
    from copilot.languages.sql_scripts import base_dataset, file_roles
    ddl = SourceFile(path="01_ddl.sql", language="plsql", content=(
        "/* encabezado (VIP) */\nCREATE TABLE t (\n  id NUMBER(10) NOT NULL,\n  monto NUMBER(14,2) DEFAULT 0 NOT NULL,\n"
        "  estado VARCHAR2(10) DEFAULT 'NUEVO' NOT NULL,\n  usuario VARCHAR2(30) DEFAULT USER NOT NULL,\n"
        "  CONSTRAINT pk_t PRIMARY KEY (id)\n);\n"))
    data = SourceFile(path="pruebas/datos.sql", language="plsql", content=(
        "ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD';\nINSERT INTO t (id) VALUES (7);\n"
        "INSERT INTO t VALUES (8, 12.5, 'O''HARA', 'x');\nCOMMIT;\n"))
    run = SourceFile(path="ejecutar.sql", language="plsql", content="SET SERVEROUTPUT ON\nBEGIN\n  p(1);\nEND;\n/\n")
    assert file_roles([ddl, data, run]) == {"01_ddl.sql": "codigo", "pruebas/datos.sql": "datos_prueba",
                                            "ejecutar.sql": "ejecucion"}
    rows = base_dataset([ddl, data, run]).rows["t"]
    assert rows[0] == {"id": 7, "monto": "0.00", "estado": "NUEVO"}          # sin usuario: lo pone Oracle
    assert rows[1] == {"id": 8, "monto": "12.50", "estado": "O'HARA", "usuario": "x"}
