"""Ingesta universal: comprimidos, repositorios, cualquier lenguaje; y el motor generando Java."""
import io
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

from copilot.api import sources
from copilot.api.service import CopilotService, RunStore
from copilot.contracts import Phase, PhaseStatus, RunMode, SourceFile
from copilot.engine.lessons import LessonStore
from copilot.engine.loop import LoopConfig
from copilot.engine.pipeline import Engine, select_for_extraction
from copilot.engine.segmenter import segment
from tests.test_engine import BUGGY, CASES, CORRECT, EXTRACTION, LEGACY, SECRET, FakeLLM


def zip_bytes(files: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def test_zip_filters_and_blocks_path_traversal():
    data = zip_bytes({"app/INTERES.cbl": LEGACY, "../../evil.cbl": "x", "/abs/x.cbl": "y",
                      "node_modules/dep.js": "z", "img/logo.png": b"\x89PNG\x00\x00", "docs/notes.md": "n",
                      "bin.cbl": b"\x00\x01\x02"})
    files = dict(sources.expand_archive("legacy.zip", data))
    assert list(files) == ["app/INTERES.cbl"]


def test_tar_gz_is_supported():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        raw = LEGACY.encode()
        info = tarfile.TarInfo("src/INTERES.cbl")
        info.size = len(raw)
        t.addfile(info, io.BytesIO(raw))
    assert [p for p, _ in sources.expand_archive("x.tar.gz", buf.getvalue())] == ["src/INTERES.cbl"]


def test_invalid_archive_has_action():
    with pytest.raises(sources.SourceError) as e:
        sources.expand_archive("x.zip", b"rar!")
    assert e.value.code == "ARCHIVE_INVALID" and ".rar" in e.value.action


def test_dominant_language_ignores_forms_and_config():
    files = [("a.pas", "x\n" * 50), ("b.dfm", "y\n" * 500), ("c.xml", "z\n" * 900), ("d.sql", "w\n" * 10)]
    assert sources.dominant_language(files) == "delphi"


def test_cp1252_files_are_decoded():
    files = sources.collect([("VIEJO.cbl", "      * AÑO de cálculo\n".encode("cp1252"))], None, None)
    assert "AÑO" in files[0][1]


@pytest.mark.parametrize("url", ["http://github.com/a/b", "https://user:token@bitbucket.org/a/b.git",
                                 "file:///etc", "https://github.com/a/b; rm -rf /", "git@github.com:a/b.git"])
def test_repo_url_validation(url):
    with pytest.raises(sources.SourceError) as e:
        sources.clone_repo(url, "main")
    assert e.value.code == "REPO_URL_INVALID"


def test_branch_validation():
    with pytest.raises(sources.SourceError) as e:
        sources.clone_repo("https://bitbucket.org/org/repo.git", "main; rm -rf /")
    assert e.value.code == "BRANCH_INVALID"


def test_generic_segmenter_handles_delphi_and_abap():
    files = [SourceFile(path="u.pas", content="procedure TForm1.Calcular(Sender: TObject);\nbegin\n if x then y;\nend;\n"),
             SourceFile(path="z.abap", content="FORM calcular.\n  IF a > b.\n  ENDIF.\nENDFORM.\n")]
    names = [u.name for u in segment(files, "delphi").units]
    assert "TForm1.Calcular" in names and "calcular" in names


def test_extraction_budget_prioritizes_logic(monkeypatch):
    monkeypatch.setattr("copilot.engine.pipeline.EXTRACTION_BUDGET", 300)
    logic = SourceFile(path="calc.pas", content="procedure P;\nbegin if a then b; if c then d; end;\n" * 3)
    noise = SourceFile(path="big.pas", content="// comentario\n" * 100)
    chosen, note = select_for_extraction([noise, logic], segment([noise, logic], "delphi"))
    assert chosen[0].path == "calc.pas" and note and "de 2 archivos" in note


# ---------------------------------------------------------------- motor multi-lenguaje: COBOL (zip) → Java
JAVA_OK = '''package app;
import java.math.*; import java.util.*;
public final class Entry {
  public static Object run(Map<String, Object> input) {
    BigDecimal monto = new BigDecimal((String) input.get("monto"));
    BigDecimal tasa = new BigDecimal((String) input.get("tasa"));
    if (monto.signum() <= 0) { Map<String, Object> e = new LinkedHashMap<>(); e.put("code", "E01"); e.put("message", ""); return Map.of("error", e); }
    // Regla BR-002 · INTERES.cbl:10
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("interes", monto.multiply(tasa).divide(BigDecimal.valueOf(100), MathContext.DECIMAL128).setScale(2, __MODE__));
    return out;
  }
}'''


@pytest.mark.skipif(shutil.which("javac") is None, reason="requiere JDK (en Docker viene instalado)")
def test_engine_migrates_zip_to_java(tmp_path):
    def project(code):
        return json.dumps({"files": {"src/main/java/app/Entry.java": code,
                                     "src/main/java/infrastructure/web/Api.java": "package x; import org.springframework.*; class A {}"}})
    llm = FakeLLM({"extractor": [EXTRACTION], "tests": [CASES], "oracle": [json.dumps({"code": CORRECT})],
                   "generator": [project(JAVA_OK.replace("__MODE__", "RoundingMode.HALF_UP")),
                                 project(JAVA_OK.replace("__MODE__", "RoundingMode.DOWN"))]})
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path, LoopConfig(max_attempts=3))
    svc = CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                         engine_factory=lambda: engine)
    run = svc.create_run([("legacy.zip", zip_bytes({"INTERES.cbl": LEGACY}))], "java",
                         framework="spring", architecture="hexagonal")
    assert run.source_language == "cobol" and run.source_ref == "legacy.zip"
    for rule in run.spec.rules:
        svc.decide_rule(run.run_id, rule.id, "approve", "qa", "ok")
    run = svc.approve_spec(run.run_id, "qa")
    assert run.phases[Phase.VERIFICACION].status == PhaseStatus.APROBADA, run.phases[Phase.VERIFICACION].gate_message
    assert run.verification.similarity == 1.0 and run.generation_attempts == 2
    assert "spring" in run.phases[Phase.DISENO].gate_message
    assert "Framework elegido: spring" in llm.prompts("generator")[0]
    assert all(SECRET not in p for _, _, p in llm.calls)


