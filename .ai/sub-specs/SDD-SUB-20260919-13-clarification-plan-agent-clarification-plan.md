---
id: SDD-SUB-20260919-13
title: Clarification and Plan Conversation Service
author: agent-clarification-plan
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement ConversationService and ClarificationEngine to evaluate vague requests with targeted single questions, generate typed plan cards in WAITING_PLAN_APPROVAL for complete requests, and maintain multi-turn follow-up context."
decisions: 
  - "Introduce Question, ClarificationResult, SelectionContext, and ConversationResponse models to structure dialog, questions, cards, and context."
  - "Implement ClarificationEngine with deterministic rule-based checks for target, action, content, and preservation intent; never mutate presentation during clarification."
  - "For vague requests, ClarificationEngine emits exactly one targeted question, keeping session in NEEDS_CLARIFICATION with an incomplete EditBrief."
  - "For complete requests, ConversationService synthesizes a TaskPlan, transitions session state to WAITING_PLAN_APPROVAL, and emits a structured typed plan card."
  - "Support multi-turn follow-ups incorporating previous EditBrief, selection context, and latest accepted deck inventory."
affected_symbols: 
  - "autoslide.conversation.clarification.Question"
  - "autoslide.conversation.clarification.ClarificationResult"
  - "autoslide.conversation.clarification.ClarificationEngine"
  - "autoslide.conversation.service.SelectionContext"
  - "autoslide.conversation.service.ConversationResponse"
  - "autoslide.conversation.service.ConversationService"
  - "autoslide.planner.models.TaskPlan"
  - "autoslide.planner.builder.PromptPayloadBuilder"
risk_level: LOW
---

# 📝 Sub Spec: Clarification and Plan Conversation Service

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa `ConversationService` và `ClarificationEngine` thuộc Task 2 của `ADS-002`. Xử lý yêu cầu tự nhiên không rõ ràng bằng cách đặt đúng 1 câu hỏi trọng tâm (không sửa đổi slide hay tạo mutation TaskPlan), chuyển sang `WAITING_PLAN_APPROVAL` kèm typed plan card khi yêu cầu đã đầy đủ, và hỗ trợ hội thoại lặp (follow-up turns) với context và previous brief.
> **Quyết định then chốt**: Kiểm tra thiếu trường (target, action, content, preservation) một cách tất định (deterministic); không gọi adapter tự ý sửa deck; chuyển trạng thái tuân thủ nghiêm ngặt state machine; đóng gói card phản hồi theo cấu trúc chuẩn.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 2 của kế hoạch Always-on Agent Chat (`ADS-002`):
1. **ClarificationEngine**:
   - `ClarificationEngine.assess(message: str, inventory: DeckInventory | None, previous_brief: EditBrief | None) -> ClarificationResult`
   - Đánh giá tính đầy đủ của yêu cầu từ người dùng dựa trên 4 chiều:
     - `target`: Slide mục tiêu hoặc thành phần cần chỉnh sửa (slide index, object fingerprint/type).
     - `action`: Hành động mong muốn (replace text, format, replace image, move/resize, duplicate, delete).
     - `content`: Dữ liệu nội dung mới (chuỗi text thay thế, đường dẫn ảnh, thuộc tính format).
     - `preservation`: Ý định bảo toàn hoặc phạm vi ảnh hưởng (giữ nguyên layout, format hay style).
   - Nếu yêu cầu mơ hồ hoặc thiếu thông tin: Đưa ra đúng 1 câu hỏi trọng tâm (`Question`), giữ trạng thái `NEEDS_CLARIFICATION`, không sinh mutation `TaskPlan`.
   - Nếu yêu cầu đầy đủ: Trả về `ClarificationResult` với `state=ConversationState.READY_FOR_PLAN` hoặc `WAITING_PLAN_APPROVAL` và `complete=True` trên `EditBrief`.
2. **ConversationService**:
   - `ConversationService.handle_message(session_id: str, message: str, context: SelectionContext | None = None) -> ConversationResponse`
   - Tải `ConversationSession` từ `SessionStore`.
   - Kết hợp `SelectionContext` (slide đang chọn, object đang focus) và `previous_brief` từ session.
   - Ghi nhận `ChatTurn` của user.
   - Chạy `ClarificationEngine.assess`.
   - Nếu chưa đầy đủ: Cập nhật brief, thêm `ChatTurn` của assistant kèm `QuestionCard`, giữ state `NEEDS_CLARIFICATION`, lưu session.
   - Nếu đầy đủ: Tạo `TaskPlan` tương ứng (hoặc ủy quyền planner builder), chuyển trạng thái sang `WAITING_PLAN_APPROVAL`, thêm `ChatTurn` của assistant kèm `PlanCard`, cập nhật session và lưu vào `SessionStore`.
   - Trả về `ConversationResponse(session, assistant_message, cards)`.
3. **Follow-up Handling**:
   - Khi có turn tiếp theo sau một brief hoặc sau khi user trả lời câu hỏi làm rõ, hệ thống hợp nhất (`merge`) thông tin từ `previous_brief` với input mới, không làm mất ngữ cảnh đã xác nhận trước đó.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Task 1 đã hoàn thiện `ConversationState`, `ChatTurn`, `EditBrief`, `ConversationSession`, và `SessionStore` tại `autoslide.conversation`.
