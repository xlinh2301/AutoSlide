"""Error hierarchy for the Phase 3 Edit Planner module."""

from __future__ import annotations


class PlannerError(Exception):
    """Base exception for planner operations and policy evaluation."""


class PolicyViolationError(PlannerError):
    """Raised when an operation or plan violates safety, preservation, or scope rules."""


class AmbiguousTargetError(PlannerError):
    """Raised when an operation refers to an ambiguous or non-existent target reference."""


class LowConfidenceError(PlannerError):
    """Raised in strict mode when a planned operation's confidence falls below threshold."""


class UnknownOperationError(PlannerError):
    """Raised when an operation is outside the allowlisted vocabulary."""


class MalformedPlanError(PlannerError):
    """Raised when raw plan text cannot be parsed into valid TaskPlan JSON."""
