import pytest

from autoslide.runtime.models import AgentEvent, RuntimeStatus


def test_runtime_status_fields_and_immutability():
    status = RuntimeStatus(
        name="codex",
        installed=True,
        version="1.2.0",
        authenticated=True,
        executable="/usr/local/bin/codex",
        reason=None,
    )

    assert status.name == "codex"
    assert status.installed is True
    assert status.version == "1.2.0"
    assert status.authenticated is True
    assert status.executable == "/usr/local/bin/codex"
    assert status.reason is None
    assert status.available is True

    unauthed = RuntimeStatus(name="codex", installed=True, authenticated=False)
    assert unauthed.available is False

    not_installed = RuntimeStatus(name="codex", installed=False, authenticated=True)
    assert not_installed.available is False

    with pytest.raises(Exception):
        status.installed = False  # type: ignore


def test_runtime_status_never_exposes_credentials():
    status = RuntimeStatus(
        name="gemini",
        installed=True,
        version="0.9.1",
        authenticated=False,
        executable="/usr/bin/gemini",
        reason="Failed authentication with OPENAI_API_KEY=sk-test-secret-1234",
    )

    status_repr = repr(status)
    status_json = status.model_dump_json()

    assert "sk-test-secret-1234" not in status_repr
    assert "sk-test-secret-1234" not in status_json
    assert "[REDACTED]" in status.reason

    # Ensure no credential attributes exist on the class
    assert "api_key" not in RuntimeStatus.model_fields
    assert "token" not in RuntimeStatus.model_fields
    assert "password" not in RuntimeStatus.model_fields


def test_agent_event_serialization_and_metadata():
    event = AgentEvent(
        job_id="job_abc",
        sequence=1,
        kind="PLAN_CREATED",
        message="Generated execution plan",
        timestamp="2026-09-18T14:00:00Z",
        metadata={"step_count": 5},
    )

    assert event.job_id == "job_abc"
    assert event.sequence == 1
    assert event.kind == "PLAN_CREATED"
    assert event.metadata["step_count"] == 5

    data = event.model_dump()
    assert data["kind"] == "PLAN_CREATED"

    with pytest.raises(Exception):
        event.sequence = 2  # type: ignore
