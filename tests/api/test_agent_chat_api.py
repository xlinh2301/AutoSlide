"""Integration tests for POST /api/v1/sessions/{session_id}/chat endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest


def test_chat_session_not_found(client: TestClient):
    """Test 404 returned when chatting on non-existent session."""
    response = client.post(
        "/api/v1/sessions/non_existent_session/chat",
        json={"message": "Sửa tiêu đề slide 1"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_chat_session_empty_message_rejected(client: TestClient, valid_pptx: bytes):
    """Test 400 returned when message is empty."""
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/chat",
        json={"message": "   "},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_chat_session_edit_text_success(client: TestClient, valid_pptx: bytes):
    """Test editing text via Agent Chat triggers tool execution and updates session."""
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    chat_res = client.post(
        f"/api/v1/sessions/{session_id}/chat",
        json={"message": "Sửa tiêu đề slide 1 thành 'Báo Cáo Tăng Trưởng Q3 2026'"},
    )
    assert chat_res.status_code == 200
    body = chat_res.json()

    assert body["session_id"] == session_id
    assert "Báo Cáo Tăng Trưởng Q3 2026" in body["assistant_message"]
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["tool_name"] == "edit_slide_text"
    assert body["modified_slide_indices"] == [1]
    assert len(body["turns"]) >= 2  # user + assistant turns

    # Check events
    events_res = client.get(f"/api/v1/sessions/{session_id}/events")
    assert events_res.status_code == 200
    event_types = [e["event_type"] for e in events_res.json()["events"]]
    assert "AGENT_CHAT_PROCESSED" in event_types


def test_chat_session_add_slide_success(client: TestClient, valid_pptx: bytes):
    """Test adding slide via Agent Chat."""
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    chat_res = client.post(
        f"/api/v1/sessions/{session_id}/chat",
        json={"message": "Thêm slide mới với tiêu đề 'Kết Luận Và Định Hướng'"},
    )
    assert chat_res.status_code == 200
    body = chat_res.json()

    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["tool_name"] == "add_slide"
    assert len(body["modified_slide_indices"]) == 1


def test_chat_session_conversational_response(client: TestClient, valid_pptx: bytes):
    """Test conversational messages return natural responses without tool invocations."""
    create_res = client.post(
        "/api/v1/sessions",
        files={"template": ("deck.pptx", valid_pptx, "application/octet-stream")},
    )
    session_id = create_res.json()["session_id"]

    chat_res = client.post(
        f"/api/v1/sessions/{session_id}/chat",
        json={"message": "Xin chào, bạn có thể làm được những gì?"},
    )
    assert chat_res.status_code == 200
    body = chat_res.json()

    assert len(body["tool_calls"]) == 0
    assert body["modified_slide_indices"] == []
    assert "AutoSlide Agent" in body["assistant_message"] or "slide" in body["assistant_message"].lower()
