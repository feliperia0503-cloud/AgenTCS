import io
import json
import zipfile
from decimal import Decimal

import pytest

from copilot.api import demo
from copilot.api.service import CopilotService, RunStore, ServiceError
from copilot.contracts import Phase, PhaseStatus, RuleStatus, RunMode
from copilot.security import Sanitizer


# ---------------------------------------------------------------- sanitizer
def test_sanitizer_masks_secrets_consistently():
    text = ('PASSWORD=Demo#2024!\nconn = "jdbc:oracle:thin:@db.local:1521/X"\n'
            'mail ana@banco.demo y otra vez ana@banco.demo\ncard 4111 1111 1111 1111\n'
            'ref 1234567890123 no es tarjeta\nuser scott/tiger@ORCL\n')
    clean, findings = Sanitizer().sanitize_text("a.cbl", text)
    for secret in ("Demo#2024!", "jdbc:oracle", "ana@banco.demo", "4111 1111 1111 1111", "scott/tiger@ORCL"):
        assert secret not in clean
    assert clean.count("<<EMAIL_1>>") == 2          # mismo valor -> mismo marcador
    assert "1234567890123" in clean                 # no pasa Luhn: no se toca
    assert {f.kind for f in findings} >= {"password", "connection_string", "email", "card_number", "oracle_credentials"}
    assert all("Demo#2024!" not in f.model_dump_json() for f in findings)


# ---------------------------------------------------------------- oráculo de referencia
def test_reference_schedule_semantics():
    rows, err = demo.reference_schedule("1000000.00", "18.00", 12)
    assert err is None and len(rows) == 12
    assert len({r["cuota"] for r in rows}) == 1                     # cuota fija
    assert Decimal(rows[-1]["saldo"]).copy_abs() < Decimal("1.00")  # saldo final ~0
    # sin ROUNDED trunca: el interés nunca tiene más de 2 decimales y no supera saldo*i
    assert rows[0]["interes"] == "15000.00"
    assert demo.reference_schedule("0", "18", 12)[1].code == "E01"
    assert demo.reference_schedule("100", "18", 400)[1].code == "E02"


def test_preferential_rate_threshold():
    below, _ = demo.reference_schedule("49999999.99", "12.00", 3)
    at, _ = demo.reference_schedule("50000000.00", "12.00", 3)
    assert Decimal(at[0]["interes"]) / Decimal("50000000") < Decimal(below[0]["interes"]) / Decimal("49999999.99")


# ---------------------------------------------------------------- servicio
@pytest.fixture
def svc(tmp_path):
    return CopilotService(store=RunStore(tmp_path), mode=RunMode.DEMO)


def test_demo_run_full_flow(svc, tmp_path):
    run = svc.create_run([], "java")
    assert run.mode == RunMode.DEMO
    assert run.phases[Phase.VALIDACION_HUMANA].status == PhaseStatus.ESPERANDO_HUMANO
    assert "Demo#2024!" not in run.files[0].content and run.sanitization
    assert not run.analysis.check_against({f.path: f for f in run.files})   # líneas válidas
    # cada regla apunta a líneas reales cuyo texto coincide con el snippet
    lines = run.files[0].content.splitlines()
    for r in run.spec.rules:
        a, b = r.source.lines
        assert "\n".join(lines[a - 1:b]) == r.source.snippet

    with pytest.raises(ServiceError) as e:
        svc.approve_spec(run.run_id, "dairon")
    assert e.value.code == "RULES_PENDING"

    with pytest.raises(ServiceError) as e:      # BR-004 tiene confianza 0.62: exige comentario
        svc.decide_rule(run.run_id, "BR-004", "approve", "dairon")
    assert e.value.code == "RULE_VALIDATION"

    for rid in ("BR-001", "BR-002", "BR-003", "BR-005"):
        svc.decide_rule(run.run_id, rid, "approve", "dairon")
    svc.decide_rule(run.run_id, "BR-004", "adjust", "dairon", "Tasa 0 debe rechazarse con E03",
                    {"assumptions": ["Tasa 0 se rechaza con E03 (decisión de negocio)"]})
    run = svc.approve_spec(run.run_id, "dairon")

    assert all(run.phases[p].status == PhaseStatus.APROBADA for p in Phase)
    assert run.spec.rule("BR-004").status == RuleStatus.AJUSTADA
    v = svc.verification(run.run_id)
    assert v["current"]["passed"] == v["current"]["total"] == 6 and v["gate_failures"] == []
    assert v["history"] and v["history"][0]["passed"] < 6               # intento 1 falló
    assert any("BR-005" in d["rule_ids"] for d in v["history"][0]["differences"])

    z = zipfile.ZipFile(io.BytesIO(svc.package(run.run_id)))
    assert "docs/traceability-matrix.md" in z.namelist()
    assert "Demo#2024!" not in "".join(z.read(n).decode() for n in z.namelist())

    reloaded = CopilotService(store=RunStore(tmp_path)).get_run(run.run_id)   # persistido en disco
    assert reloaded.approved_by == "dairon"


