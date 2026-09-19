---
id: SDD-SUB-20260919-14
title: Session API and Approval Endpoints
author: agent-session-api
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement FastAPI conversational session routes (/api/v1/sessions), approval and execution endpoints, request/response schemas, error mapping, and background pipeline wiring while preserving /api/v1/jobs."
decisions: 
  - "Create autoslide.conversation.schemas with Pydantic request/response models: CreateSessionResponse, SendMessageRequest, ApproveDecisionRequest, SessionDetailResponse, SessionEventsResponse."
  - "Add POST /api/v1/sessions accepting PPTX upload, allocating a session_id and backing job workspace, returning {session_id, job_id, state}."
  - "Add POST /api/v1/sessions/{session_id}/messages dispatching to ConversationService and returning ConversationResponse."
  - "Add GET /api/v1/sessions/{session_id} and GET /api/v1/sessions/{session_id}/events providing session inspection and redacted event log."
  - "Add POST /api/v1/sessions/{session_id}/approve supporting typed approval/revision of plan or sources, transitioning to READY_FOR_EXECUTION on plan approval or NEEDS_CLARIFICATION on revision."
  - "Add POST /api/v1/sessions/{session_id}/execute rejecting unapproved execution with 400/409, and executing approved plan via JobOrchestrator background execution while keeping /api/v1/jobs intact."
affected_symbols: 
  - "autoslide.conversation.schemas.CreateSessionResponse"
  - "autoslide.conversation.schemas.SendMessageRequest"
  - "autoslide.conversation.schemas.ApproveDecisionRequest"
  - "autoslide.conversation.schemas.SessionDetailResponse"
  - "autoslide.conversation.schemas.SessionEventsResponse"
  - "autoslide.api.create_app"
risk_level: LOW
---

# 📝 Sub Spec: Session API and Approval Endpoints

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa Task 3 của kế hoạch Always-on Agent Chat (`ADS-002`): cung cấp REST API cho hội thoại (`/api/v1/sessions`), tiếp nhận upload PPTX, trao đổi tin nhắn, truy xuất chi tiết/events, duyệt/sửa plan, và kích hoạt thực thi có kiểm soát (execution approval gate) mà không làm ảnh hưởng đến endpoint `/api/v1/jobs` hiện có.
> **Quyết định then chốt**: Định nghĩa schemas Pydantic chuẩn; tích hợp `ConversationService` và `SessionStore` vào FastAPI app factory; chặn tuyệt đối việc thực thi khi chưa được duyệt plan (HTTP 400/409); kích hoạt background pipeline khi đã duyệt `READY_FOR_EXECUTION`.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 3 trong kế hoạch Always-on Agent Chat (`ADS-002`):
1. **`POST /api/v1/sessions`**:
   - Tiếp nhận file upload `.pptx` (tương tự `/api/v1/jobs`).
   - Khởi tạo `ConversationSession` với `session_id` duy nhất, cấp phát workspace và liên kết `job_id`.
   - Trả về payload `{session_id, job_id, state="NEEDS_CLARIFICATION"}`.
2. **`POST /api/v1/sessions/{session_id}/messages`**:
   - Tiếp nhận payload `{message: str, selection_context: SelectionContext | None}`.
   - Điều phối qua `ConversationService.handle_message` để đánh giá tính rõ ràng, tạo brief, hoặc sinh typed plan.
   - Trả về `ConversationResponse` kèm trạng thái cập nhật và cards (`QuestionCard` hoặc `PlanCard`).
3. **`GET /api/v1/sessions/{session_id}`**:
   - Trả về thông tin chi tiết phiên hội thoại: `session`, `brief`, `plan`, `sources`, và `active_job` (nếu có).
4. **`GET /api/v1/sessions/{session_id}/events`**:
   - Trả về danh sách sự kiện kiểm toán (`events`) đã được che giấu dữ liệu nhạy cảm (redacted) của session/job.
5. **`POST /api/v1/sessions/{session_id}/approve`**:
   - Tiếp nhận `{kind: "plan" | "sources", approved: bool, feedback: str | None}`.
   - Nếu `kind == "plan"`:
     - `approved == True`: Chuyển trạng thái từ `WAITING_PLAN_APPROVAL` sang `READY_FOR_EXECUTION`.
     - `approved == False`: Chuyển trạng thái về `NEEDS_CLARIFICATION` kèm ghi nhận phản hồi (feedback) để điều chỉnh.
   - Nếu `kind == "sources"`:
     - Cập nhật trạng thái duyệt của danh sách nguồn, hỗ trợ chuyển trạng thái theo quy định.
