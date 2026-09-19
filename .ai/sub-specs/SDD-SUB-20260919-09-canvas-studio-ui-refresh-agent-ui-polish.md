---
id: SDD-SUB-20260919-09
title: AutoSlide Canvas-First Studio UI Refresh with Robust Preview and Ingest State
author: agent-ui-polish
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Redesign the AutoSlide workbench as a canvas-first studio with top command bar, slide filmstrip, immediate template ingest state, robust preview fallbacks, and polished event/QA panels with zero external frontend dependencies."
decisions:
  - "Transform workbench layout from a basic form-sidebar into a canvas-first studio with sticky command bar, slide filmstrip thumbnail bar, side-by-side diff canvas with drag region selection, chronological event timeline, and floating human review bar."
  - "Provide immediate explicit ingest feedback upon PPTX file selection (file size, deck badge, ingestion ready state) and clear visual placeholders before, during, and after pipeline execution."
  - "Harden preview artifact URLs against 404s/delays with image load error handlers, retry fallbacks, and clear loading/error/empty states without changing backend API contracts."
  - "Preserve zero external frontend dependencies (pure HTML5, modern CSS3 variables/grid/flexbox, vanilla ES6 JavaScript) and 100% backward compatibility for all API endpoints."
affected_symbols:
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.js.workbench.js"
  - "autoslide.ui.static.css.workbench.css"
  - "tests.api.test_workbench_api"
risk_level: LOW
---

# 📝 Sub Spec: AutoSlide Canvas-First Studio UI Refresh with Robust Preview and Ingest State

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Nâng cấp giao diện AutoSlide thành Studio tương tác hiện đại lấy slide canvas làm trung tâm (canvas-first), tích hợp command bar, filmstrip điều hướng slide, preview trước/sau với highlight khác biệt, ingest state tức thì khi chọn PPTX, timeline sự kiện và QA findings trực quan, giữ nguyên zero-dependency và bảo toàn API contracts.
> **Quyết định then chốt**: Canvas-first studio layout; Command bar đa năng; Slide filmstrip; Ingest state & preview loading/error/empty handling tức thì; Bảo toàn 100% API contract & zero external dependency.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Nâng cấp toàn diện giao diện web AutoSlide Workbench theo chuẩn Canvas-First Studio:
1. **Immediate Ingest State & Robust Preview**:
   - Ngay khi người dùng chọn/kéo thả file `.pptx`, hiển thị ngay trạng thái ingest tường minh (tên file, dung lượng, trạng thái sẵn sàng xử lý, badge Ingest Ready).
   - Xử lý trạng thái preview hoàn chỉnh: loading spinner/skeleton, error fallback placeholder khi chưa có artifact hoặc tải lỗi, và empty state rõ ràng ("No slide loaded", "Select slide from filmstrip").
   - Cơ chế nạp URL artifact ổn định (relative/absolute pathing, retry fallback).
2. **Polished Canvas-First Studio Layout**:
   - **Command Bar**: Thanh công cụ đỉnh trang gồm Runtime Readiness indicator, File Ingest Status, Target Scope selector (Current Slide / Region / All Slides), Prompt input bar, và Action button.
   - **Slide Filmstrip**: Thanh thumbnail cuộn ngang/dọc hiển thị toàn bộ slide trong deck kèm trạng thái thay đổi (Modified badge) và cho phép click chuyển đổi nhanh slide đang xem.
   - **Canvas Studio**: Khu vực trung tâm hiển thị side-by-side Before/After diff, hỗ trợ kéo chọn vùng (Drag Region Selection), highlight overlays các phần tử bị thay đổi khi hover/inspect.
   - **Event Timeline**: Bảng dòng thời gian sự kiện trực quan theo chuỗi pipeline (Ingest -> Plan -> Execute -> Quality -> Review) thay vì raw JSON thô.
   - **QA Findings Panel**: Danh sách các lỗi/cảnh báo phân hạng theo severity (ERROR, WARNING, INFO) với gợi ý khắc phục cụ thể.
   - **Review & Download Action Bar**: Floating bar cho phép Duyệt & Tải về PPTX (`Approve`), Yêu cầu AI sửa tiếp (`Repair`), hoặc Hủy bỏ (`Reject`).
