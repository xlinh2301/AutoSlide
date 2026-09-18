from pathlib import Path
import pytest

from autoslide.jobs.models import JobState
from autoslide.jobs.registry import JobRegistry


def test_registry_create_and_get(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    record = registry.create("Change title", "a" * 64)

    assert record.job_id
    assert record.state == JobState.CREATED
    assert record.instruction == "Change title"
    assert record.input_sha256 == "a" * 64

    fetched = registry.get(record.job_id)
    assert fetched == record


def test_registry_rejects_duplicate_job_id(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    registry.create("Instruction 1", "a" * 64, job_id="fixed_id")

    with pytest.raises(ValueError, match="duplicate|already exists"):
        registry.create("Instruction 2", "b" * 64, job_id="fixed_id")


def test_registry_get_missing_job_raises_key_error(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    with pytest.raises(KeyError, match="missing_id"):
        registry.get("missing_id")


def test_registry_valid_state_transitions(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    record = registry.create("Instruction", "a" * 64)

    record = registry.transition(record.job_id, JobState.INGESTING)
    assert record.state == JobState.INGESTING

    record = registry.transition(record.job_id, JobState.PLANNING)
    assert record.state == JobState.PLANNING

    record = registry.transition(record.job_id, JobState.EXECUTING)
    assert record.state == JobState.EXECUTING

    record = registry.transition(record.job_id, JobState.RENDERING)
    assert record.state == JobState.RENDERING

    record = registry.transition(record.job_id, JobState.VERIFYING)
    assert record.state == JobState.VERIFYING

    record = registry.transition(record.job_id, JobState.ACCEPTED)
    assert record.state == JobState.ACCEPTED


def test_registry_rejects_invalid_state_transition(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    record = registry.create("Instruction", "a" * 64)

    # CREATED cannot jump directly to ACCEPTED
    with pytest.raises(ValueError, match="Invalid transition"):
        registry.transition(record.job_id, JobState.ACCEPTED)


def test_registry_cancellation_from_active_states(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    active_states = [
        JobState.CREATED,
        JobState.INGESTING,
        JobState.PLANNING,
        JobState.EXECUTING,
        JobState.RENDERING,
        JobState.VERIFYING,
        JobState.REPAIRING,
        JobState.AWAITING_USER_APPROVAL,
    ]

    for state in active_states:
        registry = JobRegistry(db_path)
        record = registry.create(f"Job for {state}", "a" * 64)
        if state != JobState.CREATED:
            # Force/transition to state through registry or direct helper
            registry.force_state(record.job_id, state)
        cancelled = registry.transition(record.job_id, JobState.CANCELLED)
        assert cancelled.state == JobState.CANCELLED


def test_registry_cancellation_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    registry = JobRegistry(db_path)
    record = registry.create("Job to cancel", "a" * 64)

    cancelled1 = registry.transition(record.job_id, JobState.CANCELLED)
    assert cancelled1.state == JobState.CANCELLED

    cancelled2 = registry.transition(record.job_id, JobState.CANCELLED)
    assert cancelled2.state == JobState.CANCELLED
    assert cancelled2.job_id == record.job_id
