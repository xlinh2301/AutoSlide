"""Error hierarchy for the Phase 4 PPTX Executor module."""

from __future__ import annotations


class ExecutorError(Exception):
    """Base exception for executor operations."""


class TargetNotFoundError(ExecutorError):
    """Raised when an operation's target object or slide cannot be located in the presentation."""


class MutationRollbackError(ExecutorError):
    """Raised when an execution fails and the working copy has been safely rolled back."""


class UnintendedMutationError(ExecutorError):
    """Raised when structural diff reveals collateral changes outside the declared target scope."""
