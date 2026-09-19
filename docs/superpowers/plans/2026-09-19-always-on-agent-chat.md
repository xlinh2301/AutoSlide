# Always-on Agent Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-visible agent chatbot that clarifies natural-language slide requests, obtains approval for typed plans and web sources, executes safe deck operations, and supports follow-up edits with preview/diff evidence.

**Architecture:** Add a conversation/session layer above the existing ADS-001 job pipeline. The session layer owns turns, clarification state, plan/source approval and provenance; only approved typed plans enter the existing executor/render/QA path. The UI adds a persistent chat rail beside the existing filmstrip and canvas.

**Tech Stack:** FastAPI, Pydantic, Python standard library, existing PPTX OOXML executor, vanilla HTML/CSS/ES6 UI, authenticated local agent CLI runtimes.

**Spec:** `.ai/specs/ADS-002/requirements.md`, `.ai/specs/ADS-002/design.md`, `.ai/specs/ADS-002/CAPABILITY_MAP.md`

## Global Constraints

- No application-managed provider API keys.
- The original PPTX is immutable.
- No free-form agent-generated code executes on the host.
- No external content is inserted without an explicit approval event.
- Every mutation has a typed operation, checkpoint, diff and verification result.
- Reference DOCX/XLSX/PDF ingestion remains out of scope for this capability.
- Preserve existing `/api/v1/jobs` contracts.
- Keep frontend dependency-free and local-first.

## Review Focus

- Ambiguous prompt: agent asks a targeted question and performs zero mutation; covered by Task 2 clarification tests.
- User approves a plan containing sourced content but rejects a source: no sourced block reaches the executor; covered by Task 4 approval tests.
- Follow-up prompt after a completed edit: it targets the current checkpoint, not the original upload; covered by Task 2 session tests and Task 3 API tests.
- Unsupported arbitrary content: agent returns an actionable review card and preserves the last valid deck; covered by Task 5 operation tests.
- Runtime/search/render failure: session remains recoverable with retry/revise actions and redacted diagnostics; covered by Task 4 and Task 6 end-to-end tests.

### Task 1: Conversation domain models and checkpoint store

**Files:**
- Create: `src/autoslide/conversation/models.py`
- Create: `src/autoslide/conversation/state.py`
- Create: `src/autoslide/conversation/store.py`
- Create: `tests/conversation/test_models.py`
- Create: `tests/conversation/test_state.py`

**Interfaces:**
- `ConversationState`: `NEEDS_CLARIFICATION`, `READY_FOR_PLAN`, `WAITING_PLAN_APPROVAL`, `RESEARCHING`, `WAITING_SOURCE_APPROVAL`, `READY_FOR_EXECUTION`, `EXECUTING`, `REVIEW`, `COMPLETED`, `FAILED`.
- `ChatTurn(id: str, role: Literal["user","assistant","tool"], content: str, created_at: str, card: dict | None)`.
- `EditBrief(goal: str, target_scope: list[TargetScope], constraints: list[str], missing_fields: list[str], complete: bool)`.
- `ConversationSession(session_id: str, job_id: str | None, state: ConversationState, turns: list[ChatTurn], brief: EditBrief | None, plan: TaskPlan | None, sources: list[SourceRecord], checkpoint_path: str)`.
- `SessionStore.create/get/save(session) -> ConversationSession` with JSON checkpoint persistence inside the job workspace.

- [ ] **Step 1: Write failing model and transition tests**

```python
def test_ambiguous_session_starts_in_clarification():
    session = ConversationSession.new("session-1")
    assert session.state is ConversationState.NEEDS_CLARIFICATION

def test_invalid_transition_is_rejected():
    session = ConversationSession.new("session-1")
    with pytest.raises(ValueError):
        session.transition(ConversationState.COMPLETED)
```

- [ ] **Step 2: Run `pytest tests/conversation/test_models.py tests/conversation/test_state.py -q` and confirm failure.**
- [ ] **Step 3: Implement immutable Pydantic models, transition rules, redacted JSON serialization and atomic checkpoint writes.**
- [ ] **Step 4: Run the focused tests and assert checkpoint reload preserves state, turns and provenance without credentials.**
- [ ] **Step 5: Commit `feat(conversation): add session state and checkpoints`.**

### Task 2: Clarification and plan conversation service

