"""Exporta JSON Schema de los contratos a copilot/contracts/schemas/.

Usos: salida estructurada del LLM (Spec, Rule), validación en harness de destino de cualquier
lenguaje (Case, CaseOutput) y tipos para la UI.

    python -m copilot.contracts.export_schemas
"""
import json
from pathlib import Path

from . import AnalysisResult, Case, CaseOutput, Rule, Spec, VerificationReport

MODELS = {
    "spec": Spec, "rule": Rule, "analysis": AnalysisResult,
    "case": Case, "case_output": CaseOutput, "verification_report": VerificationReport,
}


def main() -> None:
    out = Path(__file__).parent / "schemas"
    out.mkdir(exist_ok=True)
    for name, model in MODELS.items():
        (out / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"ok  {name}.schema.json")


if __name__ == "__main__":
    main()
