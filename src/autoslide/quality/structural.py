"""Structural acceptance gate evaluating executor StructuralDiff against collateral mutations."""

from __future__ import annotations

from autoslide.executor.models import StructuralDiff
from autoslide.quality.errors import StructuralRejectionError
from autoslide.quality.models import StructuralGateResult


class StructuralAcceptanceGate:
    """Evaluates whether all planned mutations succeeded with zero unintended collateral damage."""

    def __init__(self, strict: bool = False):
        self.strict = strict

    def evaluate(self, structural_diff: StructuralDiff) -> StructuralGateResult:
        violations: list[str] = []

        if structural_diff.unintended_changes:
            for uc in structural_diff.unintended_changes:
                violations.append(
                    f"Unintended collateral modification on slide {uc.slide_index}: "
                    f"shape '{uc.shape_name}' property '{uc.property_name}' was altered."
                )

        if violations:
            if self.strict:
                raise StructuralRejectionError("; ".join(violations))
            return StructuralGateResult(
                passed=False,
                verdict="FAILED",
                intended_count=len(structural_diff.intended_changes),
                unintended_violations=violations,
            )

        return StructuralGateResult(
            passed=True,
            verdict="PASSED",
            intended_count=len(structural_diff.intended_changes),
            unintended_violations=[],
        )
