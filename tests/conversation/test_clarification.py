"""Tests for ClarificationEngine deterministic assessment and question generation."""

import pytest

from autoslide.conversation.clarification import (
    ClarificationEngine,
    ClarificationResult,
    Question,
)
from autoslide.conversation.models import ConversationState, EditBrief
from autoslide.conversation.service import SelectionContext
from autoslide.conversation.clarification import (
    ClarificationEngine,
    ClarificationResult,
    Question,
)
from autoslide.conversation.models import ConversationState, EditBrief
from autoslide.conversation.service import SelectionContext
from autoslide.ingest.models import (
    BoundingBox,
    DeckInventory,
    ShapeInventoryItem,
    SlideDimensions,
    SlideInventoryItem,
)
from autoslide.planner.models import TargetScope


@pytest.fixture
def sample_inventory() -> DeckInventory:
    """Fixture providing a sample 3-slide DeckInventory."""
    return DeckInventory(
        slide_count=3,
        dimensions=SlideDimensions(cx=12192000, cy=6858000),
        created_at="2026-09-19T00:00:00Z",
        source_sha256="mock-sha256",
        slides=[
            SlideInventoryItem(
                slide_index=1,
                slide_id="slide-1-id",
                r_id="rId1",
                slide_path="ppt/slides/slide1.xml",
                shapes=[
                    ShapeInventoryItem(
                        shape_id="title-1",
                        shape_name="Title 1",
                        shape_type="title",
                        bounds=BoundingBox(),
                        fingerprint="fp-slide1-title",
                        raw_text="Original Title",
                        placeholder_type="title",
                    ),
                    ShapeInventoryItem(
                        shape_id="sub-1",
                        shape_name="Subtitle 1",
                        shape_type="body",
                        bounds=BoundingBox(),
                        fingerprint="fp-slide1-sub",
                        raw_text="Original Subtitle",
                    ),
                ],
            ),
            SlideInventoryItem(
                slide_index=2,
                slide_id="slide-2-id",
                r_id="rId2",
                slide_path="ppt/slides/slide2.xml",
                shapes=[
                    ShapeInventoryItem(
                        shape_id="title-2",
                        shape_name="Title 2",
                        shape_type="title",
                        bounds=BoundingBox(),
                        fingerprint="fp-slide2-title",
                        raw_text="Agenda",
                        placeholder_type="title",
                    )
                ],
            ),
            SlideInventoryItem(
                slide_index=3,
                slide_id="slide-3-id",
                r_id="rId3",
                slide_path="ppt/slides/slide3.xml",
                shapes=[],
            ),
        ],
    )



def test_vague_request_produces_one_targeted_question(sample_inventory: DeckInventory):
    """Vague prompt must produce exactly 1 targeted question and remain in NEEDS_CLARIFICATION."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="Make this look much better and modernize it",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert isinstance(result, ClarificationResult)
    assert result.state == ConversationState.NEEDS_CLARIFICATION
    assert len(result.questions) == 1
    assert isinstance(result.questions[0], Question)
    assert result.brief is not None
    assert result.brief.complete is False
    assert len(result.brief.missing_fields) > 0


def test_missing_slide_target_asks_for_target(sample_inventory: DeckInventory):
    """Prompt specifying action and content but lacking slide target asks for target slide."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="Change the title to 'Q3 Financial Highlights'",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert result.state == ConversationState.NEEDS_CLARIFICATION
    assert len(result.questions) == 1
    assert result.questions[0].field == "target"
    assert "target" in result.brief.missing_fields
    assert result.brief.complete is False


def test_missing_content_asks_for_content(sample_inventory: DeckInventory):
    """Prompt targeting a slide but lacking concrete new content asks for content."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="On slide 1, change the title",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert result.state == ConversationState.NEEDS_CLARIFICATION
    assert len(result.questions) == 1
    assert result.questions[0].field == "content"
    assert "content" in result.brief.missing_fields
    assert result.brief.complete is False


def test_missing_action_asks_for_action(sample_inventory: DeckInventory):
    """Prompt targeting a slide element without clear action asks for action."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="Regarding slide 2, the agenda shape",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert result.state == ConversationState.NEEDS_CLARIFICATION
    assert len(result.questions) == 1
    assert result.questions[0].field == "action"
    assert "action" in result.brief.missing_fields


def test_complete_request_produces_complete_brief_and_no_questions(sample_inventory: DeckInventory):
    """Complete prompt with target, action, content, and preservation produces complete brief with 0 questions."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="On slide 1, change the title to 'Q3 Financial Review' while preserving formatting",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert result.state in (ConversationState.READY_FOR_PLAN, ConversationState.WAITING_PLAN_APPROVAL)
    assert len(result.questions) == 0
    assert result.brief is not None
    assert result.brief.complete is True
    assert len(result.brief.missing_fields) == 0
    assert len(result.brief.target_scope) == 1
    assert result.brief.target_scope[0].slide_index == 1


def test_selection_context_supplies_missing_target(sample_inventory: DeckInventory):
    """SelectionContext provides target slide and object when omitted in user message."""
    engine = ClarificationEngine()
    context = SelectionContext(slide_index=2, object_ref="fp-slide2-title")
    result = engine.assess(
        message="Replace text with 'Roadmap 2027'",
        inventory=sample_inventory,
        previous_brief=None,
        context=context,
    )

    assert result.brief is not None
    assert result.brief.complete is True
    assert len(result.questions) == 0
    assert result.brief.target_scope[0].slide_index == 2
    assert result.brief.target_scope[0].object_ref == "fp-slide2-title"


def test_follow_up_merges_with_previous_brief(sample_inventory: DeckInventory):
    """Follow-up answer supplies missing content to complete an existing brief."""
    engine = ClarificationEngine()

    # Turn 1: User says "On slide 1, update title" -> missing content
    turn1_result = engine.assess(
        message="On slide 1, update title",
        inventory=sample_inventory,
        previous_brief=None,
    )
    assert turn1_result.brief.complete is False
    assert "content" in turn1_result.brief.missing_fields

    # Turn 2: User provides the missing content
    turn2_result = engine.assess(
        message="Change it to 'Strategic Vision 2030'",
        inventory=sample_inventory,
        previous_brief=turn1_result.brief,
    )

    assert turn2_result.brief.complete is True
    assert len(turn2_result.questions) == 0
    assert turn2_result.brief.target_scope[0].slide_index == 1
    assert "Strategic Vision 2030" in turn2_result.brief.goal


def test_slide_out_of_range_asks_for_valid_target(sample_inventory: DeckInventory):
    """Targeting slide index exceeding deck size asks for valid slide within range."""
    engine = ClarificationEngine()
    result = engine.assess(
        message="On slide 10, change title to 'Out of range'",
        inventory=sample_inventory,
        previous_brief=None,
    )

    assert result.state == ConversationState.NEEDS_CLARIFICATION
    assert len(result.questions) == 1
    assert result.questions[0].field == "target"
    assert "target" in result.brief.missing_fields
    assert "1" in result.questions[0].prompt and "3" in result.questions[0].prompt
