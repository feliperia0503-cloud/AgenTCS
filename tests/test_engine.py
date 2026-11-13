"""Motor de autocorrección (ADR-005) con un LLM falso: sin red, sin API key, deterministas."""
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from copilot.api.service import CopilotService, RunStore
from copilot.contracts import LLMCall, OracleLevel, Phase, PhaseStatus, RunMode, SourceFile
from copilot.engine.extractor import extract_spec
from copilot.engine.lessons import LessonStore
from copilot.engine.llm import AnthropicLLM, LLMError, complete_json, prompt_hash
from copilot.engine.loop import LoopConfig, SelfCorrectingLoop, similarity
from copilot.engine.oracle import compute_expected
from copilot.engine.pipeline import Engine
from copilot.engine.segmenter import segment
from copilot.engine.test_generator import CasesResponse, generate_cases
from copilot.languages.registry import get_target
from copilot.security import Sanitizer

SECRET = "Sup3rS3creto"
LEGACY = f"""       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTERES.
      * Conexion de prueba PASSWORD={SECRET}
       PROCEDURE DIVISION.
       1000-VALIDAR.
           IF WS-MONTO NOT > 0
              MOVE 'E01' TO WS-ERROR
           END-IF.
       2000-CALCULAR.
           COMPUTE WS-INTERES = WS-MONTO * WS-TASA / 100.
"""

EXTRACTION = json.dumps({
    "operation": "calcular_interes",
    "inputs": [{"name": "monto", "type": "decimal(11,2,DOWN)", "legacy_name": "WS-MONTO"},
               {"name": "tasa", "type": "decimal(5,2,DOWN)", "legacy_name": "WS-TASA"}],
    "outputs": [{"name": "interes", "type": "decimal(11,2,DOWN)", "legacy_name": "WS-INTERES"}],
    "errors": [{"code": "E01", "message": "", "rule_id": None}],
    "rules": [
        {"name": "Monto positivo", "category": "VALIDACION", "description": "Monto debe ser > 0",
         "condition": "monto <= 0", "action": "error E01", "file": "INTERES.cbl", "unit": "1000-VALIDAR",
         "start_line": 6, "end_line": 8, "variables": {"monto": "WS-MONTO"}, "confidence": 0.95,
         "confidence_reason": "explícita"},
        {"name": "Interés truncado", "category": "CALCULO", "description": "interés = monto × tasa / 100 truncado",
         "action": "interes = TRUNC(monto * tasa / 100, 2)", "file": "INTERES.cbl", "unit": "2000-CALCULAR",
         "start_line": 10, "end_line": 10, "variables": {"monto": "WS-MONTO", "tasa": "WS-TASA"},
         "result_type": "decimal(11,2,DOWN)", "confidence": 0.9, "confidence_reason": "COMPUTE sin ROUNDED"},
        {"name": "Fantasma", "category": "CALCULO", "description": "x", "action": "x", "file": "INTERES.cbl",
         "unit": "?", "start_line": 50, "end_line": 60, "confidence": 0.9, "confidence_reason": "x"},
    ],
})

CASES = json.dumps({"cases": [
    {"input": {"monto": "10.10", "tasa": "15.00"}, "kind": "tipico", "rule_ids": ["BR-002"], "description": "redondeo .xx5"},
    {"input": {"monto": -5, "tasa": "1.00"}, "kind": "invalido", "rule_ids": ["BR-001"]},
    {"input": {"monto": "200.00", "tasa": 12.5}, "kind": "tipico", "rule_ids": ["BR-002"]},
]})

CORRECT = '''from decimal import Decimal, ROUND_DOWN

def run(inp):
    monto, tasa = Decimal(inp["monto"]), Decimal(inp["tasa"])
    if monto <= 0:
        return {"error": {"code": "E01", "message": ""}}
    # Regla BR-002 · INTERES.cbl:10
    return {"interes": str((monto * tasa / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN))}
'''
BUGGY = CORRECT.replace("ROUND_DOWN", "ROUND_HALF_UP")
WORSE = 'def run(inp):\n    return {"interes": "0.00"}\n'
SYNTAX = "def run(:\n    pass\n"


def project(code: str) -> str:
    return json.dumps({"files": {"app.py": code}, "notes": ""})


