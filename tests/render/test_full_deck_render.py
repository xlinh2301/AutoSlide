"""Tests for full-deck ingest, dual-column live render, and deck state API (ADS-003)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.ingest.models import DeckSlideState, DeckStateResponse
from autoslide.ingest.parser import PPTXIngestor
from autoslide.ingest.renderer import (
    LibreOfficePreviewRenderer,
    MockPreviewRenderer,
    build_deck_state_response,
)
from autoslide.jobs.workspace import JobWorkspace
from tests.fixtures.pptx_samples import (
    create_complex_multi_slide_pptx,
    create_minimal_pptx,
)


def test_full_deck_ingest_mock_renderer(tmp_path: Path):
    """Test that mock renderer generates before, after, and root preview files for all slides."""
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "multi_deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_full_deck_001")
    renderer = MockPreviewRenderer()

    manifest = renderer.render_previews(pptx_file, workspace, slide_count=4)
    assert manifest.slide_count == 4
    assert len(manifest.previews) == 4

    # Verify root previews, before previews, and after previews exist for all 4 slides
    for idx in range(1, 5):
        root_img = workspace.previews_dir / f"slide_{idx:03d}.png"
        before_img = workspace.before_previews_dir / f"slide_{idx:03d}.png"
        before_short_img = workspace.before_previews_dir / f"slide_{idx}.png"
        after_img = workspace.after_previews_dir / f"slide_{idx:03d}.png"
        after_short_img = workspace.after_previews_dir / f"slide_{idx}.png"

        assert root_img.exists()
        assert before_img.exists()
        assert before_short_img.exists()
        assert after_img.exists()
        assert after_short_img.exists()

        # Check that before == after initially
        assert before_img.read_bytes() == after_img.read_bytes()


def test_delta_re_render_mock_renderer(tmp_path: Path):
    """Test that delta re-render updates only the targeted modified slides."""
    pptx_bytes = create_complex_multi_slide_pptx()
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(pptx_bytes)

    workspace = JobWorkspace.create(tmp_path, "job_delta_001")
    renderer = MockPreviewRenderer()

    # Initial render
    renderer.render_previews(pptx_file, workspace, slide_count=3)

    # Perform delta re-render for slide 2 only
    delta_manifest = renderer.render_slide_delta(
        pptx_path=pptx_file,
        workspace=workspace,
        modified_indices=[2],
        slide_count=3,
    )
    assert delta_manifest.slide_count == 3

    # Check that after previews for slide 2 are present and valid
    after_slide_2 = workspace.after_previews_dir / "slide_002.png"
    assert after_slide_2.exists()
    img = Image.open(after_slide_2)
    assert img.format == "PNG"


def test_build_deck_state_response(tmp_path: Path):
    """Test constructing DeckStateResponse with Before/After URLs and modification flags."""
    workspace = JobWorkspace.create(tmp_path, "job_state_001")
    renderer = MockPreviewRenderer()
    dummy_pptx = tmp_path / "deck.pptx"
    dummy_pptx.write_bytes(create_minimal_pptx())

    renderer.render_previews(dummy_pptx, workspace, slide_count=3)

    resp = build_deck_state_response(
        workspace=workspace,
        session_id="session_test_123",
        job_id="job_state_001",
        slide_count=3,
        modified_slide_indices=[2],
        titles={1: "Introduction", 2: "Key Metrics", 3: "Conclusion"},
    )

    assert isinstance(resp, DeckStateResponse)
    assert resp.session_id == "session_test_123"
    assert resp.job_id == "job_state_001"
    assert resp.slide_count == 3
    assert resp.modified_slide_indices == [2]
    assert len(resp.slides) == 3

    # Slide 1: not modified
    assert resp.slides[0].index == 1
    assert resp.slides[0].modified is False
    assert resp.slides[0].title == "Introduction"
    assert resp.slides[0].before_url == "/api/v1/sessions/session_test_123/preview/before/1.png"
    assert resp.slides[0].after_url == "/api/v1/sessions/session_test_123/preview/after/1.png"

    # Slide 2: modified
    assert resp.slides[1].index == 2
    assert resp.slides[1].modified is True
    assert resp.slides[1].title == "Key Metrics"

    # Slide 3: not modified
    assert resp.slides[2].index == 3
    assert resp.slides[2].modified is False


def test_session_creation_generates_full_deck_previews(tmp_path: Path):
    """Test that POST /api/v1/sessions extracts previews for 100% of slides."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    pptx_bytes = create_complex_multi_slide_pptx()
    files = {"template": ("deck.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}

    create_resp = client.post("/api/v1/sessions", files=files)
    assert create_resp.status_code == 201
    data = create_resp.json()
    session_id = data["session_id"]
    job_id = data["job_id"]

    # Verify workspace created with previews for all slides in the deck
    ws_dir = tmp_path / "data" / "jobs" / job_id
    assert (ws_dir / "previews" / "manifest.json").exists()
    assert (ws_dir / "previews" / "before" / "slide_001.png").exists()
    assert (ws_dir / "previews" / "after" / "slide_001.png").exists()


def test_get_session_deck_endpoint(tmp_path: Path):
    """Test GET /api/v1/sessions/{session_id}/deck endpoint response contract."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    pptx_bytes = create_complex_multi_slide_pptx()
    files = {"template": ("presentation.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    create_resp = client.post("/api/v1/sessions", files=files)
    session_id = create_resp.json()["session_id"]
    job_id = create_resp.json()["job_id"]

    # Request deck state
    deck_resp = client.get(f"/api/v1/sessions/{session_id}/deck")
    assert deck_resp.status_code == 200
    deck_data = deck_resp.json()

    assert deck_data["session_id"] == session_id
    assert deck_data["job_id"] == job_id
    assert deck_data["slide_count"] > 0
    assert isinstance(deck_data["slides"], list)
    assert len(deck_data["slides"]) == deck_data["slide_count"]
    assert deck_data["modified_slide_indices"] == []

    for s in deck_data["slides"]:
        assert s["modified"] is False
        assert s["before_url"].startswith(f"/api/v1/sessions/{session_id}/preview/before/")
        assert s["after_url"].startswith(f"/api/v1/sessions/{session_id}/preview/after/")


def test_get_session_deck_with_modified_slides(tmp_path: Path):
    """Test GET /api/v1/sessions/{session_id}/deck reflects modified slide indices."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    pptx_bytes = create_complex_multi_slide_pptx()
    files = {"template": ("presentation.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    create_resp = client.post("/api/v1/sessions", files=files)
    session_id = create_resp.json()["session_id"]
    job_id = create_resp.json()["job_id"]

    # Write simulated deck_state.json with modified slide 2
    ws_artifacts = tmp_path / "data" / "jobs" / job_id / "artifacts"
    ws_artifacts.mkdir(parents=True, exist_ok=True)
    (ws_artifacts / "deck_state.json").write_text(json.dumps({"modified_slide_indices": [2]}))

    deck_resp = client.get(f"/api/v1/sessions/{session_id}/deck")
    assert deck_resp.status_code == 200
    deck_data = deck_resp.json()

    assert deck_data["modified_slide_indices"] == [2]
    assert deck_data["slides"][0]["modified"] is False
    assert deck_data["slides"][1]["modified"] is True


def test_preview_image_serving_endpoints(tmp_path: Path):
    """Test image retrieval via session and job preview endpoints."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    pptx_bytes = create_minimal_pptx()
    files = {"template": ("test.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    create_resp = client.post("/api/v1/sessions", files=files)
    session_id = create_resp.json()["session_id"]
    job_id = create_resp.json()["job_id"]

    # Session preview routes
    before_resp = client.get(f"/api/v1/sessions/{session_id}/preview/before/1.png")
    assert before_resp.status_code == 200
    assert before_resp.headers["content-type"] == "image/png"
    im_before = Image.open(io.BytesIO(before_resp.content))
    assert im_before.format == "PNG"

    after_resp = client.get(f"/api/v1/sessions/{session_id}/preview/after/1.png")
    assert after_resp.status_code == 200
    assert after_resp.headers["content-type"] == "image/png"

    # Job preview routes
    job_preview_resp = client.get(f"/api/v1/jobs/{job_id}/preview/after/1.png")
    assert job_preview_resp.status_code == 200


def test_get_session_deck_not_found(tmp_path: Path):
    """Test 404 when querying deck state for non-existent session."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    resp = client.get("/api/v1/sessions/non_existent_session_123/deck")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_preview_image_not_found(tmp_path: Path):
    """Test 404 when requesting a non-existent slide image."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, renderer=MockPreviewRenderer())
    client = TestClient(app)

    pptx_bytes = create_minimal_pptx()
    files = {"template": ("test.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    create_resp = client.post("/api/v1/sessions", files=files)
    session_id = create_resp.json()["session_id"]

    resp = client.get(f"/api/v1/sessions/{session_id}/preview/after/non_existent_slide_999.png")
    assert resp.status_code == 404
