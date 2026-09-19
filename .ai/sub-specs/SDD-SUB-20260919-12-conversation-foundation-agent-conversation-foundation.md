---
id: SDD-SUB-20260919-12
title: Conversation Domain Models, State Transitions, and JSON Checkpoint Store
author: agent-conversation-foundation
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement immutable Pydantic conversation domain models (ConversationState, ChatTurn, EditBrief, SourceRecord, ConversationSession), valid state machine transition rules, and atomic JSON checkpoint persistence in SessionStore."
decisions: 
  - "Define ConversationState enum with 10 explicit states: NEEDS_CLARIFICATION, READY_FOR_PLAN, WAITING_PLAN_APPROVAL, RESEARCHING, WAITING_SOURCE_APPROVAL, READY_FOR_EXECUTION, EXECUTING, REVIEW, COMPLETED, FAILED."
  - "Implement immutable Pydantic v2 models (frozen=True) for ChatTurn, EditBrief, SourceRecord, and ConversationSession, providing helper factory ConversationSession.new() and transition() methods."
  - "Enforce strict state machine transitions with explicit transition tables, rejecting invalid transitions with ValueError."
  - "Implement SessionStore supporting create, get, and save operations, persisting checkpoint JSON files atomically via temporary files and rename."
  - "Implement credential redaction during checkpoint serialization to ensure API keys, tokens, and secret parameters are never serialized into plaintext checkpoints."
affected_symbols: 
  - "autoslide.conversation.models.ConversationState"
  - "autoslide.conversation.models.ChatTurn"
  - "autoslide.conversation.models.EditBrief"
  - "autoslide.conversation.models.SourceRecord"
  - "autoslide.conversation.models.ConversationSession"
  - "autoslide.conversation.state.validate_transition"
  - "autoslide.conversation.state.TRANSITION_RULES"
  - "autoslide.conversation.store.SessionStore"
risk_level: LOW
---

# 📝 Sub Spec: Conversation Domain Models, State Transitions, and JSON Checkpoint Store

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa domain models cho hội thoại (ConversationState, ChatTurn, EditBrief, SourceRecord, ConversationSession), bộ quy tắc chuyển trạng thái state machine chặt chẽ, và module SessionStore lưu trữ checkpoint JSON atomic an toàn không chứa credentials.
> **Quyết định then chốt**: Sử dụng Pydantic v2 immutable models; Bảng chuyển đổi trạng thái tường minh ném ValueError khi sai luật; SessionStore ghi atomic file và khử credential nhạy cảm khi serialize.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 1 của kế hoạch Always-on Agent Chat (`ADS-002`):
1. **Domain Models**: Xây dựng các mô hình dữ liệu Pydantic v2 bất biến:
   - `ConversationState`: Enum 10 trạng thái (`NEEDS_CLARIFICATION`, `READY_FOR_PLAN`, `WAITING_PLAN_APPROVAL`, `RESEARCHING`, `WAITING_SOURCE_APPROVAL`, `READY_FOR_EXECUTION`, `EXECUTING`, `REVIEW`, `COMPLETED`, `FAILED`).
   - `ChatTurn`: `id`, `role` (`"user" | "assistant" | "tool"`), `content`, `created_at`, `card` (`dict | None`).
   - `EditBrief`: `goal`, `target_scope` (`list[TargetScope]`), `constraints` (`list[str]`), `missing_fields` (`list[str]`), `complete` (`bool`).
   - `SourceRecord`: `source_id`, `url`, `title`, `retrieved_at`, `summary`, `claims` (`list[str]`), `approved` (`bool`).
   - `ConversationSession`: `session_id`, `job_id`, `state`, `turns`, `brief`, `plan`, `sources`, `checkpoint_path`. Hỗ trợ factory `ConversationSession.new(session_id, ...)` và method `session.transition(target_state)`.
2. **State Machine Transitions**:
   - Định nghĩa quy tắc chuyển trạng thái hợp lệ và cấm chuyển trạng thái bất hợp lệ (ví dụ: không thể nhảy từ `NEEDS_CLARIFICATION` thẳng sang `COMPLETED`).
   - Ném `ValueError` với thông điệp rõ ràng khi vi phạm.
3. **SessionStore & Atomic JSON Checkpoint**:
   - `SessionStore.create(session) -> ConversationSession`
   - `SessionStore.get(session_id) -> ConversationSession`
   - `SessionStore.save(session) -> ConversationSession`
   - Ghi file checkpoint an toàn theo cơ chế atomic (ghi vào file `.tmp` rồi rename đè).
   - Tự động lọc và che giấu (redact) các dữ liệu nhạy cảm (credentials, API keys, auth tokens) trước khi ghi ra JSON.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: `TargetScope` và `TaskPlan` đã có sẵn tại `autoslide.planner.models` và tương thích Pydantic v2.