def test_errors_have_actions(svc):
    with pytest.raises(ServiceError) as e:
        svc.get_run("noexiste")
    assert e.value.status == 404 and e.value.action
    with pytest.raises(ServiceError) as e:
        svc.create_run([], "cobol")
    assert e.value.code == "TARGET_NOT_SUPPORTED"
    with pytest.raises(ServiceError) as e:
        svc.create_run([("x.bin", b"\x00\x01")], "java", demo_mode=False)
    assert e.value.code == "BINARY_FILE"
    with pytest.raises(ServiceError) as e:
        svc.create_run([("x.txt", b"hola")], "java", demo_mode=False)
    assert e.value.code == "LANGUAGE_UNKNOWN"


def test_real_mode_upload_is_sanitized_and_paths_stripped(tmp_path):
    from copilot.engine.llm import LLMError

    def no_engine():
        raise LLMError("NO_API_KEY", "Sin llave.", "Configura ANTHROPIC_API_KEY.")

    svc = CopilotService(store=RunStore(tmp_path), mode=RunMode.DEMO, background=False, engine_factory=no_engine)
    run = svc.create_run([("../../etc/PAGOS.cbl", b"       * PWD=abc123\n       PROCEDURE DIVISION.\n")],
                         "java", demo_mode=False)
    assert run.mode == RunMode.REAL and run.source_language == "cobol"
    assert run.files[0].path == "PAGOS.cbl" and "abc123" not in run.files[0].content
    assert run.phases[Phase.INGESTA].status == PhaseStatus.APROBADA
    assert run.phases[Phase.ANALISIS].status == PhaseStatus.FALLIDA      # el motor falla con acción sugerida
    assert "ANTHROPIC_API_KEY" in run.phases[Phase.ANALISIS].gate_message


def test_package_not_ready(svc):
    run = svc.create_run([], "java")
    with pytest.raises(ServiceError) as e:
        svc.package(run.run_id)
    assert e.value.code == "PACKAGE_NOT_READY"


# ---------------------------------------------------------------- HTTP (corre en el contenedor)
def test_http_api(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from copilot.api import app as app_module
    monkeypatch.setattr(app_module, "service", CopilotService(store=RunStore(tmp_path), mode=RunMode.DEMO))
    client = TestClient(app_module.app)
    assert client.get("/api/health").json()["status"] == "ok"
    run = client.post("/api/runs", data={"target_language": "java"}).json()
    bad = client.post(f"/api/runs/{run['run_id']}/approve", json={"by": "x"})
    assert bad.status_code == 409 and bad.json()["detail"]["action"]
    assert client.get("/api/runs/zzz").json()["detail"]["code"] == "RUN_NOT_FOUND"
    json.dumps(run)
