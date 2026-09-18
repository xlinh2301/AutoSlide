"""Error definitions for the Phase 5 Quality Gates module."""

from __future__ import annotations


class QualityGateError(Exception):
    """Base exception for quality gate rejections and failures."""


class StructuralRejectionError(QualityGateError):
    """Raised when structural acceptance fails due to unintended collateral mutations."""


class VisualRejectionError(QualityGateError):
    """Raised when critical visual defects are detected on output slides."""


class MaxRepairAttemptsExceededError(QualityGateError):
    """Raised when the bounded repair loop exceeds maximum configured attempts."""
