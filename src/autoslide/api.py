"""FastAPI application factory and route definitions for AutoSlide."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import AsyncGenerator
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from autoslide.config import Settings
from autoslide.conversation.clarification import ClarificationEngine
from autoslide.conversation.models import (
    ChatTurn,
    ConversationSession,
    ConversationState,
)
from autoslide.conversation.schemas import (
    ApproveDecisionRequest,
    ApproveDecisionResponse,
    CreateSessionResponse,
    ExecuteSessionResponse,
    SendMessageRequest,
    SessionDetailResponse,
    SessionEventsResponse,
)
from autoslide.conversation.service import (
    ConversationResponse,
    ConversationService,
    SelectionContext,
)
from autoslide.conversation.store import SessionStore
from autoslide.events import EventLog, Redactor
from autoslide.ingest.models import DeckInventory
from autoslide.ingest.renderer import BasePreviewRenderer, select_preview_renderer
from autoslide.jobs.models import (
    EditScope,
    JobDecisionRequest,
    JobDecisionResponse,
    JobRecord,
    JobState,
)
from autoslide.jobs.registry import JobRegistry
from autoslide.jobs.workspace import JobWorkspace
from autoslide.orchestrator.pipeline import JobOrchestrator
from autoslide.planner.builder import PromptPayloadBuilder
from autoslide.planner.models import TaskPlan
from autoslide.runtime.discovery import RuntimeRegistry
from autoslide.ui import STATIC_DIR, TEMPLATES_DIR


def create_app(
    settings: Settings | None = None,
    registry: JobRegistry | None = None,
    runtime_registry: RuntimeRegistry | None = None,
    event_log: EventLog | None = None,
    orchestrator: JobOrchestrator | None = None,
    renderer: BasePreviewRenderer | None = None,
    session_store: SessionStore | None = None,
    conversation_service: ConversationService | None = None,
) -> FastAPI:
    """Create and wire the AutoSlide FastAPI application."""
    app_settings = settings or Settings.from_env()
    app_settings.ensure_directories()

    app_registry = registry or JobRegistry(app_settings.data_root / "jobs.db")
    app_runtime_registry = runtime_registry or RuntimeRegistry()
    app_event_log = event_log or EventLog(log_path=app_settings.data_root / "logs")
    app_renderer = renderer or select_preview_renderer()
    app_orchestrator = orchestrator or JobOrchestrator(
        registry=app_registry,
        event_log=app_event_log,
        renderer=app_renderer,
    )
    app_session_store = session_store or SessionStore(base_dir=app_settings.data_root)

    def _provide_deck_inventory(job_id: str | None) -> DeckInventory | None:
        if not job_id:
            return None
        job_dir = app_settings.data_root / "jobs" / job_id
        working_pptx = job_dir / "working" / "presentation.pptx"
        if working_pptx.exists():
            try:
                return app_orchestrator.ingestor.parse(working_pptx)
            except Exception:
                pass
        for pptx in (job_dir / "input").glob("*.pptx"):
            try:
                return app_orchestrator.ingestor.parse(pptx)
            except Exception:
                pass
        return None

    app_conversation_service = conversation_service or ConversationService(
        store=app_session_store,
        engine=ClarificationEngine(),
        planner_builder=PromptPayloadBuilder(),
        inventory_provider=_provide_deck_inventory,
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
        scope: str | None = Form(None),
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

        parsed_scope: EditScope | None = None
        if scope is not None:
            try:
                scope_dict = json.loads(scope)
                if isinstance(scope_dict, dict):
                    parsed_scope = EditScope.model_validate(scope_dict)
                else:
                    raise ValueError("Scope payload must be a JSON object")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid scope payload: {exc}")

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
                "scope": parsed_scope.model_dump() if parsed_scope else None,
            },
        )

        def _execute_pipeline_bg(job_id: str, ws: JobWorkspace, edit_scope: EditScope | None) -> None:
            try:
                app_orchestrator.run_pipeline(job_id=job_id, workspace=ws, scope=edit_scope)
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

        background_tasks.add_task(_execute_pipeline_bg, job_record.job_id, workspace, parsed_scope)

        return JSONResponse(status_code=202, content=job_record.model_dump())

    @app.get("/api/v1/jobs/{job_id}/diff")
    @app.get("/api/v1/jobs/{job_id}/preview-diff")
    def get_job_diff(job_id: str) -> dict:
        try:
            app_registry.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        diff_path = app_settings.data_root / "jobs" / job_id / "artifacts" / "preview_diff.json"
        if not diff_path.exists():
            raise HTTPException(status_code=404, detail="Preview diff not yet available for job")

        return json.loads(diff_path.read_text(encoding="utf-8"))

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

    # -------------------------------------------------------------------------
    # Conversational Session Endpoints (ADS-002)
    # -------------------------------------------------------------------------

    @app.post("/api/v1/sessions", response_model=CreateSessionResponse, status_code=201)
    async def create_session(
        template: UploadFile = File(...),
    ) -> CreateSessionResponse:
        filename = template.filename or "template.pptx"
        if not filename.lower().endswith(".pptx"):
            raise HTTPException(
                status_code=400,
                detail="Only .pptx files are supported for session template uploads",
            )

        content = await template.read()
        if len(content) > app_settings.max_job_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed limit of {app_settings.max_job_size_bytes} bytes",
            )

        input_sha256 = hashlib.sha256(content).hexdigest()
        job_record = app_registry.create(
            instruction="Conversational session",
            input_sha256=input_sha256,
        )

        workspace = JobWorkspace.create(app_settings.data_root, job_record.job_id)
        safe_filename = Path(filename).name
        input_path = workspace.root / "input" / safe_filename
        input_path.write_bytes(content)

        # Record initial ingestion checkpoint
        checkpoint = workspace.write_checkpoint("INITIAL", input_path)

        session_id = f"session_{uuid.uuid4().hex[:12]}"
        session = ConversationSession.new(
            session_id=session_id,
            job_id=job_record.job_id,
        )
        saved_session = app_session_store.save(session)

        app_event_log.append(
            session_id,
            "SESSION_CREATED",
            {
                "session_id": session_id,
                "job_id": job_record.job_id,
                "input_sha256": input_sha256,
                "filename": safe_filename,
            },
        )

        return CreateSessionResponse(
            session_id=saved_session.session_id,
            job_id=saved_session.job_id,
            state=saved_session.state,
        )

    @app.post("/api/v1/sessions/{session_id}/messages", response_model=ConversationResponse)
    def send_session_message(
        session_id: str,
        payload: SendMessageRequest,
    ) -> ConversationResponse:
        try:
            app_session_store.get(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        clean_message = payload.message.strip()
        if not clean_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        response = app_conversation_service.handle_message(
            session_id=session_id,
            message=clean_message,
            context=payload.selection_context,
        )

        app_event_log.append(
            session_id,
            "MESSAGE_PROCESSED",
            {
                "session_id": session_id,
                "user_message": clean_message,
                "assistant_message": response.assistant_message,
                "state": response.session.state.value,
            },
        )

        return response

    @app.get("/api/v1/sessions/{session_id}", response_model=SessionDetailResponse)
    def get_session_detail(session_id: str) -> SessionDetailResponse:
        try:
            session = app_session_store.get(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        active_job_dict = None
        if session.job_id:
            try:
                job_rec = app_registry.get(session.job_id)
                active_job_dict = job_rec.model_dump()
            except KeyError:
                pass

        return SessionDetailResponse(
            session=session,
            brief=session.brief,
            plan=session.plan,
            sources=session.sources,
            active_job=active_job_dict,
        )

    @app.get("/api/v1/sessions/{session_id}/events", response_model=SessionEventsResponse)
    def get_session_events(session_id: str) -> SessionEventsResponse:
        try:
            session = app_session_store.get(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        raw_events = app_event_log.get_events(session_id)
        if session.job_id and session.job_id != session_id:
            job_events = app_event_log.get_events(session.job_id)
            seen_ids = {e.event_id for e in raw_events}
            for je in job_events:
                if je.event_id not in seen_ids:
                    raw_events.append(je)

        sanitized = [
            {
                "event_id": ev.event_id,
                "job_id": ev.job_id,
                "sequence": ev.sequence,
                "event_type": ev.event_type,
                "payload": Redactor.redact_payload(ev.payload),
                "timestamp": ev.timestamp,
            }
            for ev in raw_events
        ]
        return SessionEventsResponse(session_id=session_id, events=sanitized)

    @app.post("/api/v1/sessions/{session_id}/approve", response_model=ApproveDecisionResponse)
    def approve_session_item(
        session_id: str,
        payload: ApproveDecisionRequest,
    ) -> ApproveDecisionResponse:
        try:
            session = app_session_store.get(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        if payload.kind == "plan":
            if session.state != ConversationState.WAITING_PLAN_APPROVAL:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve/revise plan in current state '{session.state.value}'. Expected 'WAITING_PLAN_APPROVAL'",
                )

            if payload.approved:
                session = session.transition(ConversationState.READY_FOR_EXECUTION)
                app_session_store.save(session)
                app_event_log.append(
                    session_id,
                    "PLAN_APPROVED",
                    {"session_id": session_id, "state": session.state.value},
                )
                return ApproveDecisionResponse(
                    session_id=session_id,
                    state=session.state,
                    message="Plan approved successfully. Session is ready for execution.",
                )
            else:
                session = session.transition(ConversationState.NEEDS_CLARIFICATION)
                if payload.feedback:
                    feedback_turn = ChatTurn(
                        id=str(uuid.uuid4()),
                        role="user",
                        content=f"Plan revision request: {payload.feedback}",
                    )
                    session = session.with_turn(feedback_turn)
                app_session_store.save(session)
                app_event_log.append(
                    session_id,
                    "PLAN_REVISION_REQUESTED",
                    {
                        "session_id": session_id,
                        "feedback": payload.feedback,
                        "state": session.state.value,
                    },
                )
                return ApproveDecisionResponse(
                    session_id=session_id,
                    state=session.state,
                    message="Plan rejected/revision requested. Session returned to clarification.",
                )

        elif payload.kind == "sources":
            if session.state != ConversationState.WAITING_SOURCE_APPROVAL:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve/reject sources in current state '{session.state.value}'. Expected 'WAITING_SOURCE_APPROVAL'",
                )

            if payload.approved:
                session = session.transition(ConversationState.READY_FOR_EXECUTION)
                app_session_store.save(session)
                app_event_log.append(
                    session_id,
                    "SOURCES_APPROVED",
                    {"session_id": session_id, "state": session.state.value},
                )
                return ApproveDecisionResponse(
                    session_id=session_id,
                    state=session.state,
                    message="Sources approved successfully. Session is ready for execution.",
                )
            else:
                session = session.transition(ConversationState.READY_FOR_PLAN)
                app_session_store.save(session)
                app_event_log.append(
                    session_id,
                    "SOURCES_REJECTED",
                    {
                        "session_id": session_id,
                        "feedback": payload.feedback,
                        "state": session.state.value,
                    },
                )
                return ApproveDecisionResponse(
                    session_id=session_id,
                    state=session.state,
                    message="Sources rejected. Session returned to plan synthesis.",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported approval kind '{payload.kind}'. Must be 'plan' or 'sources'.",
            )

    @app.post("/api/v1/sessions/{session_id}/execute", response_model=ExecuteSessionResponse, status_code=202)
    def execute_session_plan(
        session_id: str,
        background_tasks: BackgroundTasks,
    ) -> ExecuteSessionResponse:
        try:
            session = app_session_store.get(session_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

        # Explicit approval gate: require READY_FOR_EXECUTION
        if session.state != ConversationState.READY_FOR_EXECUTION:
            raise HTTPException(
                status_code=409,
                detail=f"Execution rejected: plan has not been approved. Current state is '{session.state.value}', expected '{ConversationState.READY_FOR_EXECUTION.value}'.",
            )

        if not session.plan:
            raise HTTPException(
                status_code=400,
                detail="Execution rejected: session does not contain an approved plan.",
            )

        if not session.job_id:
            raise HTTPException(
                status_code=400,
                detail="Execution rejected: session does not have an associated job workspace.",
            )

        # Advance state to EXECUTING
        session = session.transition(ConversationState.EXECUTING)
        app_session_store.save(session)

        app_event_log.append(
            session_id,
            "EXECUTION_STARTED",
            {"session_id": session_id, "job_id": session.job_id},
        )

        ws = JobWorkspace(root=app_settings.data_root / "jobs" / session.job_id, job_id=session.job_id)

        def _execute_session_pipeline_bg(sid: str, jid: str, workspace: JobWorkspace, plan: TaskPlan) -> None:
            try:
                app_orchestrator.run_pipeline(job_id=jid, workspace=workspace, custom_plan=plan)
                try:
                    curr_session = app_session_store.get(sid)
                    if curr_session.state == ConversationState.EXECUTING:
                        curr_session = curr_session.transition(ConversationState.COMPLETED)
                        app_session_store.save(curr_session)
                except Exception:
                    pass
            except Exception as exc:
                try:
                    curr_session = app_session_store.get(sid)
                    if curr_session.state == ConversationState.EXECUTING:
                        curr_session = curr_session.transition(ConversationState.FAILED)
                        app_session_store.save(curr_session)
                except Exception:
                    pass
                app_event_log.append(
                    sid,
                    "PIPELINE_ERROR",
                    {"error": str(exc)},
                )

        background_tasks.add_task(_execute_session_pipeline_bg, session_id, session.job_id, ws, session.plan)

        return ExecuteSessionResponse(
            session_id=session_id,
            job_id=session.job_id,
            state=session.state,
            message="Plan execution started in background.",
        )

    return app
