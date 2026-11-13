"""Modo demo: una ejecución completa con datos sintéticos que cumplen los contratos.

Sirve para que la UI se integre ya y para ensayar la demo sin LLM ni internet. Los valores
esperados NO están inventados: los calcula una implementación de referencia que emula la
semántica numérica del COBOL (oráculo nivel C). En modo real, el oráculo es GnuCOBOL (nivel A).
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from pathlib import Path

from copilot.contracts import (
    AnalysisResult, Case, CaseError, CaseOutput, Classification, DataField, Entity, ErrorCode,
    IOContract, Metrics, NeutralType, OracleLevel, Phase, RiskItem, Rule, RuleCategory, RunMode,
    RunState, SourceRef, Spec, Unit, UnitKind, Variable,
)
from copilot.security import Sanitizer
from copilot.verification import compare

DEMO_FILE = Path(__file__).parent / "demo_data" / "AMORTIZA.cbl"
PROGRAM = "AMORTIZA.cbl"

MONEY_TRUNC = NeutralType.parse("decimal(11,2,DOWN)")
MONEY_ROUND = NeutralType.parse("decimal(11,2,HALF_UP)")
RATE = NeutralType.parse("decimal(5,2,DOWN)")
MONTHLY_RATE = NeutralType.parse("decimal(9,8,DOWN)")
FACTOR = NeutralType.parse("decimal(13,8,DOWN)")
INT = NeutralType.parse("integer(32)")

ORACLE_DESCRIPTION = ("Modo demo: valores esperados de la implementación de referencia que emula la "
                      "semántica COBOL (truncamiento sin ROUNDED, HALF_UP con ROUNDED). "
                      "En modo real el oráculo es GnuCOBOL (nivel A).")


# ------------------------------------------------------------------ oráculo de referencia
def reference_schedule(monto: str, tasa_anual: str, plazo: int, *,
                       interest_rounding_bug: bool = False) -> tuple[list[dict] | None, CaseError | None]:
    """Emula AMORTIZA.cbl. interest_rounding_bug=True simula el error típico de traducción
    (redondear el interés en vez de truncarlo) para mostrar la autocorrección."""
    m = Decimal(monto)
    if m <= 0:
        return None, CaseError(code="E01")
    if plazo < 1 or plazo > 360:
        return None, CaseError(code="E02")
    with localcontext() as ctx:
        ctx.prec = 34
        tasa = RATE.assign(tasa_anual)
        if m >= Decimal("50000000"):
            tasa = RATE.assign(tasa - Decimal("0.50"))
        tasa_mes = MONTHLY_RATE.assign(tasa / Decimal(1200))
        factor = FACTOR.assign((1 + tasa_mes) ** plazo)
        cuota = MONEY_ROUND.assign(m * tasa_mes * factor / (factor - 1))
        interest_type = MONEY_ROUND if interest_rounding_bug else MONEY_TRUNC
        saldo, rows = MONEY_TRUNC.assign(m), []
        for i in range(1, plazo + 1):
            interes = interest_type.assign(saldo * tasa_mes)
            capital = MONEY_TRUNC.assign(cuota - interes)
            saldo = MONEY_TRUNC.assign(saldo - capital)
            rows.append({"periodo": i, "cuota": str(cuota), "interes": str(interes),
                         "capital": str(capital), "saldo": str(saldo)})
    return rows, None


DEMO_CASES = [
    Case(id="C001", input={"monto": "1000000.00", "tasa_anual": "18.00", "plazo": 12},
         tags=["BR-004", "BR-005"], description="Crédito de consumo típico"),
    Case(id="C002", input={"monto": "60000000.00", "tasa_anual": "15.00", "plazo": 6},
         tags=["BR-003", "BR-004"], description="Tasa preferencial por monto alto"),
    Case(id="C003", input={"monto": "50000000.00", "tasa_anual": "12.00", "plazo": 3},
         tags=["BR-003", "borde"], description="Umbral exacto de tasa preferencial"),
    Case(id="C004", input={"monto": "1234567.89", "tasa_anual": "23.45", "plazo": 4},
         tags=["BR-005", "redondeo"], description="Intereses con decimales que exigen truncar"),
    Case(id="C005", input={"monto": "0.00", "tasa_anual": "18.00", "plazo": 12},
         tags=["BR-001", "invalido"], description="Monto inválido"),
    Case(id="C006", input={"monto": "1000000.00", "tasa_anual": "18.00", "plazo": 400},
         tags=["BR-002", "invalido", "borde"], description="Plazo fuera de rango"),
]


def _run_reference(cases: list[Case], **kw: bool) -> list[CaseOutput]:
    out = []
    for c in cases:
        rows, err = reference_schedule(c.input["monto"], c.input["tasa_anual"], c.input["plazo"], **kw)
        out.append(CaseOutput(id=c.id, output=rows, error=err))
    return out


# ------------------------------------------------------------------ análisis y spec
def _block(lines: list[str], start: str, end: str) -> tuple[int, int]:
    s = next(i for i, ln in enumerate(lines) if start in ln)
    e = next(i for i in range(s, len(lines)) if end in lines[i])
    return s + 1, e + 1


def _analysis(text: str) -> AnalysisResult:
    lines = text.splitlines()
    starts = [(i + 1, ln.strip()[:-1]) for i, ln in enumerate(lines)
              if ln.startswith("       ") and not ln.startswith("        ") and ln.strip().endswith(".")
              and ln.strip()[:4].isdigit()]
    units = []
    for idx, (line, name) in enumerate(starts):
        end = starts[idx + 1][0] - 1 if idx + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line - 1:end])
        infra = name in ("0000-PRINCIPAL", "1000-VALIDAR-EXIT", "4000-GENERAR-TABLA")
        units.append(Unit(
            id=f"{PROGRAM}::{name}", name=name, kind=UnitKind.PARAGRAPH, file=PROGRAM,
            start_line=line, end_line=end,
            calls=[p for p in ("1000-VALIDAR", "2000-AJUSTAR-TASA", "3000-CALCULAR-CUOTA", "4000-GENERAR-TABLA")
                   if f"PERFORM {p}" in body],
            classification=Classification.MIXTO if name == "4000-GENERAR-TABLA"
            else Classification.INFRAESTRUCTURA if infra else Classification.NEGOCIO,
            complexity=1 + body.count(" IF ") + body.count("PERFORM VARYING") + body.count(" OR "),
            notes=(["GO TO dentro de PERFORM THRU"] if "GO TO" in body else [])
            + (["DISPLAY: salida de terminal (infraestructura)"] if "DISPLAY" in body else []),
        ))
    variables = []
    for i, ln in enumerate(lines):
        if " PIC " in ln:
            parts = ln.split()
            name, pic = parts[1], " ".join(parts[2:]).rstrip(".")
            variables.append(Variable(name=name, declared_type=pic, file=PROGRAM, line=i + 1))
    loc = sum(1 for ln in lines if ln.strip() and not ln.startswith("      *"))
    cx = [u.complexity for u in units]
    return AnalysisResult(
        language="cobol", dialect="GnuCOBOL (formato fijo)", parser="demo:paragraph-segmenter",
        files=[PROGRAM], units=units, variables=variables,
        metrics=Metrics(loc=loc, units=len(units), avg_complexity=round(sum(cx) / len(cx), 2),
                        max_complexity=max(cx)),
        risks=[RiskItem(unit_id=f"{PROGRAM}::1000-VALIDAR", level="MEDIO",
                        reasons=["GO TO hacia 1000-VALIDAR-EXIT dentro de PERFORM THRU"]),
               RiskItem(unit_id=f"{PROGRAM}::3000-CALCULAR-CUOTA", level="ALTO",
                        reasons=["Potencia y división con truncamiento a 8 decimales",
                                 "Tasa 0 provoca división por cero"])],
    )


def _spec(text: str) -> Spec:
    lines = text.splitlines()

    def src(unit: str, start: str, end: str) -> SourceRef:
        a, b = _block(lines, start, end)
        return SourceRef(file=PROGRAM, unit=unit, lines=(a, b), snippet="\n".join(lines[a - 1:b]))

    rules = [
        Rule(id="BR-001", name="Monto del crédito positivo", category=RuleCategory.VALIDACION,
             description="El monto solicitado debe ser mayor que cero; si no, se rechaza con E01.",
             condition="monto <= 0", action="rechazar con error E01",
             source=src("1000-VALIDAR", "IF WS-MONTO NOT > 0", "END-IF"),
             variables={"monto": "WS-MONTO"}, confidence=0.97,
             confidence_reason="Condición explícita y local",
             gherkin="Escenario: Monto inválido\n  Dado un crédito por 0 pesos\n  Cuando se calcula la tabla\n  Entonces se rechaza con el código E01"),
        Rule(id="BR-002", name="Plazo entre 1 y 360 meses", category=RuleCategory.VALIDACION,
             description="El plazo debe estar entre 1 y 360 cuotas; si no, se rechaza con E02.",
             condition="plazo < 1 OR plazo > 360", action="rechazar con error E02",
             source=src("1000-VALIDAR", "IF WS-PLAZO < 1", "END-IF."),
             variables={"plazo": "WS-PLAZO"}, confidence=0.95,
             confidence_reason="Condición explícita; se ejecuta solo si BR-001 pasa (GO TO)",
             assumptions=["Si el monto es inválido, el plazo no se valida (orden de E01 sobre E02)"],
             gherkin="Escenario: Plazo fuera de rango\n  Dado un crédito a 400 meses\n  Cuando se calcula la tabla\n  Entonces se rechaza con el código E02"),
        Rule(id="BR-003", name="Tasa preferencial por monto alto", category=RuleCategory.DECISION,
             description="Créditos desde 50.000.000 reciben 0,50 puntos menos de tasa anual.",
             condition="monto >= 50000000", action="tasa_anual = tasa_anual - 0.50",
             source=src("2000-AJUSTAR-TASA", "IF WS-MONTO >= 50000000", "END-IF."),
             variables={"monto": "WS-MONTO", "tasa_anual": "WS-TASA-ANUAL"},
             result_type=RATE, confidence=0.93, confidence_reason="Constante y condición explícitas",
             gherkin="Escenario: Tasa preferencial\n  Dado un crédito de 60.000.000 al 15,00% anual\n  Cuando se calcula la tabla\n  Entonces la tasa aplicada es 14,50%"),
        Rule(id="BR-004", name="Cuota fija (sistema francés)", category=RuleCategory.CALCULO,
             description="Cuota = monto × i × (1+i)^n / ((1+i)^n − 1), con i = tasa anual / 1200 "
                         "truncada a 8 decimales y la cuota redondeada a 2 decimales.",
             action="cuota = ROUND_HALF_UP(monto * i * factor / (factor - 1), 2)",
             source=src("3000-CALCULAR-CUOTA", "COMPUTE WS-TASA-MES", "WS-MONTO * WS-TASA-MES"),
             variables={"monto": "WS-MONTO", "i": "WS-TASA-MES", "factor": "WS-FACTOR", "cuota": "WS-CUOTA"},
             result_type=MONEY_ROUND, confidence=0.62,
             confidence_reason="Truncamientos intermedios a 8 decimales y tasa 0 no controlada",
             assumptions=["Tasa 0 produce división por cero en el legacy: comportamiento a definir",
                          "i y factor se truncan (sin ROUNDED) a 8 decimales antes de calcular la cuota"],
             gherkin="Escenario: Cuota fija\n  Dado un crédito de 1.000.000 al 18% anual a 12 meses\n  Cuando se calcula la cuota\n  Entonces la cuota es constante en todos los periodos"),
        Rule(id="BR-005", name="Interés del periodo truncado", category=RuleCategory.CALCULO,
             description="El interés de cada periodo es saldo × i truncado a 2 decimales (sin redondeo); "
                         "capital = cuota − interés.",
             action="interes = TRUNC(saldo * i, 2); capital = cuota - interes; saldo = saldo - capital",
             source=src("4000-GENERAR-TABLA", "COMPUTE WS-INTERES", "COMPUTE WS-SALDO"),
             variables={"saldo": "WS-SALDO", "interes": "WS-INTERES", "capital": "WS-CAPITAL"},
             result_type=MONEY_TRUNC, confidence=0.88,
             confidence_reason="COMPUTE sin ROUNDED: trunca; fácil de traducir mal como redondeo"),
    ]
    money = lambda name, t, legacy: DataField(name=name, type=t, legacy_name=legacy)  # noqa: E731
    return Spec(
        program="AMORTIZA", source_language="cobol", domain="Crédito de consumo", rules=rules,
        entities=[Entity(name="Prestamo", kind="value_object", fields=[
            money("monto", MONEY_TRUNC, "WS-MONTO"), money("tasa_anual", RATE, "WS-TASA-ANUAL"),
            DataField(name="plazo", type=INT, legacy_name="WS-PLAZO")]),
            Entity(name="Cuota", kind="value_object", fields=[
                DataField(name="periodo", type=INT, legacy_name="WS-I"),
                money("cuota", MONEY_ROUND, "WS-CUOTA"), money("interes", MONEY_TRUNC, "WS-INTERES"),
                money("capital", MONEY_TRUNC, "WS-CAPITAL"), money("saldo", MONEY_TRUNC, "WS-SALDO")])],
        io=IOContract(
            operation="calcular_tabla_amortizacion",
            inputs=[money("monto", MONEY_TRUNC, "WS-MONTO"), money("tasa_anual", RATE, "WS-TASA-ANUAL"),
                    DataField(name="plazo", type=INT, legacy_name="WS-PLAZO")],
            outputs=[DataField(name="periodo", type=INT), DataField(name="cuota", type=MONEY_ROUND),
                     DataField(name="interes", type=MONEY_TRUNC), DataField(name="capital", type=MONEY_TRUNC),
                     DataField(name="saldo", type=MONEY_TRUNC)],
            errors=[ErrorCode(code="E01", message="", rule_id="BR-001"),
                    ErrorCode(code="E02", message="", rule_id="BR-002")],
            output_is_list=True),
        assumptions=["Entradas y salidas sintéticas; DISPLAY se trata como adaptador de salida"],
    )


# ------------------------------------------------------------------ código generado (vista lado a lado)
GENERATED_FILES = {
    "src/main/java/com/tcs/agentcs/amortization/domain/rule/PreferentialRateRule.java": '''package com.tcs.agentcs.amortization.domain.rule;

import java.math.BigDecimal;

/** Regla BR-003 · AMORTIZA.cbl 2000-AJUSTAR-TASA. */
public final class PreferentialRateRule {
    private static final BigDecimal THRESHOLD = new BigDecimal("50000000");
    private static final BigDecimal DISCOUNT = new BigDecimal("0.50");

    public BigDecimal apply(BigDecimal principal, BigDecimal annualRate) {
        return principal.compareTo(THRESHOLD) >= 0 ? annualRate.subtract(DISCOUNT) : annualRate;
    }
}
''',
    "src/main/java/com/tcs/agentcs/amortization/domain/rule/FixedInstallmentRule.java": '''package com.tcs.agentcs.amortization.domain.rule;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/** Regla BR-004 · AMORTIZA.cbl 3000-CALCULAR-CUOTA. */
public final class FixedInstallmentRule {
    private static final MathContext MC = MathContext.DECIMAL128;

    public BigDecimal monthlyRate(BigDecimal annualRate) {
        return annualRate.divide(new BigDecimal("1200"), MC).setScale(8, RoundingMode.DOWN);
    }

    public BigDecimal installment(BigDecimal principal, BigDecimal monthlyRate, int term) {
        BigDecimal factor = BigDecimal.ONE.add(monthlyRate).pow(term, MC).setScale(8, RoundingMode.DOWN);
        return principal.multiply(monthlyRate, MC).multiply(factor, MC)
                .divide(factor.subtract(BigDecimal.ONE), MC)
                .setScale(2, RoundingMode.HALF_UP);
    }
}
''',
    "src/main/java/com/tcs/agentcs/amortization/domain/rule/PeriodInterestRule.java": '''package com.tcs.agentcs.amortization.domain.rule;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Regla BR-005 · AMORTIZA.cbl 4000-GENERAR-TABLA (COMPUTE sin ROUNDED: trunca). */
public final class PeriodInterestRule {
    public BigDecimal interest(BigDecimal balance, BigDecimal monthlyRate) {
        return balance.multiply(monthlyRate).setScale(2, RoundingMode.DOWN);
    }
}
''',
}


# ------------------------------------------------------------------ ejecución demo
def build_demo_run(run_id: str, target_language: str = "java") -> RunState:
    raw = DEMO_FILE.read_text(encoding="utf-8")
    files, findings = Sanitizer().sanitize_files([(PROGRAM, raw)])
    clean = files[0].content
    files[0].language = "cobol"

    state = RunState(run_id=run_id, mode=RunMode.DEMO, source_language="cobol",
                     target_language=target_language, domain="Crédito de consumo")
    state.files, state.sanitization = files, findings
    state.start(Phase.INGESTA)
    state.finish(Phase.INGESTA, ok=True, message=f"COBOL detectado · {len(findings)} dato(s) sensible(s) enmascarado(s)")
    state.start(Phase.ANALISIS)
    state.analysis = _analysis(clean)
    state.finish(Phase.ANALISIS, ok=True,
                 message=f"{state.analysis.metrics.units} párrafos inventariados · {len(state.analysis.risks)} riesgos")
    state.start(Phase.EXTRACCION)
    state.update_spec(_spec(clean))
    state.finish(Phase.EXTRACCION, ok=True, message=f"{len(state.spec.rules)} reglas con línea de origen y confianza")
    pending = sum(r.needs_attention for r in state.spec.rules)
    state.wait_for_human(Phase.VALIDACION_HUMANA,
                         f"{len(state.spec.rules)} reglas por revisar ({pending} con confianza baja)")
    return state


def complete_demo_run(state: RunState) -> RunState:
    """Fases 5-8 tras la aprobación humana: diseño, generación, verificación (con un intento fallido
    y su autocorrección) y empaquetado."""
    state.finish(Phase.VALIDACION_HUMANA, ok=True, message=f"Especificación aprobada por {state.approved_by}")
    state.start(Phase.DISENO)
    state.design = {"style": "hexagonal", "entities": [e.name for e in state.spec.entities],
                    "adr": ["ADR-M01 Decimal exacto con truncamiento explícito",
                            "ADR-M02 DISPLAY reemplazado por puerto de salida"]}
    state.finish(Phase.DISENO, ok=True, message="Modelo de dominio y puertos definidos")
    state.start(Phase.GENERACION)
    state.generated_files = dict(GENERATED_FILES)
    state.generation_attempts = 1
    state.finish(Phase.GENERACION, ok=True, message=f"{len(GENERATED_FILES)} archivos generados · compila")

    state.start(Phase.VERIFICACION)
    state.cases = list(DEMO_CASES)
    state.expected = _run_reference(state.cases)
    kw = dict(target_language=state.target_language, oracle_level=OracleLevel.C,
              oracle_description=ORACLE_DESCRIPTION)
    state.actual = _run_reference(state.cases, interest_rounding_bug=True)
    state.set_verification(compare(state.spec, state.cases, state.expected, state.actual, attempt=1, **kw))
    state.generation_attempts = 2   # autocorrección: el agente recibe los casos fallidos + BR-005
    state.actual = _run_reference(state.cases)
    report = compare(state.spec, state.cases, state.expected, state.actual, attempt=2, **kw)
    state.set_verification(report.model_copy(update={
        "coverage_lines": 86.4, "coverage_branches": 78.1, "critical_findings": 0, "max_complexity": 4}))
    fails = state.verification.gate_failures()
    state.finish(Phase.VERIFICACION, ok=not fails,
                 message="; ".join(fails) or f"{report.passed}/{report.total} casos equivalentes en el intento 2")
    state.start(Phase.EMPAQUETADO)
    state.finish(Phase.EMPAQUETADO, ok=True, message="Paquete de migración listo para descargar")
    return state
