"""Tests for AutoSlide Always-on Chatbot UI, Cards, and Conversation Workflow."""

from __future__ import annotations

import io
import re
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.discovery import RuntimeRegistry
from autoslide.ui import STATIC_DIR, TEMPLATES_DIR
from tests.fixtures.pptx_samples import create_minimal_pptx


@pytest.fixture
def studio_client(tmp_path: Path):
    settings = Settings(data_root=tmp_path / "data")
    registry = JobRegistry(tmp_path / "jobs.db")
    event_log = EventLog(tmp_path / "logs")
    runtime_registry = RuntimeRegistry()

    app = create_app(
        settings=settings,
        registry=registry,
        runtime_registry=runtime_registry,
        event_log=event_log,
    )
    return TestClient(app)


def test_persistent_chat_rail_elements_in_html(studio_client):
    """Verify that index.html contains persistent chatbot rail and interactive controls."""
    res = studio_client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # Persistent Chat Rail container & header
    assert 'id="chatRail"' in html
    assert 'id="chatHeader"' in html
    assert 'id="chatMessages"' in html
    assert 'id="chatComposer"' in html
    assert 'id="chatInput"' in html
    assert 'id="btnSendChat"' in html

    # Selection Context Indicator in Chat Composer
    assert 'id="chatContextBadge"' in html
    assert 'id="btnClearChatContext"' in html


def test_card_classes_and_layout_in_css(studio_client):
    """Verify CSS has styling rules for chat rail, message bubbles, and all interactive card types."""
    res = studio_client.get("/static/css/workbench.css")
    assert res.status_code == 200
    css = res.text

    assert ".chat-rail" in css
    assert ".chat-messages" in css
    assert ".chat-composer" in css
    assert ".chat-turn" in css
    assert ".turn-user" in css
    assert ".turn-assistant" in css

    # Card component styles
    assert ".card-question" in css
    assert ".card-plan" in css
    assert ".card-source" in css
    assert ".card-execution" in css
    assert ".card-review" in css
    assert ".card-error" in css


def test_workbench_js_implements_chat_and_card_renderers(studio_client):
    """Verify workbench.js implements chat message handling, card rendering, and approval actions."""
    res = studio_client.get("/static/js/workbench.js")
    assert res.status_code == 200
    js = res.text

    # Chat & session orchestration
    assert "sendChatMessage" in js
    assert "renderChatTurn" in js
    assert "activeSessionId" in js

    # Card renderers
    assert "renderQuestionCard" in js
    assert "renderPlanCard" in js
    assert "renderSourceCard" in js
    assert "renderExecutionCard" in js
    assert "renderReviewCard" in js
    assert "renderErrorCard" in js

    # Approval and selection actions
    assert "approvePlan" in js
    assert "approveSources" in js
    assert "updateChatSelectionContext" in js


def test_session_message_e2e_flow_with_cards(studio_client):
    """Verify end-to-end backend session lifecycle with clarification and plan cards."""
    # 1. Create a session with PPTX upload
    pptx_bytes = create_minimal_pptx()
    res_session = studio_client.post(
        "/api/v1/sessions",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert res_session.status_code == 201
    session_data = res_session.json()
    session_id = session_data["session_id"]
    assert session_data["state"] in ("NEEDS_CLARIFICATION", "INITIAL")

    # 2. Send vague message -> should return QuestionCard
    res_msg1 = studio_client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Improve slide title"},
    )
    assert res_msg1.status_code == 200
    msg1_data = res_msg1.json()
    assert msg1_data["session"]["state"] == "NEEDS_CLARIFICATION"
    assert len(msg1_data["cards"]) >= 1
    assert msg1_data["cards"][0]["type"] == "question"
    assert len(msg1_data["cards"][0]["questions"]) >= 1

    # 3. Answer question with specific instruction -> should transition to WAITING_PLAN_APPROVAL with PlanCard
    res_msg2 = studio_client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={
            "message": "Change slide 1 title text to 'Q4 Growth Roadmap'",
            "selection_context": {"slide_index": 1},
        },
    )
    assert res_msg2.status_code == 200
    msg2_data = res_msg2.json()
    assert msg2_data["session"]["state"] == "WAITING_PLAN_APPROVAL"
    assert len(msg2_data["cards"]) >= 1
    assert msg2_data["cards"][0]["type"] == "plan"
    assert "operations" in msg2_data["cards"][0]

    # 4. Approve plan
    res_approve = studio_client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"kind": "plan", "approved": True},
    )
    assert res_approve.status_code == 200
    approve_data = res_approve.json()
    assert approve_data["state"] in ("READY_FOR_EXECUTION", "EXECUTING")

    # 5. Execute session
    res_exec = studio_client.post(f"/api/v1/sessions/{session_id}/execute")
    assert res_exec.status_code == 202
    exec_data = res_exec.json()
    assert exec_data["state"] in ("EXECUTING", "VERIFYING", "AWAITING_USER_APPROVAL", "COMPLETED")
