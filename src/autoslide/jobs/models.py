"""Domain models for AutoSlide job workspaces and registry."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict


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


class JobRecord(BaseModel):
    """Immutable snapshot of a registered job in SQLite registry."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    state: JobState
    instruction: str
    input_sha256: str
    created_at: str
    updated_at: str


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
