"""Tests for AutoSlide Studio UI Overhaul (ADS-003).

Verifies:
1. Dual-Column Canvas HTML components (Before / After deck columns, count badges, chat mode switch).
2. CSS styling rules for visual change highlights (.slide-modified-glow, .modified-badge, and tool cards).
3. Workbench.js contract implementations (dual-column deck synchronization, real agent chat, and tool calling renderers).
4. Zero external frontend dependencies (no external CDNs, fonts, or scripts).
5. Full-Deck initial parity (Before == After, modified=False) and dynamic delta re-render sync upon tool calls.
"""

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


def test_dual_column_canvas_elements_in_html(studio_client):
    """Verify that index.html contains all Dual-Column Canvas and Real Agent controls."""
    res = studio_client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # Dual-Column Canvas Panels
    assert 'id="canvasBeforePanel"' in html
    assert 'id="canvasAfterPanel"' in html
    assert "Original Deck (Before)" in html
    assert "Modified Deck (After)" in html

    # Slide Deck Lists for all slides
    assert 'id="beforeDeckList"' in html
    assert 'id="afterDeckList"' in html
    assert 'id="beforeDeckCountBadge"' in html
    assert 'id="afterDeckCountBadge"' in html

    # Chat Mode Switch in Chat Header
    assert 'id="chatModeSwitch"' in html
    assert 'id="btnModeAgent"' in html
    assert 'id="btnModePlan"' in html

    # Backwards compatible single slide frames and overlays
    assert 'id="beforeFrame"' in html
    assert 'id="afterFrame"' in html
    assert 'id="highlightOverlayLayer"' in html
    assert 'id="diffBadge"' in html


def test_visual_change_highlights_in_css(studio_client):
    """Verify workbench.css includes styles for Dual-Column canvas, visual change highlights, and tool cards."""
    res = studio_client.get("/static/css/workbench.css")
    assert res.status_code == 200
    css = res.text

    # Dual-column list & slide card styles
    assert ".deck-slides-list" in css
    assert ".deck-slide-card" in css
    assert ".active-slide-card" in css
    assert ".deck-count-badge" in css

    # Visual Change Highlight (Luminous glow and badge)
    assert ".slide-modified-glow" in css
    assert ".modified-badge" in css
    assert "slide-pulse-glow" in css

    # Tool Calling Cards & Result Cards
    assert ".tool-calling-card" in css
    assert ".card-tool-call" in css
    assert ".tool-result-card" in css
    assert ".tool-card-badge" in css
    assert ".tool-badge-executing" in css
    assert ".tool-badge-success" in css
    assert ".modified-slides-tag" in css


def test_workbench_js_implements_dual_column_and_real_agent_contracts(studio_client):
    """Verify workbench.js implements dual-column deck synchronization and Real Agent tool calling."""
    res = studio_client.get("/static/js/workbench.js")
    assert res.status_code == 200
    js = res.text

    # Deck synchronization functions
    assert "loadSessionDeck" in js
    assert "renderDualColumnDeck" in js
    assert "buildFilmstripFromDeck" in js
    assert "beforeDeckList" in js
    assert "afterDeckList" in js
    assert "slide-modified-glow" in js

    # Tool calling card renderers
    assert "renderToolCallingCard" in js
    assert "renderToolResultCard" in js
    assert "chatMode" in js

    # API endpoints integration
    assert "/api/v1/sessions/${activeSessionId}/chat" in js or "/api/v1/sessions/" in js
    assert "/api/v1/sessions/${sessionId}/deck" in js


def test_zero_external_frontend_dependencies():
    """Verify index.html and static assets contain no external CDN or web links."""
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    assert len(re.findall(r'(?:src|href)=["\']https?://[^"\']+["\']', html)) == 0

    css = (STATIC_DIR / "css" / "workbench.css").read_text(encoding="utf-8")
    assert "@import url(" not in css
    assert "fonts.googleapis.com" not in css
    assert "cdn.jsdelivr.net" not in css


def test_full_deck_initial_parity_and_agent_tool_sync(studio_client):
    """Verify full-deck initial Before == After parity and dynamic delta update via Agent chat."""
    pptx_bytes = create_minimal_pptx()

    # 1. Create session with PPTX template upload
    res_session = studio_client.post(
        "/api/v1/sessions",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert res_session.status_code == 201
    session_id = res_session.json()["session_id"]

    # 2. Fetch full deck state: verify initial parity (Before == After)
    res_deck = studio_client.get(f"/api/v1/sessions/{session_id}/deck")
    assert res_deck.status_code == 200
    deck_data = res_deck.json()

    assert deck_data["slide_count"] >= 1
    assert len(deck_data["slides"]) == deck_data["slide_count"]
    assert deck_data["modified_slide_indices"] == []

    for s in deck_data["slides"]:
        assert s["modified"] is False
        assert s["before_url"] is not None
        assert s["after_url"] is not None

    # 3. Chat with Real Agent Engine requesting slide modification
    res_chat = studio_client.post(
        f"/api/v1/sessions/{session_id}/chat",
        json={"message": "Sửa tiêu đề slide 1 thành 'Báo Cáo Tăng Trưởng Q4'"},
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()

    assert "assistant_message" in chat_data
    assert len(chat_data["tool_calls"]) >= 1
    assert chat_data["tool_calls"][0]["tool_name"] == "edit_slide_text"
    assert 1 in chat_data["modified_slide_indices"]

    # 4. Fetch full deck state again: verify Delta Re-render and Modified flag on slide 1
    res_deck_after = studio_client.get(f"/api/v1/sessions/{session_id}/deck")
    assert res_deck_after.status_code == 200
    deck_after = res_deck_after.json()

    assert 1 in deck_after["modified_slide_indices"]
    slide_1 = next(s for s in deck_after["slides"] if s["index"] == 1)
    assert slide_1["modified"] is True