# --- Anti-SSRF: el repositorio debe estar en internet público -----------------------------------------

@pytest.mark.parametrize("url", [
    "https://localhost/org/repo.git",
    "https://LOCALHOST:8443/org/repo.git",
    "https://git.localhost/org/repo.git",
    "https://repos.corp.internal/org/repo.git",
    "https://127.0.0.1/org/repo.git",
    "https://127.1/org/repo.git",
    "https://2130706433/org/repo.git",
    "https://0x7f000001/org/repo.git",
    "https://10.0.0.5/org/repo.git",
    "https://172.16.3.4/org/repo.git",
    "https://192.168.1.10/org/repo.git",
    "https://169.254.169.254/latest/meta-data",
    "https://100.64.0.1/org/repo.git",
    "https://0.0.0.0/org/repo.git",
])
def test_repo_url_rejects_local_and_private_hosts(url, monkeypatch):
    monkeypatch.setattr(sources, "run_cmd", lambda *a, **k: pytest.fail("no debe intentar clonar"))
    with pytest.raises(sources.SourceError) as e:
        sources.clone_repo(url, "main")
    assert e.value.code == "REPO_HOST_BLOCKED"
    assert e.value.action


@pytest.mark.parametrize("resolved", [["169.254.169.254"], ["10.1.2.3"], ["::1"], ["fe80::1"],
                                      ["::ffff:127.0.0.1"], ["140.82.112.3", "192.168.0.7"]])
def test_repo_hostname_resolving_to_private_ip_is_blocked(resolved, monkeypatch):
    monkeypatch.setattr(sources, "resolve_host", lambda host, port: resolved)
    monkeypatch.setattr(sources, "run_cmd", lambda *a, **k: pytest.fail("no debe intentar clonar"))
    with pytest.raises(sources.SourceError) as e:
        sources.clone_repo("https://git.ejemplo-sintetico.com/org/repo.git", "main")
    assert e.value.code == "REPO_HOST_BLOCKED"


def test_unresolvable_host_reports_clear_error(monkeypatch):
    def fail(host, port):
        raise OSError("sin DNS")
    monkeypatch.setattr(sources, "resolve_host", fail)
    with pytest.raises(sources.SourceError) as e:
        sources.clone_repo("https://no-existe.ejemplo-sintetico.com/org/repo.git", None)
    assert e.value.code == "REPO_HOST_UNRESOLVED"


def test_public_repo_is_cloned_pinned_to_validated_ip(monkeypatch):
    calls = []
    monkeypatch.setattr(sources, "resolve_host", lambda host, port: ["140.82.112.3"])

    def fake_run(args, cwd, timeout):
        calls.append(args)
        repo = Path(args[-1])
        repo.mkdir(parents=True)
        (repo / "CALC.cbl").write_text("       PROCEDURE DIVISION.\n           GOBACK.\n")
        return type("R", (), {"ok": True})()

    monkeypatch.setattr(sources, "run_cmd", fake_run)
    files = sources.clone_repo("https://github.com/org/repo.git", "main")
    assert [f[0] for f in files] == ["CALC.cbl"]
    args = calls[0]
    assert "http.curloptResolve=github.com:443:140.82.112.3" in args
    assert "http.followRedirects=false" in args
    assert args[args.index("--branch") + 1] == "main"


# --- samples/: programas sintéticos para las corridas reales ---------------------------------------------

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.mark.parametrize("rel, language, units", [
    ("cobol/INTMORA.cbl", "cobol", {"0000-PRINCIPAL", "1000-VALIDAR", "2000-CALCULAR-INTERES"}),
    ("cobol/PAGOMIN.cbl", "cobol", {"1000-PAGO-BASE", "2000-APLICAR-ATRASO", "3000-APLICAR-LIMITES"}),
    ("plsql/fn_comision_transferencia.sql", "plsql", {"fn_comision_transferencia"}),
])
def test_samples_are_ingested_and_segmented(rel, language, units):
    path = SAMPLES / rel
    files = sources.collect([(path.name, path.read_bytes())], None, None)
    assert sources.dominant_language(files) == language
    found = {u.name for u in segment([SourceFile(path=n, content=c) for n, c in files], language).units}
    assert units <= found


def test_samples_have_no_secrets_and_use_no_float():
    from copilot.security.sanitizer import Sanitizer
    for path in SAMPLES.rglob("*"):
        if path.suffix in {".cbl", ".sql"}:
            text = path.read_text(encoding="utf-8")
            assert Sanitizer().sanitize_text(path.name, text)[1] == [], path
            assert "COMP-1" not in text and "COMP-2" not in text and "BINARY_DOUBLE" not in text


def test_plain_sql_stays_sql_and_plsql_in_sql_file_is_detected():
    assert sources.language_of("q.sql", "SELECT id FROM cuentas WHERE saldo > 0;")[0] == "sql"
    assert sources.language_of("p.sql", "CREATE OR REPLACE PROCEDURE p IS BEGIN NULL; END;")[0] == "plsql"
    assert sources.language_of("b.sql", "DECLARE\n v NUMBER;\nBEGIN\n NULL;\nEND;\n")[0] == "plsql"
