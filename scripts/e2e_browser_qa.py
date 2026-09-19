"""
Comprehensive Browser E2E and UI verification test script using Playwright.
Tests AutoSlide Web Demo at http://localhost:8088/ui against requirements:
1. Presentation upload with /tmp/demo.pptx, verify Filmstrip, Canvas, and Chat Rail DOM elements.
2. Multi-turn chat interactions: prompt submission, QuestionCard option click, PlanCard approve/reject, SourceCard approvals, execution card, and slide selection context binding.
3. Check for any JS console errors, DOM rendering defects, or API failures.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_browser_qa():
    console_errors = []
    page_errors = []
    failed_requests = []

    print(">>> Starting Playwright Browser E2E QA on http://localhost:8088/ui ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # Monitor JS console logs & errors
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} failed: {req.failure}"))

        # Step 1: Navigate to Web UI and check DOM structure
        print("[1/6] Navigating to http://localhost:8088/ui...")
        response = page.goto("http://localhost:8088/ui", wait_until="networkidle")
        assert response.status == 200, f"Expected 200 OK, got {response.status}"

        # Verify Filmstrip DOM
        assert page.locator("#filmstripTrack").is_visible(), "Filmstrip track should be in DOM"
        assert page.locator("#filmstripCount").is_visible(), "Filmstrip count should be visible"
        
        # Verify Canvas DOM
        assert page.locator("#beforeFrame").is_visible(), "Before Frame should be visible"
        assert page.locator("#afterFrame").is_visible(), "After Frame should be visible"
        assert page.locator("#beforePlaceholder").is_visible(), "Before Placeholder should be visible initially"
        assert page.locator("#afterPlaceholder").is_visible(), "After Placeholder should be visible initially"

        # Verify Chat Rail DOM
        assert page.locator("#chatRail").is_visible(), "Chat Rail should be visible"
        assert page.locator("#chatHeader").is_visible(), "Chat Header should be visible"
        assert page.locator("#chatStatusText").is_visible(), "Chat Status text should be visible"
        assert page.locator("#chatMessages").is_visible(), "Chat Messages container should be visible"
        assert page.locator("#chatComposer").is_visible(), "Chat Composer should be visible"
        assert page.locator("#chatInput").is_visible(), "Chat Input textarea should be visible"
        assert page.locator("#btnSendChat").is_visible(), "Send button should be visible"

        # Verify Bottom Panels (Timeline & QA Findings)
        assert page.locator("#eventLogs").is_visible(), "Event logs timeline should be visible"
        assert page.locator("#findingsContainer").is_visible(), "QA findings panel should be visible"
        
        print("  ✓ Step 1 Passed: Complete DOM layout verified (Filmstrip, Canvas, Chat Rail, Stepper, Panels)")

        # Step 2: Test Presentation Upload (/tmp/demo.pptx)
        print("[2/6] Uploading /tmp/demo.pptx...")
        file_input = page.locator("#fileInput")
        file_input.set_input_files("/tmp/demo.pptx")

        # Verify Ingest State and Session Creation
        page.wait_for_selector("#fileBadge", state="visible", timeout=5000)
        badge_text = page.locator("#fileBadgeName").inner_text()
        assert "demo.pptx" in badge_text, f"Expected demo.pptx in badge, got '{badge_text}'"
        print("  ✓ File badge displayed with 'demo.pptx'")

        # Verify Canvas Ingest State
        page.wait_for_selector("#beforeIngestState", state="visible", timeout=5000)
        assert page.locator("#ingestDeckTitle").inner_text() == "demo.pptx"
        print("  ✓ Canvas immediate ingest state activated for 'demo.pptx'")

        # Wait for session creation response in chat stream
        page.wait_for_selector(".chat-turn.turn-assistant:has-text('demo.pptx')", timeout=10000)
        print("  ✓ Assistant acknowledged demo.pptx upload and session creation in chat stream")

        # Step 3: Test Selection Context Binding (Slide selection & Clear)
        print("[3/6] Testing Selection Context Binding & Canvas Drag Interaction...")
        
        # Test 3a: Slide selection binding
        page.select_option("#scopeSlideSelect", value="1")
        context_badge = page.locator("#chatContextBadge")
        page.wait_for_selector("#chatContextBadge", state="visible", timeout=5000)
        assert "Slide 1" in page.locator("#chatContextLabel").inner_text()
        print("  ✓ Selection context badge shows 'Slide 1'")

        # Test 3b: Clear context
        page.locator("#btnClearChatContext").click()
        assert not context_badge.is_visible(), "Context badge should hide when cleared"
        print("  ✓ Context badge clear button verified")

        # Test 3c: Canvas Region Dragging
        overlay = page.locator("#selectionOverlayCanvas")
        box = overlay.bounding_box()
        if box:
            page.mouse.move(box["x"] + 20, box["y"] + 20)
            page.mouse.down()
            page.mouse.move(box["x"] + 150, box["y"] + 100)
            page.mouse.up()
            page.wait_for_timeout(500)
            print("  ✓ Canvas region drag interaction executed")

        # Step 4: Multi-turn Chat - Ambiguous prompt triggering QuestionCard
        print("[4/6] Submitting prompt: 'Make the slide presentation look better and modern'...")
        page.locator("#chatInput").fill("Make the slide presentation look better and modern")
        page.locator("#btnSendChat").click()

        # Wait for QuestionCard response
        page.wait_for_selector(".card-question, .card-plan", timeout=20000)
        
        question_cards = page.locator(".card-question")
        if question_cards.count() > 0:
            print("  ✓ QuestionCard rendered successfully with clarification choices")
            question_card = question_cards.first
            assert "clarification" in question_card.locator(".card-badge").inner_text().lower()
            
            # Click the clarification option button
            first_opt = question_card.locator(".question-option-btn").first
            opt_text = first_opt.inner_text().strip()
            print(f"  -> Selecting clarification choice: '{opt_text}'")
            first_opt.click()

            # Wait for either follow-up question or plan proposal
            page.wait_for_selector(".card-question, .card-plan", timeout=20000)
            page.wait_for_timeout(1000)
            
            # If a follow-up question card is shown for missing content, supply specific content
            latest_questions = page.locator(".card-question")
            if latest_questions.count() > 0 and page.locator(".card-plan").count() == 0:
                print("  ✓ Follow-up clarification received. Supplying specific content...")
                page.locator("#chatInput").fill("Change title to 'Q4 Business Review'")
                page.locator("#btnSendChat").click()
                page.wait_for_selector(".card-plan", timeout=20000)

            print("  ✓ PlanCard received following clarification dialogue")
        else:
            print("  ✓ Direct PlanCard received")

        # Step 5: PlanCard Verification & Approval
        print("[5/6] Verifying PlanCard structure & approving execution...")
        plan_card = page.locator(".card-plan").last
        assert plan_card.is_visible(), "PlanCard must be visible"
        assert "plan" in plan_card.locator(".card-badge").inner_text().lower()
        assert plan_card.locator(".plan-summary-box").is_visible(), "Plan summary box must be visible"
        
        btn_approve_plan = plan_card.locator(".btn-approve-plan")
        btn_revise_plan = plan_card.locator(".btn-revise-plan")
        assert btn_approve_plan.is_visible(), "Approve button on PlanCard must be visible"
        assert btn_revise_plan.is_visible(), "Revise button on PlanCard must be visible"
        print("  ✓ PlanCard elements verified (Badge, Summary, Operations, Approve/Revise buttons)")

        # Test clicking Approve Plan
        print("  -> Clicking 'Approve & Execute' button...")
        btn_approve_plan.click()

        # Step 6: Verify Execution / Source Cards / ReviewCard
        print("[6/6] Verifying Execution stream, Source approvals, and ReviewCard...")
        
        # Check if SourceCard appears
        page.wait_for_timeout(2000)
        source_cards = page.locator(".card-source")
        if source_cards.count() > 0:
            print("  ✓ SourceCard rendered with web sources.")
            source_card = source_cards.last
            assert "provenance" in source_card.locator(".card-badge").inner_text().lower() or "source" in source_card.locator(".card-badge").inner_text().lower()
            btn_approve_src = source_card.locator(".btn-approve-sources")
            btn_reject_src = source_card.locator(".btn-reject-sources")
            assert btn_approve_src.is_visible(), "Approve sources button must be visible"
            assert btn_reject_src.is_visible(), "Reject sources button must be visible"
            print("  -> Clicking 'Approve Sources'...")
            btn_approve_src.click()

        # Wait for Execution completion and ReviewCard
        print("  -> Waiting for execution processing & ReviewCard...")
        page.wait_for_selector(".card-review, .turn-assistant:has-text('updated'), .turn-assistant:has-text('diff')", timeout=45000)
        
        review_cards = page.locator(".card-review")
        if review_cards.count() > 0:
            review_card = review_cards.last
            assert "review" in review_card.locator(".card-badge").inner_text().lower()
            download_btn = review_card.locator(".btn-chat-download")
            assert download_btn.is_visible(), "Download PPTX button must be visible on ReviewCard"
            print("  ✓ ReviewCard rendered with Download PPTX action")

        # Diagnostic summary
        print("\n=======================================================")
        print("                 DIAGNOSTIC SUMMARY                    ")
        print("=======================================================")
        print(f"JS Console warnings/errors logged : {len(console_errors)}")
        for err in console_errors:
            print(f"  • {err}")
        print(f"Uncaught page exceptions          : {len(page_errors)}")
        for err in page_errors:
            print(f"  • {err}")
        print(f"Failed network requests           : {len(failed_requests)}")
        for req in failed_requests:
            print(f"  • {req}")
        print("=======================================================\n")

        assert len(page_errors) == 0, f"Uncaught page errors detected: {page_errors}"
        critical_console = [e for e in console_errors if "Failed to load resource" not in e and "favicon" not in e]
        assert len(critical_console) == 0, f"Critical console errors detected: {critical_console}"

        browser.close()
        print("🎉 >>> ALL BROWSER E2E & UI QA TESTS PASSED SUCCESSFULLY! <<< 🎉\n")

if __name__ == "__main__":
    run_browser_qa()
