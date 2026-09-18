from pathlib import Path
import pytest

from autoslide.events import EventLog, EventRecord, Redactor


def test_redactor_removes_secret_like_values():
    text = "Authorization: Bearer abc123 and OPENAI_API_KEY=secret-value"
    safe = Redactor.redact(text)
    assert "abc123" not in safe
    assert "secret-value" not in safe
    assert "[REDACTED]" in safe


def test_redactor_removes_private_keys_and_cookies():
    private_key = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
    )
    cookie_str = "Cookie: sessionid=xyz987; token=secrettoken123"
    combined = f"{private_key}\n{cookie_str}"
    safe = Redactor.redact(combined)

    assert "MIIEowIBAAKCAQEA0" not in safe
    assert "xyz987" not in safe
    assert "secrettoken123" not in safe
    assert "[REDACTED]" in safe


def test_redactor_redacts_nested_payload():
    payload = {
        "command": "login --token secret_token_abc",
        "nested": {
            "key": "ANTHROPIC_API_KEY=sk-ant-12345",
            "count": 42,
        },
        "items": ["safe item", "Bearer my_jwt_token_999"],
    }
    safe_payload = Redactor.redact_payload(payload)

    assert safe_payload["nested"]["count"] == 42
    assert "secret_token_abc" not in safe_payload["command"]
    assert "sk-ant-12345" not in safe_payload["nested"]["key"]
    assert "my_jwt_token_999" not in safe_payload["items"][1]


def test_event_log_sequence_ordering_and_monotonicity():
    log = EventLog()
    e1 = log.append("job_1", "JOB_CREATED", {"stage": "init"})
    e2 = log.append("job_1", "JOB_STARTED", {"runtime": "codex"})
    e3 = log.append("job_2", "JOB_CREATED", {"stage": "init"})
    e4 = log.append("job_1", "JOB_FINISHED", {"status": "ok"})

    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 1  # job_2 starts at 1
    assert e4.sequence == 3  # job_1 continues to 3

    events_job_1 = log.get_events("job_1")
    assert [e.sequence for e in events_job_1] == [1, 2, 3]


def test_event_log_persistence_and_json_serialization(tmp_path: Path):
    log = EventLog(log_path=tmp_path)
    e1 = log.append("job_10", "SECRET_EVENT", {"token": "OPENAI_API_KEY=super-secret"})

    log_file = tmp_path / "job_10.jsonl"
    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8")
    assert "super-secret" not in content
    assert "[REDACTED]" in content
    assert '"sequence":1' in content
    assert '"event_type":"SECRET_EVENT"' in content
