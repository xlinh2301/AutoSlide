"""Fixtures for Phase 4 PPTX Executor tests: sample decks and execution task plans."""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

from autoslide.planner.models import (
    BoundingBoxUpdate,
    DeleteSlideOp,
    DuplicateSlideOp,
    FormatTextOp,
    MoveResizeShapeOp,
    ReplaceTextOp,
    TargetReference,
    TargetScope,
    TaskPlan,
)
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def create_sample_executor_deck() -> bytes:
    """Create a sample 2-slide deck for executor mutation tests."""
    return create_complex_multi_slide_pptx()
