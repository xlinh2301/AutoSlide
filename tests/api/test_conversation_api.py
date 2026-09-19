"""Focused API tests for conversational session endpoints and approval gates."""

import pytest
from fastapi.testclient import TestClient


def test_create_session_success(client: TestClient, valid_pptx: bytes):
    response = client.post(
        "/api/v1/sessions",
        files={
            "template": (
                "deck.pptx",
                valid_pptx,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert response.status_code in (200, 201)
    body = response.json()
    assert "session_id" in body
    assert body["session_id"].startswith("session_")
    assert "job_id" in body
    assert body["state"] == "NEEDS_CLARIFICATION"


def test_create_session_invalid_file_rejected(client: TestClient):
    response = client.post(
        "/api/v1/sessions",
        files={"template": ("notes.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    assert "pptx" in response.json()["detail"].lower()


def test_send_vague_message_returns_clarification(client: TestClient, valid_pptx: bytes):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    msg_res = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Make this slide better"},
    )
    assert msg_res.status_code == 200
    body = msg_res.json()
    assert body["session"]["state"] == "NEEDS_CLARIFICATION"
    assert len(body["cards"]) > 0
    assert body["cards"][0]["type"] == "question"


def test_send_complete_message_advances_to_waiting_plan_approval(
    client: TestClient, valid_pptx: bytes
):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    msg_res = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "On slide 1, change title to 'Executive Summary'"},
    )
    assert msg_res.status_code == 200
    body = msg_res.json()
    assert body["session"]["state"] == "WAITING_PLAN_APPROVAL"
    assert len(body["cards"]) > 0
    assert body["cards"][0]["type"] == "plan"


def test_get_session_detail_and_not_found(client: TestClient, valid_pptx: bytes):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    get_res = client.get(f"/api/v1/sessions/{session_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["session"]["session_id"] == session_id
    assert "brief" in body
    assert "plan" in body
    assert "sources" in body
    assert "active_job" in body

    not_found = client.get("/api/v1/sessions/nonexistent_session_123")
    assert not_found.status_code == 404


def test_get_session_events_redacted(client: TestClient, valid_pptx: bytes):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    events_res = client.get(f"/api/v1/sessions/{session_id}/events")
    assert events_res.status_code == 200
    body = events_res.json()
    assert "events" in body
    assert isinstance(body["events"], list)
    assert len(body["events"]) >= 1


def test_approve_plan_transitions_to_ready_for_execution(
    client: TestClient, valid_pptx: bytes
):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    # Produce a valid plan
    client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "On slide 1, change title to 'Executive Summary'"},
    )

    # Approve the plan
    approve_res = client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"kind": "plan", "approved": True},
    )
    assert approve_res.status_code == 200
    body = approve_res.json()
    assert body["state"] == "READY_FOR_EXECUTION"


def test_revise_plan_returns_to_needs_clarification(
    client: TestClient, valid_pptx: bytes
):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    # Produce plan
    client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "On slide 1, change title to 'Executive Summary'"},
    )

    # Revise plan
    revise_res = client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"kind": "plan", "approved": False, "feedback": "Actually use slide 2 instead"},
    )
    assert revise_res.status_code == 200
    body = revise_res.json()
    assert body["state"] == "NEEDS_CLARIFICATION"


def test_execute_before_approval_is_rejected(client: TestClient, valid_pptx: bytes):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    # Execution rejected when in NEEDS_CLARIFICATION
    exec_res1 = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_res1.status_code in (400, 409)
    assert "approved" in exec_res1.json()["detail"].lower()

    # Still rejected when in WAITING_PLAN_APPROVAL
    client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "On slide 1, change title to 'Executive Summary'"},
    )
    exec_res2 = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_res2.status_code in (400, 409)
    assert "approved" in exec_res2.json()["detail"].lower()


def test_execute_after_approval_starts_execution(
    client: TestClient, valid_pptx: bytes
):
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "On slide 1, change title to 'Executive Summary'"},
    )

    client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"kind": "plan", "approved": True},
    )

    exec_res = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_res.status_code in (200, 202)
    body = exec_res.json()
    assert body["state"] == "EXECUTING"
    assert body["session_id"] == session_id
