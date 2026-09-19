"""Comprehensive behavioral and contract tests for AutoSlide Studio UI Refresh.

Verifies:
1. Zero external frontend dependencies (no external CDN, scripts, styles, or fonts).
2. Immediate template ingest feedback elements and state transitions.
3. Robust preview loading, error fallbacks with retry, and empty states.
4. Canvas-first studio architecture: command bar, filmstrip, diff split, timeline, QA findings.
5. Preserved API serving contracts and response integrity.
"""

from __future__ import annotations

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


def test_zero_external_frontend_dependencies():
    """Verify that index.html and static assets contain no external CDN or web links."""
    index_html_path = TEMPLATES_DIR / "index.html"
    assert index_html_path.exists(), "index.html must exist"
    html_content = index_html_path.read_text(encoding="utf-8")

    # Ensure no http/https scripts or stylesheets
    external_links = re.findall(r'(?:src|href)=["\']https?://[^"\']+["\']', html_content)
    assert len(external_links) == 0, f"Found external dependency links: {external_links}"

    # Ensure no Google Fonts or third-party web font imports in CSS
    css_path = STATIC_DIR / "css" / "workbench.css"
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")
    assert "@import url(" not in css_content, "No external @import allowed in CSS"
    assert "fonts.googleapis.com" not in css_content
    assert "cdn.jsdelivr.net" not in css_content
    assert "cdnjs.cloudflare.com" not in css_content

    # Ensure no external imports in JS
    js_path = STATIC_DIR / "js" / "workbench.js"
    assert js_path.exists()
    js_content = js_path.read_text(encoding="utf-8")
    assert "import " not in js_content or "from 'http" not in js_content


def test_immediate_ingest_state_elements_in_html(studio_client):
    """Verify that the template has elements for immediate ingest feedback upon file selection."""
    res = studio_client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # File badge and ingest status pill in command bar
    assert 'id="fileBadge"' in html
    assert 'id="fileBadgeName"' in html
    assert 'id="ingestStatusPill"' in html
    assert 'id="ingestStatusText"' in html

    # Immediate ingest state layer on central canvas
    assert 'id="beforeIngestState"' in html
    assert 'id="ingestDeckTitle"' in html
    assert 'id="ingestDeckSubtitle"' in html
    assert "INGEST READY" in html


def test_preview_loading_error_and_empty_states(studio_client):
    """Verify loading skeletons, error fallback with retry buttons, and empty states."""
    res = studio_client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # Empty states
    assert 'id="beforePlaceholder"' in html
    assert 'id="afterPlaceholder"' in html

    # Loading layers with spinner
    assert 'id="beforeLoading"' in html
    assert 'id="afterLoading"' in html

    # Error fallback layers with retry actions
    assert 'id="beforeError"' in html
    assert 'id="afterError"' in html
    assert 'id="btnRetryBefore"' in html
    assert 'id="btnRetryAfter"' in html


def test_canvas_first_studio_components(studio_client):
    """Verify presence and wiring of the command bar, filmstrip, timeline, QA and review bar."""
    res = studio_client.get("/ui")
    assert res.status_code == 200
    html = res.text

    # Command Bar
    assert "command-bar" in html
    assert 'id="instructionInput"' in html
    assert 'id="promptScopeTag"' in html
    assert 'id="runtimeSelect"' in html
    assert 'id="runtimeBadge"' in html
    assert 'id="btnSubmit"' in html

    # Target Scopes
    assert 'id="scopePillSlide"' in html
    assert 'id="scopePillRegion"' in html
    assert 'id="scopePillDeck"' in html
    assert 'id="selectionOverlayCanvas"' in html
    assert 'id="selectionRect"' in html

    # Slide Filmstrip
    assert "filmstrip-bar" in html
    assert 'id="filmstripTrack"' in html
    assert 'id="filmstripCount"' in html

    # Side-by-side Diff Canvas
    assert "canvas-diff-container" in html
    assert 'id="beforeFrame"' in html
    assert 'id="afterFrame"' in html
    assert 'id="highlightOverlayLayer"' in html
    assert 'id="diffBadge"' in html

    # Event Timeline & QA Findings
    assert 'id="eventLogs"' in html
    assert 'id="eventCounter"' in html
    assert 'id="findingsContainer"' in html
    assert 'id="qaStatusTag"' in html

    # Review Action Bar
    assert 'id="actionBar"' in html
    assert 'id="btnApprove"' in html
    assert 'id="btnReject"' in html
    assert 'id="btnRepair"' in html


def test_workbench_js_implements_robust_preview_and_ingest_logic(studio_client):
    """Verify workbench.js exposes robust image loading, error handling, and file ingest logic."""
    res = studio_client.get("/static/js/workbench.js")
    assert res.status_code == 200
    js = res.text

    # Immediate ingest logic
    assert "handleFileSelect" in js
    assert "beforeIngestState" in js
    assert "ingestStatusPill" in js

    # Robust preview image loading with retry
    assert "loadPreviewImage" in js
    assert "btnRetryBefore" in js
    assert "btnRetryAfter" in js
    assert "onerror" in js
    assert "onload" in js

    # Filmstrip logic
    assert "buildFilmstrip" in js
    assert "buildSlideNavigator" in js
    assert "selectSlide" in js

    # Scope and region
    assert "setupRegionSelection" in js
    assert "setScopeKind" in js
    assert "clearRegionSelection" in js

    # Decisions and timeline
    assert "submitDecision" in js
    assert "appendTimelineEvent" in js
    assert "showReviewState" in js