3. **Kỹ thuật & Kiến trúc**:
   - Giữ nguyên nguyên tắc **Zero External Frontend Dependencies** (thuần Vanilla ES6, CSS3 variables/flex/grid, HTML5 semantic).
   - Bảo toàn 100% hợp đồng API (`/api/v1/jobs`, `/api/v1/jobs/{id}`, `/api/v1/jobs/{id}/diff`, `/api/v1/jobs/{id}/events`, `/api/v1/jobs/{id}/decision`, `/api/v1/runtimes`, `/api/v1/jobs/{id}/artifacts/{name}`).
   - Thêm unit & UI smoke tests kiểm tra trạng thái preview loading/error, filmstrip, command bar và các tương tác cốt lõi.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Backend đã hỗ trợ render preview sang PNG qua LibreOffice/PptxRenderer trong workspace của job và trả về diff qua `/api/v1/jobs/{id}/diff`.
- [x] **Giả định**: Người dùng truy cập qua trình duyệt hiện đại hỗ trợ CSS Grid, Flexbox, Canvas/SVG, ES6 async/await.
- [ ] **Rủi ro**: Render ảnh từ PPTX cần thời gian (vài giây) tùy dung lượng file; nếu không có loading state rõ ràng, người dùng có thể tưởng hệ thống bị treo.
  - *Giải pháp*: Cung cấp visual progress skeleton, spinner loading và step progress trực tiếp trên canvas.
- [ ] **Rủi ro**: Trình duyệt có thể cache ảnh artifact cũ khi reload.
  - *Giải pháp*: Sử dụng query parameter hoặc timestamp cache-busting khi tải lại ảnh diff preview.
- [ ] **`[UNKNOWN]`**: Trình duyệt không có thư viện giải nén PPTX phía client mà vẫn cần zero dependencies.
  - *Giải pháp*: Khi chọn file, client đọc metadata file (name, size, lastModified) hiển thị trạng thái Ingest Ready ngay lập tức trên canvas; khi job được tạo hoặc pipeline chạy, load preview từ API.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ui/templates/index.html` | Modify | Cấu trúc lại layout theo Canvas-First Studio: Command bar, Slide filmstrip container, Canvas diff workspace với loading/error/empty layers, Event timeline stream, Quality findings drawer, Review action bar. |
| `src/autoslide/ui/static/css/workbench.css` | Modify | Thiết kế giao diện studio hiện đại: theme màu chuẩn IDE/Studio, responsive canvas, filmstrip cards, loading skeletons, error badges, timeline markers, overlays. |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Nâng cấp client logic: xử lý file selection immediate ingest state, robust preview image loading (onload/onerror fallbacks), dynamic filmstrip rendering, scope switching, drag region selection, timeline formatting, decision actions. |
| `tests/api/test_workbench_api.py` | Modify | Bổ sung các test cases kiểm thử giao diện HTML/JS: preview loading/error states, filmstrip elements, command bar components, decision actions. |
| `tests/ui/test_ui_behavior.py` | Add | Tạo bộ kiểm thử hành vi UI độc lập kiểm tra contract render HTML/CSS/JS, zero external dependencies (không chứa external CDN script/link), và các selectors thiết yếu. |

### Phân tích Logic Cốt lõi:

- **Canvas-First Layout**: Chuyển trọng tâm thị giác từ form nhập liệu sang Slide Canvas. Command bar phía trên giữ các thao tác thường trực (upload file, chọn scope, nhập instruction, chọn runtime, nút chạy). Slide filmstrip đặt ở cạnh hoặc đáy canvas giúp người dùng có cái nhìn toàn cảnh toàn bộ bài thuyết trình.
- **Robust Preview & Ingest State**:
  - Khi file PPTX được chọn qua `<input type="file">` hoặc kéo thả: giao diện chuyển ngay sang trạng thái `INGEST_READY`, cập nhật file badge và thông báo sẵn sàng trên canvas.
  - Khi bắt đầu edit: hiển thị overlay loading spinner với thông điệp từng giai đoạn ("Ingesting slide...", "Generating diff...").
  - Khi tải ảnh preview: đính kèm `onerror` handler để hiển thị fallback card có nút "Retry" hoặc thông báo lỗi thân thiện thay vì vỡ layout ảnh.
- **Zero Dependencies**: Sử dụng hoàn toàn Vanilla Web Standards, không import bất kỳ external CDN/library nào, đảm bảo hoạt động hoàn hảo trong môi trường offline/air-gapped.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Khi chọn file PPTX, hiển thị ngay lập tức trạng thái ingest tường minh (tên file, dung lượng, trạng thái Ingest Ready) mà không bị trống giao diện.
- [ ] Command bar đỉnh trang hiển thị đầy đủ: file upload/status, runtime readiness badge, scope switcher (Slide, Region, Deck), prompt input và execute button.
- [ ] Slide filmstrip hiển thị danh sách slide dạng thẻ thu nhỏ kèm số thứ tự slide và badge đánh dấu slide bị sửa đổi (`Modified`).
- [ ] Central canvas hiển thị đối sánh Original (Before) và Modified (After) cạnh nhau kèm highlight overlay khi có thay đổi.
- [ ] Vùng chọn kéo chuột (Drag Region Selection) hoạt động mượt mà trên canvas slide Before và đồng bộ tọa độ vào scope state.
- [ ] Preview hiển thị đầy đủ các trạng thái: Empty state, Loading skeleton/spinner, Error fallback state có nút retry.
- [ ] Event stream hiển thị dạng timeline trực quan với thời gian, loại sự kiện và trạng thái thành công/thất bại.
- [ ] Quality findings hiển thị rõ ràng mức độ nghiêm trọng (ERROR/WARNING/INFO), phần tử bị ảnh hưởng và giải pháp sửa.
- [ ] Human review action bar xuất hiện khi job hoàn thành hoặc chờ duyệt với 3 nút: Approve (tải PPTX), Repair, Reject.
- [ ] Không có bất kỳ external dependency nào (không `<script src="http...">`, không external stylesheet/fonts ngoài local).
- [ ] Tất cả các bài test (pytest, compileall) chạy thành công 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated

```bash
# 1. Chạy toàn bộ pytest suite
pytest -q

