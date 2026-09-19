# Task 2 Completion Report: Clarification and Plan Conversation Service

**Spec ID:** ADS-002 (Task 2)  
**Sub-Spec:** `SDD-SUB-20260919-13` (`.ai/sub-specs/SDD-SUB-20260919-13-clarification-plan-agent-clarification-plan.md`)  
**Worktree:** `@`  
**Branch:** `agent/clarification-plan`  
**Status:** COMPLETED  

---

## 1. Executive Summary

Task 2 implements the clarification dialogue and planning orchestration service for the always-on agent chat capability. The core deliverable introduces two complementary services:
- **`ClarificationEngine`**: Evaluates user prompts deterministically against 4 core facets (`target`, `action`, `content`, `preservation`). For ambiguous or incomplete requests, it emits exactly one targeted question without triggering deck mutations.
- **`ConversationService`**: Application service that coordinates user turns, session state persistence via `SessionStore`, and converts complete briefs into typed `TaskPlan` structures with plan cards in `WAITING_PLAN_APPROVAL`.

---

## 2. Implemented Files & Interfaces

### Created Files
1. **`src/autoslide/conversation/clarification.py`**
   - `Question`: Typed clarifying question model with `id`, `prompt`, `options`, and `field`.
   - `ClarificationResult`: Holds `state`, `assistant_message`, `questions`, and `brief`.
   - `ClarificationEngine`: Deterministic evaluator checking target slide/object, operation allowlist, replacement content, and preservation rules.
2. **`src/autoslide/conversation/service.py`**
   - `SelectionContext`: Pydantic model capturing UI selection (`slide_index`, `object_ref`, `selected_text`).
   - `ConversationResponse`: Encapsulates `session`, `assistant_message`, and `cards`.
   - `ConversationService`: Coordinates turn logging, clarification checks, plan construction, state transitions, and checkpoint persistence.
3. **`tests/conversation/test_clarification.py`**
   - 8 unit tests covering vague request gating, missing target, missing action, missing content, selection context integration, follow-up brief merging, and slide out-of-range detection.
4. **`tests/conversation/test_service.py`**
   - 5 unit tests covering multi-turn dialogue, atomic session store persistence, plan card emission, and selection context injection.

### Modified Files
1. **`src/autoslide/planner/models.py`**
   - Added `TaskPlan.to_card()` method to serialize versioned, typed plan representations for chat UI cards.
2. **`src/autoslide/planner/builder.py`**
   - Added `PromptPayloadBuilder.build_plan_from_brief()` to deterministically synthesize strongly typed `TaskPlan` instances with allowlisted operations directly from completed `EditBrief` models.
3. **`src/autoslide/conversation/__init__.py`**
   - Exported newly implemented symbols (`ClarificationEngine`, `ClarificationResult`, `Question`, `ConversationService`, `ConversationResponse`, `SelectionContext`).

---

## 3. Key Invariants & Behavioral Guarantees

1. **Zero Mutation on Ambiguity**: Vague requests (e.g. "make this look better") remain strictly in `NEEDS_CLARIFICATION`. No `TaskPlan` is synthesized, and the deck checkpoint remains completely untouched.
2. **Single Targeted Question Rule**: When multiple fields are missing, the clarification engine prioritizes Target > Action > Content, asking only 1 focused question at a time.
3. **Selection Context Awareness**: Explicit user UI selection (e.g., clicking slide 2) automatically populates target scope without forcing the user to repeat slide numbers in text.
4. **Seamless Follow-up Context**: Successive user turns merge into the prior `EditBrief`, preserving accumulated context across turns.
5. **Atomic State Machine Advancement**: A complete request progresses cleanly through `READY_FOR_PLAN` into `WAITING_PLAN_APPROVAL`, ready for explicit user approval before execution.

---

## 4. Verification & Quality Gates

### Automated Test Results
- **Focused tests**:
  ```bash
  pytest tests/conversation tests/planner -q
  # 44 passed, 1 warning in 0.40s
  ```
- **Bytecode compilation**:
  ```bash
  python3 -m compileall src tests
  # Listing and compiling all modules: 0 errors
  ```
- **Full test suite regression**:
  ```bash
  pytest -q
  # 166 passed, 1 warning in 175.75s
  ```

---

## 5. Git Commit Trace

- `cae0a3a`: `docs(spec): add sub-spec for clarification and plan conversation service`
- `8dc46fa`: `feat(conversation): add clarification and plan loop`
