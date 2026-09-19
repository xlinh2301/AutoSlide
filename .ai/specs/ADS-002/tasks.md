# Tasks: Always-on Agent Chat for AutoSlide

**Status:** COMPLETED

## Phase 1 — Conversation foundation
- [x] Define session, turn, event, `EditBrief` and state transition models.
- [x] Add session/message/events APIs with redacted persistence and checkpoint recovery.
- [x] Add clarification policy that blocks mutation until the brief is complete.

## Phase 2 — Plan and approval
- [x] Extend planner response with typed plan cards and explicit approval decisions.
- [x] Add plan revision loop and follow-up turns against the current deck checkpoint.
- [x] Add API/UI tests for approve, revise, retry and failure paths.

## Phase 3 — Deck operations
- [x] Complete allowlisted add/delete/duplicate/reorder slide operations.
- [x] Add supported arbitrary-content operations with explicit unsupported responses.
- [x] Verify structural diff, render output and provenance references.

## Phase 4 — Research and generation
- [x] Add runtime-mediated research intent and normalized source model.
- [x] Add source approval gate and content-to-slide provenance.
- [x] Add generated-content labels and runtime metadata redaction.

## Phase 5 — Always-on chatbot UI
- [x] Replace one-shot prompt emphasis with persistent chatbot rail.
- [x] Implement question, plan, source, execution, review and error cards.
- [x] Integrate filmstrip/canvas selection context into chat composer.

## Phase 6 — End-to-end hardening
- [x] Run browser flow across clarification, plan approval, research approval, execution and follow-up.
- [x] Validate no API-key requests/logging and checkpoint recovery.
- [x] Update user docs and release evidence.

## Phase 7 — Release Gate & Sign-off
- [x] Verify full regression pytest suite (200+ unit, integration, and UI tests).
- [x] Compile all Python source code with `python3 -m compileall`.
- [x] Validate smoke UI checks and full conversation flow scripts.
- [x] Compile `.ai/reports/ADS-002-evidence.md` and complete Sub-Spec report.