# 2. Kiểm tra biên dịch mã nguồn
python3 -m compileall src tests

# 3. Kiểm tra zero external dependencies trong UI templates
python3 -c '
from pathlib import Path
html = Path("src/autoslide/ui/templates/index.html").read_text()
assert "http://" not in html and "https://" not in html, "External CDN link detected!"
print("Zero external dependency check PASSED")
'
```

### Manual QA

1. Mở trình duyệt tại `http://localhost:8000/ui`.
2. Kéo thả file PPTX mẫu (`Template Weekly Report.pptx` hoặc test fixture).
3. Xác nhận Command Bar hiển thị thông tin file và Canvas hiển thị trạng thái Ingest Ready.
4. Chọn scope "Current Slide", nhập prompt "Update slide title", nhấn "Run AI Slide Edit".
5. Kiểm tra timeline hiển thị các bước, canvas hiển thị loading skeleton.
6. Khi hoàn tất, kiểm tra Slide Filmstrip có slide được đánh dấu modified, canvas Before/After hiển thị ảnh và overlays.
7. Thử kéo thả chuột tạo region trên slide Before, kiểm tra thông số tọa độ hiển thị chính xác.
8. Nhấn "Approve & Download" và kiểm tra file tải về.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: ADS-001 requirements (US-01, US-02, US-03, FR-07, FR-08, FR-10) và design (Section 2, 3.1, 3.7).
- **Related Sessions**: SDD-SUB-20260918-08-preview-diff-targeted-edit-agent-preview-diff.md, SDD-SUB-20260918-05-local-workbench-report.md.
- **Code Graph**: `autoslide.ui` (`index.html`, `workbench.js`, `workbench.css`) <-> `autoslide.api` (`create_app`, `/api/v1/jobs`, `/api/v1/jobs/{id}/diff`).

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
