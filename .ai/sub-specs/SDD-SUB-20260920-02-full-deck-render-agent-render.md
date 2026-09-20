---
id: SDD-SUB-20260920-02
title: Full-Deck Ingest & Dual-Column Live Render Engine
author: agent-render
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Implement full-deck slide ingestion with 100% thumbnail preview extraction, dual-column Before/After state tracking, delta re-rendering for modified slides, and the GET /api/v1/sessions/{session_id}/deck API endpoint."
decisions:
  - "Extract and render preview thumbnails for 100% of slides in a presentation during initial ingestion and session creation."
  - "Maintain dual-column Before (original baseline) and After (working/mutated) slide preview states, initialized with Before == After (modified=False)."
  - "Provide a Delta Re-render mechanism in autoslide.ingest.renderer and workspace manager that re-renders only affected slides upon text/style mutations, and re-indexes on structural slide changes (add/delete/reorder)."
  - "Define structured schemas DeckSlideState and DeckStateResponse to represent the dual-column live deck view with preview URLs, slide indices, and modification flags."
  - "Expose GET /api/v1/sessions/{session_id}/deck in autoslide.api to serve the real-time Before/After presentation state to the UI workbench."
affected_symbols:
  - "autoslide.ingest.renderer.BasePreviewRenderer.render_previews"
  - "autoslide.ingest.renderer.BasePreviewRenderer.render_slide_delta"
  - "autoslide.ingest.renderer.MockPreviewRenderer"
  - "autoslide.ingest.renderer.LibreOfficePreviewRenderer"
  - "autoslide.ingest.models.DeckSlideState"
  - "autoslide.ingest.models.DeckStateResponse"
  - "autoslide.jobs.workspace.JobWorkspace"
  - "autoslide.api.get_session_deck"
  - "tests.render.test_full_deck_render"
risk_level: MEDIUM
---

# 📝 Sub Spec: Full-Deck Ingest & Dual-Column Live Render Engine

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Xây dựng engine xử lý toàn bộ slide (Full-Deck Ingest), tự động trích xuất và sinh ảnh preview cho 100% số slide trong tệp PPTX khi tải lên; thiết lập trạng thái đồng bộ 2 cột Before (Gốc) và After (Chỉnh sửa) ban đầu giống nhau 100%; hỗ trợ cơ chế Delta Re-render chỉ cập nhật các slide bị thay đổi sau mỗi thao tác mutation của Agent; và cung cấp endpoint `GET /api/v1/sessions/{session_id}/deck` cho giao diện Studio Canvas.
> **Quyết định then chốt**:
> 1. Render đầy đủ 100% slide ngay khi khởi tạo session (`POST /api/v1/sessions` & `JobWorkspace`).
> 2. Quản lý ảnh Before và After riêng biệt: `previews/before/slide_XXX.png` và `previews/after/slide_XXX.png`.
> 3. Cơ chế Delta Re-render tối ưu hiệu năng: chỉ render lại slide bị sửa đổi và gắn cờ `modified: true`.
> 4. Cung cấp API `GET /api/v1/sessions/{session_id}/deck` trả về danh sách slide đầy đủ kèm link ảnh Before & After.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Full-Deck Ingest & Preview Extraction**:
   - Khi người dùng tải lên tệp PPTX (tạo Session hoặc Job), hệ thống phân tích toàn bộ cấu trúc deck và tự động sinh ảnh preview độ nét cao cho **100% số slide** (không chỉ slide 1 hoặc slide mẫu).
2. **Dual-Column Synchronization (Before / After Parity)**:
   - Cung cấp dữ liệu trực quan cho giao diện Studio 2 cột:
     * Cột Bên Trái (**Before**): Giữ nguyên ảnh preview của tệp gốc ban đầu (`baseline.pptx`).
     * Cột Bên Phải (**After**): Khởi tạo với ảnh giống hệt cột Before (`before == after`, `modified: false`).