**Files:**
- Create: `src/autoslide/conversation/service.py`
- Create: `src/autoslide/conversation/clarification.py`
- Modify: `src/autoslide/planner/models.py`
- Modify: `src/autoslide/planner/builder.py`
- Create: `tests/conversation/test_service.py`
- Create: `tests/conversation/test_clarification.py`

**Interfaces:**
- `ConversationService.handle_message(session_id: str, message: str, context: SelectionContext | None = None) -> ConversationResponse`.
- `ClarificationEngine.assess(message: str, inventory: DeckInventory | None, previous_brief: EditBrief | None) -> ClarificationResult`.
- `ClarificationResult(state: ConversationState, assistant_message: str, questions: list[Question], brief: EditBrief | None)`.
- `ConversationResponse(session: ConversationSession, assistant_message: str, cards: list[dict])`.

- [ ] **Step 1: Add tests proving vague requests produce one targeted question and no `TaskPlan` mutation.**
- [ ] **Step 2: Add tests proving a complete request produces a typed plan card in `WAITING_PLAN_APPROVAL`.**
- [ ] **Step 3: Run the focused tests and confirm they fail before implementation.**
- [ ] **Step 4: Implement deterministic missing-field checks for target, action, content and preservation intent; use the runtime adapter only for natural-language interpretation, never for direct mutation.**
- [ ] **Step 5: Implement follow-up handling so the current accepted checkpoint and prior brief are included in the next turn.**
- [ ] **Step 6: Run `pytest tests/conversation tests/planner -q`.**
- [ ] **Step 7: Commit `feat(conversation): add clarification and plan loop`.**

### Task 3: Session API and approval endpoints

**Files:**
- Modify: `src/autoslide/api.py`
- Create: `src/autoslide/conversation/schemas.py`
- Modify: `tests/conftest.py`
- Create: `tests/api/test_conversation_api.py`

**Interfaces:**
- `POST /api/v1/sessions` accepts the existing PPTX upload and returns `{session_id, job_id, state}`.
- `POST /api/v1/sessions/{session_id}/messages` accepts `{message, selection_context}` and returns `ConversationResponse`.
- `GET /api/v1/sessions/{session_id}` returns session, brief, plan, sources and active job.
- `GET /api/v1/sessions/{session_id}/events` returns redacted events.
- `POST /api/v1/sessions/{session_id}/approve` accepts `{kind: "plan"|"sources", approved: bool, feedback: str | None}`.
- `POST /api/v1/sessions/{session_id}/execute` creates/starts an ADS-001 job only after plan approval.

- [ ] **Step 1: Write API tests for create, message, inspect, approve/revise and execute-before-approval rejection.**
- [ ] **Step 2: Run `pytest tests/api/test_conversation_api.py -q` and confirm the new routes fail.**
- [ ] **Step 3: Implement request/response schemas, session registry wiring and HTTP error mapping.**
- [ ] **Step 4: Connect approved execution to the existing background pipeline and preserve `/api/v1/jobs` behavior.**
- [ ] **Step 5: Run API tests plus the existing job API tests.**
- [ ] **Step 6: Commit `feat(api): add conversational session endpoints`.**

### Task 4: Research, generated content and provenance approval

**Files:**
- Create: `src/autoslide/conversation/provenance.py`
- Create: `src/autoslide/content/research.py`
- Create: `src/autoslide/content/models.py`
- Modify: `src/autoslide/runtime/adapters.py`
- Create: `tests/content/test_research.py`
- Create: `tests/content/test_provenance.py`

**Interfaces:**
- `SourceRecord(source_id: str, url: str, title: str, retrieved_at: str, summary: str, claims: list[str], approved: bool)`.
- `ContentOrigin(kind: Literal["USER","WEB","AI_GENERATED"], source_ids: list[str], runtime_name: str | None)`.
- `ResearchService.search(query: str, session: ConversationSession) -> ResearchResult`.
- `ResearchService.generate(prompt: str, session: ConversationSession) -> GeneratedContent`.
- `ProvenanceStore.attach(content_ref: str, origin: ContentOrigin, destination: TargetReference) -> None`.

