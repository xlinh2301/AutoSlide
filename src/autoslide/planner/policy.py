"""Policy gate and validation engine for TaskPlans."""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from pydantic import BaseModel, Field, ValidationError

from autoslide.ingest.models import DeckInventory
from autoslide.planner.errors import (
    AmbiguousTargetError,
    LowConfidenceError,
    MalformedPlanError,
    PolicyViolationError,
    UnknownOperationError,
)
from autoslide.planner.models import (
    DeleteSlideOp,
    DuplicateSlideOp,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceImageOp,
    ReplaceTextOp,
    TaskPlan,
)
from autoslide.planner.vocabulary import ALLOWLISTED_OPERATIONS

DANGEROUS_PATTERNS = (
    "__import__",
    "os.system",
    "subprocess.",
    "eval(",
    "exec(",
    "shutil.rmtree",
    "rm -rf",
    "/bin/sh",
    "/bin/bash",
)


class PolicyEvaluationResult(BaseModel):
    """Result of policy gate validation on a TaskPlan."""

    verdict: Literal["APPROVED", "REJECTED", "NEEDS_REVIEW"]
    requires_review: bool = False
    violations: list[str] = Field(default_factory=list)
    plan: TaskPlan | None = None


class PolicyGate:
    """Evaluates TaskPlans against preservation rules, confidence thresholds, and safety policies."""

    def __init__(self, min_confidence: float = 0.80, strict: bool = True):
        self.min_confidence = min_confidence
        self.strict = strict

    def parse_plan_json(self, raw_text: str) -> TaskPlan:
        """Extract and parse TaskPlan JSON from raw agent string output."""
        cleaned = raw_text.strip()
        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise MalformedPlanError(f"Failed to parse JSON plan: {exc}") from exc

        try:
            return TaskPlan.model_validate(data)
        except ValidationError as exc:
            raise MalformedPlanError(f"Schema validation error in TaskPlan: {exc}") from exc

    def evaluate(self, plan: TaskPlan, inventory: DeckInventory) -> PolicyEvaluationResult:
        """Validate safety, operation vocabulary, target references, and confidence."""
        violations: list[str] = []

        # 1. Safety check for dangerous patterns
        plan_str = plan.model_dump_json()
        for pat in DANGEROUS_PATTERNS:
            if pat in plan_str:
                raise PolicyViolationError(f"Dangerous code injection pattern detected in plan: '{pat}'")

        # 2. Build index of valid targets in inventory
        valid_slides: set[int] = {s.slide_index for s in inventory.slides}
        valid_fps: set[tuple[int, str]] = set()

        for slide in inventory.slides:
            for shape in slide.shapes:
                valid_fps.add((slide.slide_index, shape.fingerprint))
                if shape.children:
                    for child in shape.children:
                        valid_fps.add((slide.slide_index, child.fingerprint))

        # 3. Check each operation
        for op in plan.operations:
            # Operation type allowlist
            if op.op.value not in ALLOWLISTED_OPERATIONS:
                raise UnknownOperationError(f"Operation '{op.op.value}' is not in allowlisted vocabulary")

            # Confidence threshold check
            if op.confidence < self.min_confidence:
                msg = f"Confidence {op.confidence} is below threshold {self.min_confidence}"
                if self.strict:
                    raise LowConfidenceError(msg)
                violations.append(msg)

            # Target reference validity
            target_slide: int | None = None
            target_obj: str | None = None

            if isinstance(op, (ReplaceTextOp, FormatTextOp, ReplaceImageOp, MoveResizeShapeOp)):
                target_slide = op.target.slide_index
                target_obj = op.target.object_ref

                if target_obj is not None:
                    if (target_slide, target_obj) not in valid_fps:
                        msg = f"Target object_ref '{target_obj}' on slide {target_slide} not found in inventory"
                        if self.strict:
                            raise AmbiguousTargetError(msg)
                        violations.append(msg)
            elif isinstance(op, DuplicateSlideOp):
                target_slide = op.source_slide_index
                if target_slide not in valid_slides:
                    msg = f"Duplicate slide source {target_slide} not found in inventory"
                    if self.strict:
                        raise AmbiguousTargetError(msg)
                    violations.append(msg)
            elif isinstance(op, DeleteSlideOp):
                target_slide = op.slide_index
                if target_slide not in valid_slides:
                    msg = f"Delete slide target {target_slide} not found in inventory"
                    if self.strict:
                        raise AmbiguousTargetError(msg)
                    violations.append(msg)

            # Scope containment check
            if target_slide is not None and plan.target_scope:
                covered = False
                for scope in plan.target_scope:
                    if scope.slide_index == target_slide:
                        if scope.object_ref is None or scope.object_ref == target_obj:
                            covered = True
                            break
                if not covered:
                    msg = f"Operation target (slide {target_slide}, ref {target_obj}) not covered by target_scope"
                    if self.strict:
                        raise PolicyViolationError(msg)
                    violations.append(msg)

        if violations:
            return PolicyEvaluationResult(
                verdict="NEEDS_REVIEW",
                requires_review=True,
                violations=violations,
                plan=plan,
            )

        return PolicyEvaluationResult(
            verdict="APPROVED",
            requires_review=plan.requires_review,
            violations=[],
            plan=plan,
        )
