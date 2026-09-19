"""Atomic JSON checkpoint store for conversation sessions with sensitive credential redaction."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from autoslide.conversation.models import ConversationSession

SENSITIVE_KEY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"api[_-]?key",
        r"token",
        r"secret",
        r"password",
        r"credential",
        r"private[_-]?key",
        r"bearer",
        r"auth",
    )
]

REDACTED_PLACEHOLDER = "[REDACTED]"


def redact_credentials(obj: Any) -> Any:
    """Recursively scrub credential values matching sensitive key names or patterns."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            k_str = str(k)
            if any(pattern.search(k_str) for pattern in SENSITIVE_KEY_PATTERNS):
                cleaned[k_str] = REDACTED_PLACEHOLDER
            else:
                cleaned[k_str] = redact_credentials(v)
        return cleaned
    if isinstance(obj, list):
        return [redact_credentials(item) for item in obj]
    if isinstance(obj, str):
        # Check for token-like substrings or prefixes
        if re.match(r"^sk-[A-Za-z0-9_-]{10,}$", obj) or re.match(r"^bearer\s+[\w\.-]+$", obj, re.IGNORECASE):
            return REDACTED_PLACEHOLDER
        return obj
    return obj


class SessionStore:
    """Persists and reloads conversation sessions as JSON checkpoints atomically."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(os.environ.get("AUTOSLIDE_SESSION_DIR", ".autoslide"))
        self.base_dir = Path(base_dir)

    def _resolve_checkpoint_path(self, session_id: str, job_id: str | None = None) -> Path:
        """Resolve primary storage path for a session checkpoint."""
        target_dir = self.base_dir / "sessions" / session_id
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / "checkpoint.json"

    def _atomic_write_json(self, target_path: Path, data: dict[str, Any]) -> None:
        """Write json data to target_path atomically using a temporary file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.parent / f".{target_path.name}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)

    def create(self, session: ConversationSession) -> ConversationSession:
        """Create a new session record and serialize initial checkpoint."""
        return self.save(session)

    def save(self, session: ConversationSession) -> ConversationSession:
        """Atomically persist session state to JSON checkpoint file."""
        if session.checkpoint_path:
            primary_path = Path(session.checkpoint_path)
        else:
            primary_path = self._resolve_checkpoint_path(session.session_id, session.job_id)

        session_with_path = session.model_copy(update={"checkpoint_path": str(primary_path.resolve())})
        raw_dict = session_with_path.model_dump(mode="json")
        sanitized_dict = redact_credentials(raw_dict)

        # Write to primary checkpoint path
        self._atomic_write_json(primary_path, sanitized_dict)

        # If job_id is associated, also persist checkpoint in the job workspace
        if session.job_id:
            job_workspace_path = self.base_dir / "workspaces" / session.job_id / "checkpoint.json"
            self._atomic_write_json(job_workspace_path, sanitized_dict)

        return session_with_path

    def get(self, session_id: str, job_id: str | None = None) -> ConversationSession:
        """Load and deserialize session from checkpoint file."""
        primary_path = self._resolve_checkpoint_path(session_id, job_id)
        if primary_path.exists():
            target_path = primary_path
        elif job_id and (self.base_dir / "workspaces" / job_id / "checkpoint.json").exists():
            target_path = self.base_dir / "workspaces" / job_id / "checkpoint.json"
        else:
            raise FileNotFoundError(f"Checkpoint not found for session '{session_id}' at {primary_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ConversationSession.model_validate(data)
