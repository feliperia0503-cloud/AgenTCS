"""Contratos del núcleo agnóstico de lenguaje de AgenTCS.

Origen (SourceAdapter) -> AnalysisResult -> Spec neutral (HITL) -> TargetAdapter -> código
Verificación: Case (cases.json) -> CaseOutput (expected.json / actual.json) -> VerificationReport

Cambiar estos contratos afecta a los 3 roles: acordarlo en equipo.
"""
from .adapters import (
    BuildResult, LegacyRunner, PackInfo, PackRole, QualityFinding, QualityReport,
    SourceAdapter, TargetAdapter, TestResult,
)
from .analysis import (
    AnalysisResult, Classification, Dependency, Metrics, RiskItem, SanitizationFinding,
    SourceFile, Unit, UnitKind, Variable,
)
from .spec import (
    LOW_CONFIDENCE, DataField, Entity, ErrorCode, IOContract, Review, Rule, RuleCategory,
    RuleStatus, SourceRef, Spec,
)
from .state import LLMCall, Phase, PhaseRecord, PhaseStatus, RunState
from .types import NeutralType, Rounding, TypeKind, decimal_str
from .verification import (
    Case, CaseError, CaseOutput, Difference, OracleLevel, VerificationReport,
)

__all__ = [n for n in dir() if not n.startswith("_")]