class FakeLLM:
    model = "fake"

    def __init__(self, script: dict[str, list[str]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[str, str, str]] = []
        self.tokens_used = 0
        self.recorder = None

    def complete(self, system, prompt, *, agent, phase):
        self.calls.append((agent, system, prompt))
        if self.recorder:
            self.recorder(LLMCall(phase=phase, agent=agent, prompt_hash="fake", model=self.model))
        queue = self.script.get(agent)
        if not queue:
            return "{}"
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def prompts(self, agent):
        return [p for a, _, p in self.calls if a == agent]


def base_script(*projects: str) -> dict[str, list[str]]:
    return {"extractor": [EXTRACTION], "tests": [CASES], "oracle": [json.dumps({"code": CORRECT})],
            "generator": [project(p) for p in projects],
            "lessons": [json.dumps({"lesson": "COMPUTE sin ROUNDED trunca: usar ROUND_DOWN", "tags": ["redondeo"]})]}


@pytest.fixture
def prepared(tmp_path):
    def _prepare(*projects: str):
        llm = FakeLLM(base_script(*projects))
        files, _ = Sanitizer().sanitize_files([("INTERES.cbl", LEGACY)])
        spec = extract_spec(llm, files, segment(files, "cobol"), program="INTERES")
        for r in spec.rules:
            spec = spec.replace_rule(r.approve(by="qa", comment="ok"))
        cases = generate_cases(llm, spec)
        oracle = compute_expected(spec, cases, workdir=tmp_path / "oracle", llm=llm)
        loop = SelfCorrectingLoop(llm, get_target("python"), tmp_path / "attempts",
                                  LoopConfig(max_attempts=5, patience=2), LessonStore(tmp_path / "lessons.json"))
        return llm, spec, cases, oracle, loop
    return _prepare


def run_loop(prepared, *projects):
    llm, spec, cases, oracle, loop = prepared(*projects)
    result = loop.run(spec, cases, oracle.outputs, oracle_level=oracle.level, oracle_description=oracle.description)
    return llm, result, loop


# ---------------------------------------------------------------- extractor y casos
def test_extractor_validates_lines_and_discards_invalid(prepared):
    _, spec, cases, oracle, _ = prepared(CORRECT)
    assert [r.id for r in spec.rules] == ["BR-001", "BR-002"]
    assert any("Fantasma" in a for a in spec.assumptions)              # descartada por líneas inválidas
    assert spec.rules[1].source.snippet.strip().startswith("COMPUTE WS-INTERES")
    assert spec.rules[0].confidence < 0.95                            # penalización del segmentador genérico
    assert oracle.level == OracleLevel.C


def test_boundary_and_normalized_cases(prepared):
    _, _, cases, _, _ = prepared(CORRECT)
    montos = {c.input["monto"] for c in cases}
    assert {"-0.01", "0.00", "0.01"} <= montos                        # frontera de "monto <= 0"
    assert "999999999.99" in montos                                   # máximo del tipo
    assert all(not isinstance(v, float) for c in cases for v in c.input.values())
    assert len({json.dumps(c.input, sort_keys=True) for c in cases}) == len(cases)


# ---------------------------------------------------------------- escenarios del bucle
def test_scenario1_fixes_rounding_and_stops(prepared, tmp_path):
    llm, result, _ = run_loop(prepared, BUGGY, CORRECT)
    assert [a.passed == a.total for a in result.attempts] == [False, True]
    assert result.stop_reason == "equivalencia_total" and result.best_attempt == 2
    assert result.best_score == 1.0 and "ROUND_DOWN" in result.best_files["app.py"]
    feedback = llm.prompts("generator")[1]
    assert "esperado '1.51', obtenido '1.52'" in feedback and "BR-002" in feedback
    assert LessonStore(tmp_path / "lessons.json").relevant("cobol→python")   # aprendió una lección


def test_scenario2_plateau_returns_best(prepared):
    _, result, _ = run_loop(prepared, BUGGY, BUGGY, BUGGY)
    assert result.stop_reason == "meseta" and len(result.attempts) == 3
    assert result.best_attempt == 1


def test_scenario3_worse_version_does_not_replace_best(prepared):
    _, result, _ = run_loop(prepared, BUGGY, WORSE, WORSE)
    assert result.best_attempt == 1
    assert result.attempts[1].similarity < result.attempts[0].similarity
    assert "ROUND_HALF_UP" in result.best_files["app.py"]


def test_scenario4_compile_error_is_feedback(prepared):
    llm, result, _ = run_loop(prepared, SYNTAX, CORRECT)
    assert result.attempts[0].compiled is False and result.attempts[0].similarity == 0
    assert "no compila" in llm.prompts("generator")[1]
    assert result.stop_reason == "equivalencia_total"


def test_similarity_gives_partial_credit(prepared):
    _, result, _ = run_loop(prepared, BUGGY, CORRECT)
    first = result.attempts[0]
    assert 0.3 < first.similarity < 1.0


def test_lessons_are_injected_next_time(prepared, tmp_path):
    run_loop(prepared, BUGGY, CORRECT)
    llm, _, _ = run_loop(prepared, CORRECT)
    assert "COMPUTE sin ROUNDED trunca" in llm.prompts("generator")[0]


# ---------------------------------------------------------------- escenario 5: extremo a extremo + sanitizador
def test_scenario5_end_to_end_service_sanitizes_before_llm(tmp_path):
    llm = FakeLLM(base_script(BUGGY, CORRECT))
    engine = Engine(llm, LessonStore(tmp_path / "lessons.json"), tmp_path, LoopConfig(max_attempts=4))
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    run = svc.create_run([("INTERES.cbl", LEGACY.encode())], "python")
    assert run.phases[Phase.VALIDACION_HUMANA].status == PhaseStatus.ESPERANDO_HUMANO
    for rule in run.spec.rules:
        run = svc.decide_rule(run.run_id, rule.id, "approve", "qa", "revisada")
    run = svc.approve_spec(run.run_id, "qa")

    assert all(SECRET not in system + prompt for _, system, prompt in llm.calls)
    assert all(run.phases[p].status == PhaseStatus.APROBADA for p in Phase)
    assert run.verification.passed == run.verification.total and run.verification.similarity == 1.0
    assert [r.attempt for r in run.verification_history] == [1] and run.generation_attempts == 2
    assert run.llm_calls and {c.agent for c in run.llm_calls} >= {"extractor", "tests", "oracle", "generator"}
    names = zipfile.ZipFile(io.BytesIO(svc.package(run.run_id))).namelist()
    assert "app.py" in names and "docs/traceability-matrix.md" in names


def test_missing_toolchain_is_explained(tmp_path, monkeypatch):
    from copilot.languages.java.adapter import JavaTarget
    monkeypatch.setattr(JavaTarget, "missing_tools", lambda self: ["javac"])
    llm = FakeLLM(base_script(CORRECT))
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path)
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    run = svc.create_run([("INTERES.cbl", LEGACY.encode())], "java")
    for rule in run.spec.rules:
        svc.decide_rule(run.run_id, rule.id, "approve", "qa", "ok")
    from copilot.api.service import ServiceError
    with pytest.raises(ServiceError) as e:
        svc.approve_spec(run.run_id, "qa")
    assert e.value.code == "TOOLCHAIN_MISSING" and "Docker" in e.value.action


