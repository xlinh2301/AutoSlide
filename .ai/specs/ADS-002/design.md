# Design: Always-on Agent Chat for AutoSlide

## 1. System boundary

ADS-002 adds a conversational orchestration layer above the existing ADS-001 pipeline. The chat layer owns dialogue, clarification, plan approval and provenance. The existing planner/executor/render/quality pipeline remains the only mutation path.

```text
Chat UI → Conversation API → Agent Turn Orchestrator
                              ├─ clarification / EditBrief
                              ├─ typed EditPlan
                              ├─ optional research adapter
                              └─ approval gate
                                      ↓
                              ADS-001 execution pipeline
                                      ↓
                              preview / diff / QA / download
```

## 2. State machine

```text
NEEDS_CLARIFICATION → READY_FOR_PLAN → WAITING_PLAN_APPROVAL
                                           ├─ revise → NEEDS_CLARIFICATION
                                           └─ approve
                                                ↓
                         RESEARCHING → WAITING_SOURCE_APPROVAL
                                                ├─ reject/revise
                                                └─ approve
                                                      ↓
                                             READY_FOR_EXECUTION
                                                      ↓
                                                  EXECUTING
                                                      ↓
                                             REVIEW → COMPLETED
```

Every transition emits a structured event and is persisted in the session checkpoint. A failed transition returns to the last safe state rather than silently continuing.

## 3. Contracts

The public API should be introduced as versioned session endpoints without breaking `/api/v1/jobs`:

- `POST /api/v1/sessions` — create session for an uploaded/current deck.
- `POST /api/v1/sessions/{id}/messages` — append user turn and return assistant state/card.
- `GET /api/v1/sessions/{id}` — current state, brief, plan, source approvals and active job.
- `GET /api/v1/sessions/{id}/events` — redacted event history.
- `POST /api/v1/sessions/{id}/approve` — approve plan or source set using a typed decision.
- `POST /api/v1/sessions/{id}/execute` — execute only an approved plan.

The first implementation may use in-memory registry plus job workspace persistence, matching ADS-001; a later persistence backend can replace internals without changing the contract.

## 4. Content and research policy

- Web search is an explicit intent, not an implicit side effect of every prompt.
- The runtime adapter returns normalized sources and content claims; the application stores only redacted structured results.
- Source cards show URL, title, retrieval time, summary and destination slide.
- User must approve the source set before insertion.
- Generated text/images are marked `AI_GENERATED`; the UI must distinguish them from sourced claims.

## 5. UI composition

- Right rail: always-on chatbot with messages, composer, runtime indicator and action cards.
- Center: slide canvas/diff with loading/error/empty states.
- Left: filmstrip and slide-level targeting.
- Chat cards: `QuestionCard`, `PlanCard`, `SourceCard`, `ExecutionCard`, `ReviewCard`, `ErrorCard`.
- Region selection and slide selection feed structured context into the next chat turn.

## 6. Failure handling

- Ambiguous intent: ask one question and keep current deck unchanged.
- Runtime unavailable: explain authenticated CLI setup; never ask for an app API key.
- Search failure: preserve the plan and offer retry or generate-without-web.
- Source rejected: remove only unapproved sourced blocks and return to plan revision.
- Executor/render failure: restore last valid checkpoint and expose diagnostics in the chat.

## 7. Verification strategy

- Unit tests for state transitions, question gating, plan approval, provenance and operation validation.
- API tests for session/message/approval contracts and backward compatibility with jobs.
- Executor tests for add/delete/duplicate/reorder and content-origin metadata.
- UI behavior tests for chat cards, approval buttons, source review and follow-up turns.
- Browser smoke flow: upload → vague prompt → agent question → answer → plan → approve → research/source approval → execute → diff → follow-up edit → download.
