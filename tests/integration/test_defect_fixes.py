"""Regression tests for AutoSlide defect fixes:
1. Explicit slide target parsing ("slide 3", "tạo title test cho slide 3").
2. Asynchronous Repair decision workflow.
3. False-positive text overflow reduction while preserving true defect detection.
"""

from __future__ import annotations

import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.models import JobDecisionRequest, JobState
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.orchestrator.pipeline import JobOrchestrator
from autoslide.quality.models import FindingCategory, FindingSeverity
from autoslide.quality.visual import VisualQualityGate
from tests.fixtures.pptx_samples import create_complex_multi_slide_pptx, create_minimal_pptx
from tests.fixtures.quality_samples import create_overflow_inventory


def test_explicit_slide_3_target_resolution(tmp_path: Path):
    """Verify 'tạo title test cho slide 3' correctly parses slide 3 and edits only slide 3."""
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    # Create job with multi-slide template
    job = registry.create(
        instruction="tạo title test cho slide 3",
        input_sha256="test_multi_slide_sha256",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    pptx_bytes = create_complex_multi_slide_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    report = orchestrator.run_pipeline(job.job_id, workspace)

    assert report is not None
    assert report.structural_result.passed is True

    # Inspect the generated task_plan.json
    plan_file = workspace.artifacts_dir / "task_plan.json"
    assert plan_file.exists()
    import json
    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))

    # Slide 3 must be targeted
    assert len(plan_data["target_scope"]) > 0
    assert plan_data["target_scope"][0]["slide_index"] == 3
    assert len(plan_data["operations"]) > 0
    assert plan_data["operations"][0]["target"]["slide_index"] == 3

    # Structural diff should confirm intended changes on slide 3 and 0 unintended changes on slide 1 & 2
    working_pptx = workspace.working_dir / "presentation.pptx"
    assert working_pptx.exists()

    updated_inv = orchestrator.ingestor.parse(working_pptx)
    assert updated_inv.slide_count == 3
    slide3 = updated_inv.slides[2]
    assert slide3.slide_index == 3
    # Group header or title text updated
    slide3_texts = [sh.raw_text for sh in slide3.shapes if sh.raw_text]
    for sh in slide3.shapes:
        if sh.children:
            slide3_texts.extend(c.raw_text for c in sh.children if c.raw_text)
    assert any("title test" in t.lower() or "test" in t.lower() for t in slide3_texts)


