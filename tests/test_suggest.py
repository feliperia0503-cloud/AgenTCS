"""'Sugerir configuración' con un LLM simulado (no consume créditos)."""
import io
import json
import zipfile

import pytest

from copilot.api.catalog import catalog, is_valid
from copilot.api.service import CopilotService, RunStore, ServiceError
from copilot.api.suggest import Suggestion
from copilot.contracts import RunMode
from copilot.engine.lessons import LessonStore
from copilot.engine.pipeline import Engine
from tests.test_engine import LEGACY, SECRET, FakeLLM

GOOD = {"source_summary": "Calcula intereses de crédito.", "language": "java", "framework": "spring",
        "architecture": "hexagonal", "rationale": "Precisión decimal con BigDecimal.", "risks": ["Truncamiento"],
        "confidence": 0.8, "alternatives": [{"language": "csharp", "framework": "aspnet",
                                             "architecture": "clean", "reason": "Equipo .NET"}]}
DELPHI = """unit Calculos;
interface
function Interes(Monto, Tasa: Currency): Currency;
implementation
function Interes(Monto, Tasa: Currency): Currency;
begin
  if Monto <= 0 then raise Exception.Create('E01');
  Result := Trunc(Monto * Tasa) / 100;
end;
end.
"""


def service(tmp_path, *responses):
    llm = FakeLLM({"advisor": list(responses)})
    engine = Engine(llm, LessonStore(tmp_path / "l.json"), tmp_path)
    return llm, CopilotService(store=RunStore(tmp_path / "runs"), mode=RunMode.REAL, background=False,
                               engine_factory=lambda: engine)


def zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def test_suggest_from_files_sanitizes_and_returns_inventory(tmp_path):
    llm, svc = service(tmp_path, json.dumps(GOOD))
    result = svc.suggest_target([("INTERES.cbl", LEGACY.encode())], None, None)
    assert result["suggestion"]["language"] == "java" and result["labels"]["framework"] == "Spring Boot 3"
    assert result["inventory"]["languages"][0]["name"] == "COBOL" and result["source_language"] == "cobol"
    assert result["sanitized_findings"] >= 1
    assert all(SECRET not in prompt for _, _, prompt in llm.calls)


def test_suggest_from_zip_with_delphi(tmp_path):
    _, svc = service(tmp_path, json.dumps({**GOOD, "language": "csharp", "framework": "aspnet"}))
    data = zip_bytes({"src/Calculos.pas": DELPHI, "src/Main.dfm": "object Form1: TForm1 end", "README.md": "x"})
    result = svc.suggest_target([("legacy.zip", data)], None, None)
    assert result["source_language"] == "delphi"
    assert {lang["name"] for lang in result["inventory"]["languages"]} == {"Delphi / Pascal", "Delphi (formulario)"}


def test_suggest_retries_when_option_not_in_catalog(tmp_path):
    llm, svc = service(tmp_path, json.dumps({**GOOD, "framework": "django"}), json.dumps(GOOD))
    assert svc.suggest_target([("INTERES.cbl", LEGACY.encode())], None, None)["suggestion"]["framework"] == "spring"
    assert "framework para java" in llm.calls[1][2]


def test_suggest_requires_source(tmp_path):
    _, svc = service(tmp_path, json.dumps(GOOD))
    with pytest.raises(ServiceError) as e:
        svc.suggest_target([], "", None)
    assert e.value.code == "NO_SOURCE" and e.value.action


def test_suggest_invalid_llm_output_maps_to_502(tmp_path):
    _, svc = service(tmp_path, "no es json")
    with pytest.raises(ServiceError) as e:
        svc.suggest_target([("INTERES.cbl", LEGACY.encode())], None, None)
    assert e.value.status == 502 and e.value.code == "INVALID_LLM_OUTPUT"


def test_catalog_shape_and_validation():
    data = catalog()
    assert {lang["id"] for lang in data["languages"]} == {"java", "csharp", "typescript", "python"}
    assert all("available" in lang and lang["frameworks"] for lang in data["languages"])
    assert is_valid("java", "spring", "hexagonal") is None
    assert is_valid("java", "aspnet", "hexagonal") and is_valid("cobol", "x", "y")
    with pytest.raises(ValueError):
        Suggestion.model_validate({**GOOD, "architecture": "serverless"})
