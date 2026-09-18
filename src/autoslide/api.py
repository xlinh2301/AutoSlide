"""FastAPI application factory and route definitions for AutoSlide."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.models import JobDecisionRequest, JobDecisionResponse, JobRecord, JobState
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.orchestrator.pipeline import JobOrchestrator
from autoslide.runtime.discovery import RuntimeRegistry
from autoslide.ui import STATIC_DIR, TEMPLATES_DIR


def create_app(
    settings: Settings | None = None,
    registry: JobRegistry | None = None,
    runtime_registry: RuntimeRegistry | None = None,
    event_log: EventLog | None = None,
    orchestrator: JobOrchestrator | None = None,
) -> FastAPI:
    """Create and wire the AutoSlide FastAPI application."""
    app_settings = settings or Settings.from_env()
    app_settings.ensure_directories()

    app_registry = registry or JobRegistry(app_settings.data_root / "jobs.db")
    app_runtime_registry = runtime_registry or RuntimeRegistry()
    app_event_log = event_log or EventLog(log_path=app_settings.data_root / "logs")
    app_orchestrator = orchestrator or JobOrchestrator(
        registry=app_registry,
        event_log=app_event_log,
    )

    app = FastAPI(
        title="AutoSlide Foundation API",
        version="0.1.0",
        description="Local-first slide editing job runtime and agent orchestrator",
    )

    # Static assets mount
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Workbench UI Web Routes
    @app.get("/", response_class=HTMLResponse)
    @app.get("/ui", response_class=HTMLResponse)
    def render_workbench() -> HTMLResponse:
        index_path = TEMPLATES_DIR / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>AutoSlide Workbench UI</h1>", status_code=200)
        return HTMLResponse(index_path.read_text(encoding="utf-8"), status_code=200)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/runtimes")
    def list_runtimes() -> list[dict]:
        statuses = app_runtime_registry.detect_all()
        return [s.model_dump() for s in statuses]

    @app.post("/api/v1/jobs")
    async def create_job(
        background_tasks: BackgroundTasks,
        template: UploadFile = File(...),
        instruction: str = Form(...),
        runtime: str | None = Form(None),
    ) -> JSONResponse:
        cleaned_instruction = instruction.strip()
        if not cleaned_instruction:
            raise HTTPException(status_code=400, detail="Instruction cannot be empty")

        filename = template.filename or "template.pptx"
        if not filename.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail="Only .pptx files are supported for template uploads")

        content = await template.read()
        if len(content) > app_settings.max_job_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed limit of {app_settings.max_job_size_bytes} bytes",
            )

        if runtime is not None and runtime not in app_settings.allowed_runtimes:
            raise HTTPException(
                status_code=400,
                detail=f"Requested runtime '{runtime}' is not in allowed runtimes: {app_settings.allowed_runtimes}",
            )

        input_sha256 = hashlib.sha256(content).hexdigest()
        job_record = app_registry.create(instruction=cleaned_instruction, input_sha256=input_sha256)

        workspace = JobWorkspace.create(app_settings.data_root, job_record.job_id)
        safe_filename = Path(filename).name
        input_path = workspace.root / "input" / safe_filename
        input_path.write_bytes(content)

        # Record initial ingestion checkpoint
        workspace.write_checkpoint("INGESTED", input_path)

        # Log creation event
        app_event_log.append(
            job_record.job_id,
            "JOB_CREATED",
            {
                "instruction": cleaned_instruction,
                "input_sha256": input_sha256,
                "filename": safe_filename,
            },
        )

        def _execute_pipeline_bg(job_id: str, ws: JobWorkspace) -> None:
            try:
                app_orchestrator.run_pipeline(job_id=job_id, workspace=ws)
            except Exception as exc:
                try:
                    curr_job = app_registry.get(job_id)
                    if curr_job.state not in (
                        JobState.FAILED,
                        JobState.ACCEPTED,
                        JobState.REJECTED,
                        JobState.CANCELLED,
                    ):
                        app_registry.transition(job_id, JobState.FAILED)
                except Exception:
                    pass
                app_event_log.append(
                    job_id,
                    "PIPELINE_ERROR",
                    {"error": str(exc)},
                )

        background_tasks.add_task(_execute_pipeline_bg, job_record.job_id, workspace)

        return JSONResponse(status_code=202, content=job_record.model_dump())

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            record = app_registry.get(job_id)
            return record.model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    @app.get("/api/v1/jobs/{job_id}/events")
    def get_job_events(job_id: str) -> list[dict]:
        try:
            app_registry.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        events = app_event_log.get_events(job_id)
        return [e.model_dump() for e in events]

    @app.get("/api/v1/jobs/{job_id}/events/stream")
    async def stream_job_events(job_id: str) -> StreamingResponse:
        try:
            app_registry.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        async def event_generator() -> AsyncGenerator[str, None]:
            seen = 0
            for _ in range(30):
                events = app_event_log.get_events(job_id)
                if len(events) > seen:
                    for ev in events[seen:]:
                        yield f"event: agent_event\ndata: {ev.model_dump_json()}\n\n"
                    seen = len(events)
                await asyncio.sleep(0.5)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/v1/jobs/{job_id}/decision")
    def submit_decision(
        job_id: str,
        request: JobDecisionRequest,
        background_tasks: BackgroundTasks,
    ) -> dict:
        try:
            current_job = app_registry.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        decision = request.decision
        target_state: JobState

        if decision == "approve":
            target_state = JobState.ACCEPTED
            message = "Job approved and marked as accepted."
            download_url = f"/api/v1/jobs/{job_id}/artifacts/presentation.pptx"
        elif decision == "reject":
            target_state = JobState.REJECTED
            message = "Job rejected by user."
            download_url = None
        elif decision == "repair":
            target_state = JobState.REPAIRING
            message = "Job repair requested."
            download_url = None
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported decision '{decision}'")

        try:
            # Force or transition based on current state
            if current_job.state in (JobState.AWAITING_USER_APPROVAL, JobState.VERIFYING, JobState.CREATED):
                updated_job = app_registry.transition(job_id, target_state)
            else:
                app_registry.force_state(job_id, target_state)
                updated_job = app_registry.get(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        app_event_log.append(
            job_id,
            "HUMAN_DECISION",
            {
                "decision": decision,
                "feedback": request.feedback,
                "resulting_state": target_state.value,
            },
        )

        if decision == "repair":
            def _execute_repair_bg(j_id: str, ws: JobWorkspace, feedback: str | None) -> None:
                try:
                    app_orchestrator.run_repair(job_id=j_id, workspace=ws, feedback=feedback)
                except Exception as exc:
                    try:
                        app_registry.force_state(j_id, JobState.FAILED)
                    except Exception:
                        pass
                    app_event_log.append(
                        j_id,
                        "REPAIR_ERROR",
                        {"error": str(exc)},
                    )

            workspace = JobWorkspace(root=app_settings.data_root / "jobs" / job_id, job_id=job_id)
            background_tasks.add_task(_execute_repair_bg, job_id, workspace, request.feedback)

        resp = JobDecisionResponse(
            job_id=job_id,
            state=updated_job.state,
            message=message,
            download_url=download_url,
        )
        return resp.model_dump()

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        try:
            record = app_registry.transition(job_id, JobState.CANCELLED)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        app_event_log.append(
            job_id,
            "JOB_CANCELLED",
            {"message": "Job cancelled by user request"},
        )
        return record.model_dump()

    @app.get("/api/v1/jobs/{job_id}/artifacts/{artifact_name}")
    def get_artifact(job_id: str, artifact_name: str) -> FileResponse:
        try:
            app_registry.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        workspace_root = app_settings.data_root / "jobs" / job_id
        candidate_dirs = [
            workspace_root / "checkpoints",
            workspace_root / "artifacts",
            workspace_root / "previews",
            workspace_root / "working",
            workspace_root / "input",
        ]

        found_path: Path | None = None
        for base_dir in candidate_dirs:
            candidate = (base_dir / artifact_name).resolve()
            try:
                candidate.relative_to(base_dir)
                if candidate.is_file():
                    found_path = candidate
                    break
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid path traversal attempted")

        if not found_path:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_name}")

        return FileResponse(found_path, filename=found_path.name)

    return app
