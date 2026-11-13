"""Punta a punta con el paquete PL/SQL completo de prueba (tablas + configuración + paquete + datos + lote).

Los archivos de la evaluación NO se versionan (el repositorio es público): la prueba se activa apuntando
AGENTCS_JURY_DIR a la carpeta que contiene src/ y pruebas/. El LLM es simulado y no hay Oracle, así que el
oráculo cae a nivel C y debe declararlo; lo que se prueba es la plataforma con los archivos reales: roles de
archivo, datos de prueba convertidos en tablas, caso oficial, código muerto, herencia de tablas y paquete.
"""
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from copilot.api.service import CopilotService, RunStore
from copilot.contracts import Phase, PhaseStatus, RunMode
from copilot.engine.lessons import LessonStore
from copilot.engine.loop import LoopConfig
from copilot.engine.pipeline import Engine
from tests.test_engine import FakeLLM

JURY = Path(os.environ.get("AGENTCS_JURY_DIR", "/nonexistent"))
pytestmark = pytest.mark.skipif(not (JURY / "src").is_dir(), reason="define AGENTCS_JURY_DIR con src/ y pruebas/")

BODY = "src/04_pkg_liquidacion_siniestros_body.sql"
STORED = Path(BODY).name     # la ingesta guarda el nombre del archivo (así lo ve el LLM)


def line_of(path: str, text: str) -> int:
    lines = (JURY / path).read_text(encoding="utf-8").splitlines()
    return next(i for i, ln in enumerate(lines, 1) if text in ln)


def extraction() -> str:
    v1 = line_of(BODY, "FUNCTION fn_calcular_deducible_v1")
    v1_end = line_of(BODY, "END fn_calcular_deducible_v1")
    plazo = line_of(BODY, "IF v_dias_denuncia > v_dias_max_denuncia THEN")
    lote = line_of(BODY, "CURSOR cur_pendientes IS")
    return json.dumps({
        "operation": "procesar_lote",
        "inputs": [{"name": "fecha_proceso", "type": "date", "legacy_name": "p_fecha_proceso"}],
        "outputs": [{"name": "siniestro_id", "type": "integer(32)"},
                    {"name": "monto_reclamado", "type": "decimal(14,2,HALF_UP)"}],
        "output_is_list": True,
        "tables": [{"name": "LS_SINIESTROS", "access": "lectura_escritura", "columns": [
            {"name": "siniestro_id", "type": "integer(32)"}, {"name": "estado", "type": "string(20)"},
            {"name": "fecha_denuncia", "type": "date"}, {"name": "monto_reclamado", "type": "decimal(14,2,HALF_UP)"}]}],
        "dead_code": [{"file": STORED, "unit": "fn_calcular_deducible_v1", "start_line": v1, "end_line": v1_end,
                       "reason": "Reemplazada en SIN-0310; nadie la invoca"},
                      {"file": STORED, "unit": "fantasma", "start_line": 99999, "end_line": 99999, "reason": "x"}],
        "excluded_outputs": [{"name": "usuario_proceso", "reason": "USER: depende de la sesión"}],
        "rules": [
            {"name": "Denuncia extemporánea", "category": "VALIDACION", "description": "Plazo de denuncia",
             "condition": "dias_denuncia > dias_max_denuncia", "action": "rechazar DENUNCIA_EXTEMPORANEA",
             "file": STORED, "unit": "pr_liquidar_siniestro", "start_line": plazo, "end_line": plazo + 3,
             "variables": {}, "confidence": 0.95, "confidence_reason": "explícita"},
            {"name": "Selección del lote", "category": "DECISION", "description": "REGISTRADO y denuncia <= fecha",
             "condition": "estado = REGISTRADO y fecha_denuncia <= fecha_proceso", "action": "procesar en orden de id",
             "file": STORED, "unit": "pr_procesar_lote", "start_line": lote, "end_line": lote + 6,
             "variables": {}, "confidence": 0.9, "confidence_reason": "cursor explícito"}]})


CASES = json.dumps({"cases": [
    {"input": {"fecha_proceso": "2026-01-15", "_tablas": {"LS_SINIESTROS": [
        {"siniestro_id": 9001, "estado": "REGISTRADO", "fecha_denuncia": "2026-01-10", "monto_reclamado": 10}]}},
     "kind": "borde", "rule_ids": ["BR-002"], "description": "Un solo siniestro"},
    {"input": {"fecha_proceso": "2026-03-31"}, "kind": "oficial", "rule_ids": ["BR-002"]},
]})

