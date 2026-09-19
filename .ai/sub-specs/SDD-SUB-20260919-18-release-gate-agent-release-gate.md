---
id: SDD-SUB-20260919-18
title: Release Gate, Final Documentation & Full Evidence Verification
author: agent-release-gate
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Execute final release gate for ADS-002 Always-on Agent Chat: compile comprehensive evidence verification report, update README and capability documentation, verify end-to-end test suites and safety invariants, and advance spec statuses to COMPLETED."
decisions:
  - "Synthesize full evidence verification in .ai/reports/ADS-002-evidence.md covering all 6 user stories, 12 functional requirements, and 9 acceptance criteria with exact test logs and smoke script outputs."
  - "Update README.md and CAPABILITY_MAP.md to comprehensively document the conversational agent workflow, session lifecycle, interactive cards, runtime security boundary, and provenance tracking."
  - "Update .ai/specs/ADS-002/requirements.md and .ai/specs/ADS-002/tasks.md to mark all acceptance criteria and phase deliverables as COMPLETED."
  - "Run comprehensive verification gates: pytest test suite (models, clarification, service, API, research, provenance, executor operations, UI), compileall checks, smoke UI check, smoke conversation flow, and git hygiene validation."
affected_symbols:
  - "README.md"
  - "CAPABILITY_MAP.md"
  - ".ai/specs/ADS-002/requirements.md"
  - ".ai/specs/ADS-002/tasks.md"
  - ".ai/specs/ADS-002/CAPABILITY_MAP.md"
  - ".ai/reports/ADS-002-evidence.md"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Release Gate, Final Documentation & Full Evidence Verification

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thực hiện Release Gate cho năng lực `ADS-002` (Always-on Agent Chat): tổng hợp báo cáo bằng chứng xác thực (`.ai/reports/ADS-002-evidence.md`), cập nhật tài liệu kỹ thuật & hướng dẫn người dùng (`README.md`, `CAPABILITY_MAP.md`), đánh dấu hoàn thành các tiêu chí nghiệm thu trong specs (`requirements.md`, `tasks.md`), và xác minh 100% các cổng kiểm thử tự động, an toàn và toàn vẹn mã nguồn.
> **Quyết định then chốt**: Thu thập kết quả chạy thực tế của toàn bộ test suite; ghi nhận đầy đủ ma trận truy vết yêu cầu (Traceability Matrix); cập nhật tài liệu hệ thống rõ ràng về kiến trúc session, policy duyệt kế hoạch & nguồn tin, không lưu API key; đảm bảo quy chuẩn commit và đóng gói release sạch.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Hoàn thành Task 7 theo kế hoạch `docs/superpowers/plans/2026-09-19-always-on-agent-chat.md`:
1. **Tài liệu hóa quy trình Hội thoại & Khả năng Hệ thống**:
   - Cập nhật `README.md` với các hướng dẫn về kiến trúc Chatbot thường trực (Always-on Chat Rail), các loại thẻ tương tác (`QuestionCard`, `PlanCard`, `SourceCard`, `ExecutionCard`, `ReviewCard`, `ErrorCard`), thiết lập runtime agent cục bộ (không dùng API key trong app), chính sách phê duyệt hai lớp (Plan Approval & Source Approval), và theo dõi nguồn gốc nội dung (`Provenance`).
   - Cập nhật `CAPABILITY_MAP.md` và `.ai/specs/ADS-002/CAPABILITY_MAP.md` ghi nhận sự hoàn thiện của năng lực ADS-002.
2. **Tổng hợp Báo cáo Bằng chứng Nghiệm thu (`.ai/reports/ADS-002-evidence.md`)**:
   - Ghi lại nhật ký kiểm thử chi tiết từ unit tests, API tests, executor deck operations, UI contract tests, và E2E conversation smoke flow.
   - Bảng đối soát 6 User Stories (`US-01` -> `US-06`), 12 Functional Requirements (`FR-01` -> `FR-12`), 9 Acceptance Criteria, cùng 4 Bất biến an toàn (`Invariants`).
   - Ghi nhận các giới hạn kỹ thuật đã biết (Known Limitations) và hướng phát triển tiếp theo.
