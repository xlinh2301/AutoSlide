"""Deterministic redaction and append-only event logging."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import threading
from typing import Any

from pydantic import BaseModel, ConfigDict

REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer tokens
    (re.compile(r"(?i)\b(bearer[\s\-]+)[A-Za-z0-9_\-\.]+"), r"\1[REDACTED]"),
    # Common API-key environment assignments and key: value pairs
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|SECRET_KEY|TOKEN|PASSWORD|AUTH|CREDENTIALS|API\s+KEY|SECRET)[A-Z0-9_]*\s*[:=]\s*)([^\s;&]+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(--token\s+|--api-key\s+|--password\s+)([^\s]+)"),
        r"\1[REDACTED]",
    ),
    # Cookie names / values
    (
        re.compile(
            r"(?i)\b(sessionid|token|auth|cookie|jwt|csrftoken)\s*[:=]\s*([^\s;,\r\n]+)"
        ),
        r"\1=[REDACTED]",
    ),
    # Private-key blocks
    (
        re.compile(
            r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"
        ),
        "[REDACTED]",
    ),
    # Absolute credential paths
    (
        re.compile(
            r"(?:/(?:home|root|Users)/[^\s/]+/|\~/(?:\.config/|\.local/|\.credentials/)?)\.?(?:aws|azure|gcp|openai|anthropic|gemini|credentials|id_rsa|id_ed25519)[^\s]*"
        ),
        "[REDACTED]",
    ),
]


class Redactor:
    """Deterministic redactor for removing credentials, tokens, and secret patterns."""

    @classmethod
    def redact(cls, value: str) -> str:
        """Apply all redaction rules to a string."""
        redacted = value
        for pattern, replacement in REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    @classmethod
    def redact_payload(cls, payload: Any) -> Any:
        """Recursively redact strings within nested dictionaries, lists, or primitives."""
        if isinstance(payload, str):
            return cls.redact(payload)
        elif isinstance(payload, dict):
            return {k: cls.redact_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [cls.redact_payload(v) for v in payload]
        elif isinstance(payload, tuple):
            return tuple(cls.redact_payload(v) for v in payload)
        return payload


class EventRecord(BaseModel):
    """Immutable record of an append-only job event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    job_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    timestamp: str


class EventLog:
    """Thread-safe, append-only event log with automatic redaction and sequence monotonicity."""

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path
        self._lock = threading.RLock()
        self._sequences: dict[str, int] = {}
        self._events: dict[str, list[EventRecord]] = {}

    def append(
        self,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> EventRecord:
        """Append a redacted event record with a monotonically increasing sequence per job."""
        with self._lock:
            seq = self._sequences.get(job_id, 0) + 1
            self._sequences[job_id] = seq

            redacted_payload = Redactor.redact_payload(payload)
            now = datetime.now(timezone.utc).isoformat()
            event_id = f"evt_{job_id}_{seq:06d}"

            record = EventRecord(
                event_id=event_id,
                job_id=job_id,
                sequence=seq,
                event_type=event_type,
                payload=redacted_payload,
                timestamp=now,
            )

            if job_id not in self._events:
                self._events[job_id] = []
            self._events[job_id].append(record)

            if self.log_path is not None:
                file_path = (
                    self.log_path / f"{job_id}.jsonl"
                    if self.log_path.is_dir()
                    else self.log_path
                )
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with file_path.open("a", encoding="utf-8") as f:
                    f.write(record.model_dump_json() + "\n")

            return record

    def get_events(self, job_id: str) -> list[EventRecord]:
        """Return all recorded events for a given job."""
        with self._lock:
            return list(self._events.get(job_id, []))
