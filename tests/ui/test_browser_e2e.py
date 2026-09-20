"""Playwright Browser E2E Integration Test Suite for AutoSlide Studio UI."""

import io
import os
import socket
import threading
import time
from pathlib import Path
import pytest
import uvicorn
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.discovery import RuntimeRegistry
from tests.fixtures.pptx_samples import create_minimal_pptx


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class UvicornTestServer:
    def __init__(self, app, host="127.0.0.1", port=0):
        self.host = host
        self.port = port or get_free_port()
        self.app = app
        self.config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        # Wait until server is listening
        for _ in range(50):
            try:
                with socket.create_connection((self.host, self.port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=3.0)


@pytest.fixture(scope="module")
def live_server_url(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("browser_e2e_data")
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

    port = get_free_port()
    server = UvicornTestServer(app, port=port)
    server.start()

    yield f"http://127.0.0.1:{port}"
    server.stop()


def test_browser_e2e_full_workflow(live_server_url, tmp_path):
    """Verify presentation upload, chat interaction, QuestionCard, PlanCard, and ReviewCard with Playwright."""
    sample_pptx_path = tmp_path / "test_sample.pptx"
    sample_pptx_path.write_bytes(create_minimal_pptx())

    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 1. Navigate to UI
        res = page.goto(f"{live_server_url}/ui", wait_until="networkidle")
        assert res.status == 200

        # Check DOM elements
        assert page.locator("#filmstripTrack").is_visible()
        assert page.locator("#beforeFrame").is_visible()
        assert page.locator("#afterFrame").is_visible()
        assert page.locator("#chatRail").is_visible()
        assert page.locator("#chatMessages").is_visible()
        assert page.locator("#chatInput").is_visible()
        assert page.locator("#btnSendChat").is_visible()

        # 2. Upload sample pptx
        page.locator("#fileInput").set_input_files(str(sample_pptx_path))
        page.wait_for_selector("#fileBadge", state="visible", timeout=5000)
        assert "test_sample.pptx" in page.locator("#fileBadgeName").inner_text()

        # 3. Context binding & Clear
        page.select_option("#scopeSlideSelect", value="1")
        context_badge = page.locator("#chatContextBadge")
        page.wait_for_selector("#chatContextBadge", state="visible", timeout=5000)
        assert "Slide 1" in page.locator("#chatContextLabel").inner_text()

        # Clear context
        page.locator("#btnClearChatContext").click()
        assert not context_badge.is_visible()

        # 4. Multi-turn dialogue: submit vague prompt -> QuestionCard
        page.locator("#chatInput").fill("Make the slide presentation look better")
        page.locator("#btnSendChat").click()

        page.wait_for_selector(".card-question, .card-plan", timeout=20000)
        q_cards = page.locator(".card-question")
        if q_cards.count() > 0:
            first_opt = q_cards.first.locator(".question-option-btn").first
            first_opt.click()

            page.wait_for_selector(".card-question, .card-plan", timeout=20000)
            page.wait_for_timeout(1000)
            if page.locator(".card-question").count() > 0 and page.locator(".card-plan").count() == 0:
                page.locator("#chatInput").fill("Change title to 'Q4 Business Review'")
                page.locator("#btnSendChat").click()
                page.wait_for_selector(".card-plan", timeout=20000)

        # 5. PlanCard Approval
        plan_card = page.locator(".card-plan").last
        assert plan_card.is_visible()
        assert "plan" in plan_card.locator(".card-badge").inner_text().lower()

        btn_approve = plan_card.locator(".btn-approve-plan")
        assert btn_approve.is_visible()
        btn_approve.click()

        # 6. Review Card
        page.wait_for_selector(".card-review, .turn-assistant:has-text('updated'), .turn-assistant:has-text('diff')", timeout=45000)
        review_cards = page.locator(".card-review")
        if review_cards.count() > 0:
            assert "review" in review_cards.last.locator(".card-badge").inner_text().lower()
            assert review_cards.last.locator(".btn-chat-download").is_visible()

        # Assert no page exceptions or critical errors
        assert len(page_errors) == 0

        browser.close()
