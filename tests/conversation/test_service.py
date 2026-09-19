"""Tests for ConversationService orchestrating sessions, turns, and plan generation."""

import pytest
from pathlib import Path

from autoslide.conversation.models import ConversationSession, ConversationState
from autoslide.conversation.service import (
    ConversationResponse,
    ConversationService,
    SelectionContext,
)
from autoslide.conversation.store import SessionStore
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
)
from autoslide.planner.models import TaskPlan


@pytest.fixture
def sample_inventory() -> DeckInventory:
    return DeckInventory(
        slide_count=2,
        dimensions=SlideDimensions(cx=12192000, cy=6858000),
        created_at="2026-09-19T00:00:00Z",
        source_sha256="test-sha256",
        slides=[
            SlideInventoryItem(
                slide_index=1,
                slide_id="slide-1",
                r_id="rId1",
                slide_path="ppt/slides/slide1.xml",
                shapes=[
                    ShapeInventoryItem(
                        shape_id="title-1",
                        shape_name="Title",
                        shape_type="title",
                        bounds=BoundingBox(),
                        fingerprint="fp-s1-title",
                        raw_text="Old Title",
                    )
                ],
            ),
            SlideInventoryItem(
                slide_index=2,
                slide_id="slide-2",
                r_id="rId2",
                slide_path="ppt/slides/slide2.xml",
                shapes=[],
            ),
        ],
    )



@pytest.fixture
def service(tmp_path: Path, sample_inventory: DeckInventory) -> ConversationService:
    store = SessionStore(base_dir=tmp_path)
    return ConversationService(
        store=store,
        inventory_provider=lambda job_id: sample_inventory,
    )



def test_vague_request_leaves_session_in_clarification_and_no_plan(service: ConversationService):
    """Vague prompt leaves session in NEEDS_CLARIFICATION with 0 TaskPlan mutation."""
    response = service.handle_message(
        session_id="sess-vague-1",
        message="Make this look much better",
    )

    assert isinstance(response, ConversationResponse)
    assert response.session.state == ConversationState.NEEDS_CLARIFICATION
    assert response.session.plan is None
    assert len(response.session.turns) == 2
    assert response.session.turns[0].role == "user"
    assert response.session.turns[1].role == "assistant"

    # Card must contain question card, no plan card
    assert len(response.cards) >= 1
    card_types = [c.get("type") for c in response.cards]
    assert "question" in card_types
    assert "plan" not in card_types


def test_complete_request_moves_to_waiting_plan_approval_with_typed_plan_card(
    service: ConversationService,
):
    """Complete prompt transitions session to WAITING_PLAN_APPROVAL and emits typed plan card."""
    response = service.handle_message(
        session_id="sess-complete-1",
        message="On slide 1, change the title to 'Q3 Financial Review'",
    )

    assert response.session.state == ConversationState.WAITING_PLAN_APPROVAL
    assert response.session.plan is not None
    assert isinstance(response.session.plan, TaskPlan)
    assert len(response.session.plan.operations) > 0

    # Must contain typed plan card
    card_types = [c.get("type") for c in response.cards]
    assert "plan" in card_types
    plan_card = next(c for c in response.cards if c.get("type") == "plan")
    assert plan_card["schema_version"] == "1.0"
    assert len(plan_card["operations"]) > 0


def test_service_persists_session_to_store(service: ConversationService):
    """ConversationService persists session updates atomically to SessionStore."""
    response = service.handle_message(
        session_id="sess-persist-1",
        message="On slide 1, change the title to 'Updated Title'",
    )

    reloaded = service.store.get("sess-persist-1")
    assert reloaded is not None
    assert reloaded.state == response.session.state
    assert len(reloaded.turns) == len(response.session.turns)
    assert reloaded.plan is not None


def test_service_follow_up_turn_completes_plan(service: ConversationService):
    """Two-turn dialogue merges clarification and transitions to WAITING_PLAN_APPROVAL."""
    # Turn 1: Vague request missing content
    resp1 = service.handle_message(
        session_id="sess-multi-1",
        message="On slide 1, change the title",
    )
    assert resp1.session.state == ConversationState.NEEDS_CLARIFICATION
    assert resp1.session.plan is None

    # Turn 2: User provides missing title content
    resp2 = service.handle_message(
        session_id="sess-multi-1",
        message="Set the title to '2026 Strategy'",
    )
    assert resp2.session.state == ConversationState.WAITING_PLAN_APPROVAL
    assert resp2.session.plan is not None
    assert len(resp2.session.turns) == 4


def test_service_with_selection_context(service: ConversationService):
    """SelectionContext supplies slide targeting for prompt lacking slide number."""
    response = service.handle_message(
        session_id="sess-ctx-1",
        message="Change the title to 'Contextual Title'",
        context=SelectionContext(slide_index=1),
    )

    assert response.session.state == ConversationState.WAITING_PLAN_APPROVAL
    assert response.session.plan is not None
    assert response.session.plan.target_scope[0].slide_index == 1
