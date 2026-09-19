---
id: SDD-SUB-20260919-17
title: Always-on Chatbot UI and End-to-End Verification
author: agent-chatbot-ui
status: APPROVED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement always-on conversational chatbot rail, interactive cards (QuestionCard, PlanCard, SourceCard, ExecutionCard, ReviewCard, ErrorCard), selection context binding, and browser smoke verification flow."
decisions:
  - "Introduce a persistent right-rail chat interface in index.html alongside the canvas and filmstrip, replacing one-shot prompt emphasis with continuous multi-turn dialogue."
  - "Implement structured card renderers in workbench.js for QuestionCard (clarification choices), PlanCard (typed operations with approve/revise), SourceCard (web provenance with approve/reject), ExecutionCard (pipeline progress), ReviewCard (diff & download actions), and ErrorCard (sanitized diagnostics & retry)."
  - "Bind canvas drag-region and filmstrip slide selection into SelectionContext payloads transmitted over POST /api/v1/sessions/{id}/messages."
  - "Preserve existing /api/v1/jobs compatibility while adopting /api/v1/sessions as the primary interactive workflow transport."
  - "Create tests/ui/test_conversation_ui.py and scripts/smoke_conversation_flow.py to verify full lifecycle: upload -> clarification -> answer -> plan approval -> execution -> diff -> follow-up edit -> download."
affected_symbols:
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.js.workbench.js"
  - "autoslide.ui.static.css.workbench.css"
  - "scripts.smoke_conversation_flow"
  - "scripts.smoke_ui_check"
  - "tests.ui.test_conversation_ui"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Always-on Chatbot UI and End-to-End Verification

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa Task 6 trong kế hoạch Always-on Agent Chat (`ADS-002`): xây dựng giao diện chatbot thường trực (always-on chatbot rail) trên AutoSlide Studio Workbench, hỗ trợ hiển thị thẻ tương tác chuyên dụng (`QuestionCard`, `PlanCard`, `SourceCard`, `ExecutionCard`, `ReviewCard`, `ErrorCard`), tự động gắn kết ngữ cảnh chọn slide/vùng (`SelectionContext`) vào thanh soạn thảo chat, và thiết lập kịch bản kiểm thử luồng hội thoại hoàn chỉnh (`scripts/smoke_conversation_flow.py` & `tests/ui/test_conversation_ui.py`).
> **Quyết định then chốt**: Tích hợp thanh chat cố định bên phải (right rail) hoạt động song song với Canvas Before/After và Filmstrip; hỗ trợ API transport `POST /api/v1/sessions/{id}/messages`; chuyển hóa các quyết định phê duyệt (plan approval, source approval) thành các action trên thẻ; giữ vững tính khả dụng độc lập không phụ thuộc thư viện frontend ngoài (vanilla HTML/CSS/ES6).
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 6 theo thiết kế `ADS-002`:
1. **Always-on Chatbot Rail (`index.html` & `workbench.css`)**:
   - Bổ sung cấu trúc giao diện chat thường trực bên cạnh Canvas Before/After và Filmstrip.
   - Bao gồm Header phiên làm việc (Session status, active runtime indicator), dòng thời gian hội thoại (Message turn stream), và bộ soạn thảo tin nhắn (Composer with Send button, clear context action, and shortcut keys).
2. **Hệ thống Thẻ Tương tác Chuyên biệt (Interactive Card System in `workbench.js`)**:
   - `QuestionCard`: Hiển thị các câu hỏi làm rõ từ `ClarificationEngine`, cho phép người dùng nhấp chọn phương án trả lời nhanh hoặc nhập câu trả lời tự do.
   - `PlanCard`: Hiển thị kế hoạch thao tác có cấu trúc (`TaskPlan`), danh sách slide mục tiêu, độ tin cậy (`confidence`), quy tắc bảo toàn, kèm 2 nút hành động: **Approve Plan** (`POST /api/v1/sessions/{id}/approve` kind=plan) và **Revise / Clarify**.
   - `SourceCard`: Hiển thị các nguồn tin tìm kiếm web (`SourceRecord`: URL, tiêu đề, tóm tắt, thời điểm thu thập), hỗ trợ nút **Approve Sources** (`kind=sources`) và **Reject / Skip Web**.
   - `ExecutionCard`: Hiển thị tiến trình thực thi backend (Planning -> Mutating -> QA Verifying), spinner trạng thái, và liên kết job workspace.
   - `ReviewCard`: Hiển thị tóm tắt diff trực quan, các thay đổi đã thực hiện, cùng nút **Download Result PPTX** và gợi ý prompt chỉnh sửa tiếp theo (Follow-up turn).
   - `ErrorCard`: Hiển thị thông báo lỗi đã làm sạch (redacted diagnostics), nút **Retry** hoặc **Revise Instruction**.
