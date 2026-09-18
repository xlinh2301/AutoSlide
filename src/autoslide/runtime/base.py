"""Base classes and contracts for agent CLI runtime adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoslide.runtime.models import RuntimeStatus


@dataclass(frozen=True)
class RuntimeHandle:
    """Handle representing a spawned agent execution process."""

    job_id: str
    adapter_name: str
    process: Any
    started_at: str
    timeout_seconds: int
    argv: list[str]


class RuntimeAdapter(ABC):
    """Abstract contract for an agent CLI runtime adapter."""

    name: str
    executable_name: str

    @abstractmethod
    def detect(self) -> RuntimeStatus:
        """Detect installation, version, and authentication state of this runtime."""
        raise NotImplementedError

    @abstractmethod
    def start(
        self,
        job_id: str,
        prompt: str,
        workspace: Path,
        timeout_seconds: int = 300,
    ) -> RuntimeHandle:
        """Spawn the agent CLI process in an isolated workspace with safe argument array."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self, handle: RuntimeHandle) -> None:
        """Terminate the running agent process."""
        raise NotImplementedError