- [x] **Giả định**: `DeckInventory` có sẵn tại `autoslide.ingest.models` để cung cấp cấu trúc slide phục vụ kiểm tra target hợp lệ.
- [x] **Rủi ro**: Yêu cầu tự nhiên của người dùng có thể phong phú, nếu regex/rule-based quá cứng nhắc có thể gây false positive (báo thiếu thông tin dù đã nói rõ).
  - *Biện pháp*: Phân tích kết hợp heuristic theo từ khóa hành động, số slide, nội dung trong ngoặc kép hoặc ngữ cảnh tuyển lựa `SelectionContext`.
- [x] **Rủi ro**: Người dùng trả lời bổ sung cho câu hỏi trước đó (follow-up).
  - *Biện pháp*: Kế thừa `previous_brief` từ session, bổ sung thông tin còn thiếu vào brief hiện tại.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/conversation/clarification.py` | Create | Định nghĩa `Question`, `ClarificationResult`, và lớp `ClarificationEngine` với deterministic missing-field checks |
| `src/autoslide/conversation/service.py` | Create | Định nghĩa `SelectionContext`, `ConversationResponse`, và lớp `ConversationService` điều phối session & clarification/plan |
| `src/autoslide/planner/models.py` | Modify | Thêm helper `to_card()` hoặc representation phục vụ render card cho `TaskPlan` |
| `src/autoslide/planner/builder.py` | Modify | Hỗ trợ build `TaskPlan` trực tiếp từ `EditBrief` hoặc bổ sung context hỗ trợ conversation |
| `tests/conversation/test_clarification.py` | Create | Unit test cho `ClarificationEngine`: vague request, complete request, follow-up merge |
| `tests/conversation/test_service.py` | Create | Unit test cho `ConversationService`: handle_message với vague input, complete input, selection context, plan card generation |

### Phân tích Logic Cốt lõi:
- **Tại sao cần tách riêng `ClarificationEngine` và `ConversationService`?**
  Single Responsibility Principle: `ClarificationEngine` là pure domain logic kiểm tra độ hoàn thiện của yêu cầu và tổng hợp brief (không phụ thuộc I/O hay persistence). `ConversationService` là application service điều phối I/O (`SessionStore`), quản lý vòng đời session và sinh response.
- **Quy tắc 1 câu hỏi duy nhất (Single Targeted Question Invariant)**:
  Khi một yêu cầu thiếu nhiều trường (ví dụ vừa thiếu slide mục tiêu vừa thiếu nội dung mới), `ClarificationEngine` ưu tiên hỏi thông tin quan trọng nhất trước (Target > Action > Content > Preservation), tránh hỏi dồn dập nhiều câu cùng lúc theo quy tắc AGENTS.md.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-1**: Yêu cầu mơ hồ (ví dụ: "make this better", "update the title") sinh ra đúng 1 câu hỏi làm rõ (`Question`), trạng thái ở `NEEDS_CLARIFICATION`, và tuyệt đối không tạo `TaskPlan` mutation.
- [x] **AC-2**: Yêu cầu đầy đủ (ví dụ: "On slide 1, change the title to 'Q3 Financial Results'") sinh ra `TaskPlan`, chuyển session sang `WAITING_PLAN_APPROVAL`, và đính kèm typed `PlanCard`.
- [x] **AC-3**: `SelectionContext` (ví dụ `slide_index=1`) được tôn trọng và tự động điền vào trường target còn thiếu nếu user không nhắc lại số slide trong lời nhắn.
- [x] **AC-4**: Follow-up turns: Khi session đã có `previous_brief` thiếu `content`, tin nhắn tiếp theo chứa content sẽ hoàn thiện brief và chuyển sang `WAITING_PLAN_APPROVAL`.
- [x] **AC-5**: `ConversationService.handle_message` ghi nhận đầy đủ `ChatTurn` (user + assistant) và lưu atomic checkpoint vào `SessionStore`.
- [x] **AC-6**: Tất cả tests mới trong `tests/conversation/test_service.py` và `tests/conversation/test_clarification.py` chạy qua 100%, đồng thời không gây hồi quy trên `tests/planner`.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Chạy test mới cho clarification và service
pytest tests/conversation/test_clarification.py tests/conversation/test_service.py -q -v
# Output: 13 passed in 0.10s

# 2. Chạy test liên quan cho toàn bộ module conversation và planner
pytest tests/conversation tests/planner -q
# Output: 44 passed in 0.40s

# 3. Kiểm tra cú pháp và compile
python3 -m compileall src tests
# Output: 0 errors

# 4. Regression toàn hệ thống
pytest -q
# Output: 166 passed, 1 warning in 175.75s
```


### Manual QA
1. Khởi tạo `ConversationSession` và gọi `ConversationService.handle_message` với câu lệnh mập mờ `"Fix my slide"`.
2. Kiểm tra `ConversationResponse`: session state phải là `NEEDS_CLARIFICATION`, có 1 câu hỏi gợi ý, không có plan.
3. Gửi câu trả lời tiếp theo `"Slide 2, change subtitle to 'Annual Report 2026'"`.
4. Kiểm tra `ConversationResponse`: session state chuyển sang `WAITING_PLAN_APPROVAL`, card chứa `plan` hợp lệ.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Tiếp nối `SDD-SUB-20260919-12` (Task 1). Làm tiền đề cho Task 3 (`Session API and approval endpoints`) và Task 5 (`Deck structure operations`).
- **Related Sessions**: `docs/superpowers/plans/2026-09-19-always-on-agent-chat.md`
- **Code Graph**: `autoslide.conversation.service` kết nối `autoslide.conversation.store`, `autoslide.conversation.clarification`, và `autoslide.planner.models`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