3. **Gắn kết Ngữ cảnh Chọn (`SelectionContext` Binding)**:
   - Khi người dùng click chọn slide trên filmstrip hoặc kéo thả vùng chữ nhật trên canvas Before, tự động sinh badge ngữ cảnh trên khung chat (`Slide X` hoặc `Region [x, y, w, h]`).
   - Gửi kèm `selection_context: {slide_index, object_ref, selected_text}` trong payload `POST /api/v1/sessions/{id}/messages`.
4. **Kiểm thử Hợp đồng UI & Kịch bản Khói Trình duyệt (E2E Verification)**:
   - Viết bộ test hợp đồng UI trong `tests/ui/test_conversation_ui.py` kiểm tra cấu trúc DOM, selectors, message transport, card rendering, and context attachments.
   - Viết kịch bản khói tự động `scripts/smoke_conversation_flow.py` mô phỏng đầy đủ luồng người dùng: Upload PPTX -> Gửi prompt mơ hồ -> Nhận câu hỏi làm rõ -> Trả lời câu hỏi -> Nhận PlanCard -> Duyệt Plan -> (Duyệt Nguồn nếu có) -> Thực thi -> Xem Diff -> Gửi Prompt Follow-up -> Tải file kết quả.
   - Cập nhật `scripts/smoke_ui_check.py` để xác thực các thành phần UI mới.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: Backend endpoints `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/messages`, `GET /api/v1/sessions/{id}`, `POST /api/v1/sessions/{id}/approve`, và `POST /api/v1/sessions/{id}/execute` đã sẵn sàng và tuân thủ `ADS-002`.
- [ ] **Giả định**: Mã nguồn UI tuân thủ nguyên tắc vanilla HTML/CSS/JavaScript (ES6), không dùng NPM package build step hay React/Vue framework để đảm bảo tính nhẹ và chạy cục bộ 100%.
- [ ] **Rủi ro**: Việc mở rộng layout thêm thanh Chatbot Rail có thể làm co hẹp không gian hiển thị của Canvas Before/After trên màn hình nhỏ.
  - *Biện pháp*: Thiết kế responsive layout với CSS Grid / Flexbox, cho phép cuộn độc lập và hỗ trợ toggle thu gọn/mở rộng chat rail khi cần thiết.
- [ ] **Rủi ro**: Lỗi mạng hoặc trễ phản hồi từ LLM runtime có thể làm giao diện bị treo trạng thái loading.
  - *Biện pháp*: Bổ sung optimistic UI rendering, timeout handling, trạng thái disabled cho nút gửi khi đang xử lý, và hiển thị `ErrorCard` có nút Retry khi request thất bại.
- [ ] **`[UNKNOWN]`**: [UNKNOWN: None - API contracts and DOM schemas are fully defined in ADS-002 specs and Task 1-5 sub-specs]

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ui/templates/index.html` | Modify | Thêm cấu trúc DOM cho Persistent Chat Rail (`#chatRail`, `#chatMessages`, `#chatComposer`, `#chatInput`, `#btnSendChat`, `#chatContextBadge`), gắn kết các card templates. |
| `src/autoslide/ui/static/css/workbench.css` | Modify | Thêm CSS styles cho Chat Rail (layout 3 cột: Filmstrip, Canvas Diff, Chat Rail), kiểu dáng từng loại card (`card-question`, `card-plan`, `card-source`, `card-execution`, `card-review`, `card-error`), message bubbles, và composer context tags. |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Bổ sung module quản lý Session (`sessionState`), hàm gửi tin nhắn `sendChatMessage`, các hàm render thẻ (`renderQuestionCard`, `renderPlanCard`, `renderSourceCard`, `renderExecutionCard`, `renderReviewCard`, `renderErrorCard`), hàm xử lý approve/reject plan và sources, cùng cơ chế gắn `SelectionContext` từ canvas/filmstrip. |
| `tests/ui/test_conversation_ui.py` | Create | Bộ test kiểm thử cấu trúc DOM, sự hiện diện của chat elements, message endpoints contract, card schemas, và selection context propagation. |
| `scripts/smoke_conversation_flow.py` | Create | Kịch bản kiểm thử E2E giả lập luồng hội thoại hoàn chỉnh từ upload, clarification, plan approval, execution, diff preview, đến follow-up turn. |
| `scripts/smoke_ui_check.py` | Modify | Cập nhật các assertions kiểm tra sự tồn tại của chatbot rail, message containers, và CSS classes liên quan. |

