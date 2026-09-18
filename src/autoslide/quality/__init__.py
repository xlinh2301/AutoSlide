"""Quality gates package for structural acceptance, visual defect analysis, and repair management."""

from __future__ import annotations

from autoslide.quality.errors import (
    MaxRepairAttemptsExceededError,
    QualityGateError,
    StructuralRejectionError,
)
from autoslide.quality.models import (
    FindingCategory,
    FindingSeverity,
    QualityReport,
    RepairDecision,
    StructuralGateResult,
    VisualFinding,
    VisualGateResult,
)
from autoslide.quality.repair import RepairLoopController
from autoslide.quality.structural import StructuralAcceptanceGate
from autoslide.quality.visual import VisualQualityGate

__all__ = [
    "FindingCategory",
    "FindingSeverity",
    "MaxRepairAttemptsExceededError",
    "QualityGateError",
    "QualityReport",
    "RepairDecision",
    "RepairLoopController",
    "StructuralAcceptanceGate",
    "StructuralGateResult",
    "StructuralRejectionError",
    "VisualFinding",
    "VisualGateResult",
    "VisualQualityGate",
]
