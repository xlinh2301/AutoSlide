import pytest
from pydantic import ValidationError
from autoslide.planner.models import TargetScope, TaskPlan, EditOperation
from autoslide.conversation.models import (
    ConversationState,
    ChatTurn,
    EditBrief,
    SourceRecord,
    ConversationSession,
)
from autoslide.conversation.store import SessionStore


def test_ambiguous_session_starts_in_clarification():
    session = ConversationSession.new("session-1")
    assert session.state is ConversationState.NEEDS_CLARIFICATION
    assert session.session_id == "session-1"
    assert session.turns == []
    assert session.brief is None
    assert session.plan is None
    assert session.sources == []
    assert session.job_id is None


def test_models_are_immutable():
    session = ConversationSession.new("session-1")
    with pytest.raises((ValidationError, TypeError)):
        session.state = ConversationState.READY_FOR_PLAN  # type: ignore

    turn = ChatTurn(
        id="turn-1",
        role="user",
        content="Make title bold",
        created_at="2026-09-19T10:00:00Z",
        card=None,
    )
    with pytest.raises((ValidationError, TypeError)):
        turn.content = "Changed"  # type: ignore


def test_chat_turn_role_validation():
    ChatTurn(
        id="turn-1",
        role="user",
        content="hello",
        created_at="2026-09-19T10:00:00Z",
    )
    ChatTurn(
        id="turn-2",
        role="assistant",
        content="hi",
        created_at="2026-09-19T10:00:01Z",
    )
    ChatTurn(
        id="turn-3",
        role="tool",
        content="exec",
        created_at="2026-09-19T10:00:02Z",
    )
    with pytest.raises(ValidationError):
        ChatTurn(
            id="turn-4",
            role="invalid_role",  # type: ignore
            content="bad",
            created_at="2026-09-19T10:00:03Z",
        )


def test_edit_brief_model():
    brief = EditBrief(
        goal="Change subtitle on slide 1",
        target_scope=[TargetScope(slide_index=1, shape_name="Subtitle 1")],
        constraints=["Preserve theme colors"],
        missing_fields=[],
        complete=True,
    )
    assert brief.complete is True
    assert len(brief.target_scope) == 1
    assert brief.target_scope[0].slide_index == 1


def test_source_record_model():
    record = SourceRecord(
        source_id="src-1",
        url="https://example.com/data",
        title="Sample Data",
        retrieved_at="2026-09-19T10:00:00Z",
        summary="Company quarterly revenue metrics",
        claims=["Revenue up 15%"],
        approved=False,
    )
    assert record.approved is False
    assert len(record.claims) == 1


def test_session_store_create_save_get_and_atomic_checkpoint(tmp_path):
    store = SessionStore(base_dir=tmp_path)
    session = ConversationSession.new("session-100", job_id="job-abc")

    # Add a turn
    turn1 = ChatTurn(
        id="t-1",
        role="user",
        content="Update slide 2",
        created_at="2026-09-19T10:00:00Z",
    )
    session = session.with_turn(turn1)

    created_session = store.create(session)
    assert created_session.checkpoint_path != ""
    assert (tmp_path / "sessions" / "session-100" / "checkpoint.json").exists()
    assert (tmp_path / "workspaces" / "job-abc" / "checkpoint.json").exists()

    # Reload from store
    loaded = store.get("session-100")
    assert loaded.session_id == "session-100"
    assert loaded.job_id == "job-abc"
    assert loaded.state is ConversationState.NEEDS_CLARIFICATION
    assert len(loaded.turns) == 1
    assert loaded.turns[0].content == "Update slide 2"

    # Save transition
    next_session = loaded.transition(ConversationState.READY_FOR_PLAN)
    saved = store.save(next_session)
    assert saved.state is ConversationState.READY_FOR_PLAN

    reloaded = store.get("session-100")
    assert reloaded.state is ConversationState.READY_FOR_PLAN


def test_session_store_preserves_provenance_and_plan_without_credentials(tmp_path):
    store = SessionStore(base_dir=tmp_path)
    session = ConversationSession.new("session-provenance", job_id="job-prov-1")

    # Turns with some credentials in card
    turn = ChatTurn(
        id="turn-prov",
        role="assistant",
        content="Analyzed sources and formed plan",
        card={"api_key": "secret-12345", "token": "bearer-abc", "public_meta": "safe"},
    )
    session = session.with_turn(turn)

    # EditBrief
    brief = EditBrief(
        goal="Incorporate market stats into slide 3",
        target_scope=[TargetScope(slide_index=3)],
        constraints=["Keep footer font 12pt"],
        complete=True,
    )
    session = session.with_brief(brief)

    # TaskPlan
    from autoslide.planner.models import ReplaceTextOp, TargetReference
    plan = TaskPlan(
        target_scope=[TargetScope(slide_index=3)],
        operations=[
            ReplaceTextOp(
                target=TargetReference(slide_index=3, shape_name="TextBox 1"),
                value="Market grew 20% YoY",
            )
        ],
        rationale="Update slide 3 stats",
    )
    session = session.with_plan(plan)

    # SourceRecord (provenance)
    source = SourceRecord(
        source_id="src-99",
        url="https://marketresearch.org/report-2026",
        title="2026 Tech Market Survey",
        retrieved_at="2026-09-19T12:00:00Z",
        summary="Tech market expanded by 20% YoY",
        claims=["Market grew 20% YoY"],
        approved=True,
    )
    session = session.with_sources([source])

    # Save to store
    saved_session = store.save(session)

    # Verify JSON content on disk contains no credentials
    checkpoint_file = tmp_path / "workspaces" / "job-prov-1" / "checkpoint.json"
    assert checkpoint_file.exists()
    raw_content = checkpoint_file.read_text(encoding="utf-8")
    assert "secret-12345" not in raw_content
    assert "bearer-abc" not in raw_content
    assert "[REDACTED]" in raw_content
    assert "https://marketresearch.org/report-2026" in raw_content

    # Reload and verify provenance, plan, turns and brief preservation
    reloaded = store.get("session-provenance", job_id="job-prov-1")
    assert reloaded.session_id == "session-provenance"
    assert reloaded.job_id == "job-prov-1"
    assert len(reloaded.turns) == 1
    assert reloaded.turns[0].card["api_key"] == "[REDACTED]"
    assert reloaded.turns[0].card["public_meta"] == "safe"
    assert reloaded.brief is not None
    assert reloaded.brief.goal == "Incorporate market stats into slide 3"
    assert reloaded.plan is not None
    assert len(reloaded.plan.operations) == 1
    assert reloaded.plan.rationale == "Update slide 3 stats"
    assert len(reloaded.sources) == 1
    assert reloaded.sources[0].source_id == "src-99"
    assert reloaded.sources[0].approved is True
    assert reloaded.sources[0].claims == ["Market grew 20% YoY"]
