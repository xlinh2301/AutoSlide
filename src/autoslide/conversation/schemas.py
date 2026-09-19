"""Pydantic schemas for AutoSlide conversation session API endpoints."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from autoslide.conversation.models import (
    ConversationSession,
    ConversationState,
    EditBrief,
    SourceRecord,
)
from autoslide.conversation.service import SelectionContext
from autoslide.planner.models import TaskPlan


class CreateSessionResponse(BaseModel):
    """Response returned when a new conversational session is created."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    job_id: str | None
    state: ConversationState


class SendMessageRequest(BaseModel):
    """Payload for submitting a user message to an active conversational session."""

    message: str
    selection_context: SelectionContext | None = None


class ApproveDecisionRequest(BaseModel):
    """Payload for approving or revising a plan or source set."""

    kind: Literal["plan", "sources"]
    approved: bool
    feedback: str | None = None


class ApproveDecisionResponse(BaseModel):
    """Response returned after processing an approval decision."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    state: ConversationState
    message: str


class ExecuteSessionResponse(BaseModel):
    """Response returned when an approved session starts background execution."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    job_id: str
    state: ConversationState
    message: str


class SessionDetailResponse(BaseModel):
    """Complete inspection representation of a conversational session."""

    model_config = ConfigDict(frozen=True)

    session: ConversationSession
    brief: EditBrief | None = None
    plan: TaskPlan | None = None
    sources: list[SourceRecord] = Field(default_factory=list)
    active_job: dict[str, Any] | None = None


class SessionEventsResponse(BaseModel):
    """Redacted event log entries associated with a conversational session."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
