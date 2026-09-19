---
id: SDD-SUB-20260919-10
title: AutoSlide Merged UI QA Verification and Studio E2E Audit
author: agent-ui-qa
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Comprehensive QA verification and browser audit of the merged canvas-first studio UI without modifying source code, validating bytecode compilation, pytest regression suite, smoke UI check, and real Playwright browser inspection."
decisions:
  - "Preserve strict QA invariant: do not modify application source code, verifying system state as merged from agent-ui-polish."
  - "Execute 4-tier verification matrix: (1) bytecode compilation across src and tests, (2) full pytest regression suite, (3) smoke_ui_check end-to-end runner, (4) Playwright headless Chromium browser inspection with user interaction simulations."
  - "Preserve machine-verifiable evidence in SESSION_STATE.json, log.csv, screenshots directory, and formal QA report in .ai/reports/."
affected_symbols:
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.js.workbench.js"
  - "autoslide.ui.static.css.workbench.css"
  - "tests.ui.test_ui_behavior"
  - "scripts.smoke_ui_check"
risk_level: LOW
---

# 📝 Sub Spec: AutoSlide Merged UI QA Verification and Studio E2E Audit

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thực hiện kiểm thử đảm bảo chất lượng (QA) toàn diện trên giao diện AutoSlide Studio Canvas-First đã merge, xác thực tính đúng đắn của giao diện, API contracts, tính ổn định tương tác người dùng, không thay đổi source code, và lưu giữ đầy đủ bằng chứng kiểm thử.
> **Quyết định then chốt**: Giữ nguyên mã nguồn; Kiểm thử 4 tầng (bytecode compile, pytest 134/134, smoke check, Playwright browser inspection); Thu thập bằng chứng visual screenshots và log.csv; Cập nhật SESSION_STATE.json.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

Đánh giá chất lượng toàn diện của nhánh `agent/ui-qa` sau khi merge tính năng Canvas-First Studio UI Refresh (`SDD-SUB-20260919-09`):
1. Đảm bảo toàn bộ mã nguồn `src/` và `tests/` biên dịch sạch (bytecode compilation clean).
2. Kiểm tra toàn bộ bộ kiểm thử tự động `pytest` (134 tests) đạt 100% pass rate.
3. Chạy kịch bản kiểm tra khói end-to-end `scripts/smoke_ui_check.py` kiểm tra kết nối API, layout HTML, CSS, JS, Runtime discovery, và SSE events.
4. Thực hiện kiểm thử trình duyệt thực tế (Browser Inspection via Playwright Chromium) mô phỏng hành vi người dùng:
   - Tải trang studio canvas-first và kiểm tra các trạng thái rỗng (empty states).
   - Tải file presentation `.pptx` và kiểm tra phản hồi tức thì (Immediate Ingest State: badge, pill, text).
   - Chuyển đổi scope chỉnh sửa và thao tác kéo thả chọn vùng (Drag Region Selection) trên canvas overlay.
   - Kích hoạt pipeline chỉnh sửa bằng AI, theo dõi event timeline stream hiển thị trực tiếp.
   - Kiểm tra hiển thị diff Before/After, quality findings, và thanh hành động Review (`Approve`, `Repair`, `Reject`).
   - Kiểm tra console log trình duyệt nhằm đảm bảo không có unhandled JavaScript errors hay layout breaks.
5. Ghi nhận đầy đủ bằng chứng kiểm thử vào `SESSION_STATE.json`, `log.csv`, thư mục screenshot và báo cáo nghiệm thu QA.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Môi trường có sẵn runtime Python 3.12, Chromium/Playwright hỗ trợ chế độ headless để chạy browser inspection.
- [x] **Giả định**: Backend API phục vụ chính xác static assets tại `/static` và template tại `/` và `/ui`.
- [ ] **Rủi ro**: Render ảnh từ PPTX cần thời gian (vài giây) tùy dung lượng file; nếu không có loading state rõ ràng, người dùng có thể tưởng hệ thống bị treo.
  - *Kết quả thẩm định*: UI đã có visual spinner skeleton (`#beforeLoading`, `#afterLoading`), badge Ingest Ready, và step progress hoạt động mượt mà.
