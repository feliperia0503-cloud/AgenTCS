"""Oráculo nivel A con compiladores/intérpretes REALES (se omiten si la herramienta no está instalada).

El LLM se simula con planes de arnés fijos: lo que se prueba es la plataforma determinista (protocolo,
validaciones, compilación, ejecución por caso, normalización, autocorrección del arnés y caída a nivel C).
"""
import json

import pytest

from copilot.contracts import (
    Case, DataField, ErrorCode, IOContract, NeutralType, OracleLevel, Rule, RuleCategory, SourceFile, SourceRef,
    Spec,
)
from copilot.engine.oracle import compute_expected
from copilot.engine.sandbox import resolve
from copilot.languages.registry import available_sources, get_source
from copilot.languages.source_runner import (
    HarnessFailure, HarnessPlan, InputField, RunnerConfig, normalize, render_stdin, validate_plan,
)
from tests.test_engine import CORRECT, FakeLLM, prepared, run_loop  # noqa: F401  (prepared es fixture)

MONEY = NeutralType.parse("decimal(11,2,DOWN)")
RATE = NeutralType.parse("decimal(5,2,DOWN)")


def make_spec(language: str) -> Spec:
    rule = Rule(id="BR-001", name="Interés", category=RuleCategory.CALCULO, description="interés truncado",
                action="interes = TRUNC(monto * tasa / 100, 2)",
                source=SourceRef(file="x", unit="u", lines=(1, 2)), confidence=0.9, confidence_reason="ok")
    io = IOContract(operation="calcular_interes",
                    inputs=[DataField(name="monto", type=MONEY), DataField(name="tasa", type=RATE)],
                    outputs=[DataField(name="interes", type=MONEY)],
                    errors=[ErrorCode(code="E01", message="MONTO INVALIDO")])
    return Spec(program="INTERES", source_language=language, rules=[rule], io=io)


CASES = [Case(id="C1", input={"monto": "987654.32", "tasa": "18.37"}),    # 181432.0985... -> trunca a .09
         Case(id="C2", input={"monto": "10.10", "tasa": "15.00"}),        # 1.515 -> trunca a 1.51
         Case(id="C3", input={"monto": "0.00", "tasa": "5.00"})]          # error de negocio


def plan(**kw) -> str:
    base = {"mode": "driver", "inputs": [{"name": "monto"}, {"name": "tasa"}], "outputs": [{"name": "interes"}]}
    return json.dumps({**base, **kw})


def needs(*tools):
    return pytest.mark.skipif(any(resolve(t) is None for t in tools), reason=f"requiere {', '.join(tools)}")


def run_level_a(language: str, legacy: dict[str, str], plans: list[str], tmp_path):
    spec = make_spec(language)
    llm = FakeLLM({"legacy_harness": plans, "oracle": [json.dumps({"code": CORRECT})]})
    files = [SourceFile(path=p, content=c, language=language) for p, c in legacy.items()]
    return compute_expected(spec, CASES, workdir=tmp_path, llm=llm, runner=get_source(language).runner,
                            files=files), llm


def outputs(result):
    return {o.id: (o.error.code if o.error else o.output["interes"]) for o in result.outputs}


# ---------------------------------------------------------------- COBOL (GnuCOBOL)
COBOL_LEGACY = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTERES.
       DATA DIVISION.
       LINKAGE SECTION.
       01 LK-MONTO    PIC S9(9)V99.
       01 LK-TASA     PIC S9(3)V99.
       01 LK-INTERES  PIC S9(9)V99.
       01 LK-ERROR    PIC X(3).
       PROCEDURE DIVISION USING LK-MONTO LK-TASA LK-INTERES LK-ERROR.
           MOVE SPACES TO LK-ERROR
           IF LK-MONTO NOT > 0
              MOVE 'E01' TO LK-ERROR
              GOBACK
           END-IF
           COMPUTE LK-INTERES = LK-MONTO * LK-TASA / 100
           GOBACK.
"""
COBOL_DRIVER = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. AGENTCS-DRIVER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-IN       PIC X(40).
       01 WS-MONTO    PIC S9(9)V99.
       01 WS-TASA     PIC S9(3)V99.
       01 WS-INTERES  PIC S9(9)V99.
       01 WS-ERROR    PIC X(3).
       01 WS-OUT      PIC -(10)9.99.
       PROCEDURE DIVISION.
           ACCEPT WS-IN
           COMPUTE WS-MONTO = FUNCTION NUMVAL(WS-IN)
           ACCEPT WS-IN
           COMPUTE WS-TASA = FUNCTION NUMVAL(WS-IN)
           CALL 'INTERES' USING WS-MONTO WS-TASA WS-INTERES WS-ERROR
           IF WS-ERROR NOT = SPACES
              DISPLAY "@@ERROR=" WS-ERROR "|"
           ELSE
              MOVE WS-INTERES TO WS-OUT
              DISPLAY "@@interes=" WS-OUT
           END-IF
           STOP RUN.
"""