3. **Delta Re-rendering & Change Tracking Engine**:
   - Khi Agent hoặc Executor thực thi mutation trên `working.pptx` (như `edit_slide_text`, `update_slide_style`):
     * Chỉ re-render các slide bị tác động (`modified_slide_indices`), cập nhật ảnh `after` tương ứng.
     * Khi có thay đổi cấu trúc (`add_slide`, `delete_slide`, `reorder_slide`), tái lập chỉ mục và cập nhật toàn bộ danh sách slide.
     * Gắn cờ `modified: true` cho các slide có sự khác biệt so với baseline.
4. **API Contract**:
   - Triển khai endpoint `GET /api/v1/sessions/{session_id}/deck` trả về mô hình `DeckStateResponse` bao gồm danh sách `DeckSlideState` và danh sách `modified_slide_indices`.
   - Cung cấp route phục vụ ảnh preview tĩnh hoặc artifact download cho Before và After previews.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**:
  - `JobWorkspace` đã có sẵn thư mục `previews/` và có thể mở rộng lưu trữ `previews/before/` và `previews/after/`.
  - Hệ thống hỗ trợ cả `MockPreviewRenderer` (cho unit tests cô lập và môi trường không có headless office) và `LibreOfficePreviewRenderer` (với `soffice` + `pdftoppm`/`fitz`).
  - Presentation có thể có từ 1 đến hàng chục slide; engine cần xử lý mượt mà và giới hạn thời gian render tối đa qua timeout.
- [ ] **Rủi ro**:
  - Tệp PPTX có nhiều slide (>50 slides) có thể mất vài giây để LibreOffice render ra PDF và rasterize toàn bộ ảnh.
  - *Phương án giải quyết*: Sử dụng caching cho ảnh Before (chỉ render 1 lần duy nhất lúc ingest); Delta Re-render chỉ rasterize các trang PDF bị ảnh hưởng ở cột After khi có thay đổi nội dung.
