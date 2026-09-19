# Requirements: Always-on Agent Chat for AutoSlide

**Spec ID:** ADS-002  
**Status:** DRAFT — user design approved; implementation plan pending spec review  
**Parent:** ADS-001

## Objective

Turn the one-shot AutoSlide edit form into an always-visible agent chatbot. The user should be able to describe a deck outcome in natural language, answer clarification questions, approve a typed plan, optionally approve researched sources, and review the resulting editable PPTX in the same session.

## User stories

- **US-01 Conversational brief:** I can start with an incomplete natural-language request and the agent asks only the questions needed to remove ambiguity.
- **US-02 Plan approval:** I can inspect and revise a structured plan before any PPTX mutation occurs.
- **US-03 Deck structure:** I can ask the agent to add, delete, duplicate or reorder slides and add arbitrary supported content.
- **US-04 Research:** I can ask the agent to search the web or generate content; web-derived content includes sources and generated content is labeled.
- **US-05 Iteration:** I can continue chatting after an edit to request follow-up changes without losing the deck/session context.
- **US-06 Safe execution:** Ambiguous, unsupported or unverified requests remain in chat clarification/review states and never become guessed mutations.

## Scope

### In scope

- Persistent local conversation session associated with a job workspace.
- Agent turns with user messages, assistant messages, tool/status events and structured cards.
- Clarification state and typed `EditBrief`.
- Typed `EditPlan` approval before execution.
- Add/delete/duplicate/reorder slide operations, subject to executor allowlists and verification.
- Add/edit text, image, table, chart or generated-content blocks where the current executor supports them; unsupported types produce a review response.
- Agent CLI runtime invocation without application-managed provider API keys.
- Optional web research through the selected CLI runtime, with source URL/title/access time and claim-to-slide provenance.
- Content generation through the selected runtime, marked `AI_GENERATED`.
- Always-on chatbot UI with clarification, plan, source, execution and review cards.
- Follow-up turns that create a new plan against the current accepted or reviewable deck state.

### Out of scope

- Application-managed API keys or hidden provider credentials.
- Silent web browsing or silent insertion of externally sourced content.
- Arbitrary shell/code execution by agent output.
- Reference DOCX/XLSX/PDF ingestion in this capability.
- Multi-user collaboration, cloud sync or hosted session persistence.

## Functional requirements

- **FR-01 Session:** Every chat session MUST have a stable local session id, job id, current deck checkpoint and append-only redacted turn/event log.
- **FR-02 Clarification:** The agent MUST classify each turn as `NEEDS_CLARIFICATION`, `READY_FOR_PLAN`, `WAITING_PLAN_APPROVAL`, `RESEARCHING`, `READY_FOR_EXECUTION`, `EXECUTING`, `REVIEW`, `COMPLETED` or `FAILED`.
- **FR-03 Question quality:** Clarifying questions MUST identify the missing decision, offer contextual choices where possible, and never mutate the deck.
- **FR-04 Plan contract:** A plan MUST be schema-valid, list slide/target scope, operations, content origin, preservation rules, expected postconditions and confidence.
- **FR-05 Approval gate:** No mutation, web insertion or generated-content insertion MAY occur before explicit user approval of the relevant plan. Research may be proposed before approval, but external content requires source approval before insertion.
- **FR-06 Operations:** The executor MUST support allowlisted add, delete, duplicate, reorder, add-content and existing edit operations, with structural and visual verification.
- **FR-07 Unsupported request:** Unsupported object/content requests MUST become an actionable review message; the agent MUST not approximate silently.
- **FR-08 Research provenance:** Every web-derived content block MUST retain source URL, title, retrieval time, source excerpt/claim summary and destination slide/object reference.
- **FR-09 Generated provenance:** Every generated content block MUST be labeled `AI_GENERATED` and retain the runtime/model label when available without exposing credentials.
- **FR-10 Follow-up:** After execution, the user MUST be able to continue the chat and target the current deck state; prior accepted checkpoints remain recoverable.
- **FR-11 UI:** The chatbot MUST remain visible beside filmstrip and before/after canvas; cards MUST expose approve, revise, retry and source-review actions.
- **FR-12 Safety:** Runtime calls, web results and content must be bounded, redacted and stored inside the isolated job workspace.

## Acceptance criteria

- [ ] User can upload a PPTX and start with a free-form prompt.
- [ ] Agent asks a targeted question for an ambiguous request and does not edit before clarification.
- [ ] Agent renders a typed plan and waits for explicit approval.
- [ ] Approved plan can add and delete a slide with structural diff and preview evidence.
- [ ] Approved plan can add generated content and label its origin.
- [ ] Web research shows sources before sourced content is inserted.
- [ ] User can request a follow-up edit in the same chatbot session.
- [ ] Failed runtime/research/render operations show retry or clarification actions and preserve the last valid checkpoint.
- [ ] No provider API key is requested, stored or logged.

## Invariants

- Original PPTX is immutable.
- No agent-generated free-form code is executed on the host.
- No external content is inserted without an explicit approval event.
- Every mutation has a typed operation, checkpoint, diff and verification result.
