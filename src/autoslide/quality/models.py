"""Pydantic data models for Quality Gates, Visual Findings, and Repair Loop Decisions."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    """Severity levels for quality gate findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class FindingCategory(str, Enum):
    """Categorization for visual and structural quality findings."""

    TEXT_OVERFLOW = "TEXT_OVERFLOW"
    BOUNDS_CLIPPING = "BOUNDS_CLIPPING"
    MISSING_TARGET = "MISSING_TARGET"
    RENDER_FAILURE = "RENDER_FAILURE"
    COLLATERAL_CHANGE = "COLLATERAL_CHANGE"


class VisualFinding(BaseModel):
    """Detailed visual defect or layout anomaly detected on a slide."""

    slide_index: int
    shape_name: str
    object_ref: str | None = None
    category: FindingCategory
    severity: FindingSeverity = FindingSeverity.ERROR
    message: str
    suggested_fix: str | None = None


class StructuralGateResult(BaseModel):
    """Outcome of structural acceptance evaluation."""

    passed: bool
    verdict: Literal["PASSED", "FAILED"]
    intended_count: int = 0
    unintended_violations: list[str] = Field(default_factory=list)


class VisualGateResult(BaseModel):
    """Outcome of visual quality evaluation across all rendered slides."""

    passed: bool
    findings: list[VisualFinding] = Field(default_factory=list)
    has_critical_or_error: bool = False


class QualityReport(BaseModel):
    """Consolidated evidence report combining structural and visual gate evaluations."""

    overall_verdict: Literal["PASSED", "FAILED", "NEEDS_REVIEW"]
    structural_result: StructuralGateResult
    visual_result: VisualGateResult
    generated_at: str
    repair_attempts_count: int = 0


class RepairDecision(BaseModel):
    """Decision emitted by the repair controller determining whether to accept, repair, or escalate."""

    action: Literal["ACCEPT", "REPAIR", "ESCALATE_REVIEW"]
    attempt: int = 1
    repair_instruction: str | None = None
    reason: str | None = None
