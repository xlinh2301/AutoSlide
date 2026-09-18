"""Tests for RepairLoopController: attempt counting, repair prompt construction, and escalation."""

from __future__ import annotations

import pytest

from autoslide.quality.models import (
    FindingCategory,
    FindingSeverity,
    StructuralGateResult,
    VisualFinding,
)
from autoslide.quality.repair import RepairLoopController


def test_repair_decision_generates_repair_instruction():
    controller = RepairLoopController(max_repair_attempts=3)

    findings = [
        VisualFinding(
            slide_index=1,
            shape_name="Title 1",
            object_ref="fp123",
            category=FindingCategory.TEXT_OVERFLOW,
            severity=FindingSeverity.ERROR,
            message="Text overflows bounding box by approx 40%",
            suggested_fix="Reduce font size by 20% or enlarge bounding box",
        )
    ]
    struct_result = StructuralGateResult(passed=True, verdict="PASSED")

    decision = controller.decide(
        attempt=1,
        visual_findings=findings,
        structural_result=struct_result,
    )

    assert decision.action == "REPAIR"
    assert decision.repair_instruction is not None
    assert "Reduce font size" in decision.repair_instruction or "overflows" in decision.repair_instruction


def test_repair_decision_escalates_on_max_attempts():
    controller = RepairLoopController(max_repair_attempts=3)

    findings = [
        VisualFinding(
            slide_index=1,
            shape_name="Title 1",
            category=FindingCategory.TEXT_OVERFLOW,
            severity=FindingSeverity.ERROR,
            message="Text overflows bounding box",
        )
    ]
    struct_result = StructuralGateResult(passed=True, verdict="PASSED")

    # Attempt 3 reaches max_repair_attempts -> must escalate
    decision = controller.decide(
        attempt=3,
        visual_findings=findings,
        structural_result=struct_result,
    )

    assert decision.action == "ESCALATE_REVIEW"
    assert "Max repair attempts (3) reached" in decision.reason


def test_repair_decision_accepts_clean_gates():
    controller = RepairLoopController(max_repair_attempts=3)
    struct_result = StructuralGateResult(passed=True, verdict="PASSED")

    decision = controller.decide(
        attempt=1,
        visual_findings=[],
        structural_result=struct_result,
    )

    assert decision.action == "ACCEPT"