3. **Cập nhật Trạng thái Specs & Tasks**:
   - Chuyển trạng thái của `.ai/specs/ADS-002/requirements.md` từ `DRAFT` sang `COMPLETED`, đánh dấu toàn bộ checklist nghiệm thu `[x]`.
   - Cập nhật `.ai/specs/ADS-002/tasks.md` và plan document đánh dấu hoàn tất toàn bộ các Phase 1-6 và Task 7.
4. **Kiểm tra Cổng Chất lượng Toàn diện (Release Quality Gates)**:
   - Chạy toàn bộ pytest suite bao phủ các mô-đun: `tests/conversation/`, `tests/content/`, `tests/executor/`, `tests/api/`, `tests/ui/`.
   - Thực thi `python3 -m compileall src tests scripts`.
   - Thực thi `scripts/smoke_ui_check.py` và `scripts/smoke_conversation_flow.py`.
   - Kiểm tra định dạng và khoảng trắng (`git diff --check`).

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Tất cả 6 Tasks trước (Task 1: Domain models/checkpoints, Task 2: Clarification/planning, Task 3: Session APIs, Task 4: Research/provenance, Task 5: Deck operations, Task 6: UI & E2E smoke flow) đã được hoàn thành và tích hợp đầy đủ vào codebase.
- [x] **Giả định**: Các kịch bản kiểm thử không yêu cầu kết nối mạng bên ngoài hay provider API keys bí mật, đảm bảo tính chạy độc lập (air-gapped / local-first).
- [x] **Rủi ro**: Báo cáo bằng chứng có thể bị thiếu sót các trường hợp biên hoặc kiểm thử hồi quy đối với năng lực nền tảng ADS-001.
  - *Biện pháp*: Chạy đồng thời cả bộ test của ADS-001 (`tests/pptx/`, `tests/planner/`, `tests/render/`, `tests/qa/`) và ADS-002 (`tests/conversation/`, `tests/content/`, `tests/ui/`) để chứng minh tương thích ngược 100%.
- [x] **`[UNKNOWN]`**: [UNKNOWN: None - Tất cả thành phần đã được hoàn thiện trong các lát cắt trước]

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `README.md` | Modify | Thêm tài liệu hướng dẫn về Always-on Chatbot, Session endpoints (`/api/v1/sessions`), hệ thống thẻ tương tác, quy trình phê duyệt Plan/Sources, chính sách bảo mật Zero-API-Key, và ngữ cảnh chọn vùng/slide. |
| `CAPABILITY_MAP.md` | Modify | Cập nhật trạng thái năng lực ADS-002 sang Active/Delivered, liên kết các module hội thoại, nội dung và giao diện mới. |
| `.ai/specs/ADS-002/requirements.md` | Modify | Cập nhật Status thành `COMPLETED`, đánh dấu hoàn thành tất cả các mục Acceptance Criteria `[x]`. |
| `.ai/specs/ADS-002/tasks.md` | Modify | Đánh dấu hoàn thành toàn bộ Phase 1 - Phase 6 và Task 7. |
| `.ai/specs/ADS-002/CAPABILITY_MAP.md` | Modify | Đồng bộ hóa bản đồ năng lực chi tiết cho ADS-002. |
| `.ai/reports/ADS-002-evidence.md` | Create | Tạo báo cáo tổng kết bằng chứng release đầy đủ: test commands, log outputs, ma trận yêu cầu, kết quả smoke test E2E và ghi nhận trạng thái an toàn. |

