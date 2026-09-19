import pytest
from autoslide.conversation.models import ConversationState, ConversationSession
from autoslide.conversation.state import validate_transition, TRANSITION_RULES


def test_invalid_transition_is_rejected():
    session = ConversationSession.new("session-1")
    with pytest.raises(ValueError, match="Invalid transition"):
        session.transition(ConversationState.COMPLETED)


def test_clarification_allowed_transitions():
    session = ConversationSession.new("session-1")
    assert session.state is ConversationState.NEEDS_CLARIFICATION

    # To READY_FOR_PLAN
    s2 = session.transition(ConversationState.READY_FOR_PLAN)
    assert s2.state is ConversationState.READY_FOR_PLAN

    # To FAILED
    s_failed = session.transition(ConversationState.FAILED)
    assert s_failed.state is ConversationState.FAILED


def test_full_successful_lifecycle_transitions():
    s = ConversationSession.new("s-lifecycle")
    assert s.state is ConversationState.NEEDS_CLARIFICATION

    s = s.transition(ConversationState.READY_FOR_PLAN)
    assert s.state is ConversationState.READY_FOR_PLAN

    s = s.transition(ConversationState.WAITING_PLAN_APPROVAL)
    assert s.state is ConversationState.WAITING_PLAN_APPROVAL

    s = s.transition(ConversationState.READY_FOR_EXECUTION)
    assert s.state is ConversationState.READY_FOR_EXECUTION

    s = s.transition(ConversationState.EXECUTING)
    assert s.state is ConversationState.EXECUTING

    s = s.transition(ConversationState.REVIEW)
    assert s.state is ConversationState.REVIEW

    s = s.transition(ConversationState.COMPLETED)
    assert s.state is ConversationState.COMPLETED


def test_research_branch_lifecycle_transitions():
    s = ConversationSession.new("s-research")
    s = s.transition(ConversationState.READY_FOR_PLAN)
    s = s.transition(ConversationState.WAITING_PLAN_APPROVAL)
    s = s.transition(ConversationState.RESEARCHING)
    assert s.state is ConversationState.RESEARCHING

    s = s.transition(ConversationState.WAITING_SOURCE_APPROVAL)
    assert s.state is ConversationState.WAITING_SOURCE_APPROVAL

    s = s.transition(ConversationState.READY_FOR_PLAN)
    assert s.state is ConversationState.READY_FOR_PLAN


def test_recovery_from_failed_or_completed():
    s = ConversationSession.new("s-fail")
    s = s.transition(ConversationState.FAILED)

    # Can recover to NEEDS_CLARIFICATION or READY_FOR_PLAN
    s_retry = s.transition(ConversationState.NEEDS_CLARIFICATION)
    assert s_retry.state is ConversationState.NEEDS_CLARIFICATION

    # From COMPLETED, can initiate next request
    s_comp = s_retry.transition(ConversationState.READY_FOR_PLAN)
    s_comp = s_comp.transition(ConversationState.WAITING_PLAN_APPROVAL)
    s_comp = s_comp.transition(ConversationState.READY_FOR_EXECUTION)
    s_comp = s_comp.transition(ConversationState.EXECUTING)
    s_comp = s_comp.transition(ConversationState.COMPLETED)
    s_next = s_comp.transition(ConversationState.NEEDS_CLARIFICATION)
    assert s_next.state is ConversationState.NEEDS_CLARIFICATION


def test_validate_transition_helper():
    assert validate_transition(
        ConversationState.NEEDS_CLARIFICATION, ConversationState.READY_FOR_PLAN
    )
    with pytest.raises(ValueError):
        validate_transition(
            ConversationState.NEEDS_CLARIFICATION, ConversationState.EXECUTING
        )