- [ ] **Step 1: Write tests for normalized sources, URL validation, redaction, generated labels and source approval gating.**
- [ ] **Step 2: Run focused content tests and confirm failure.**
- [ ] **Step 3: Implement runtime-mediated search/generation adapters using structured JSON output and bounded results.**
- [ ] **Step 4: Implement source approval so rejected sources cannot be passed into an `EditPlan`.**
- [ ] **Step 5: Run focused tests and security/sanitizer checks.**
- [ ] **Step 6: Commit `feat(content): add researched and generated content provenance`.**

### Task 5: Deck structure and arbitrary supported content operations

**Files:**
- Modify: `src/autoslide/planner/vocabulary.py`
- Modify: `src/autoslide/planner/models.py`
- Modify: `src/autoslide/executor/mutator.py`
- Modify: `src/autoslide/executor/engine.py`
- Create: `tests/executor/test_conversation_operations.py`

**Interfaces:**
- `AddSlideOp(source_slide_index: int | None, insert_at_index: int, layout_ref: str | None, content: list[ContentBlock])`.
- `DeleteSlideOp(slide_index: int)`.
- `DuplicateSlideOp(source_slide_index: int, insert_at_index: int)`.
- `ReorderSlideOp(slide_index: int, new_index: int)`.
- `AddContentOp(target_slide_index: int, content: ContentBlock, bounds: BoundingBox | None)`.
- `PPTXExecutor.execute(plan, input_pptx, workspace) -> ExecutionResult` remains the only mutation interface.

- [ ] **Step 1: Add failing executor tests for add, delete, duplicate, reorder, text block and unsupported content.**
- [ ] **Step 2: Run focused executor tests and confirm failure or missing validation.**
- [ ] **Step 3: Implement allowlisted operations with slide-index normalization, bounds validation, preservation rules and provenance references.**
- [ ] **Step 4: Re-parse output and assert postconditions for slide count/order and content origin.**
- [ ] **Step 5: Run executor, structural diff and renderer tests.**
- [ ] **Step 6: Commit `feat(executor): support conversational deck operations`.**

### Task 6: Always-on chatbot UI and end-to-end verification

**Files:**
- Modify: `src/autoslide/ui/templates/index.html`
- Modify: `src/autoslide/ui/static/js/workbench.js`
- Modify: `src/autoslide/ui/static/css/workbench.css`
- Create: `tests/ui/test_conversation_ui.py`
- Modify: `scripts/smoke_ui_check.py`
- Create: `scripts/smoke_conversation_flow.py`

**Interfaces:**
- `POST /api/v1/sessions/{id}/messages` is the UI message transport.
- UI state renders `QuestionCard`, `PlanCard`, `SourceCard`, `ExecutionCard`, `ReviewCard` and `ErrorCard` from server payloads.
- Existing canvas/filmstrip selection emits `SelectionContext` into the chat composer.

- [ ] **Step 1: Add UI contract tests for persistent chat rail, card selectors, approval actions and follow-up composer.**
- [ ] **Step 2: Run UI tests and confirm missing selectors/routes fail.**
- [ ] **Step 3: Implement chat rail, message rendering, optimistic loading, retry/error states and source/plan approval cards without external dependencies.**
- [ ] **Step 4: Wire slide/region selection into the next chat message and preserve current preview/diff behavior.**
- [ ] **Step 5: Implement browser smoke flow: upload → vague prompt → clarification → answer → plan approval → source approval → execute → diff → follow-up → download.**
- [ ] **Step 6: Run `pytest -q`, `python3 -m compileall src tests`, `PYTHONPATH=src:. python3 scripts/smoke_ui_check.py`, `PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py`, sanitizer and browser inspection.**
- [ ] **Step 7: Commit `feat(ui): add always-on agent chatbot workflow`.**

### Task 7: Release gate and documentation

**Files:**
- Modify: `README.md`
- Modify: `.ai/specs/ADS-002/requirements.md`
- Modify: `.ai/specs/ADS-002/tasks.md`
- Create: `.ai/reports/ADS-002-evidence.md`

- [ ] **Step 1: Document chat commands, approval policy, runtime setup and provenance behavior.**
- [ ] **Step 2: Record exact test commands, outputs, browser screenshots and known limitations.**
- [ ] **Step 3: Run `git diff --check`, `pre-commit run --all-files` and sanitizer gates.**
- [ ] **Step 4: Commit `docs: document conversational agent workflow and evidence`.**
