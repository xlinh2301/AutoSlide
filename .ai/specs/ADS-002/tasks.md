# Tasks: Always-on Agent Chat for AutoSlide

## Phase 1 — Conversation foundation

- Define session, turn, event, `EditBrief` and state transition models.
- Add session/message/events APIs with redacted persistence and checkpoint recovery.
- Add clarification policy that blocks mutation until the brief is complete.

## Phase 2 — Plan and approval

- Extend planner response with typed plan cards and explicit approval decisions.
- Add plan revision loop and follow-up turns against the current deck checkpoint.
- Add API/UI tests for approve, revise, retry and failure paths.

## Phase 3 — Deck operations

- Complete allowlisted add/delete/duplicate/reorder slide operations.
- Add supported arbitrary-content operations with explicit unsupported responses.
- Verify structural diff, render output and provenance references.

## Phase 4 — Research and generation

- Add runtime-mediated research intent and normalized source model.
- Add source approval gate and content-to-slide provenance.
- Add generated-content labels and runtime metadata redaction.

## Phase 5 — Always-on chatbot UI

- Replace one-shot prompt emphasis with persistent chatbot rail.
- Implement question, plan, source, execution, review and error cards.
- Integrate filmstrip/canvas selection context into chat composer.

## Phase 6 — End-to-end hardening

- Run browser flow across clarification, plan approval, research approval, execution and follow-up.
- Validate no API-key requests/logging and checkpoint recovery.
- Update user docs and release evidence.
