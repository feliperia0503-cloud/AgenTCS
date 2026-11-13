"""Oráculo nivel B (pares E/S del usuario) y reportes del paquete (seguridad + resumen ejecutivo)."""
import io
import json
import shutil
import zipfile

import pytest

from copilot.api import pairs, reports
from copilot.api.service import CopilotService, RunStore, ServiceError
from copilot.contracts import OracleLevel, Phase, PhaseStatus, RunMode
from copilot.engine.lessons import LessonStore
from copilot.engine.loop import LoopConfig
from copilot.engine.pipeline import Engine
from copilot.engine.sandbox import ProcResult

from .test_engine import CORRECT, EXTRACTION, LEGACY, FakeLLM, project

PAIRS = [
    {"id": "redondeo", "input": {"monto": "10.10", "tasa": "15.00"}, "output": {"interes": "1.51"}},
    {"input": {"monto": "200.00", "tasa": "12.50"}, "output": {"interes": "25.00"}},
    {"input": {"monto": "-5.00", "tasa": "1.00"}, "error": {"code": "E01", "message": ""}},
]


def as_bytes(obj) -> bytes:
    return json.dumps(obj).encode()


# ---------------------------------------------------------------- forma del archivo
def test_parse_valid_pairs_numbers_ids_and_keeps_errors():
    parsed = pairs.parse("pares.json", as_bytes(PAIRS))
    assert [c.id for c, _ in parsed] == ["redondeo", "P002", "P003"]
    assert parsed[1][1].output == {"interes": "25.00"}
    assert parsed[2][1].error.code == "E01" and parsed[2][1].output is None


@pytest.mark.parametrize("payload, fragment", [
    ([{"input": {"monto": 10.5}, "output": {"interes": "1"}}], "string"),
    ([{"input": {"monto": "1"}, "output": {"interes": "1"}, "error": {"code": "E"}}], "exactamente uno"),
    ([{"input": {"monto": "1"}}], "exactamente uno"),
    ([{"output": {"interes": "1"}}], "input"),
    ([{"id": "x", "input": {}, "output": {}}, {"id": "x", "input": {}, "output": {}}], "repetido"),
    ({"input": {}}, "lista"),
    ([], "lista"),
])
def test_parse_rejects_malformed_pairs(payload, fragment):
    with pytest.raises(pairs.PairsError) as e:
        pairs.parse("p.json", as_bytes(payload))
    assert e.value.code == "PAIRS_INVALID" and fragment in e.value.message + e.value.action


def test_parse_rejects_non_json_and_wrong_extension():
    with pytest.raises(pairs.PairsError):
        pairs.parse("p.json", b"no es json")
    with pytest.raises(pairs.PairsError):
        pairs.parse("p.csv", as_bytes(PAIRS))


# ---------------------------------------------------------------- flujo completo con el servicio
@pytest.fixture
def service(tmp_path):
    llm = FakeLLM({"extractor": [EXTRACTION], "generator": [project(CORRECT)],
                   "lessons": [json.dumps({"lesson": "x", "tags": []})]})
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path, LoopConfig(max_attempts=2))
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    # "texto": lenguaje sin pack de origen (sin runner), así el oráculo no intenta nivel A
    run = svc.create_run([("INTERES.cbl", LEGACY.encode())], "python", source_language="texto")
    return svc, run, llm


def approve_all(svc, run):
    for rule in run.spec.rules:
        svc.decide_rule(run.run_id, rule.id, "approve", "qa", "ok")
    return svc.approve_spec(run.run_id, "qa")


def test_level_b_uses_user_pairs_as_cases_and_oracle(service):
    svc, run, llm = service
    info = svc.upload_expected(run.run_id, "pares.json", as_bytes(PAIRS))
    assert info["pairs"] == 3 and info["validated_against_spec"] is True
    run = approve_all(svc, run)
    assert run.phases[Phase.VERIFICACION].status == PhaseStatus.APROBADA, run.phases[Phase.VERIFICACION].gate_message
    assert run.verification.oracle_level == OracleLevel.B
    assert [c.id for c in run.cases] == ["redondeo", "P002", "P003"]
    assert run.verification.passed == run.verification.total == 3
    assert not llm.prompts("tests") and not llm.prompts("oracle")       # ni casos ni referencia del LLM


def test_level_b_detects_a_wrong_expected_value(service):
    svc, run, _ = service
    wrong = [dict(PAIRS[0], output={"interes": "1.52"}), *PAIRS[1:]]      # el legacy trunca: 1.51
    svc.upload_expected(run.run_id, "pares.json", as_bytes(wrong))
    run = approve_all(svc, run)
    assert run.verification.oracle_level == OracleLevel.B
    assert run.verification.passed == 2
    assert run.phases[Phase.VERIFICACION].status == PhaseStatus.FALLIDA