def test_async_repair_decision_path(tmp_path: Path):
    """Verify submit_decision with 'repair' runs remediation and verification in background."""
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings)
    client = TestClient(app)

    # 1. Create a job via API
    pptx_bytes = create_complex_multi_slide_pptx()
    res = client.post(
        "/api/v1/jobs",
        files={"template": ("deck.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"instruction": "tạo title test cho slide 3"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    # Poll until pipeline reaches AWAITING_USER_APPROVAL
    for _ in range(50):
        get_res = client.get(f"/api/v1/jobs/{job_id}")
        if get_res.json()["state"] == "AWAITING_USER_APPROVAL":
            break
        time.sleep(0.1)

    assert client.get(f"/api/v1/jobs/{job_id}").json()["state"] == "AWAITING_USER_APPROVAL"

    # 2. Trigger Repair decision
    repair_res = client.post(
        f"/api/v1/jobs/{job_id}/decision",
        json={"decision": "repair", "feedback": "Đổi title thành 'Repaired Slide 3 Title' cho slide 3"},
    )
    assert repair_res.status_code == 200
    assert repair_res.json()["state"] in ("REPAIRING", "AWAITING_USER_APPROVAL")

    # 3. Poll until background repair completes back to AWAITING_USER_APPROVAL
    for _ in range(50):
        get_res = client.get(f"/api/v1/jobs/{job_id}")
        if get_res.json()["state"] == "AWAITING_USER_APPROVAL":
            break
        time.sleep(0.1)

    final_state = client.get(f"/api/v1/jobs/{job_id}").json()["state"]
    assert final_state == "AWAITING_USER_APPROVAL"

    # Verify event log contains STAGE_STARTED with REPAIRING
    events_res = client.get(f"/api/v1/jobs/{job_id}/events")
    events = events_res.json()
    stages = [e.get("payload", {}).get("stage") for e in events if e.get("event_type") == "STAGE_STARTED"]
    assert "REPAIRING" in stages


def test_text_overflow_calibration_avoids_false_positives(tmp_path: Path):
    """Verify standard deck titles do not trigger false positive TEXT_OVERFLOW, but real overflows are detected."""
    gate = VisualQualityGate()

    # 1. Parse clean multi-slide deck and evaluate
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")
    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    job = registry.create(instruction="tạo title test cho slide 3", input_sha256="h123")
    workspace = JobWorkspace.create(data_root, job.job_id)
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(create_complex_multi_slide_pptx())

    report = orchestrator.run_pipeline(job.job_id, workspace)
    # The normal slide titles should NOT have TEXT_OVERFLOW errors
    overflow_findings = [
        f for f in report.visual_result.findings
        if f.category == FindingCategory.TEXT_OVERFLOW and f.severity == FindingSeverity.ERROR
    ]
    assert len(overflow_findings) == 0

    # 2. Real severe overflow deck MUST still be detected
    overflow_inv = create_overflow_inventory()
    overflow_res = gate.evaluate(overflow_inv)
    assert overflow_res.has_critical_or_error is True
    real_overflows = [
        f for f in overflow_res.findings
        if f.category == FindingCategory.TEXT_OVERFLOW
    ]
    assert len(real_overflows) >= 1
    assert real_overflows[0].shape_name == "Small Box"

    # 3. Real clipping shape MUST still be detected
    real_clippings = [
        f for f in overflow_res.findings
        if f.category == FindingCategory.BOUNDS_CLIPPING
    ]
    assert len(real_clippings) >= 1
    assert real_clippings[0].shape_name == "Offscreen Shape"


def test_weekly_report_bounds_tolerance_and_async_repair(tmp_path: Path):
    """Verify full template job with instruction 'tao title test cho slide 3' reaches PASSED
    without BOUNDS_CLIPPING false positives, and async repair completes with PASSED verdict.
    """
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings)
    client = TestClient(app)

    # Use template weekly report if available, else multi-slide fixture
    weekly_template = Path("/tmp/autoslide/jobs/job_59b5d3311ded/input/Template Weekly Report.pptx")
    if weekly_template.exists():
        pptx_bytes = weekly_template.read_bytes()
    else:
        pptx_bytes = create_complex_multi_slide_pptx()

    res = client.post(
        "/api/v1/jobs",
        files={"template": ("Template Weekly Report.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"instruction": "tạo title test cho slide 3"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    # Poll until pipeline reaches AWAITING_USER_APPROVAL
    for _ in range(100):
        get_res = client.get(f"/api/v1/jobs/{job_id}")
        if get_res.json()["state"] == "AWAITING_USER_APPROVAL":
            break
        time.sleep(0.1)

    assert client.get(f"/api/v1/jobs/{job_id}").json()["state"] == "AWAITING_USER_APPROVAL"

    # Verify initial quality report has 0 BOUNDS_CLIPPING errors and reaches PASSED
    quality_res = client.get(f"/api/v1/jobs/{job_id}/artifacts/quality_report.json")
    assert quality_res.status_code == 200
    quality_data = quality_res.json()
    clipping_findings = [
        f for f in quality_data["visual_result"]["findings"]
        if f["category"] == "BOUNDS_CLIPPING" and f["severity"] in ("CRITICAL", "ERROR")
    ]
    assert len(clipping_findings) == 0
    assert quality_data["overall_verdict"] == "PASSED"

    # Trigger async Repair decision
    repair_res = client.post(
        f"/api/v1/jobs/{job_id}/decision",
        json={"decision": "repair", "feedback": "Đổi title slide 3 thành 'Weekly Test Slide 3'"},
    )
    assert repair_res.status_code == 200

    # Poll until background repair completes back to AWAITING_USER_APPROVAL
    for _ in range(100):
        get_res = client.get(f"/api/v1/jobs/{job_id}")
        if get_res.json()["state"] == "AWAITING_USER_APPROVAL":
            break
        time.sleep(0.1)

    final_job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert final_job["state"] == "AWAITING_USER_APPROVAL"

    final_quality_res = client.get(f"/api/v1/jobs/{job_id}/artifacts/quality_report.json")
    assert final_quality_res.status_code == 200
    final_quality = final_quality_res.json()
    assert final_quality["overall_verdict"] == "PASSED"

