"""Tests for Phase 6 Workbench API endpoints: UI serving, decisions, and SSE streams."""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.models import JobState
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.discovery import RuntimeRegistry
from tests.fixtures.workbench_samples import (
    create_sample_decision_approve,
    create_sample_decision_reject,
    create_sample_decision_repair,
)


@pytest.fixture
def client(tmp_path: Path):
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
    return TestClient(app), registry, event_log


def test_workbench_ui_routes_serve_html(client):
    test_client, _, _ = client

    res_root = test_client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers["content-type"]
    assert "AutoSlide Workbench" in res_root.text

    res_ui = test_client.get("/ui")
    assert res_ui.status_code == 200
    assert "AutoSlide Workbench" in res_ui.text


def test_static_assets_serve(client):
    test_client, _, _ = client

    res_css = test_client.get("/static/css/workbench.css")
    assert res_css.status_code == 200
    assert "workbench-container" in res_css.text

    res_js = test_client.get("/static/js/workbench.js")
    assert res_js.status_code == 200
    assert "submitJob" in res_js.text


def test_submit_decision_approve(client):
    test_client, registry, _ = client

    # Create job in AWAITING_USER_APPROVAL
    job = registry.create(instruction="Edit title", input_sha256="abc12345")
    registry.force_state(job.job_id, JobState.AWAITING_USER_APPROVAL)

    approve_req = create_sample_decision_approve()
    res = test_client.post(f"/api/v1/jobs/{job.job_id}/decision", json=approve_req.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "ACCEPTED"
    assert "artifacts/presentation.pptx" in data["download_url"]

    # Verify state in DB
    updated = registry.get(job.job_id)
    assert updated.state == JobState.ACCEPTED


def test_submit_decision_reject(client):
    test_client, registry, _ = client

    job = registry.create(instruction="Edit title", input_sha256="abc12345")
    registry.force_state(job.job_id, JobState.AWAITING_USER_APPROVAL)

    reject_req = create_sample_decision_reject()
    res = test_client.post(f"/api/v1/jobs/{job.job_id}/decision", json=reject_req.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "REJECTED"

    updated = registry.get(job.job_id)
    assert updated.state == JobState.REJECTED


def test_submit_decision_repair(client):
    test_client, registry, _ = client

    job = registry.create(instruction="Edit title", input_sha256="abc12345")
    registry.force_state(job.job_id, JobState.AWAITING_USER_APPROVAL)

    repair_req = create_sample_decision_repair()
    res = test_client.post(f"/api/v1/jobs/{job.job_id}/decision", json=repair_req.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "REPAIRING"


def test_submit_decision_nonexistent_job_returns_404(client):
    test_client, _, _ = client
    res = test_client.post(
        "/api/v1/jobs/job_unknown/decision",
        json={"decision": "approve"},
    )
    assert res.status_code == 404


def test_runtimes_endpoint_readiness_and_contract(tmp_path: Path):
    from autoslide.runtime.base import RuntimeAdapter, RuntimeHandle
    from autoslide.runtime.models import RuntimeStatus

    class MockReadyAdapter(RuntimeAdapter):
        @property
        def name(self) -> str:
            return "ready-agent"

        def detect(self) -> RuntimeStatus:
            return RuntimeStatus(name="ready-agent", installed=True, authenticated=True)

        def start(self, job_context, prompt_payload):
            raise NotImplementedError

        def stream(self, handle):
            raise NotImplementedError

        def cancel(self, handle):
            raise NotImplementedError

    class MockUnauthenticatedAdapter(RuntimeAdapter):
        @property
        def name(self) -> str:
            return "unauthenticated-agent"

        def detect(self) -> RuntimeStatus:
            return RuntimeStatus(name="unauthenticated-agent", installed=True, authenticated=False, reason="Auth missing")

        def start(self, job_context, prompt_payload):
            raise NotImplementedError

        def stream(self, handle):
            raise NotImplementedError

        def cancel(self, handle):
            raise NotImplementedError

    runtime_registry = RuntimeRegistry([MockReadyAdapter(), MockUnauthenticatedAdapter()])
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings, runtime_registry=runtime_registry)
    test_client = TestClient(app)

    res = test_client.get("/api/v1/runtimes")
    assert res.status_code == 200
    runtimes = res.json()

    ready = next((r for r in runtimes if r["name"] == "ready-agent"), None)
    assert ready is not None
    assert ready["installed"] is True
    assert ready["authenticated"] is True
    assert ready["available"] is True

    unauthed = next((r for r in runtimes if r["name"] == "unauthenticated-agent"), None)
    assert unauthed is not None
    assert unauthed["installed"] is True
    assert unauthed["authenticated"] is False
    assert unauthed["available"] is False


def test_default_runtime_registry_endpoint_exposes_all_runtimes(tmp_path: Path):
    settings = Settings(data_root=tmp_path / "data")
    app = create_app(settings=settings)
    test_client = TestClient(app)

    res = test_client.get("/api/v1/runtimes")
    assert res.status_code == 200
    runtimes = res.json()
    names = [r["name"] for r in runtimes]
    assert "codex" in names
    assert "gemini" in names
    assert "claude" in names
    assert "antigravity" in names
    for r in runtimes:
        assert "available" in r
        assert "installed" in r
        assert "authenticated" in r


def test_job_creation_dispatches_pipeline_and_advances_beyond_created(tmp_path: Path):
    import io
    from tests.fixtures.pptx_samples import create_minimal_pptx

    settings = Settings(data_root=tmp_path / "data")
    registry = JobRegistry(tmp_path / "jobs.db")
    event_log = EventLog(tmp_path / "logs")
    app = create_app(settings=settings, registry=registry, event_log=event_log)
    test_client = TestClient(app)

    pptx_bytes = create_minimal_pptx()
    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"instruction": "Change slide title to Executive Summary", "runtime": "codex"},
    )
    assert res.status_code == 202
    job_data = res.json()
    job_id = job_data["job_id"]
    assert job_data["state"] == "CREATED"

    # Verify that the background task advanced the job state
    job_status_res = test_client.get(f"/api/v1/jobs/{job_id}")
    assert job_status_res.status_code == 200
    current_job = job_status_res.json()
    assert current_job["state"] == "AWAITING_USER_APPROVAL"

    # Verify event stream records the transitions
    events_res = test_client.get(f"/api/v1/jobs/{job_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    event_types = [e["event_type"] for e in events]
    assert "JOB_CREATED" in event_types
    assert "STAGE_STARTED" in event_types
    assert "AWAITING_APPROVAL" in event_types

    # Ensure artifacts were generated and accessible
    art_res = test_client.get(f"/api/v1/jobs/{job_id}/artifacts/quality_report.json")
    assert art_res.status_code == 200
    assert "overall_verdict" in art_res.json()


def test_concurrent_job_state_and_events_polling(tmp_path: Path):
    import concurrent.futures
    import io
    from tests.fixtures.pptx_samples import create_minimal_pptx

    settings = Settings(data_root=tmp_path / "data")
    registry = JobRegistry(tmp_path / "jobs.db")
    event_log = EventLog(tmp_path / "logs")
    app = create_app(settings=settings, registry=registry, event_log=event_log)
    test_client = TestClient(app)

    pptx_bytes = create_minimal_pptx()
    res = test_client.post(
        "/api/v1/jobs",
        files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/octet-stream")},
        data={"instruction": "Concurrent test", "runtime": "codex"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    errors = []

    def poll_job():
        try:
            r = test_client.get(f"/api/v1/jobs/{job_id}")
            if r.status_code != 200:
                errors.append(f"Unexpected status code {r.status_code}")
        except Exception as e:
            errors.append(str(e))

    def poll_events():
        try:
            r = test_client.get(f"/api/v1/jobs/{job_id}/events")
            if r.status_code != 200:
                errors.append(f"Unexpected status code {r.status_code}")
        except Exception as e:
            errors.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for _ in range(25):
            futures.append(executor.submit(poll_job))
            futures.append(executor.submit(poll_events))
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert len(errors) == 0, f"Concurrent polling produced errors: {errors}"