- [ ] **`[UNKNOWN]`**:
  - Chưa rõ khi có thao tác `delete_slide` hoặc `add_slide`, cột Before hiển thị như thế nào đối với các vị trí slide mới thêm hoặc đã xóa.
  - *Giải pháp thiết kế*: Cột Before luôn phản ánh danh sách slide ban đầu của baseline deck; cột After phản ánh danh sách slide hiện tại của working deck. Các slide mới thêm vào cột After sẽ có `before_url: null` và `modified: true`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/models.py` | Modify | Bổ sung model `DeckSlideState` (`index`, `before_url`, `after_url`, `modified`, `title`) và `DeckStateResponse` (`session_id`, `job_id`, `slide_count`, `slides`, `modified_slide_indices`, `last_modified_at`) |
| `src/autoslide/ingest/renderer.py` | Modify | Cập nhật `BasePreviewRenderer`, `MockPreviewRenderer`, `LibreOfficePreviewRenderer`: hỗ trợ render toàn bộ slide vào `previews/before` & `previews/after`, và phương thức `render_slide_delta(pptx_path, workspace, target_slide_indices)` |
| `src/autoslide/jobs/workspace.py` | Modify | Hỗ trợ quản lý thư mục `previews/before/` và `previews/after/`, cung cấp helper lấy preview path và cập nhật delta previews |
| `src/autoslide/conversation/service.py` | Modify | Khi khởi tạo session hoặc sau khi có tool mutation, kích hoạt full preview render và lưu trữ state liên kết |
| `src/autoslide/api.py` | Modify | Thêm endpoint `GET /api/v1/sessions/{session_id}/deck`, phục vụ ảnh preview qua static/artifact routes, và tự động kích hoạt full-deck preview khi upload session template |
| `tests/render/test_full_deck_render.py` | Create | Bộ test toàn diện: Full-deck ingest, Before==After initial state, Delta re-render khi sửa text, structural mutation (add/delete), và API verification |

### Phân tích Logic Cốt lõi:
- **Dual Directory Structure**:
  - `workspace.root / "previews" / "before"` chứa ảnh gốc: `slide_001.png`, `slide_002.png`, ...
  - `workspace.root / "previews" / "after"` chứa ảnh sau sửa đổi: `slide_001.png`, `slide_002.png`, ...
  - Khi khởi tạo session, sao chép toàn bộ ảnh từ `before/` sang `after/` để đảm bảo ban đầu `Before == After`.
- **Delta Re-rendering Algorithm**:
  - Khi nhận danh sách `modified_indices: list[int]`:
    - Với `MockPreviewRenderer`: Chỉ ghi lại file `after/slide_{idx:03d}.png` với timestamp/signature mới.
    - Với `LibreOfficePreviewRenderer`: Render `working.pptx` ra PDF tạm, chỉ trích xuất các trang tương ứng trong `modified_indices` vào thư mục `after/`.
    - Cập nhật manifest và trả về `DeckStateResponse` với cờ `modified: true` cho các slide trong `modified_indices`.
- **API Endpoint Contract**:
  - `GET /api/v1/sessions/{session_id}/deck` tổng hợp thông tin từ `baseline.pptx` và `working.pptx` trong workspace của session, đối chiếu file ảnh hiện có và trả về payload chuẩn xác cho Studio UI.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-01 (Full-Deck Preview Extraction)**: Khi khởi tạo Session với file PPTX có $N$ slide ($N \ge 1$), hệ thống trích xuất và sinh đầy đủ $N$ file ảnh preview cho toàn bộ deck.
- [x] **AC-02 (Initial Parity)**: Trạng thái ban đầu của deck (`GET /api/v1/sessions/{session_id}/deck`) trả về `slide_count == N`, tất cả các slide đều có `modified == False`, `before_url` và `after_url` trỏ đến ảnh tương ứng hợp lệ.
- [x] **AC-03 (Delta Re-render on Edit)**: Khi gọi hàm re-render delta với danh sách slide bị sửa đổi (ví dụ slide 2), chỉ ảnh preview của slide 2 ở cột After được cập nhật; các slide khác giữ nguyên; `modified_slide_indices` chứa `[2]`.
- [x] **AC-04 (Structural Mutation Support)**: Khi thêm slide mới (`add_slide`) hoặc xóa slide (`delete_slide`), hệ thống cập nhật đúng `slide_count` mới và chỉ mục của các slide.
- [x] **AC-05 (Fast Fallback & Mock Compatibility)**: Trong môi trường unit test không có LibreOffice, `MockPreviewRenderer` sinh đầy đủ mock PNGs hợp lệ cho tất cả các slide và pass 100% tests.
- [x] **AC-06 (API Integration)**: Endpoint `GET /api/v1/sessions/{session_id}/deck` trả về HTTP 200 kèm payload `DeckStateResponse` chuẩn schema; trả về HTTP 404 khi session không tồn tại.
- [x] **AC-07 (Quality & Hygiene)**: Mã nguồn tuân thủ type annotations đầy đủ, không có lint error, và toàn bộ test suite trong `tests/render/test_full_deck_render.py` cùng các regression tests hiện có đều vượt qua 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated Tests Execution
```bash
# 1. Chạy riêng bộ unit test Full-Deck Render Engine
PYTHONPATH=src pytest -v tests/render/test_full_deck_render.py

# 2. Chạy regression test suite toàn bộ dự án
PYTHONPATH=src pytest -q

# 3. Kiểm tra tính hợp lệ của cú pháp và type check
python3 -m compileall src tests
```

### Manual QA
1. Khởi tạo session với tệp PPTX mẫu 3 slide (`sample_3_slides.pptx`).
2. Gửi request `GET /api/v1/sessions/{session_id}/deck`:
   - Xác nhận nhận về 3 slide.
   - Xác nhận `before_url` và `after_url` có thể truy cập được và trả về HTTP 200 (PNG image).
   - Xác nhận `modified == False` cho cả 3 slide.
3. Giả lập mutation trên slide 2 và gọi delta re-render:
   - Gửi request `GET /api/v1/sessions/{session_id}/deck`.
   - Xác nhận slide 2 có `modified == True`, slide 1 và 3 có `modified == False`.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: `[[.ai/sub-specs/SDD-SUB-20260919-11-renderer-fallback-review-agent-render-fix.md]]`
- **Main Specification**: `[[.ai/specs/ADS-003/requirements.md]]`
- **Design Specification**: `[[.ai/specs/ADS-003/design.md]]`
- **Task Breakdown**: `[[.ai/specs/ADS-003/tasks.md]]`
- **Code Graph**: `autoslide.ingest.renderer -> autoslide.jobs.workspace -> autoslide.api -> autoslide.ui`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