@needs("cobc")
def test_cobol_level_a_captures_real_truncation(tmp_path):
    good = plan(entry="agentcs_driver.cbl", files={"agentcs_driver.cbl": COBOL_DRIVER})
    result, _ = run_level_a("cobol", {"INTERES.cbl": COBOL_LEGACY}, [good], tmp_path)
    assert result.level == OracleLevel.A
    # COMPUTE sin ROUNDED trunca: el golden master real lo demuestra (HALF_UP daría .10 y 1.52)
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}
    assert result.outputs[2].error.message == "MONTO INVALIDO"     # mensaje del contrato, no del LLM
    assert "agentcs_driver.cbl" in result.reference_code             # el arnés queda para auditoría


@needs("cobc")
def test_harness_self_corrects_after_compile_error(tmp_path):
    broken = plan(entry="agentcs_driver.cbl", files={"agentcs_driver.cbl": COBOL_DRIVER.replace("CALL", "CALLL")})
    good = plan(entry="agentcs_driver.cbl", files={"agentcs_driver.cbl": COBOL_DRIVER})
    result, llm = run_level_a("cobol", {"INTERES.cbl": COBOL_LEGACY}, [broken, good], tmp_path)
    assert result.level == OracleLevel.A and "2 intento(s)" in result.description
    assert "No compila" in llm.prompts("legacy_harness")[1]           # el error volvió al LLM


def test_falls_back_to_level_c_and_says_why(tmp_path):
    result, _ = run_level_a("cobol", {"INTERES.cbl": COBOL_LEGACY}, ["{}"], tmp_path)
    assert result.level == OracleLevel.C
    assert result.description.startswith("Nivel A no disponible")
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}


# ---------------------------------------------------------------- PHP
PHP_LEGACY = """<?php
function calcular_interes($monto, $tasa) {
    if ($monto <= 0) { return array('error' => 'E01'); }
    return floor($monto * $tasa) / 100;   // trunca a centavos
}
"""
PHP_DRIVER = """<?php
require_once __DIR__ . '/legacy/interes.php';
$m = (float) trim(fgets(STDIN)); $t = (float) trim(fgets(STDIN));
$r = calcular_interes($m, $t);
if (is_array($r)) { echo "@@ERROR=" . $r['error'] . "|\\n"; }
else { echo "@@interes=" . number_format($r, 2, '.', '') . "\\n"; }
"""


@needs("php")
def test_php_level_a(tmp_path):
    good = plan(entry="agentcs_driver.php", files={"agentcs_driver.php": PHP_DRIVER})
    result, _ = run_level_a("php", {"legacy/interes.php": PHP_LEGACY}, [good], tmp_path)
    assert result.level == OracleLevel.A
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}


# ---------------------------------------------------------------- Delphi / Pascal (Free Pascal)
PAS_LEGACY = """unit Interes;
{$mode delphi}
interface
function CalcularInteres(Monto, Tasa: Currency; out Codigo: string): Currency;
implementation
function CalcularInteres(Monto, Tasa: Currency; out Codigo: string): Currency;
begin
  Codigo := '';
  Result := 0;
  if Monto <= 0 then begin Codigo := 'E01'; Exit; end;
  Result := Trunc(Monto * Tasa) / 100;
end;
end.
"""
PAS_DRIVER = """program agentcs_driver;
{$mode delphi}
uses SysUtils, Interes;
var S: string; M, T, R: Currency; Code: string; FS: TFormatSettings;
begin
  FS := DefaultFormatSettings; FS.DecimalSeparator := '.';
  ReadLn(S); M := StrToCurr(S, FS);
  ReadLn(S); T := StrToCurr(S, FS);
  R := CalcularInteres(M, T, Code);
  if Code <> '' then WriteLn('@@ERROR=', Code, '|')
  else WriteLn('@@interes=', CurrToStrF(R, ffFixed, 2, FS));
end.
"""


@needs("fpc")
def test_delphi_level_a(tmp_path):
    good = plan(entry="agentcs_driver.pas", files={"agentcs_driver.pas": PAS_DRIVER})
    result, _ = run_level_a("delphi", {"Interes.pas": PAS_LEGACY}, [good], tmp_path)
    assert result.level == OracleLevel.A
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}


# ---------------------------------------------------------------- C# legacy (Mono)
CS_LEGACY = """namespace Banco {
  public class Interes {
    public static string Error;
    public static decimal Calcular(decimal monto, decimal tasa) {
      Error = null;
      if (monto <= 0) { Error = "E01"; return 0; }
      return decimal.Truncate(monto * tasa) / 100m;
    }
  }
}
"""
CS_DRIVER = """using System; using System.Globalization;
static class AgenTCSDriver {
  static void Main() {
    var ci = CultureInfo.InvariantCulture;
    decimal m = decimal.Parse(Console.ReadLine(), ci), t = decimal.Parse(Console.ReadLine(), ci);
    decimal r = Banco.Interes.Calcular(m, t);
    if (Banco.Interes.Error != null) Console.WriteLine("@@ERROR=" + Banco.Interes.Error + "|");
    else Console.WriteLine("@@interes=" + r.ToString(ci));
  }
}
"""


