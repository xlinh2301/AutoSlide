"""Tests for Preview Diff and Targeted Slide or Region Editing API endpoints."""

from __future__ import annotations

import io
import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.models import (
    DeckPreviewDiff,
    EditScope,
    NormalizedRegion,
    OverlayBox,
    SlidePreviewDiff,
)
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.discovery import RuntimeRegistry
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


@pytest.fixture
def api_client(tmp_path: Path):
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
    return TestClient(app), registry, event_log, settings


def test_edit_scope_and_diff_models_validation():
    # 1. Valid NormalizedRegion
    reg = NormalizedRegion(x=0.1, y=0.2, width=0.5, height=0.3)
    assert reg.x == 0.1
    assert reg.width == 0.5

    # 2. Out of bounds NormalizedRegion
    with pytest.raises(Exception):
        NormalizedRegion(x=-0.1, y=0.2, width=0.5, height=0.3)
    with pytest.raises(Exception):
        NormalizedRegion(x=0.1, y=0.2, width=1.5, height=0.3)

    # 3. Valid EditScopes
    scope_slide = EditScope(kind="slide", slide_index=2)
    assert scope_slide.kind == "slide"
    assert scope_slide.slide_index == 2

    scope_deck = EditScope(kind="deck")
    assert scope_deck.kind == "deck"

    scope_region = EditScope(kind="region", slide_index=1, region=reg)
    assert scope_region.kind == "region"
    assert scope_region.region.x == 0.1

    # 4. Preview diff models
    overlay = OverlayBox(
        x=0.05,
        y=0.08,
        width=0.8,
        height=0.15,
        shape_name="Title 1",
        object_ref="shape_fp_123",
        change_type="modified",
    )
    slide_diff = SlidePreviewDiff(
        slide_index=1,
        before_image_url="/api/v1/jobs/job_1/artifacts/slide_001_before.png",
        after_image_url="/api/v1/jobs/job_1/artifacts/slide_001_after.png",
        status="modified",
        changed_object_refs=["shape_fp_123"],
        overlays=[overlay],
    )
    deck_diff = DeckPreviewDiff(
        job_id="job_1",
        total_slides=1,
        changed_slides_count=1,
        slides=[slide_diff],
    )
    assert deck_diff.total_slides == 1
    assert deck_diff.changed_slides_count == 1
    assert len(deck_diff.slides[0].overlays) == 1


def test_create_job_with_explicit_slide_scope(api_client):
    test_client, registry, event_log, _ = api_client

    pptx_bytes = create_complex_multi_slide_pptx()
    scope_payload = {"kind": "slide", "slide_index": 2}

    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={
            "instruction": "Update metrics title to Global Metrics",
            "runtime": "codex",
            "scope": json.dumps(scope_payload),
        },
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    # Verify event log captures scope in JOB_CREATED
    events = event_log.get_events(job_id)
    created_ev = next(e for e in events if e.event_type == "JOB_CREATED")
    assert "scope" in created_ev.payload
    assert created_ev.payload["scope"]["kind"] == "slide"
    assert created_ev.payload["scope"]["slide_index"] == 2


def test_create_job_with_all_slides_deck_scope(api_client):
    test_client, registry, event_log, _ = api_client

    pptx_bytes = create_complex_multi_slide_pptx()
    scope_payload = {"kind": "deck"}

    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={
            "instruction": "Set header title to All Hands",
            "runtime": "codex",
            "scope": json.dumps(scope_payload),
        },
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    events = event_log.get_events(job_id)
    created_ev = next(e for e in events if e.event_type == "JOB_CREATED")
    assert created_ev.payload["scope"]["kind"] == "deck"


def test_create_job_with_selected_region_scope(api_client):
    test_client, registry, event_log, _ = api_client

    pptx_bytes = create_complex_multi_slide_pptx()
    scope_payload = {
        "kind": "region",
        "slide_index": 1,
        "region": {"x": 0.05, "y": 0.05, "width": 0.85, "height": 0.20},
    }

    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={
            "instruction": "Change to Region Title",
            "runtime": "codex",
            "scope": json.dumps(scope_payload),
        },
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    events = event_log.get_events(job_id)
    created_ev = next(e for e in events if e.event_type == "JOB_CREATED")
    assert created_ev.payload["scope"]["kind"] == "region"
    assert created_ev.payload["scope"]["slide_index"] == 1
    assert created_ev.payload["scope"]["region"]["x"] == 0.05