def test_engine_failure_marks_phase_with_action(tmp_path):
    llm = FakeLLM({"extractor": ["esto no es json"]})
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path)
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    run = svc.create_run([("INTERES.cbl", LEGACY.encode())], "python")
    rec = run.phases[Phase.EXTRACCION]
    assert rec.status == PhaseStatus.FALLIDA and "Acción:" in rec.gate_message


# ---------------------------------------------------------------- escenario 6: replay y JSON
def test_scenario6_replay_reads_cache_without_sdk(tmp_path):
    class Boom:
        @property
        def messages(self):
            raise AssertionError("no debe llamar al SDK en replay")

    llm = AnthropicLLM("m", cache_dir=tmp_path, replay=True, client=Boom())
    (tmp_path / f"{prompt_hash('m', 'sys', 'hola')}.json").write_text(json.dumps({"text": "respuesta"}))
    calls = []
    llm.recorder = calls.append
    assert llm.complete("sys", "hola", agent="a", phase=Phase.GENERACION) == "respuesta"
    assert calls[0].replayed is True
    with pytest.raises(LLMError) as e:
        llm.complete("sys", "otra", agent="a", phase=Phase.GENERACION)
    assert e.value.code == "REPLAY_MISS"


def test_llm_caches_real_calls(tmp_path):
    sdk_calls = []

    def create(**kw):
        sdk_calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(text='{"ok": 1}')],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    llm = AnthropicLLM("m", cache_dir=tmp_path, replay=False,
                       client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    for _ in range(2):
        assert llm.complete("s", "p", agent="a", phase=Phase.GENERACION) == '{"ok": 1}'
    assert len(sdk_calls) == 1 and llm.tokens_used == 15


def test_complete_json_retries_with_validation_error():
    llm = FakeLLM({"tests": ["no es json", CASES]})
    resp = complete_json(llm, "s", "p", CasesResponse, agent="tests", phase=Phase.VERIFICACION)
    assert len(resp.cases) == 3
    assert "no cumplió el esquema" in llm.prompts("tests")[1]


def test_similarity_bounds(prepared):
    _, _, cases, oracle, _ = prepared(CORRECT)
    from copilot.verification import compare
    _, spec, *_ = prepared(CORRECT)
    perfect = compare(spec, cases, oracle.outputs, oracle.outputs, target_language="python",
                      oracle_level=OracleLevel.C, oracle_description="x")
    empty = compare(spec, cases, oracle.outputs, [], target_language="python",
                    oracle_level=OracleLevel.C, oracle_description="x")
    assert similarity(perfect, oracle.outputs) == 1.0 and similarity(empty, oracle.outputs) == 0.0


def test_sandbox_rejects_path_traversal(tmp_path):
    from copilot.engine.sandbox import SandboxError, write_files
    for bad in ("../x.py", "/etc/x", "C:/x.py", "a/../../x"):
        with pytest.raises(SandboxError):
            write_files(tmp_path, {bad: "x"})


def test_segmenter_finds_units():
    files = [SourceFile(path="INTERES.cbl", content=LEGACY)]
    names = [u.name for u in segment(files, "cobol").units]
    assert "1000-VALIDAR" in names and "2000-CALCULAR" in names