6. **`POST /api/v1/sessions/{session_id}/execute`**:
   - Kiểm tra cổng phê duyệt (**Approval Gate**): Chỉ cho phép thực thi khi session đang ở trạng thái `READY_FOR_EXECUTION` với `plan` hợp lệ.
   - Nếu gọi trước khi được duyệt (ví dụ đang ở `NEEDS_CLARIFICATION` hoặc `WAITING_PLAN_APPROVAL`), từ chối ngay với HTTP 400 hoặc 409.
   - Khi hợp lệ: Chuyển trạng thái sang `EXECUTING`, tạo/kích hoạt job thực thi trong `JobOrchestrator` qua `BackgroundTasks`, giữ nguyên định dạng và hành vi của ADS-001.
7. **Tương thích ngược (Backward Compatibility)**:
   - Toàn bộ endpoint `/api/v1/jobs` và `/health`, `/ui`, `/api/v1/runtimes` tiếp tục hoạt động nguyên vẹn.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Task 1 (`ConversationSession`, `SessionStore`, state transitions) và Task 2 (`ConversationService`, `ClarificationEngine`, `SelectionContext`) đã hoàn thành và hoạt động ổn định.
- [x] **Giả định**: `JobWorkspace`, `JobOrchestrator`, và `JobRegistry` có khả năng phối hợp để lưu trữ PPTX gốc và thực thi các thao tác plan khi được duyệt.
- [ ] **Rủi ro**: Đồng bộ trạng thái giữa `JobRecord` (ADS-001) và `ConversationSession` (ADS-002) khi thực thi nền.
  - *Biện pháp*: Lưu trữ `job_id` trong session, cấp phát workspace tương thích và cập nhật session checkpoint khi job hoàn thành hoặc chuyển trạng thái.
- [ ] **Rủi ro**: Client gọi `/execute` đồng thời hoặc lặp lại khi session đang `EXECUTING`.
  - *Biện pháp*: Kiểm tra ràng buộc chuyển trạng thái `validate_transition`; từ chối nếu không ở `READY_FOR_EXECUTION`.