- [ ] **Rủi ro**: Lỗi JavaScript runtime tiềm ẩn trên trình duyệt không bộc lộ qua unit tests.
  - *Kết quả thẩm định*: Playwright browser inspection ghi nhận chính xác 0 console errors và 0 page errors qua toàn bộ user journey.
- [ ] **`[UNKNOWN]`**: Trình duyệt không có thư viện giải nén PPTX phía client mà vẫn cần zero dependencies.
  - *Kết quả thẩm định*: Client đọc metadata file an toàn và server xử lý render background, duy trì nguyên tắc Zero Frontend Dependencies.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

Theo chỉ thị QA: **Không sửa đổi mã nguồn ứng dụng (Do not modify source)**.
Các tệp được tạo / cập nhật để phục vụ kiểm thử và lưu trữ bằng chứng:

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `SESSION_STATE.json` | Create/Update | Ghi nhận bằng chứng kiểm thử QA, kết quả test và trạng thái hoàn thành. |
| `log.csv` | Create | Ghi lại log thực thi lệnh bash theo quy chuẩn hội thoại. |
| `.ai/sub-specs/SDD-SUB-20260919-10-ui-qa-verification-agent-ui-qa.md` | Create | Sub-spec đặc tả quy trình và tiêu chí kiểm thử QA. |
| `.ai/reports/SDD-SUB-20260919-10-ui-qa-verification-report.md` | Create | Báo cáo chi tiết kết quả QA và audit. |

### Phân tích Logic Cốt lõi:
- Tuân thủ quy tắc kiểm thử độc lập (Independent QA Verification): QA không sửa đổi mã logic để giữ tính khách quan tuyệt đối.
- Sử dụng mô hình kiểm thử hộp đen kết hợp hộp trắng (Black-box & Gray-box) thông qua automated TestClient và headless Chromium.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] `python3 -m compileall src tests` thực thi thành công với 0 lỗi cú pháp.
- [x] `pytest -q` đạt 134/134 passed, 0 failures, 0 errors.
- [x] `scripts/smoke_ui_check.py` vượt qua tất cả các bước (Health, HTML, CSS, JS, Runtimes, Job creation, Events, Diff).
- [x] Playwright Browser Inspection hoàn thành trọn vẹn:
  - [x] Layout Canvas Studio và Command bar hiển thị đầy đủ.
  - [x] Immediate Ingest State hiển thị ngay khi nạp file PPTX.
  - [x] Thao tác kéo chọn vùng (Drag-to-select region) phản hồi chính xác tọa độ.
  - [x] Event timeline stream nhận và render sự kiện thời gian thực.
  - [x] Thanh Human Review Bar hiển thị khi pipeline hoàn tất và xử lý hành động Approve/Download.
  - [x] Trình duyệt không có lỗi console (0 console errors, 0 page errors).
- [x] Bằng chứng hình ảnh được lưu trữ đầy đủ.
- [x] `SESSION_STATE.json` và `log.csv` được cập nhật chính xác.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Bytecode Compilation
python3 -m compileall src tests

# 2. Pytest Regression Suite
pytest -q

# 3. End-to-End UI & API Smoke Check
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py
```

### Manual QA & Browser Inspection
```bash
# 4. Playwright Headless Browser Inspection
PYTHONPATH=src:. python3 $HOME/.gemini/antigravity-cli/brain/608f0019-08f0-49c3-9eea-a97e8e8ae4dd/scratch/run_browser_inspection.py
```

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/sub-specs/SDD-SUB-20260919-09-canvas-studio-ui-refresh-agent-ui-polish.md]]`
- **Related Sessions**: `[[.ai/reports/SDD-SUB-20260918-05-local-workbench-report.md]]`
- **Code Graph**: `src/autoslide/ui/templates/index.html` -> `src/autoslide/ui/static/js/workbench.js` -> `src/autoslide/api.py`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