### Phân tích Logic Cốt lõi:
- **Tương thích Ngược (Backward Compatibility)**: Người dùng vẫn có thể thực hiện flow tải file và chạy lệnh trực tiếp từ Command Bar nếu muốn, đồng thời luồng Chatbot Rail tự động đồng bộ hóa trạng thái phiên làm việc (`activeSessionId`) khi upload presentation.
- **Event-Driven UI Updates**: Khi nhận phản hồi từ backend `ConversationResponse`, UI phân tách `cards` và render tương ứng vào dòng thời gian (`#chatMessages`), cuộn mượt xuống cuối (auto-scroll) và cập nhật trạng thái pipeline stepper.
- **Xử lý Tương tác Thẻ (Interactive Card Actions)**:
  - Khi click vào option trong `QuestionCard` -> Điền hoặc gửi ngay nội dung lựa chọn vào luồng chat.
  - Khi click **Approve Plan** -> Gửi `POST /api/v1/sessions/{id}/approve` (`kind: "plan", approved: true`) -> Tự động kích hoạt `POST /api/v1/sessions/{id}/execute` hoặc chuyển tiếp sang duyệt nguồn.
  - Khi click **Revise Plan** -> Kích hoạt composer với prompt tiền định hướng người dùng nêu điểm cần sửa.
  - Khi click **Approve Sources** / **Reject Sources** -> Gửi `POST /api/v1/sessions/{id}/approve` (`kind: "sources"`).

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Giao diện AutoSlide Studio hiển thị đầy đủ Chat Rail thường trực (`#chatRail`) bên cạnh Canvas Before/After và Filmstrip.
- [ ] Gửi tin nhắn qua Chat Composer gọi đúng endpoint `POST /api/v1/sessions/{session_id}/messages` và hiển thị tin nhắn user/assistant.
- [ ] Phản hồi chứa câu hỏi làm rõ hiển thị đúng định dạng `QuestionCard` với danh sách lựa chọn có thể click chọn.
- [ ] Phản hồi chứa kế hoạch hiển thị đúng định dạng `PlanCard` với chi tiết operations và nút hành động Approve / Revise.
- [ ] Phản hồi chứa nguồn tin hiển thị đúng định dạng `SourceCard` với URL, tóm tắt và nút Approve / Reject.
- [ ] Trạng thái thực thi hiển thị đúng `ExecutionCard` kèm tiến trình và liên kết trạng thái.
- [ ] Sau khi thực thi hoàn tất, hiển thị `ReviewCard` kèm nút Download PPTX và hỗ trợ gửi tin nhắn Follow-up.
- [ ] Lỗi hệ thống/mạng hiển thị đúng `ErrorCard` kèm nút Retry.
- [ ] Chọn slide trên filmstrip hoặc chọn vùng trên canvas tự động cập nhật `SelectionContext` vào tin nhắn chat tiếp theo.
- [ ] Kịch bản `scripts/smoke_conversation_flow.py` chạy thành công toàn bộ chu trình không có lỗi.
- [ ] Kịch bản `scripts/smoke_ui_check.py` và toàn bộ test suite `pytest tests/ui` vượt qua 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Chạy bộ kiểm thử UI và hợp đồng hội thoại
pytest tests/ui/test_conversation_ui.py -v

# 2. Chạy toàn bộ regression test suite
pytest tests/ui tests/conversation tests/api tests/executor -q

# 3. Biên dịch kiểm tra cú pháp toàn bộ project
python3 -m compileall src tests scripts

# 4. Chạy smoke test UI hiện hữu
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py

# 5. Chạy smoke test luồng hội thoại E2E mới
PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py
```

### Manual QA
1. Khởi động server AutoSlide cục bộ qua `uvicorn autoslide.api:create_app --factory --port 8000`.
2. Mở trình duyệt truy cập `http://localhost:8000/ui`.
3. Tải lên file PPTX mẫu -> Xác nhận phiên chat (`session_id`) được khởi tạo.
4. Nhập prompt không rõ ràng: *"Cải thiện slide"* -> Xác nhận `QuestionCard` xuất hiện với các câu hỏi làm rõ.
5. Click chọn phương án làm rõ -> Xác nhận `PlanCard` xuất hiện với chi tiết chỉnh sửa.
6. Click **Approve Plan** -> Xác nhận `ExecutionCard` chạy và Canvas Before/After cập nhật kết quả.
7. Chọn một vùng trên canvas Before -> Xác nhận context badge hiển thị trong chat composer.
8. Gửi prompt follow-up -> Xác nhận hệ thống tiếp nhận ngữ cảnh mới trên nền deck đã sửa đổi.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/walkthroughs/impact-report-ADS-002-chatbot-ui]]`
- **Related Sessions**: `[[.ai/walkthroughs/session-20260919-chatbot-ui]]`
- **Code Graph**: `autoslide.ui.workbench -> autoslide.conversation.service -> autoslide.api`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
