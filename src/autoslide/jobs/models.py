"""Domain models for AutoSlide job workspaces, registry, preview diffs, and edit scopes."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class JobState(str, Enum):
    """Lifecycle states for an AutoSlide job execution."""

    CREATED = "CREATED"
    INGESTING = "INGESTING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    RENDERING = "RENDERING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    AWAITING_USER_APPROVAL = "AWAITING_USER_APPROVAL"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NormalizedRegion(BaseModel):
    """Region within a slide normalized to viewport coordinates [0.0, 1.0]."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)


class EditScope(BaseModel):
    """Target scope declaration for an edit job (slide, deck, or region)."""

    kind: Literal["deck", "slide", "region"] = "slide"
    slide_index: int | None = None
    region: NormalizedRegion | None = None


class OverlayBox(BaseModel):
    """Visual bounding box overlay representing an edited region or shape."""

    x: float
    y: float
    width: float
    height: float
    shape_name: str
    object_ref: str | None = None
    change_type: str = "modified"


class SlidePreviewDiff(BaseModel):
    """Side-by-side preview pair and highlight overlays for a slide."""

    slide_index: int
    before_image_url: str
    after_image_url: str
    status: str = "unchanged"  # "modified", "unchanged", "added", "deleted"
    changed_object_refs: list[str] = Field(default_factory=list)
    overlays: list[OverlayBox] = Field(default_factory=list)


class DeckPreviewDiff(BaseModel):
    """Complete set of preview diff pairs across all slides in the deck."""

    job_id: str
    total_slides: int
    changed_slides_count: int
    slides: list[SlidePreviewDiff] = Field(default_factory=list)


class JobRecord(BaseModel):
    """Immutable snapshot of a registered job in SQLite registry."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    state: JobState
    instruction: str
    input_sha256: str
    created_at: str
    updated_at: str
    scope: EditScope | None = None


class CheckpointRecord(BaseModel):
    """Immutable record of an intermediate job artifact checkpoint."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    job_id: str
    stage: str
    path: Path
    sha256: str
    created_at: str
    parent_checkpoint_id: str | None = None


class JobDecisionRequest(BaseModel):
    """Payload for submitting human review decisions (approve, reject, repair)."""

    decision: Literal["approve", "reject", "repair"]
    feedback: str | None = None


class JobDecisionResponse(BaseModel):
    """Response returned after processing a human review decision."""

    job_id: str
    state: JobState
    message: str
    download_url: str | None = None
