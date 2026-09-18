"""FastAPI application factory and route definitions for AutoSlide."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.models import JobState
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.runtime.discovery import RuntimeRegistry


def create_app(
    settings: Settings | None = None,
    registry: JobRegistry | None = None,
    runtime_registry: RuntimeRegistry | None = None,
    event_log: EventLog | None = None,
) -> FastAPI:
    """Create and wire the AutoSlide FastAPI application."""
    app_settings = settings or Settings.from_env()
    app_settings.ensure_directories()

    app_registry = registry or JobRegistry(app_settings.data_root / "jobs.db")
    app_runtime_registry = runtime_registry or RuntimeRegistry()
    app_event_log = event_log or EventLog(log_path=app_settings.data_root / "logs")

    app = FastAPI(
        title="AutoSlide Foundation API",
        version="0.1.0",
        description="Local-first slide editing job runtime and agent orchestrator",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/runtimes")
    def list_runtimes() -> list[dict]:
        statuses = app_runtime_registry.detect_all()
        return [s.model_dump() for s in statuses]

    @app.post("/api/v1/jobs")
    async def create_job(
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
