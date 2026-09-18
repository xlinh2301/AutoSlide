"""Runtime models, adapters, and discovery package for AutoSlide."""

from autoslide.runtime.adapters import (
    BaseRuntimeAdapter,
    ClaudeAdapter,
    CodexAdapter,
    FakeRuntimeAdapter,
    GeminiAdapter,
)
from autoslide.runtime.base import RuntimeAdapter, RuntimeHandle
from autoslide.runtime.discovery import RuntimeRegistry
from autoslide.runtime.models import AgentEvent, RuntimeStatus

__all__ = [
    "AgentEvent",
    "BaseRuntimeAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "FakeRuntimeAdapter",
    "GeminiAdapter",
    "RuntimeAdapter",
    "RuntimeHandle",
    "RuntimeRegistry",
    "RuntimeStatus",
]
