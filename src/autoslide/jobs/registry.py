"""SQLite-backed job state machine and lifecycle registry."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import ClassVar
from uuid import uuid4

from autoslide.jobs.models import JobRecord, JobState

VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.INGESTING, JobState.FAILED, JobState.CANCELLED},
    JobState.INGESTING: {JobState.PLANNING, JobState.FAILED, JobState.CANCELLED},
    JobState.PLANNING: {
        JobState.EXECUTING,
        JobState.AWAITING_USER_APPROVAL,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.EXECUTING: {JobState.RENDERING, JobState.FAILED, JobState.CANCELLED},
    JobState.RENDERING: {JobState.VERIFYING, JobState.FAILED, JobState.CANCELLED},
    JobState.VERIFYING: {
        JobState.REPAIRING,
        JobState.PLANNING,
        JobState.AWAITING_USER_APPROVAL,
        JobState.ACCEPTED,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.REPAIRING: {
        JobState.PLANNING,
        JobState.EXECUTING,
        JobState.RENDERING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.AWAITING_USER_APPROVAL: {
        JobState.ACCEPTED,
        JobState.REJECTED,
        JobState.REPAIRING,
        JobState.PLANNING,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.ACCEPTED: set(),
    JobState.REJECTED: set(),
    JobState.FAILED: set(),
    JobState.CANCELLED: {JobState.CANCELLED},
}


class JobRegistry:
    """Registry maintaining job states, instructions, and transitions in SQLite."""

    VALID_TRANSITIONS: ClassVar[dict[JobState, set[JobState]]] = VALID_TRANSITIONS

    def __init__(self, db_path: Path | str = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables and indexes within a transaction."""
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create(
        self,
        instruction: str,
        input_sha256: str,
        job_id: str | None = None,
    ) -> JobRecord:
        """Create a new job record initialized in CREATED state."""
        assigned_id = job_id or f"job_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        state = JobState.CREATED.value

        try:
            with self._lock, self._conn:
                self._conn.execute(
                    """
                    INSERT INTO jobs (job_id, state, instruction, input_sha256, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (assigned_id, state, instruction, input_sha256, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Job already exists with ID: '{assigned_id}'") from exc

        return JobRecord(
            job_id=assigned_id,
            state=JobState.CREATED,
            instruction=instruction,
            input_sha256=input_sha256,
            created_at=now,
            updated_at=now,
        )

    def get(self, job_id: str) -> JobRecord:
        """Retrieve an existing job record by identifier."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT job_id, state, instruction, input_sha256, created_at, updated_at FROM jobs WHERE job_id = ?",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"Job not found: '{job_id}'")

            return JobRecord(
                job_id=row["job_id"],
                state=JobState(row["state"]),
                instruction=row["instruction"],
                input_sha256=row["input_sha256"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def transition(self, job_id: str, new_state: JobState) -> JobRecord:
        """Transition job to a new state if permitted by the lifecycle state machine."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "SELECT job_id, state, instruction, input_sha256, created_at, updated_at FROM jobs WHERE job_id = ?",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"Job not found: '{job_id}'")

            current_state = JobState(row["state"])

            # Idempotent cancellation
            if current_state == JobState.CANCELLED and new_state == JobState.CANCELLED:
                return JobRecord(
                    job_id=row["job_id"],
                    state=current_state,
                    instruction=row["instruction"],
                    input_sha256=row["input_sha256"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

            allowed = VALID_TRANSITIONS.get(current_state, set())
            if new_state not in allowed:
                raise ValueError(
                    f"Invalid transition from {current_state.value} to {new_state.value}"
                )

            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                "UPDATE jobs SET state = ?, updated_at = ? WHERE job_id = ?",
                (new_state.value, now, job_id),
            )

            cur = self._conn.execute(
                "SELECT job_id, state, instruction, input_sha256, created_at, updated_at FROM jobs WHERE job_id = ?",
                (job_id,),
            )
            updated_row = cur.fetchone()
            return JobRecord(
                job_id=updated_row["job_id"],
                state=JobState(updated_row["state"]),
                instruction=updated_row["instruction"],
                input_sha256=updated_row["input_sha256"],
                created_at=updated_row["created_at"],
                updated_at=updated_row["updated_at"],
            )

    def force_state(self, job_id: str, state: JobState) -> None:
        """Force a state change for testing lifecycle stages directly."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE jobs SET state = ?, updated_at = ? WHERE job_id = ?",
                (state.value, now, job_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Job not found: '{job_id}'")
