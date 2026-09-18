"""Fixtures for Phase 6 Workbench tests: decisions, mock previews, and orchestrator payloads."""

from __future__ import annotations

from pathlib import Path

from autoslide.jobs.models import JobDecisionRequest, JobState
from autoslide.planner.models import (
    OperationType,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)


def create_sample_decision_approve() -> JobDecisionRequest:
    """Create an approve decision payload."""
    return JobDecisionRequest(
        decision="approve",
        feedback="Looks great! Approved.",
    )


def create_sample_decision_reject() -> JobDecisionRequest:
    """Create a reject decision payload."""
    return JobDecisionRequest(
        decision="reject",
        feedback="Changes are not compliant with style guide.",
    )


def create_sample_decision_repair() -> JobDecisionRequest:
    """Create a repair request decision payload."""
    return JobDecisionRequest(
        decision="repair",
        feedback="Title text is still slightly overflowing on slide 1.",
    )


def create_mock_task_plan() -> TaskPlan:
    """Create a valid TaskPlan for pipeline tests."""
    return TaskPlan(
        schema_version="1.0",
        target_scope=[
            TargetScope(slide_index=1, object_ref="fp_sample_123")
        ],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=1, object_ref="fp_sample_123"),
                value="AutoSlide Automated Title",
                confidence=0.98,
            )
        ],
        requires_review=False,
    )
