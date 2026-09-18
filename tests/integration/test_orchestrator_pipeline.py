"""End-to-end integration tests for the full JobOrchestrator pipeline."""

from __future__ import annotations

from pathlib import Path
import pytest

from autoslide.events import EventLog
from autoslide.jobs.models import JobState
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.orchestrator.pipeline import JobOrchestrator
from tests.fixtures.pptx_samples import create_minimal_pptx


def test_orchestrator_full_pipeline_run(tmp_path: Path):
    data_root = tmp_path / "data"
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(data_root / "logs")

    orchestrator = JobOrchestrator(registry=registry, event_log=event_log)

    # 1. Create job & workspace
    job = registry.create(
        instruction="Updated Company Title",
        input_sha256="sample_sha256_hash",
    )
    workspace = JobWorkspace.create(data_root, job.job_id)

    # 2. Write input presentation
    pptx_bytes = create_minimal_pptx()
    input_file = workspace.input_dir / "presentation.pptx"
    input_file.write_bytes(pptx_bytes)

    # 3. Run pipeline
    report = orchestrator.run_pipeline(job.job_id, workspace)

    # 4. Assert report and state machine
    assert report is not None
    assert report.structural_result.passed is True

    updated_job = registry.get(job.job_id)
    assert updated_job.state == JobState.AWAITING_USER_APPROVAL

    # 5. Assert artifacts generated
    assert (workspace.artifacts_dir / "task_plan.json").exists()
    assert (workspace.artifacts_dir / "quality_report.json").exists()
    assert (workspace.artifacts_dir / "visual_findings.json").exists()
    assert (workspace.working_dir / "presentation.pptx").exists()

    # 6. Assert event log captures stages
    events = event_log.get_events(job.job_id)
    event_types = [e.event_type for e in events]
    assert "STAGE_STARTED" in event_types
    assert "AWAITING_APPROVAL" in event_types
