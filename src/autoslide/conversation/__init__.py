"""Conversation foundation module for always-on conversational agent sessions."""

from autoslide.conversation.models import (
    ChatTurn,
    ConversationSession,
    ConversationState,
    EditBrief,
    SourceRecord,
)
from autoslide.conversation.state import TRANSITION_RULES, validate_transition
from autoslide.conversation.store import SessionStore

__all__ = [
    "ChatTurn",
    "ConversationSession",
    "ConversationState",
    "EditBrief",
    "SourceRecord",
    "TRANSITION_RULES",
    "validate_transition",
    "SessionStore",
]
