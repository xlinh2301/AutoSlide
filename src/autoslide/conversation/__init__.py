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
from autoslide.conversation.schemas import (
    ApproveDecisionRequest,
    ApproveDecisionResponse,
    CreateSessionResponse,
    ExecuteSessionResponse,
    SendMessageRequest,
    SessionDetailResponse,
    SessionEventsResponse,
)
from autoslide.conversation.state import TRANSITION_RULES, validate_transition
from autoslide.conversation.store import SessionStore

__all__ = [
    "ApproveDecisionRequest",
    "ApproveDecisionResponse",
    "ChatTurn",
    "ClarificationEngine",
    "ClarificationResult",
    "ConversationResponse",
    "ConversationService",
    "ConversationSession",
    "ConversationState",
    "CreateSessionResponse",
    "EditBrief",
    "ExecuteSessionResponse",
    "Question",
    "SelectionContext",
    "SendMessageRequest",
    "SessionDetailResponse",
    "SessionEventsResponse",
    "SessionStore",
    "TRANSITION_RULES",
    "validate_transition",
]

