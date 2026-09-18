"""Integration tests for Preview Diff and Targeted Slide or Region Editing Pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from autoslide.events import EventLog
from autoslide.jobs.models import (
    DeckPreviewDiff,
    EditScope,
    JobState,
    NormalizedRegion,
)
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.orchestrator.pipeline import JobOrchestrator
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx


def test_pipeline_slide_scope_targets_only_selected_slide(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(
        instruction="Update title to Target Slide 2",
        input_sha256="multi_slide_sha",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    scope = EditScope(kind="slide", slide_index=2)
    report = orchestrator.run_pipeline(job.job_id, workspace, scope=scope)

    assert report is not None
    assert report.structural_result.passed is True

    # Inspect task_plan.json
    plan_file = workspace.artifacts_dir / "task_plan.json"
    assert plan_file.exists()
    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    assert len(plan_data["target_scope"]) > 0
    assert plan_data["target_scope"][0]["slide_index"] == 2

    # Inspect preview_diff.json
    diff_file = workspace.artifacts_dir / "preview_diff.json"
    assert diff_file.exists()
    diff_data = json.loads(diff_file.read_text(encoding="utf-8"))
    assert diff_data["total_slides"] == 3
    assert diff_data["changed_slides_count"] == 1

    slide1_diff = diff_data["slides"][0]
    assert slide1_diff["status"] == "unchanged"

    slide2_diff = diff_data["slides"][1]
    assert slide2_diff["status"] == "modified"
    assert len(slide2_diff["overlays"]) > 0

    # Ensure before/after preview artifacts exist
    previews_dir = workspace.root / "previews"
    assert (previews_dir / "slide_001_before.png").exists()
    assert (previews_dir / "slide_001_after.png").exists()
    assert (previews_dir / "slide_002_before.png").exists()
    assert (previews_dir / "slide_002_after.png").exists()


def test_pipeline_deck_scope_targets_all_slides(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(
        instruction="Update title to All Hands Global Title",
        input_sha256="multi_slide_sha",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    scope = EditScope(kind="deck")
    report = orchestrator.run_pipeline(job.job_id, workspace, scope=scope)

    assert report is not None
    assert report.structural_result.passed is True

    plan_file = workspace.artifacts_dir / "task_plan.json"
    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    targeted_slides = {ts["slide_index"] for ts in plan_data["target_scope"]}
    assert targeted_slides == {1, 2, 3}

    diff_file = workspace.artifacts_dir / "preview_diff.json"
    diff_data = json.loads(diff_file.read_text(encoding="utf-8"))
    assert diff_data["changed_slides_count"] == 3
    for s in diff_data["slides"]:
        assert s["status"] == "modified"
        assert len(s["overlays"]) > 0


def test_pipeline_region_scope_resolves_targeted_shape(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(
        instruction="Change to Selected Region Heading",
        input_sha256="multi_slide_sha",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    # Slide 1: Title 1 is at x=500000, y=500000, cx=8000000, cy=1000000 of 9144000x6858000
    # Normalized: x ~ 0.054, y ~ 0.073, w ~ 0.875, h ~ 0.146
    reg = NormalizedRegion(x=0.05, y=0.05, width=0.85, height=0.20)
    scope = EditScope(kind="region", slide_index=1, region=reg)

    report = orchestrator.run_pipeline(job.job_id, workspace, scope=scope)
    assert report is not None
    assert report.structural_result.passed is True

    plan_file = workspace.artifacts_dir / "task_plan.json"
    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    assert plan_data["target_scope"][0]["slide_index"] == 1

    working_pptx = workspace.working_dir / "presentation.pptx"
    updated_inv = orchestrator.ingestor.parse(working_pptx)
    slide1 = updated_inv.slides[0]
    slide1_texts = [sh.raw_text for sh in slide1.shapes]
    assert any("selected region heading" in t.lower() for t in slide1_texts)


def test_pipeline_unresolvable_region_transitions_to_review(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(
        instruction="Change empty corner text",
        input_sha256="multi_slide_sha",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    # Empty region in bottom right corner where no shapes exist
    reg = NormalizedRegion(x=0.92, y=0.92, width=0.05, height=0.05)
    scope = EditScope(kind="region", slide_index=1, region=reg)

    report = orchestrator.run_pipeline(job.job_id, workspace, scope=scope)

    assert report.overall_verdict == "NEEDS_REVIEW"
    updated_job = registry.get(job.job_id)
    assert updated_job.state == JobState.AWAITING_USER_APPROVAL

    events = event_log.get_events(job.job_id)
    event_types = [e.event_type for e in events]
    assert "NEEDS_CLARIFICATION" in event_types


def test_original_pptx_remains_strictly_immutable(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(
        instruction="Modify everything on all slides",
        input_sha256="immutable_check_sha",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)
    original_sha = hashlib.sha256(input_file.read_bytes()).hexdigest()

    scope = EditScope(kind="deck")
    orchestrator.run_pipeline(job.job_id, workspace, scope=scope)

    # Assert byte-exact identity of input presentation after pipeline execution
    post_execution_sha = hashlib.sha256(input_file.read_bytes()).hexdigest()
    assert original_sha == post_execution_sha