def test_pairs_that_do_not_match_the_contract_explain_the_expected_fields(service):
    svc, run, _ = service
    bad = [{"input": {"importe": "1.00"}, "output": {"interes": "0.01"}}]
    with pytest.raises(ServiceError) as e:
        svc.upload_expected(run.run_id, "pares.json", as_bytes(bad))
    assert e.value.code == "PAIRS_MISMATCH"
    assert "importe" in e.value.message and "monto, tasa" in e.value.action


def test_pairs_cannot_change_after_generation_started(service):
    svc, run, _ = service
    approve_all(svc, run)
    with pytest.raises(ServiceError) as e:
        svc.upload_expected(run.run_id, "pares.json", as_bytes(PAIRS))
    assert e.value.code == "PAIRS_TOO_LATE"


def test_package_includes_executive_summary_and_security_reports(service):
    svc, run, _ = service
    svc.upload_expected(run.run_id, "pares.json", as_bytes(PAIRS))
    run = approve_all(svc, run)
    z = zipfile.ZipFile(io.BytesIO(svc.package(run.run_id)))
    assert {"reports/executive-summary.md", "reports/security.md", "reports/security.json"} <= set(z.namelist())
    summary = z.read("reports/executive-summary.md").decode()
    assert "3 de 3" in summary and "B · pares entrada/salida" in summary and "python" in summary
    security = json.loads(z.read("reports/security.json"))
    assert security["files"] == len(run.generated_files)
    if not security["complete"]:                       # sin herramientas: nunca se afirma "0 hallazgos"
        assert security["critical_findings"] is None and "Escaneo incompleto" in summary + z.read("reports/security.md").decode()


# ---------------------------------------------------------------- escaneo de seguridad
def test_security_scan_parses_tools_and_never_includes_secret_values(monkeypatch):
    def fake_run(args, cwd, timeout, extra_env=None):
        if args[0] == "gitleaks":
            report = args[args.index("--report-path") + 1]
            open(report, "w").write(json.dumps([{"File": "x/app.py", "StartLine": 3, "RuleID": "generic-api-key",
                                                 "Secret": "REDACTED", "Match": "token = 'abc'"}]))
            return ProcResult(0, "", "")
        return ProcResult(0, json.dumps({"results": [
            {"check_id": "copilot.api.agentcs.money-float-python", "path": "app.py", "start": {"line": 5},
             "extra": {"severity": "ERROR", "message": "float()"}},
            {"check_id": "agentcs.dynamic-eval", "path": "app.py", "start": {"line": 9},
             "extra": {"severity": "WARNING", "message": "eval"}}]}), "")
    monkeypatch.setattr(reports, "resolve", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(reports, "run_cmd", fake_run)
    sec = reports.security_scan({"app.py": "x = 1\n"})
    assert sec["complete"] and sec["critical_findings"] == 2            # 1 secreto + 1 ERROR de semgrep
    assert sec["semgrep"]["items"][0]["rule"] == "money-float-python"
    dumped = json.dumps(sec)
    assert "abc" not in dumped and "Match" not in dumped
    assert "2 hallazgo(s) crítico(s)" in reports.security_markdown(sec)


def test_security_scan_without_tools_is_incomplete_not_clean(monkeypatch):
    monkeypatch.setattr(reports, "resolve", lambda name: None)
    sec = reports.security_scan({"app.py": "x = 1\n"})
    assert not sec["complete"] and sec["critical_findings"] is None
    assert "no disponible" in reports.security_markdown(sec)


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="requiere semgrep (en Docker viene instalado)")
def test_local_semgrep_rules_flag_float_money_offline():
    sec = reports.security_scan({"src/main/java/app/Entry.java": "class E { double monto = 1.0; }\n",
                                 "app.py": "from decimal import Decimal\nx = Decimal('1.00')\n"})
    rules = {i["rule"] for i in sec["semgrep"]["items"]}
    assert "money-float-java-csharp" in rules and sec["semgrep"]["errors"] >= 1


def test_cli_accepts_expected_pairs(tmp_path, monkeypatch):
    from copilot.engine import __main__ as cli
    llm = FakeLLM({"extractor": [EXTRACTION], "generator": [project(CORRECT)]})
    monkeypatch.setattr(cli.Engine, "from_env", classmethod(
        lambda cls, config=None: Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path, config)))
    monkeypatch.setattr(cli, "CopilotService", lambda **kw: CopilotService(store=RunStore(tmp_path / "runs"), **kw))
    src, exp = tmp_path / "INTERES.cbl", tmp_path / "pares.json"
    src.write_text(LEGACY)
    exp.write_bytes(as_bytes(PAIRS))
    code = cli.main(["migrate", "--source", str(src), "--target", "python", "--source-language", "texto",
                     "--expected", str(exp), "--auto-approve"])
    assert code == 0
    assert not llm.prompts("tests")
