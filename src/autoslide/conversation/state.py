"""State machine transitions and rules for ConversationSession lifecycle."""

from __future__ import annotations

from autoslide.conversation.models import ConversationState

TRANSITION_RULES: dict[ConversationState, set[ConversationState]] = {
    ConversationState.NEEDS_CLARIFICATION: {
        ConversationState.READY_FOR_PLAN,
        ConversationState.FAILED,
    },
    ConversationState.READY_FOR_PLAN: {
        ConversationState.WAITING_PLAN_APPROVAL,
        ConversationState.NEEDS_CLARIFICATION,
        ConversationState.FAILED,
    },
    ConversationState.WAITING_PLAN_APPROVAL: {
        ConversationState.READY_FOR_EXECUTION,
        ConversationState.RESEARCHING,
        ConversationState.NEEDS_CLARIFICATION,
        ConversationState.FAILED,
    },
    ConversationState.RESEARCHING: {
        ConversationState.WAITING_SOURCE_APPROVAL,
        ConversationState.READY_FOR_PLAN,
        ConversationState.FAILED,
    },
    ConversationState.WAITING_SOURCE_APPROVAL: {
        ConversationState.READY_FOR_PLAN,
        ConversationState.WAITING_PLAN_APPROVAL,
        ConversationState.RESEARCHING,
        ConversationState.FAILED,
    },
    ConversationState.READY_FOR_EXECUTION: {
        ConversationState.EXECUTING,
        ConversationState.WAITING_PLAN_APPROVAL,
        ConversationState.FAILED,
    },
    ConversationState.EXECUTING: {
        ConversationState.REVIEW,
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.REVIEW: {
        ConversationState.COMPLETED,
        ConversationState.READY_FOR_PLAN,
        ConversationState.NEEDS_CLARIFICATION,
        ConversationState.FAILED,
    },
    ConversationState.COMPLETED: {
        ConversationState.NEEDS_CLARIFICATION,
        ConversationState.READY_FOR_PLAN,
    },
    ConversationState.FAILED: {
        ConversationState.NEEDS_CLARIFICATION,
        ConversationState.READY_FOR_PLAN,
    },
}


def validate_transition(current_state: ConversationState, target_state: ConversationState) -> bool:
    """Validate if transition from current_state to target_state is allowed.

    Raises:
        ValueError: If the transition is not permitted by TRANSITION_RULES.
    """
    allowed_targets = TRANSITION_RULES.get(current_state, set())
    if target_state not in allowed_targets:
        raise ValueError(
            f"Invalid transition from {current_state.value} to {target_state.value}. "
            f"Allowed transitions: {[s.value for s in allowed_targets]}"
        )
    return True
