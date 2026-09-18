"""Bounded repair loop controller managing error remediation and human escalation."""

from __future__ import annotations

from autoslide.quality.models import (
    FindingSeverity,
    RepairDecision,
    StructuralGateResult,
    VisualFinding,
)


class RepairLoopController:
    """Controls iterative repair cycles, generating remediation instructions and escalating when budget is exhausted."""

    def __init__(self, max_repair_attempts: int = 3):
        self.max_repair_attempts = max_repair_attempts

    def decide(
        self,
        attempt: int,
        visual_findings: list[VisualFinding],
        structural_result: StructuralGateResult,
    ) -> RepairDecision:
        # Check structural failure first
        if not structural_result.passed:
            if attempt >= self.max_repair_attempts:
                reason = (
                    f"Max repair attempts ({self.max_repair_attempts}) reached. "
                    f"Structural gate violations: {'; '.join(structural_result.unintended_violations)}"
                )
                return RepairDecision(
                    action="ESCALATE_REVIEW",
                    attempt=attempt,
                    reason=reason,
                )
            else:
                instructions = [
                    f"Revert unintended collateral modifications: {v}"
                    for v in structural_result.unintended_violations
                ]
                return RepairDecision(
                    action="REPAIR",
                    attempt=attempt,
                    repair_instruction="; ".join(instructions),
                    reason="Structural gate detected collateral changes requiring reversion",
                )

        # Check visual defects
        blocking_findings = [
            f for f in visual_findings if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.ERROR)
        ]

        if not blocking_findings:
            return RepairDecision(
                action="ACCEPT",
                attempt=attempt,
                reason="All quality gates passed successfully.",
            )

        if attempt >= self.max_repair_attempts:
            reason = (
                f"Max repair attempts ({self.max_repair_attempts}) reached with "
                f"{len(blocking_findings)} unresolved visual defect(s)."
            )
            return RepairDecision(
                action="ESCALATE_REVIEW",
                attempt=attempt,
                reason=reason,
            )

        # Formulate repair instructions
        instructions: list[str] = []
        for finding in blocking_findings:
            fix = finding.suggested_fix or finding.message
            instructions.append(f"Slide {finding.slide_index} shape '{finding.shape_name}': {fix}")

        return RepairDecision(
            action="REPAIR",
            attempt=attempt,
            repair_instruction="; ".join(instructions),
            reason=f"Detected {len(blocking_findings)} defect(s) requiring automated remediation",
        )
