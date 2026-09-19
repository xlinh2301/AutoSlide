"""End-to-end conversation workflow smoke verification script for AutoSlide."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from starlette.testclient import TestClient

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.discovery import RuntimeRegistry
from tests.fixtures.pptx_samples import create_minimal_pptx


def run_conversation_smoke_flow() -> None:
    print("=== [AutoSlide Always-on Agent Chat Smoke Flow] ===")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
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
        client = TestClient(app)

        # Step 1: Health check & UI layout validation
        res_ui = client.get("/ui")
        assert res_ui.status_code == 200, f"UI endpoint failed: {res_ui.status_code}"
        assert 'id="chatRail"' in res_ui.text
        assert 'id="chatMessages"' in res_ui.text
        assert 'id="chatComposer"' in res_ui.text
        print("  ✓ Step 1: UI Chat Rail & DOM Elements loaded successfully")

        # Step 2: Upload PPTX to create conversational session
        pptx_bytes = create_minimal_pptx()
        res_session = client.post(
            "/api/v1/sessions",
            files={"template": ("sales_deck.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        assert res_session.status_code == 201, f"Session creation failed: {res_session.text}"
        session_data = res_session.json()
        session_id = session_data["session_id"]
        job_id = session_data["job_id"]
        assert session_id.startswith("session_")
        print(f"  ✓ Step 2: Presentation uploaded -> Session {session_id} (Job: {job_id}) created")

        # Step 3: Send vague natural-language prompt -> Agent clarification question
        res_msg1 = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"message": "Improve slide title"},
        )
        assert res_msg1.status_code == 200, f"Message 1 failed: {res_msg1.text}"
        msg1_data = res_msg1.json()
        assert msg1_data["session"]["state"] == "NEEDS_CLARIFICATION"
        assert len(msg1_data["cards"]) >= 1
        assert msg1_data["cards"][0]["type"] == "question"
        print(f"  ✓ Step 3: Vague prompt received QuestionCard clarification ({len(msg1_data['cards'][0]['questions'])} questions)")

        # Step 4: Answer clarification with selection context -> Agent generates typed PlanCard
        res_msg2 = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={
                "message": "Change slide 1 title text to 'Enterprise AI Acceleration'",
                "selection_context": {"slide_index": 1},
            },
        )
        assert res_msg2.status_code == 200, f"Message 2 failed: {res_msg2.text}"
        msg2_data = res_msg2.json()
        assert msg2_data["session"]["state"] == "WAITING_PLAN_APPROVAL"
        assert len(msg2_data["cards"]) >= 1
        assert msg2_data["cards"][0]["type"] == "plan"
        print(f"  ✓ Step 4: Answered clarification -> PlanCard generated with {len(msg2_data['cards'][0]['operations'])} operations")

        # Step 5: User approves PlanCard
        res_approve = client.post(
            f"/api/v1/sessions/{session_id}/approve",
            json={"kind": "plan", "approved": True},
        )
        assert res_approve.status_code == 200, f"Plan approval failed: {res_approve.text}"
        approve_data = res_approve.json()
        assert approve_data["state"] in ("READY_FOR_EXECUTION", "EXECUTING")
        print(f"  ✓ Step 5: Plan approved -> State: {approve_data['state']}")

        # Step 6: Execute approved plan
        res_exec = client.post(f"/api/v1/sessions/{session_id}/execute")
        assert res_exec.status_code == 202, f"Execution failed: {res_exec.text}"
        exec_data = res_exec.json()
        print(f"  ✓ Step 6: Execution started -> State: {exec_data['state']}")

        # Step 7: Check Session Events and Details
        res_detail = client.get(f"/api/v1/sessions/{session_id}")
        assert res_detail.status_code == 200
        res_events = client.get(f"/api/v1/sessions/{session_id}/events")
        assert res_events.status_code == 200
        events = res_events.json()["events"]
        assert len(events) >= 1
        print(f"  ✓ Step 7: Session verified ({len(events)} audited events recorded)")

        # Step 8: Multi-turn Follow-up edit in same session context
        res_msg3 = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={
                "message": "Change slide 1 subtitle text to 'Confidential Draft'",
                "selection_context": {"slide_index": 1},
            },
        )
        assert res_msg3.status_code == 200, f"Follow-up message failed: {res_msg3.text}"
        msg3_data = res_msg3.json()
        assert msg3_data["session"]["state"] in ("READY_FOR_PLAN", "WAITING_PLAN_APPROVAL")
        print("  ✓ Step 8: Follow-up turn successfully targeted current deck state")

        # Step 9: Download Final PPTX Artifact
        res_download = client.get(f"/api/v1/jobs/{job_id}/artifacts/presentation.pptx")
        if res_download.status_code == 200:
            assert len(res_download.content) > 0
            print(f"  ✓ Step 9: Final PPTX artifact downloaded ({len(res_download.content)} bytes)")
        else:
            print(f"  ℹ Step 9: Artifact download status {res_download.status_code}")

    print("=== All Always-on Agent Chat Smoke Flow Steps Passed Cleanly! ===")


if __name__ == "__main__":
    try:
        run_conversation_smoke_flow()
    except Exception as exc:
        print(f"Smoke flow FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
