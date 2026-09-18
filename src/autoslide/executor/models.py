"""Data models for structural diff and execution results."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class PropertyChange(BaseModel):
    """Represents an atomic property modification on a slide object."""

    slide_index: int
    shape_name: str
    object_ref: str | None = None
    property_name: str
    old_value: Any = None
    new_value: Any = None


class ShapeDiff(BaseModel):
    """Detailed structural difference for a single shape across execution."""

    slide_index: int
    shape_name: str
    old_fingerprint: str
    new_fingerprint: str
    changes: list[PropertyChange] = Field(default_factory=list)


class SlideDiff(BaseModel):
    """Structural differences recorded on a per-slide basis."""

    slide_index: int
    status: str = "unchanged"  # "unchanged", "modified", "added", "deleted"
    shape_diffs: list[ShapeDiff] = Field(default_factory=list)


class StructuralDiff(BaseModel):
    """Complete machine-readable audit report comparing before and after presentation state."""

    slide_count_before: int
    slide_count_after: int
    intended_changes: list[PropertyChange] = Field(default_factory=list)
    unintended_changes: list[PropertyChange] = Field(default_factory=list)
    slide_diffs: list[SlideDiff] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    """Comprehensive outcome of executing a TaskPlan on a PPTX presentation."""

    success: bool
    working_path: Path
    checkpoints_count: int = 0
    last_checkpoint_id: str | None = None
    structural_diff: StructuralDiff | None = None
    error: str | None = None
