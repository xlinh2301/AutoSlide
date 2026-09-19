"""End-to-end local UI & API smoke check script for AutoSlide Studio."""

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


def run_smoke_checks() -> None:
    print("=== [AutoSlide UI & API Smoke Check] ===")

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

        # 1. Health check
        res_health = client.get("/health")
        assert res_health.status_code == 200, f"Health check failed: {res_health.status_code}"
        print("  ✓ Health check: OK")

        # 2. UI Route
        res_ui = client.get("/ui")
        assert res_ui.status_code == 200, f"UI route failed: {res_ui.status_code}"
        html = res_ui.text
        assert "AutoSlide Workbench" in html
        assert "command-bar" in html
        assert "filmstrip-bar" in html
        assert "canvas-diff-container" in html
        assert "beforeIngestState" in html
        assert "selectionOverlayCanvas" in html
        assert "highlightOverlayLayer" in html
        # Always-on chat rail elements
        assert 'id="chatRail"' in html
        assert 'id="chatMessages"' in html
        assert 'id="chatComposer"' in html
        assert 'id="chatInput"' in html
        assert 'id="btnSendChat"' in html
        assert 'id="chatContextBadge"' in html
        print("  ✓ Studio HTML layout with persistent Chat Rail: OK")

        # 3. Static Assets
        res_css = client.get("/static/css/workbench.css")
        assert res_css.status_code == 200
        assert "workbench-container" in res_css.text
        assert "diff-highlight-box" in res_css.text
        assert "chat-rail" in res_css.text
        assert "card-question" in res_css.text
        assert "card-plan" in res_css.text
        assert "card-source" in res_css.text
        print("  ✓ Studio CSS stylesheet with Card components: OK")

        res_js = client.get("/static/js/workbench.js")
        assert res_js.status_code == 200
        assert "handleFileSelect" in res_js.text
        assert "buildSlideNavigator" in res_js.text
        assert "sendChatMessage" in res_js.text
        assert "renderQuestionCard" in res_js.text
        assert "renderPlanCard" in res_js.text
        assert "approvePlan" in res_js.text
        print("  ✓ Studio JS client bundle with Chatbot orchestration: OK")

        # 4. Runtimes endpoint
        res_runtimes = client.get("/api/v1/runtimes")
        assert res_runtimes.status_code == 200
        runtimes = res_runtimes.json()
        assert len(runtimes) >= 1
        print(f"  ✓ Runtimes discovery: OK ({len(runtimes)} detected)")

        # 5. Create Job with PPTX upload and edit scope
        pptx_bytes = create_minimal_pptx()
        scope_payload = '{"kind": "slide", "slide_index": 1}'
        res_job = client.post(
            "/api/v1/jobs",
            files={"template": ("sample.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"instruction": "Change slide title to Q4 Executive Summary", "runtime": "codex", "scope": scope_payload},
        )
        assert res_job.status_code == 202, f"Job creation failed: {res_job.text}"
        job_data = res_job.json()
        job_id = job_data["job_id"]
        print(f"  ✓ Job creation: OK (job_id: {job_id})")

        # 6. Check Job Status & Events
        res_status = client.get(f"/api/v1/jobs/{job_id}")
        assert res_status.status_code == 200
        assert res_status.json()["state"] in ("CREATED", "INGESTING", "PLANNING", "EXECUTING", "VERIFYING", "AWAITING_USER_APPROVAL")

        res_events = client.get(f"/api/v1/jobs/{job_id}/events")
        assert res_events.status_code == 200
        events = res_events.json()
        assert len(events) >= 1
        print(f"  ✓ Event stream: OK ({len(events)} events recorded)")

        # 7. Check Diff endpoint
        res_diff = client.get(f"/api/v1/jobs/{job_id}/diff")
        if res_diff.status_code == 200:
            print("  ✓ Preview diff: OK")
        else:
            print(f"  ℹ Preview diff pending pipeline completion (status {res_diff.status_code})")

    print("=== All AutoSlide UI & API Smoke Checks Passed Successfully! ===")


if __name__ == "__main__":
    try:
        run_smoke_checks()
    except Exception as exc:
        print(f"Smoke check FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
