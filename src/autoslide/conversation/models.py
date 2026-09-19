"""Pydantic v2 data models for conversational agent sessions, turns, briefs, and sources."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from autoslide.planner.models import TargetScope, TaskPlan


class ConversationState(str, Enum):
    """Lifecycle states of an always-on conversational agent session."""

    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY_FOR_PLAN = "READY_FOR_PLAN"
    WAITING_PLAN_APPROVAL = "WAITING_PLAN_APPROVAL"
    RESEARCHING = "RESEARCHING"
    WAITING_SOURCE_APPROVAL = "WAITING_SOURCE_APPROVAL"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTING = "EXECUTING"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ChatTurn(BaseModel):
    """Represents a single immutable turn in a multi-turn conversation."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: Literal["user", "assistant", "tool"]
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    card: dict[str, Any] | None = None


class EditBrief(BaseModel):
    """Structured intermediate brief synthesized from user dialogue."""

    model_config = ConfigDict(frozen=True)

    goal: str
    target_scope: list[TargetScope] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    complete: bool = False


class SourceRecord(BaseModel):
    """External or research source cited in support of presentation edits."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    url: str
    title: str
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str = ""
    claims: list[str] = Field(default_factory=list)
    approved: bool = False


class ConversationSession(BaseModel):
    """Immutable conversation session coordinating turns, brief, plan, and state."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    job_id: str | None = None
    state: ConversationState = ConversationState.NEEDS_CLARIFICATION
    turns: list[ChatTurn] = Field(default_factory=list)
    brief: EditBrief | None = None
    plan: TaskPlan | None = None
    sources: list[SourceRecord] = Field(default_factory=list)
    checkpoint_path: str = ""

    @classmethod
    def new(
        cls,
        session_id: str,
        job_id: str | None = None,
        checkpoint_path: str = "",
    ) -> ConversationSession:
        """Factory for a fresh conversation session starting in clarification."""
        return cls(
            session_id=session_id,
            job_id=job_id,
            state=ConversationState.NEEDS_CLARIFICATION,
            turns=[],
            brief=None,
            plan=None,
            sources=[],
            checkpoint_path=checkpoint_path,
        )

    def with_turn(self, turn: ChatTurn) -> ConversationSession:
        """Return a new session instance with the appended turn."""
        return self.model_copy(update={"turns": [*self.turns, turn]})

    def with_brief(self, brief: EditBrief | None) -> ConversationSession:
        """Return a new session instance with the updated brief."""
        return self.model_copy(update={"brief": brief})

    def with_plan(self, plan: TaskPlan | None) -> ConversationSession:
        """Return a new session instance with the updated plan."""
        return self.model_copy(update={"plan": plan})

    def with_sources(self, sources: list[SourceRecord]) -> ConversationSession:
        """Return a new session instance with the updated source records."""
        return self.model_copy(update={"sources": list(sources)})

    def transition(self, target_state: ConversationState) -> ConversationSession:
        """Transition session to target_state after validating transition rules."""
        from autoslide.conversation.state import validate_transition

        validate_transition(self.state, target_state)
        return self.model_copy(update={"state": target_state})
