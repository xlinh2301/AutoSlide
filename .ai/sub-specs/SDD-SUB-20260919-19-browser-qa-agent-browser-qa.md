---
id: SDD-SUB-20260919-19
title: Comprehensive Browser E2E and UI Verification
author: agent-browser-qa
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Execute comprehensive Playwright browser E2E test suite against AutoSlide Web Demo on http://localhost:8088/ui, verify presentation upload, filmstrip, canvas diff, chat rail, multi-turn dialogue, card interactions, fix selection context clearing defect in workbench.js, and establish automated browser regression testing."
decisions:
  - "Fix clearChatSelectionContext in workbench.js to properly nullify selection context and hide the context badge rather than re-triggering slide context re-display via clearRegionSelection()."
  - "Support optional selection_context in sendChatMessage when no slide or object is explicitly selected."
  - "Implement automated Playwright browser test script in scripts/e2e_browser_qa.py and full pytest integration test in tests/ui/test_browser_e2e.py using dynamic ephemeral port binding."
affected_symbols:
  - "autoslide.ui.static.js.workbench.js"
  - "scripts.e2e_browser_qa"
  - "tests.ui.test_browser_e2e"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Comprehensive Browser E2E and UI Verification

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thực hiện kiểm thử toàn diện Browser E2E và giao diện người dùng (UI) trên AutoSlide Web Demo (`http://localhost:8088/ui`). Kiểm tra quy trình tải lên `/tmp/demo.pptx`, hiển thị Filmstrip, Canvas Before/After, Chat Rail thường trực, tương tác thẻ đa lượt (`QuestionCard`, `PlanCard`, `SourceCard`, `ExecutionCard`, `ReviewCard`), gắn kết ngữ cảnh `SelectionContext`, phát hiện & khắc phục lỗi UI, viết test hồi quy và lập báo cáo chi tiết.
> **Quyết định then chốt**: Sửa lỗi hàm `clearChatSelectionContext()` trong `workbench.js` (trước đó gọi `clearRegionSelection()` làm kích hoạt lại `updateChatSelectionContext` khiến badge ngữ cảnh không ẩn khi người dùng bấm nút xóa); bổ sung script `scripts/e2e_browser_qa.py` và test Playwright `tests/ui/test_browser_e2e.py`.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

1. **Kiểm thử E2E Trình duyệt thực tế (Live Browser E2E)**:
   - Truy cập `http://localhost:8088/ui` thông qua trình duyệt Chromium tự động hóa bằng Playwright.
   - Kiểm tra đầy đủ cấu trúc DOM: Filmstrip Navigator (`#filmstripTrack`, `#filmstripCount`), Canvas Before/After (`#beforeFrame`, `#afterFrame`, `#beforePlaceholder`, `#afterPlaceholder`), Chat Rail (`#chatRail`, `#chatHeader`, `#chatMessages`, `#chatComposer`, `#chatInput`, `#btnSendChat`), Timeline & Quality Findings panels.
2. **Kiểm thử Luồng Tương tác Hội thoại Đa Lượt (Multi-turn Chat & Interactive Cards)**:
   - Tải lên tệp trình chiếu `/tmp/demo.pptx`, xác thực phản hồi khởi tạo phiên `session_id` và thông báo chào mừng từ trợ lý.
   - Thao tác gắn kết và xóa ngữ cảnh chọn slide / vùng canvas (`#chatContextBadge`, `#btnClearChatContext`).
   - Gửi yêu cầu chỉnh sửa mơ hồ để kích hoạt `QuestionCard` với danh sách lựa chọn làm rõ.
   - Nhấp chọn phương án làm rõ từ `QuestionCard` và nhập nội dung cụ thể.
   - Kiểm tra hiển thị `PlanCard` (Badge, Summary, Operations list, Confidence, nút Approve/Revise).
   - Nhấp **Approve & Execute**, kiểm tra hiển thị `SourceCard` (nếu có nghiên cứu web), `ExecutionCard` (tiến trình thực thi), và `ReviewCard` (nút tải xuống PPTX kết quả).
3. **Giám sát & Khắc phục Lỗi Frontend / Backend (Defect Remediation)**:
   - Giám sát toàn bộ JS Console errors/warnings, uncaught page exceptions, và failed network requests.
   - Phát hiện và sửa lỗi trong `workbench.js` khi xóa ngữ cảnh chọn.
   - Bổ sung bộ test hồi quy Playwright tự động trong `tests/ui/test_browser_e2e.py`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: AutoSlide backend server khởi chạy trên cổng 8088 hoặc chạy độc lập qua uvicorn test fixtures.
- [x] **Giả định**: Playwright và trình duyệt Chromium có sẵn trong môi trường thử nghiệm.
- [x] **Rủi ro**: Trùng cổng mạng (port collision) khi chạy song song nhiều tiến trình kiểm thử.
  - *Biện pháp*: Sử dụng hàm cấp phát cổng động `get_free_port()` cho fixture pytest `live_server_url`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Sửa `clearChatSelectionContext()` để gán `slide_index = null`, xóa vùng chọn và ẩn `#chatContextBadge` dứt điểm; cập nhật `sendChatMessage` xử lý `payloadContext` khi không có context. |
| `scripts/e2e_browser_qa.py` | Create | Script tự động hóa Playwright Chromium chạy qua toàn bộ 6 bước kiểm thử browser E2E, kiểm tra DOM, card interactions, console logs, và network errors. |
| `tests/ui/test_browser_e2e.py` | Create | Pytest integration test sử dụng Playwright và live Uvicorn test server để kiểm thử hồi quy luồng browser E2E hoàn chỉnh. |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] Toàn bộ các phần tử DOM chính (Filmstrip, Canvas Before/After, Chat Rail, Composer, Timeline, QA Findings) hiển thị đầy đủ và đúng vị trí trên trình duyệt.
- [x] Tải lên `/tmp/demo.pptx` thành công, kích hoạt Immediate Ingest State và khởi tạo phiên làm việc với tin nhắn phản hồi từ trợ lý.
- [x] Tương tác gắn kết ngữ cảnh `SelectionContext` hoạt động chính xác: chọn slide hiển thị badge "Slide 1", bấm nút clear ẩn badge hoàn toàn.
- [x] Gửi prompt làm rõ hiển thị đúng `QuestionCard`, click chọn option tự động điền/gửi câu trả lời.
- [x] `PlanCard` hiển thị đầy đủ danh sách thao tác, tóm tắt và nút Approve & Execute; click Approve kích hoạt thực thi thành công.
- [x] Kết thúc thực thi hiển thị `ReviewCard` với nút Download PPTX hoạt động tốt.
- [x] JS Console errors: 0, Page uncaught exceptions: 0, Failed HTTP requests: 0.
- [x] Toàn bộ test suite `pytest tests/ui` (10/10) và toàn bộ pytest suite (210/210) vượt qua 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Chạy kịch bản Playwright E2E trực tiếp trên server live 8088
python3 scripts/e2e_browser_qa.py

# 2. Chạy bộ kiểm thử browser E2E trong pytest
pytest tests/ui/test_browser_e2e.py -v

# 3. Chạy toàn bộ UI tests suite
pytest tests/ui -v

# 4. Chạy smoke scripts
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py
PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py

# 5. Chạy toàn bộ pytest suite
pytest -q
```

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Report Reference**: `[[.ai/reports/SDD-SUB-20260919-19-browser-qa-report.md]]`
- **Main Spec**: `[[.ai/specs/ADS-002/requirements.md]]`
- **Code Graph**: `autoslide.ui.workbench.js -> autoslide.ui.templates.index.html -> autoslide.conversation.service`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
