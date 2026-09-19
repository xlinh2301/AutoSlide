"""ConversationService coordinating dialogue, clarification questions, and plan approval."""

from __future__ import annotations

import uuid
from typing import Any, Callable
from pydantic import BaseModel, ConfigDict, Field

from autoslide.conversation.clarification import ClarificationEngine
from autoslide.conversation.models import (
    ChatTurn,
    ConversationSession,
    ConversationState,
)
from autoslide.conversation.store import SessionStore
from autoslide.ingest.models import DeckInventory
from autoslide.planner.builder import PromptPayloadBuilder


class SelectionContext(BaseModel):
    """UI selection context capturing highlighted slide, element, or text range."""

    model_config = ConfigDict(frozen=True)

    slide_index: int | None = None
    object_ref: str | None = None
    selected_text: str | None = None


class ConversationResponse(BaseModel):
    """Structured response payload from ConversationService for assistant turns."""

    model_config = ConfigDict(frozen=True)

    session: ConversationSession
    assistant_message: str
    cards: list[dict[str, Any]] = Field(default_factory=list)


class ConversationService:
    """Coordinates conversational sessions, clarification logic, and typed plan synthesis."""

    def __init__(
        self,
        store: SessionStore | None = None,
        engine: ClarificationEngine | None = None,
        planner_builder: PromptPayloadBuilder | None = None,
        inventory_provider: Callable[[str | None], DeckInventory | None] | None = None,
    ):
        self.store = store or SessionStore()
        self.engine = engine or ClarificationEngine()
        self.planner_builder = planner_builder or PromptPayloadBuilder()
        self.inventory_provider = inventory_provider

    def handle_message(
        self,
        session_id: str,
        message: str,
        context: SelectionContext | None = None,
    ) -> ConversationResponse:
        """Process incoming user turn, evaluate clarification, and advance session state."""
        try:
            session = self.store.get(session_id)
        except FileNotFoundError:
            session = ConversationSession.new(session_id=session_id)


        # 1. Append user turn
        user_turn = ChatTurn(
            id=str(uuid.uuid4()),
            role="user",
            content=message,
        )
        session = session.with_turn(user_turn)

        # 2. Acquire current deck inventory if provider configured
        inventory: DeckInventory | None = None
        if self.inventory_provider:
            inventory = self.inventory_provider(session.job_id)

        # 3. Assess message completeness
        result = self.engine.assess(
            message=message,
            inventory=inventory,
            previous_brief=session.brief,
            context=context,
        )

        cards: list[dict[str, Any]] = []

        # 4. Handle complete vs incomplete request
        if result.brief and result.brief.complete:
            # Build typed TaskPlan from complete brief
            plan = self.planner_builder.build_plan_from_brief(result.brief, inventory=inventory)

            # Advance state machine to WAITING_PLAN_APPROVAL
            if session.state == ConversationState.NEEDS_CLARIFICATION:
                session = session.transition(ConversationState.READY_FOR_PLAN)
                session = session.transition(ConversationState.WAITING_PLAN_APPROVAL)
            elif session.state == ConversationState.READY_FOR_PLAN:
                session = session.transition(ConversationState.WAITING_PLAN_APPROVAL)
            elif session.state != ConversationState.WAITING_PLAN_APPROVAL:
                # Attempt standard path if re-entering from another state
                try:
                    session = session.transition(ConversationState.READY_FOR_PLAN)
                    session = session.transition(ConversationState.WAITING_PLAN_APPROVAL)
                except Exception:
                    pass

            session = session.with_brief(result.brief)
            session = session.with_plan(plan)

            plan_card = plan.to_card()
            cards.append(plan_card)

            assistant_turn = ChatTurn(
                id=str(uuid.uuid4()),
                role="assistant",
                content=result.assistant_message,
                card=plan_card,
            )
            session = session.with_turn(assistant_turn)
        else:
            # Ambiguous or missing fields: keep in NEEDS_CLARIFICATION, no TaskPlan mutation
            if session.state != ConversationState.NEEDS_CLARIFICATION:
                try:
                    session = session.transition(ConversationState.NEEDS_CLARIFICATION)
                except Exception:
                    pass

            session = session.with_brief(result.brief)

            question_card = {
                "type": "question",
                "questions": [q.model_dump() for q in result.questions],
            }
            cards.append(question_card)

            assistant_turn = ChatTurn(
                id=str(uuid.uuid4()),
                role="assistant",
                content=result.assistant_message,
                card=question_card,
            )
            session = session.with_turn(assistant_turn)

        # 5. Persist checkpoint and return structured response
        saved_session = self.store.save(session)
        return ConversationResponse(
            session=saved_session,
            assistant_message=result.assistant_message,
            cards=cards,
        )