### Phân tích Logic Cốt lõi:
- **Tính Minh bạch & Toàn vẹn (Evidence Integrity)**: Mọi kết quả kiểm thử trong báo cáo đều được trích xuất trực tiếp từ đầu ra thực tế của môi trường kiểm thử tự động, không giả lập kết quả.
- **Tuân thủ Bất biến An toàn (Security Invariants)**:
  1. *Original PPTX Immutable*: PPTX gốc không bị ghi đè, luôn tạo bản sao trong workspace.
  2. *Zero Provider API Keys*: Không yêu cầu, không ghi nhận API keys của LLM provider trong cấu hình ứng dụng; sử dụng local CLI runtime.
  3. *Zero Arbitrary Host Code Execution*: Mọi thao tác chỉnh sửa PPTX đều đi qua OOXML mutator an toàn với danh sách thao tác được kiểm soát (allowlisted ops).
  4. *Explicit Approval Gate*: Không chỉnh sửa PPTX và không chèn nguồn web nếu chưa có sự đồng ý tường minh từ người dùng qua thẻ hành động.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] `README.md` phản ánh đầy đủ kiến trúc hội thoại mới, cách sử dụng Always-on Chatbot, workflow duyệt kế hoạch/nguồn, và hướng dẫn chạy smoke test.
- [ ] `CAPABILITY_MAP.md` và `.ai/specs/ADS-002/CAPABILITY_MAP.md` được cập nhật đầy đủ thông tin về ADS-002.
- [ ] `.ai/specs/ADS-002/requirements.md` có Status `COMPLETED` và 9/9 tiêu chí nghiệm thu được đánh dấu `[x]`.
- [ ] `.ai/specs/ADS-002/tasks.md` được đánh dấu hoàn thành toàn bộ các Phase 1 đến Phase 6.
- [ ] `.ai/reports/ADS-002-evidence.md` được tạo với đầy đủ thông tin chi tiết: Traceability Matrix, Test Suite execution logs, Smoke flow logs, Security invariant verifications, và Known Limitations.
- [ ] Bộ test tự động `pytest` (tất cả các unit, integration, API, executor, UI tests) vượt qua 100% không có lỗi.
- [ ] Lệnh kiểm tra biên dịch `python3 -m compileall src tests scripts` thực thi không có lỗi cú pháp.
- [ ] Script `PYTHONPATH=src:. python3 scripts/smoke_ui_check.py` chạy thành công.
- [ ] Script `PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py` chạy thành công toàn bộ kịch bản E2E.
- [ ] `git diff --check` sạch sẽ, không có trailing whitespace hay conflict markers.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Kiểm tra biên dịch cú pháp mã nguồn
python3 -m compileall src tests scripts

# 2. Chạy toàn bộ test suite (ADS-001 & ADS-002)
pytest -v

# 3. Chạy smoke test UI
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py

# 4. Chạy smoke test luồng hội thoại hoàn chỉnh
PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py

# 5. Kiểm tra định dạng git diff
git diff --check
```

### Manual QA
1. Xem xét toàn bộ tài liệu `README.md`, `.ai/specs/ADS-002/requirements.md`, `.ai/specs/ADS-002/tasks.md`.
2. Kiểm tra tính mạch lạc, nhất quán và đầy đủ của báo cáo `.ai/reports/ADS-002-evidence.md`.
3. Kiểm tra tính đồng bộ của các ma trận yêu cầu so với mã nguồn thực tế.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/reports/ADS-002-evidence.md]]`
- **Related Sessions**: `[[.ai/sub-specs/SDD-SUB-20260919-12-conversation-foundation-agent-conversation-foundation.md]]`, `[[.ai/sub-specs/SDD-SUB-20260919-13-clarification-plan-agent-clarification-plan.md]]`, `[[.ai/sub-specs/SDD-SUB-20260919-14-session-api-agent-session-api.md]]`, `[[.ai/sub-specs/SDD-SUB-20260919-15-research-provenance-agent-research-provenance.md]]`, `[[.ai/sub-specs/SDD-SUB-20260919-16-deck-operations-agent-deck-ops.md]]`, `[[.ai/sub-specs/SDD-SUB-20260919-17-chatbot-ui-agent-chatbot-ui.md]]`
- **Code Graph**: `autoslide.conversation -> autoslide.content -> autoslide.executor -> autoslide.api -> autoslide.ui`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