@needs("mcs", "mono")
def test_csharp_legacy_level_a(tmp_path):
    good = plan(entry="agentcs_driver.cs", files={"agentcs_driver.cs": CS_DRIVER})
    result, _ = run_level_a("csharp-legacy", {"Interes.cs": CS_LEGACY}, [good], tmp_path)
    assert result.level == OracleLevel.A
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}


# ---------------------------------------------------------------- Java legacy
JAVA_LEGACY = """package banco;
import java.math.BigDecimal;
public class Interes {
    public static BigDecimal calcular(BigDecimal monto, BigDecimal tasa) {
        if (monto.signum() <= 0) throw new IllegalArgumentException("E01");
        return monto.multiply(tasa).divide(new BigDecimal("100"), 2, BigDecimal.ROUND_DOWN);
    }
}
"""
JAVA_DRIVER = """import java.io.*; import java.math.BigDecimal;
public class agentcs_driver {
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        BigDecimal m = new BigDecimal(in.readLine().trim()), t = new BigDecimal(in.readLine().trim());
        try { System.out.println("@@interes=" + banco.Interes.calcular(m, t).toPlainString()); }
        catch (IllegalArgumentException e) { System.out.println("@@ERROR=" + e.getMessage() + "|"); }
    }
}
"""


@needs("javac", "java")
def test_java_legacy_level_a(tmp_path):
    good = plan(entry="agentcs_driver.java", files={"agentcs_driver.java": JAVA_DRIVER})
    result, _ = run_level_a("java-legacy", {"banco/Interes.java": JAVA_LEGACY}, [good], tmp_path)
    assert result.level == OracleLevel.A
    assert outputs(result) == {"C1": "181432.09", "C2": "1.51", "C3": "E01"}


# ---------------------------------------------------------------- salvaguardas deterministas
LEGACY_FILES = [SourceFile(path="INTERES.cbl", content=COBOL_LEGACY, language="cobol")]
CFG = RunnerConfig(tools=["cobc"], build=["cobc"], run=["./x"], compile_extensions=[".cbl"], allowed_flags=["-free"])


def test_plan_cannot_overwrite_legacy_or_use_unlisted_flags():
    bad = HarnessPlan.model_validate_json(plan(entry="INTERES.cbl", files={"interes.cbl": "x"}, flags=["-O3"]))
    with pytest.raises(HarnessFailure) as exc:
        validate_plan(bad, LEGACY_FILES, make_spec("cobol"), CFG)
    assert "sobrescribir" in str(exc.value) and "flags no permitidos" in str(exc.value)


def test_driver_must_use_the_legacy_code():
    fake = HarnessPlan.model_validate_json(plan(entry="agentcs_driver.cbl", compile=["agentcs_driver.cbl"],
                                                files={"agentcs_driver.cbl": "DISPLAY '@@interes=1.00'"}))
    with pytest.raises(HarnessFailure, match="debe usar el código legacy"):
        validate_plan(fake, LEGACY_FILES, make_spec("cobol"), CFG)


def test_normalize_handles_legacy_number_formats():
    assert normalize("    181432.09", MONEY) == "181432.09"
    assert normalize("1234.5-", MONEY) == "-1234.50"            # signo al final
    assert normalize("000123456", MONEY, "implied") == "1234.56"  # punto implícito (PIC 9(7)V99)
    assert normalize("1.519", MONEY) == "1.519"                   # nunca redondea: la diferencia se ve
    assert normalize("42", NeutralType.parse("integer(32)")) == 42


def test_implied_inputs_are_zero_padded():
    p = HarnessPlan(mode="driver", entry="d", inputs=[InputField(name="monto", format="implied", width=11),
                                                      InputField(name="tasa")])
    assert render_stdin(p, CASES[0], {"monto": MONEY, "tasa": RATE}) == "00098765432\n18.37\n"


def test_registry_exposes_declarative_source_packs():
    assert {"cobol", "php", "delphi", "plsql", "csharp-legacy", "java-legacy"} <= set(available_sources())
    assert get_source("sql") is get_source("plsql")               # alias de la ingesta
    assert get_source("plsql").runner is None                     # sin Oracle: nivel B/C declarado
    assert "TRUNCAN" in get_source("cobol").knowledge()           # la semántica llega al extractor


# ---------------------------------------------------------------- bucle: regresiones
NO_VALIDATION = '''from decimal import Decimal, ROUND_DOWN

def run(inp):
    monto, tasa = Decimal(str(inp["monto"])), Decimal(str(inp["tasa"]))
    return {"interes": str((monto * tasa / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN))}
'''
ONLY_ERRORS = '''from decimal import Decimal

def run(inp):
    if Decimal(str(inp["monto"])) <= 0:
        return {"error": {"code": "E01", "message": ""}}
    return {"interes": "0.00"}
'''


def test_regression_is_flagged_even_when_similarity_improves(prepared):  # noqa: F811
    llm, result, _ = run_loop(prepared, ONLY_ERRORS, NO_VALIDATION, CORRECT)
    assert result.attempts[1].similarity > result.attempts[0].similarity   # el intento 2 "mejoró"...
    assert "REGRESIÓN" in llm.prompts("generator")[2]                     # ...pero rompió casos que pasaban