- [ ] **Giả định**: Thư mục lưu checkpoint có thể cấu hình được theo session hoặc job workspace (`job_id` hoặc thư mục workspace định sẵn).
- [ ] **Rủi ro**: Việc serialize `TaskPlan` và các model lồng nhau sang JSON có thể gặp vấn đề nếu không cấu hình encoder chuẩn Pydantic v2 (`model_dump_json`).
  - *Biện pháp*: Dùng chuẩn `model_dump_json()` và `model_validate_json()` của Pydantic v2.
- [ ] **`[UNKNOWN]`**: [UNKNOWN: Vị trí mặc định của checkpoint khi `job_id` chưa được khởi tạo lúc session mới tạo]
  - *Giải pháp đề xuất*: Lưu trong thư mục `.autoslide/sessions/{session_id}/checkpoint.json` hoặc thư mục cấu hình truyền vào `SessionStore(storage_dir=...)`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/conversation/__init__.py` | Create | Package initialization & exports cho domain models, state, và store |
| `src/autoslide/conversation/models.py` | Create | Định nghĩa `ConversationState`, `ChatTurn`, `EditBrief`, `SourceRecord`, `ConversationSession` |
| `src/autoslide/conversation/state.py` | Create | Bảng quy tắc chuyển dịch trạng thái `TRANSITION_RULES`, hàm `validate_transition` |
| `src/autoslide/conversation/store.py` | Create | `SessionStore` quản lý lưu/đọc checkpoint JSON atomic, cơ chế redact credentials |
| `tests/conversation/__init__.py` | Create | Tests package marker |
| `tests/conversation/test_models.py` | Create | Unit tests cho models: khởi tạo, bất biến, serialization, redaction |
| `tests/conversation/test_state.py` | Create | Unit tests cho quy tắc state transitions hợp lệ và bất hợp lệ |

### Phân tích Logic Cốt lõi:
- **Tại sao dùng Immutable Models (`frozen=True`)?** Đảm bảo an toàn luồng và trạng thái hội thoại không bị mutate ngoài ý muốn giữa các step; mọi thay đổi trạng thái đều sinh ra snapshot/instance mới rõ ràng.
- **Sử dụng Pattern nào?** State Pattern kết hợp Repository Pattern (`SessionStore`) và Value Objects / Entities (Pydantic v2).

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] `ConversationSession.new("session-1")` khởi tạo mặc định ở trạng thái `ConversationState.NEEDS_CLARIFICATION`.
- [ ] Chuyển trạng thái bất hợp lệ (ví dụ `session.transition(ConversationState.COMPLETED)`) bị từ chối và ném `ValueError`.
- [ ] Các chuyển trạng thái hợp lệ (ví dụ: `NEEDS_CLARIFICATION -> READY_FOR_PLAN`, `READY_FOR_PLAN -> WAITING_PLAN_APPROVAL`, `WAITING_PLAN_APPROVAL -> READY_FOR_EXECUTION` hoặc `RESEARCHING`, v.v.) hoạt động chính xác.
- [ ] `SessionStore.save()` ghi checkpoint JSON an toàn (atomic write) vào thư mục workspace/sessions.
- [ ] Checkpoint reload qua `SessionStore.get()` phục hồi chính xác trạng thái, turns, brief, plan, sources mà không làm mất tính toàn vẹn dữ liệu.
- [ ] Dữ liệu nhạy cảm (ví dụ chuỗi chứa `api_key`, `token`, `secret`, `password`) được redact sạch sẽ khi serialize checkpoint.
- [ ] Toàn bộ test trong `tests/conversation/test_models.py` và `tests/conversation/test_state.py` chạy qua 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# Chạy focused test suite cho conversation domain
pytest tests/conversation/test_models.py tests/conversation/test_state.py -q -v

# Chạy toàn bộ test suite để đảm bảo không hồi quy
pytest tests/ -q
```

### Manual QA
1. Khởi tạo một session mẫu qua `ConversationSession.new("demo-session")`, thêm `ChatTurn`, cập nhật `EditBrief`.
2. Lưu qua `SessionStore.save(session)`, kiểm tra tính nguyên vẹn của file JSON sinh ra trên đĩa và xác minh định dạng JSON.
3. Đọc lại qua `SessionStore.get("demo-session")` và so sánh thuộc tính tương đương.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Phục vụ làm nền tảng cho các task tiếp theo của `ADS-002`: Task 2 (`Clarification and plan conversation service`), Task 3 (`Session API`), Task 4 (`Research & provenance`), Task 5 (`Deck structure`).
- **Related Sessions**: `docs/superpowers/plans/2026-09-19-always-on-agent-chat.md`
- **Code Graph**: `autoslide.conversation` liên kết với `autoslide.planner.models` (`TargetScope`, `TaskPlan`).

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