REFERENCE = '''def run(inp):
    corte, rows = inp["fecha_proceso"], []
    for s in sorted(inp["_tablas"]["ls_siniestros"], key=lambda r: r["siniestro_id"]):
        if s["estado"] == "REGISTRADO" and s["fecha_denuncia"] <= corte:
            rows.append({"siniestro_id": s["siniestro_id"], "monto_reclamado": s["monto_reclamado"]})
    return rows
'''


def test_full_plsql_package_end_to_end(tmp_path, monkeypatch):
    monkeypatch.delenv("ORACLE_DSN", raising=False)
    llm = FakeLLM({"extractor": [extraction()], "tests": [CASES], "oracle": [json.dumps({"code": REFERENCE})],
                   "generator": [json.dumps({"files": {"app.py": REFERENCE}, "notes": ""})]})
    engine = Engine(llm, LessonStore(tmp_path / "lessons.json"), tmp_path, LoopConfig(max_attempts=2))
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    uploads = [(str(p.relative_to(JURY)), p.read_bytes()) for p in sorted(JURY.rglob("*.sql"))]
    run = svc.create_run(uploads, "python")

    roles = run.design["file_roles"]
    assert sorted(roles.values()) == ["codigo", "codigo", "codigo", "configuracion", "datos_prueba", "ejecucion"]
    extractor_prompt = llm.prompts("extractor")[0]
    assert "ANA TORRES" not in extractor_prompt                     # datos de prueba no son reglas
    assert "pr_procesar_lote(p_fecha_proceso" in extractor_prompt   # el script de ejecución sí es contexto
    assert [d["unit"] for d in run.design["dead_code"]] == ["fn_calcular_deducible_v1"]   # línea inválida descartada
    assert run.analysis.metrics.dead_units and any("Código muerto" in a for a in run.spec.assumptions)

    for rule in run.spec.rules:
        run = svc.decide_rule(run.run_id, rule.id, "approve", "qa", "revisada")
    run = svc.approve_spec(run.run_id, "qa")

    official, variant = run.cases[0], run.cases[1]
    assert "oficial" in official.tags and official.input["fecha_proceso"] == "2026-03-31"
    tables = official.input["_tablas"]
    assert {t: len(r) for t, r in tables.items() if r} == {
        "ls_parametros": 15, "ls_clientes": 5, "ls_polizas": 13, "ls_coberturas": 18, "ls_siniestros": 23,
        "ls_liquidaciones": 5}
    assert len(variant.input["_tablas"]["ls_siniestros"]) == 1 and len(variant.input["_tablas"]["ls_polizas"]) == 13
    assert "ANA TORRES" in llm.prompts("tests")[0]                  # el QA ve el escenario base del cliente

    expected = {o.id: o for o in run.expected}[official.id].output
    ids = [r["siniestro_id"] for r in expected]
    assert ids == sorted(ids) and 1016 not in ids and len(ids) == 17   # 1016 se denunció después del corte
    assert run.verification.oracle_level.value == "C"
    assert run.verification.oracle_description.startswith("Nivel A no disponible (Oracle no configurado")
    assert run.verification.passed == run.verification.total
    assert all(run.phases[p].status == PhaseStatus.APROBADA for p in Phase)

    package = zipfile.ZipFile(io.BytesIO(svc.package(run.run_id)))
    findings = package.read("docs/hallazgos.md").decode()
    assert "fn_calcular_deducible_v1" in findings and "usuario_proceso" in findings and "datos_prueba" in findings


def test_expert_can_add_rules_with_real_lines(tmp_path, monkeypatch):
    monkeypatch.delenv("ORACLE_DSN", raising=False)
    llm = FakeLLM({"extractor": [extraction()]})
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path, LoopConfig(max_attempts=1))
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    run = svc.create_run([(str(p.relative_to(JURY)), p.read_bytes()) for p in sorted(JURY.rglob("*.sql"))], "python")
    path = next(f.path for f in run.files if f.path.endswith("04_pkg_liquidacion_siniestros_body.sql"))
    fraude = line_of(BODY, "v_motivo     := 'SOSPECHA_FRAUDE';")
    run = svc.add_rule(run.run_id, "experto@banco", "documenta_legacy", "Prioridad de fraude", "DECISION",
                       "La alerta de fraude prevalece sobre el tope", "estado = PENDIENTE / SOSPECHA_FRAUDE",
                       path, fraude - 4, fraude, "Confirmado con el área de siniestros")
    new = run.spec.rules[-1]
    assert new.id == "BR-003" and new.status.value == "APROBADA" and "SOSPECHA_FRAUDE" in new.source.snippet
    from copilot.api.service import ServiceError
    with pytest.raises(ServiceError, match="no existen"):
        svc.add_rule(run.run_id, "experto", "cambio_negocio", "x", "CALCULO", "x", "x", path, 1, 999999, "c")
