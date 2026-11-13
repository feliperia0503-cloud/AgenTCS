from decimal import Decimal

import pytest
from pydantic import ValidationError

from copilot.contracts import (
    Case, CaseError, CaseOutput, DataField, IOContract, NeutralType, OracleLevel, Phase,
    PhaseStatus, Rounding, Rule, RuleCategory, RuleStatus, RunState, SourceRef, Spec, TypeKind,
)
from copilot.verification import compare, failing_cases

MONEY = NeutralType.parse("decimal(11,2,HALF_UP)")
MONEY_TRUNC = NeutralType.parse("decimal(11,2,DOWN)")


# ---------------- tipos neutrales ----------------
@pytest.mark.parametrize("value,rounding,expected", [
    ("2.345", Rounding.HALF_UP, "2.35"),
    ("2.345", Rounding.DOWN, "2.34"),
    ("-2.345", Rounding.HALF_UP, "-2.35"),     # mitad lejos de cero
    ("-2.345", Rounding.DOWN, "-2.34"),        # truncar hacia cero
    ("2.345", Rounding.HALF_EVEN, "2.34"),     # banquero (.NET Math.Round)
    ("2.355", Rounding.HALF_EVEN, "2.36"),
])
def test_assign_rounding(value, rounding, expected):
    t = NeutralType(kind=TypeKind.DECIMAL, precision=9, scale=2, rounding=rounding)
    assert t.assign(value) == Decimal(expected)


def test_assign_unsigned_keeps_absolute_value():
    t = NeutralType.parse("decimal(5,2,DOWN) unsigned")
    assert t.assign("-12.349") == Decimal("12.34")


def test_assign_overflow():
    with pytest.raises(OverflowError):
        NeutralType.parse("decimal(5,2,HALF_UP)").assign("1000.00")


def test_decimal_requires_rounding():
    with pytest.raises(ValidationError):
        NeutralType(kind=TypeKind.DECIMAL, precision=9, scale=2)


@pytest.mark.parametrize("text", [
    "decimal(9,2,HALF_UP)", "decimal(5,0,DOWN) unsigned", "string(30)", "integer(32)",
    "enum(A|B|C)", "list<decimal(9,2,HALF_EVEN)>", "date", "boolean",
])
def test_parse_describe_roundtrip(text):
    assert NeutralType.parse(text).describe() == text


# ---------------- reglas y spec ----------------
def make_rule(rid="BR-001", confidence=0.95, **kw):
    return Rule(
        id=rid, name="Tasa preferencial", category=RuleCategory.DECISION,
        description="Monto >= 50M descuenta 0,5 puntos", condition="monto >= 50000000",
        action="tasa_anual = tasa_anual - 0.50",
        source=SourceRef(file="AMORTIZA.cbl", unit="2100-AJUSTAR-TASA", lines=(142, 147)),
        confidence=confidence, confidence_reason="explícita", **kw)


def make_spec(rules=None):
    return Spec(
        program="AMORTIZA", source_language="cobol", rules=rules or [make_rule()],
        io=IOContract(
            operation="calcular_tabla_amortizacion",
            inputs=[DataField(name="monto", type=MONEY)],
            outputs=[DataField(name="cuota", type=MONEY), DataField(name="interes", type=MONEY_TRUNC),
                     DataField(name="estado", type=NeutralType.parse("string(10)"))],
            output_is_list=True))


def test_rule_id_format():
    with pytest.raises(ValidationError):
        make_rule(rid="R1")


def test_source_lines_order():
    with pytest.raises(ValidationError):
        SourceRef(file="x", unit="u", lines=(10, 5))


def test_low_confidence_approval_needs_comment():
    rule = make_rule(confidence=0.5)
    with pytest.raises(ValidationError):
        rule.approve(by="dairon")
    approved = rule.approve(by="dairon", comment="Verificado con negocio")
    assert approved.status == RuleStatus.APROBADA and approved.review.by == "dairon"


def test_adjust_and_spec_flow():
    spec = make_spec([make_rule("BR-001"), make_rule("BR-002")])
    assert len(spec.pending) == 2 and not spec.is_fully_reviewed
    spec = spec.replace_rule(spec.rule("BR-001").adjust(by="juan", comment="umbral real", condition="monto > 50000000"))
    spec = spec.replace_rule(spec.rule("BR-002").reject(by="juan", comment="es infraestructura"))
    assert spec.is_fully_reviewed
    assert [r.id for r in spec.active_rules] == ["BR-001"]
    assert spec.rule("BR-001").condition == "monto > 50000000"


def test_duplicate_rule_ids():
    with pytest.raises(ValidationError):
        make_spec([make_rule("BR-001"), make_rule("BR-001")])


# ---------------- casos y comparador ----------------
def test_case_rejects_floats():
    with pytest.raises(ValidationError):
        Case(id="C1", input={"monto": 1000.5})
    Case(id="C1", input={"monto": "1000.50", "plazo": 12})


def _cases():
    return [Case(id="C1", input={"monto": "1000000"}, tags=["BR-001"]),
            Case(id="C2", input={"monto": "-5"}, tags=["invalido"])]


def _expected():
    return [CaseOutput(id="C1", output=[{"cuota": "88.85", "interes": "15.00", "estado": "OK        "}]),
            CaseOutput(id="C2", error=CaseError(code="E01", message="MONTO INVALIDO"))]


def test_compare_all_equal():
    actual = [CaseOutput(id="C1", output=[{"cuota": "88.850", "interes": "15", "estado": "OK"}]),
              CaseOutput(id="C2", error=CaseError(code="E01", message="MONTO INVALIDO"))]
    r = compare(make_spec(), _cases(), _expected(), actual, target_language="java",
                oracle_level=OracleLevel.A, oracle_description="GnuCOBOL")
    assert (r.passed, r.total, r.equivalence_pct) == (2, 2, 100.0)
    assert r.gate_failures() == []


def test_compare_detects_one_cent_and_error_mismatch():
    actual = [CaseOutput(id="C1", output=[{"cuota": "88.86", "interes": "15.00", "estado": "OK"}]),
              CaseOutput(id="C2", output=[])]
    r = compare(make_spec(), _cases(), _expected(), actual, target_language="typescript",
                oracle_level=OracleLevel.A, oracle_description="GnuCOBOL")
    assert r.passed == 0
    fails = failing_cases(r)
    assert fails["C1"][0].field == "[0].cuota" and fails["C1"][0].rule_ids == ["BR-001"]
    assert fails["C2"][0].field == "error"
    assert any("equivalencia" in f for f in r.gate_failures())


def test_compare_missing_actual_case():
    r = compare(make_spec(), _cases(), _expected(), [], target_language="java",
                oracle_level=OracleLevel.C, oracle_description="referencia")
    assert r.passed == 0 and len(r.differences) == 2


# ---------------- estado ----------------
def test_run_state_phases():
    s = RunState(run_id="r1", target_language="java")
    s.start(Phase.INGESTA)
    s.finish(Phase.INGESTA, ok=True, message="0 secretos")
    s.wait_for_human(Phase.VALIDACION_HUMANA, "3 reglas pendientes")
    assert s.phases[Phase.INGESTA].status == PhaseStatus.APROBADA
    assert s.phases[Phase.VALIDACION_HUMANA].status == PhaseStatus.ESPERANDO_HUMANO
    s.update_spec(make_spec())
    s.update_spec(make_spec())
    assert len(s.spec_history) == 1
    RunState.model_validate_json(s.model_dump_json())  # serializable (checkpoint de LangGraph)
