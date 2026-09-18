"""Runtime models representing agent execution status and telemetry events."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from autoslide.events import Redactor


class RuntimeStatus(BaseModel):
    """Detection status and capability metadata for an agent runtime."""

    model_config = ConfigDict(frozen=True)

    name: str
    installed: bool
    version: str | None = None
    authenticated: bool = False
    executable: str | None = None
    reason: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available(self) -> bool:
        """Returns True only when the runtime is installed and authenticated."""
        return bool(self.installed and self.authenticated)

    @field_validator("version", "reason", mode="after")
    @classmethod
    def sanitize_strings(cls, v: str | None) -> str | None:
        """Ensure no secrets or tokens are stored in runtime version/reason."""
        if v is None:
            return None
        return Redactor.redact(v)


class AgentEvent(BaseModel):
    """Structured event emitted during runtime execution of an agent."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    sequence: int
    kind: str
    message: str
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message", mode="after")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Sanitize message using the deterministic redactor."""
        return Redactor.redact(v)

    @field_validator("metadata", mode="after")
    @classmethod
    def sanitize_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize metadata dictionary."""
        return Redactor.redact_payload(v)
