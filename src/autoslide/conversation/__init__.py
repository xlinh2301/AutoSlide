"""Conversation foundation module for always-on conversational agent sessions."""

from autoslide.conversation.clarification import (
    ClarificationEngine,
    ClarificationResult,
    Question,
)
from autoslide.conversation.models import (
    ChatTurn,
    ConversationSession,
    ConversationState,
    EditBrief,
    SourceRecord,
)
from autoslide.conversation.service import (
    ConversationResponse,
    ConversationService,
    SelectionContext,
)
from autoslide.conversation.state import TRANSITION_RULES, validate_transition
from autoslide.conversation.store import SessionStore

__all__ = [
    "ChatTurn",
    "ClarificationEngine",
    "ClarificationResult",
    "ConversationResponse",
    "ConversationService",
    "ConversationSession",
    "ConversationState",
    "EditBrief",
    "Question",
    "SelectionContext",
    "SessionStore",
    "TRANSITION_RULES",
    "validate_transition",
]