- [ ] **`[UNKNOWN]`**: Chưa có quy định riêng biệt về rate limiting cho endpoint gửi tin nhắn; hiện tại áp dụng xử lý tuần tự theo phiên.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/conversation/schemas.py` | Create | Định nghĩa Pydantic schemas: `CreateSessionResponse`, `SendMessageRequest`, `ApproveDecisionRequest`, `SessionDetailResponse`, `SessionEventsResponse` |
| `src/autoslide/api.py` | Modify | Tích hợp `ConversationService` và `SessionStore` vào `create_app`; bổ sung 6 endpoints `/api/v1/sessions*`; cài đặt HTTP error handling và execution gate |
| `tests/conftest.py` | Modify | Đảm bảo test environment cung cấp `conversation_service` / `session_store` và hỗ trợ kiểm thử API session |
| `tests/api/test_conversation_api.py` | Create | Bộ test toàn diện cho các route `/api/v1/sessions*`: create, message, detail, events, approve/revise, rejection before approval, execute after approval |

### Phân tích Logic Cốt lõi:
- **Nguyên tắc Phân tách Trách nhiệm (Separation of Concerns)**:
  - `schemas.py` chỉ chứa DTO/contract của tầng Web/HTTP.
  - `api.py` đóng vai trò Controller/Adapter tiếp nhận HTTP requests, kiểm tra định dạng file, xác thực trạng thái, và ủy quyền cho `ConversationService` hoặc `JobOrchestrator`.
  - `JobOrchestrator` và background pipeline tiếp tục quản lý quá trình thực thi nặng (rendering, mutation, quality gates).
- **Execution Approval Gate Pattern**:
  - Không bao giờ cho phép mutate hoặc chạy pipeline khi chưa có sự chấp thuận minh thị của người dùng (`approved: true` trên plan). Mọi nỗ lực gọi `/execute` trước thời điểm này đều bị chặn cứng ở tầng HTTP (HTTP 400/409).

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-1**: `POST /api/v1/sessions` chấp nhận file `.pptx` hợp lệ, khởi tạo workspace/session và trả về HTTP 201 với `{session_id, job_id, state="NEEDS_CLARIFICATION"}`. File không phải `.pptx` hoặc quá dung lượng bị từ chối với HTTP 400 / 413.
- [x] **AC-2**: `POST /api/v1/sessions/{session_id}/messages` nhận `{message, selection_context}`:
  - Yêu cầu chưa rõ ràng: Trả về HTTP 200, session ở `NEEDS_CLARIFICATION`, có câu hỏi làm rõ trong cards (`QuestionCard`).
  - Yêu cầu rõ ràng: Trả về HTTP 200, session ở `WAITING_PLAN_APPROVAL`, có typed `PlanCard` trong cards.
- [x] **AC-3**: `GET /api/v1/sessions/{session_id}` trả về đầy đủ session state, brief, plan, sources, và active job reference. Trả về HTTP 404 nếu `session_id` không tồn tại.
- [x] **AC-4**: `GET /api/v1/sessions/{session_id}/events` trả về danh sách events đã được che giấu dữ liệu nhạy cảm (redacted).
- [x] **AC-5**: `POST /api/v1/sessions/{session_id}/approve`:
  - `{kind: "plan", approved: true}` chuyển session từ `WAITING_PLAN_APPROVAL` sang `READY_FOR_EXECUTION`.
  - `{kind: "plan", approved: false, feedback: "..."}` chuyển session về `NEEDS_CLARIFICATION` kèm phản hồi.
- [x] **AC-6**: `POST /api/v1/sessions/{session_id}/execute`:
  - Khi session chưa ở `READY_FOR_EXECUTION`: Bị từ chối với HTTP 409 (`Execution rejected: plan has not been approved`).
  - Khi session ở `READY_FOR_EXECUTION`: Chuyển session sang `EXECUTING` và khởi động background job pipeline.
- [x] **AC-7**: Bảo toàn tính tương thích 100% của `/api/v1/jobs` và toàn bộ test suites hiện có (`tests/api/test_jobs.py`, `tests/api/test_workbench_api.py`, `tests/api/test_preview_diff_api.py`).

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Bytecode compilation
python3 -m compileall src tests
# Output: 0 errors

# 2. Chạy các test mới cho Session API
pytest tests/api/test_conversation_api.py -q -v
# Output: 10 passed, 1 warning in 6.50s

# 3. Chạy toàn bộ API test suite (đảm bảo backwards compatibility cho /api/v1/jobs)
pytest tests/api -q -v
# Output: 36 passed, 1 warning in 71.86s
```

### Manual QA
1. Khởi tạo session mới qua `POST /api/v1/sessions` kèm template PPTX và nhận `session_id`.
2. Gửi tin nhắn mập mờ `"Fix this slide"` tới `POST /api/v1/sessions/{session_id}/messages`, xác nhận nhận được `QuestionCard` và state `NEEDS_CLARIFICATION`.
3. Gửi tin nhắn chi tiết `"On slide 1, change title to 'Executive Summary'"` và kiểm tra nhận được `PlanCard` cùng state `WAITING_PLAN_APPROVAL`.
4. Gọi `POST /api/v1/sessions/{session_id}/execute` trước khi duyệt, xác nhận bị từ chối với mã lỗi 400/409.
5. Gọi `POST /api/v1/sessions/{session_id}/approve` với `{kind: "plan", approved: true}`, xác nhận state chuyển sang `READY_FOR_EXECUTION`.
6. Gọi `POST /api/v1/sessions/{session_id}/execute`, xác nhận nhận phản hồi thành công và session chuyển sang `EXECUTING`.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Kế thừa `SDD-SUB-20260919-12` (Domain Models & Store) và `SDD-SUB-20260919-13` (Clarification & Plan Conversation Service). Cung cấp giao diện API làm nền tảng cho Task 4 (Research Provenance), Task 5 (Deck Operations), và Task 6 (Always-on Chatbot UI).
- **Related Sessions**: `docs/superpowers/plans/2026-09-19-always-on-agent-chat.md`
- **Code Graph**: `autoslide.api` $\rightarrow$ `autoslide.conversation.service.ConversationService`, `autoslide.conversation.store.SessionStore`, `autoslide.conversation.schemas`, `autoslide.orchestrator.pipeline.JobOrchestrator`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