def test_create_job_with_invalid_scope_returns_400(api_client):
    test_client, _, _, _ = api_client

    pptx_bytes = create_minimal_pptx()
    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={
            "instruction": "Test instruction",
            "scope": "not-valid-json",
        },
    )
    assert res.status_code == 400


def test_get_preview_diff_endpoints(api_client):
    test_client, registry, _, settings = api_client

    # 1. Nonexistent job returns 404
    res_404 = test_client.get("/api/v1/jobs/unknown_job/diff")
    assert res_404.status_code == 404

    # 2. Existing job before diff is generated returns 404
    job = registry.create(instruction="test", input_sha256="abc")
    res_not_ready = test_client.get(f"/api/v1/jobs/{job.job_id}/diff")
    assert res_not_ready.status_code == 404

    # 3. Create dummy preview_diff.json in artifacts
    job_art_dir = settings.data_root / "jobs" / job.job_id / "artifacts"
    job_art_dir.mkdir(parents=True, exist_ok=True)
    deck_diff = DeckPreviewDiff(
        job_id=job.job_id,
        total_slides=2,
        changed_slides_count=1,
        slides=[
            SlidePreviewDiff(
                slide_index=1,
                before_image_url=f"/api/v1/jobs/{job.job_id}/artifacts/slide_001_before.png",
                after_image_url=f"/api/v1/jobs/{job.job_id}/artifacts/slide_001_after.png",
                status="modified",
                changed_object_refs=["fp_1"],
                overlays=[
                    OverlayBox(
                        x=0.1, y=0.1, width=0.8, height=0.2, shape_name="Title", object_ref="fp_1"
                    )
                ],
            ),
            SlidePreviewDiff(
                slide_index=2,
                before_image_url=f"/api/v1/jobs/{job.job_id}/artifacts/slide_002_before.png",
                after_image_url=f"/api/v1/jobs/{job.job_id}/artifacts/slide_002_after.png",
                status="unchanged",
                changed_object_refs=[],
                overlays=[],
            ),
        ],
    )
    (job_art_dir / "preview_diff.json").write_text(deck_diff.model_dump_json(), encoding="utf-8")

    # Test /diff endpoint
    res = test_client.get(f"/api/v1/jobs/{job.job_id}/diff")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job.job_id
    assert data["total_slides"] == 2
    assert data["changed_slides_count"] == 1
    assert len(data["slides"]) == 2
    assert data["slides"][0]["overlays"][0]["shape_name"] == "Title"

    # Test alias /preview-diff endpoint
    res_alias = test_client.get(f"/api/v1/jobs/{job.job_id}/preview-diff")
    assert res_alias.status_code == 200
    assert res_alias.json()["job_id"] == job.job_id


def test_workbench_ui_exposes_scope_and_diff_controls(api_client):
    test_client, _, _, _ = api_client

    # 1. Verify HTML has scope and diff elements
    res_ui = test_client.get("/ui")
    assert res_ui.status_code == 200
    html = res_ui.text
    assert "Current Slide" in html
    assert "Selected Region" in html
    assert "All Slides" in html
    assert 'id="scopeSlideSelect"' in html
    assert 'id="previewNavigator"' in html
    assert 'id="selectionOverlayCanvas"' in html
    assert 'id="highlightOverlayLayer"' in html

    # 2. Verify JS has scope and drag selection logic
    res_js = test_client.get("/static/js/workbench.js")
    assert res_js.status_code == 200
    js = res_js.text
    assert "setupRegionSelection" in js
    assert "buildSlideNavigator" in js
    assert "renderOverlays" in js
    assert "diff-highlight-box" in js

    # 3. Verify CSS has scope and overlay classes
    res_css = test_client.get("/static/css/workbench.css")
    assert res_css.status_code == 200
    css = res_css.text
    assert ".scope-options" in css
    assert ".selection-overlay-canvas" in css
    assert ".diff-highlight-box" in css
    assert ".preview-navigator" in css
