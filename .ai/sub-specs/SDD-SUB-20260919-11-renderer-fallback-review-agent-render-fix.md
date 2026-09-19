---
id: SDD-SUB-20260919-11
title: Slide Preview Renderer Bug Fix, Valid PNG Fallback, and Selection Review
author: agent-render-fix
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Replace corrupted MINIMAL_PNG_BYTES with valid PNG standard byte stream, implement resilient preview fallback mechanisms, review and establish intelligent preview renderer selection across pipeline and ingest, and add regression tests."
decisions:
  - "Replace hardcoded MINIMAL_PNG_BYTES in autoslide.ingest.renderer with a verified, valid 1x1 RGBA PNG byte stream passing PIL.Image.open / verify."
  - "Introduce select_preview_renderer() factory in autoslide.ingest.renderer with host capability detection (LibreOffice + pdftoppm / PyMuPDF) and resilient fallback to MockPreviewRenderer with valid PNG."
  - "Allow optional fallback_to_mock flag or graceful degradation in LibreOfficePreviewRenderer when headless conversion fails or external binaries are absent."
  - "Update JobOrchestrator and PPTXIngestor to accept configurable renderer via dependency injection, utilizing select_preview_renderer() instead of hardcoded MockPreviewRenderer."
  - "Preserve full backwards compatibility with existing 134 regression tests while providing robust preview rendering across testing and live environments."
affected_symbols:
  - "autoslide.ingest.renderer.MINIMAL_PNG_BYTES"
  - "autoslide.ingest.renderer.select_preview_renderer"
  - "autoslide.ingest.renderer.BasePreviewRenderer"
  - "autoslide.ingest.renderer.MockPreviewRenderer"
  - "autoslide.ingest.renderer.LibreOfficePreviewRenderer"
  - "autoslide.ingest.parser.PPTXIngestor"
  - "autoslide.orchestrator.pipeline.JobOrchestrator"
  - "tests.ingest.test_renderer"
risk_level: LOW
---

# 📝 Sub Spec: Slide Preview Renderer Bug Fix, Valid PNG Fallback, and Selection Review

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Sửa lỗi binary data của `MINIMAL_PNG_BYTES` thành định dạng PNG chuẩn hợp lệ (mở được bằng PIL/trình duyệt), bổ sung cơ chế fallback preview an toàn, chuẩn hóa selection logic cho renderer dựa trên năng lực môi trường host (LibreOffice + pdftoppm/fitz), và bổ sung kiểm thử hồi quy.
> **Quyết định then chốt**: Chuẩn hóa byte PNG 1x1 hợp lệ; Thêm hàm `select_preview_renderer()` tự động nhận diện runtime; Cho phép DI renderer vào `JobOrchestrator` và `PPTXIngestor`; Bổ sung fallback an toàn không làm gãy pipeline khi render ngoại vi gặp sự cố.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Khắc phục lỗi Invalid PNG**: Thay thế `MINIMAL_PNG_BYTES` trong `src/autoslide/ingest/renderer.py` vốn có checksum/chunk lỗi (`PIL.UnidentifiedImageError: cannot identify image file`) bằng chuỗi byte PNG 1x1 RGBA chuẩn, hợp lệ 100% khi giải mã bằng thư viện PIL và trình duyệt.
2. **Review & Cải tiến Renderer Selection**:
   - Hiện tại `JobOrchestrator` đang hardcode `renderer = MockPreviewRenderer()` tại mọi giai đoạn pipeline (`run_pipeline` và `review`), bỏ qua năng lực thực tế của host ngay cả khi đã cài đặt `soffice` và `pdftoppm`.
   - Cung cấp hàm chọn lựa renderer thông minh `select_preview_renderer(prefer_real: bool = True)` tự động kiểm tra sự tồn tại của `soffice` và công cụ chuyển PDF (`pdftoppm` hoặc `fitz`).
   - Hỗ trợ Dependency Injection (DI) cho `JobOrchestrator` và `PPTXIngestor` để caller có thể chỉ định renderer tùy ý.
3. **Cơ chế Fallback An toàn (Resilient Fallback)**:
   - Khi renderer thực tế (`LibreOfficePreviewRenderer`) gặp lỗi không mong muốn hoặc thiếu binary phụ thuộc trong quy trình xử lý, cung cấp tùy chọn fallback sang mock renderer sinh ảnh PNG hợp lệ thay vì làm đứt gãy toàn bộ pipeline chỉnh sửa slide.
4. **Kiểm thử & Bằng chứng**:
   - Bổ sung unit tests kiểm tra tính hợp lệ của PNG fallback (PIL verify).
   - Kiểm tra hành vi của `select_preview_renderer()` trong các điều kiện môi trường khác nhau.
   - Bảo toàn 100% số lượng tests hiện có (134/134 passed).

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Host Linux hiện tại có sẵn `soffice` (`/usr/bin/soffice`) và `pdftoppm` (`/usr/bin/pdftoppm`).
- [x] **Giả định**: Thư viện `PIL` (`Pillow`) có sẵn trong môi trường Python để kiểm chứng tính toàn vẹn của PNG.
- [ ] **Rủi ro**: Việc thay đổi renderer mặc định trong `JobOrchestrator` có thể ảnh hưởng đến tốc độ chạy của unit tests nếu tests gọi trực tiếp `JobOrchestrator` mà không mock renderer.
  - *Biện pháp kiểm soát*: Giữ `JobOrchestrator(renderer=None)` fallback an toàn hoặc cho phép cấu hình linh hoạt (mặc định trong test environment có thể dùng `MockPreviewRenderer` hoặc mock adapter khi cần, trong khi production/live tận dụng `select_preview_renderer()`).
- [ ] **`[UNKNOWN]`**: Yêu cầu cụ thể của User đối với hành vi mặc định khi `soffice` bị timeout: có nên fail fast qua `RenderError` hay fallback sang placeholder?
  - *Biện pháp*: Giữ `LibreOfficePreviewRenderer` ném `RenderError` theo đúng contract cũ cho các test case timeout/not found, đồng thời cung cấp fallback mode hoặc wrapper orchestrator xử lý fallback êm dịu (graceful fallback).

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/renderer.py` | Modify | Cập nhật `MINIMAL_PNG_BYTES` thành byte stream PNG 1x1 RGBA chuẩn; Bổ sung `select_preview_renderer(prefer_real=True, ...)` |
| `src/autoslide/ingest/__init__.py` | Modify | Export `select_preview_renderer` |
| `src/autoslide/orchestrator/pipeline.py` | Modify | Nhận `renderer: BasePreviewRenderer | None` trong `JobOrchestrator.__init__` và sử dụng thay vì khởi tạo cứng `MockPreviewRenderer` |
| `src/autoslide/ingest/parser.py` | Modify | Hỗ trợ sử dụng `select_preview_renderer` hoặc renderer truyền vào |
| `tests/ingest/test_renderer.py` | Modify | Thêm test kiểm tra `MINIMAL_PNG_BYTES` hợp lệ bằng PIL, kiểm thử `select_preview_renderer` và fallback behaviors |

### Phân tích Logic Cốt lõi:
- **Valid PNG Standards**: Chuỗi byte PNG phải có đầy đủ Signature (`\x89PNG\r\n\x1a\n`), IHDR chunk với CRC chính xác (`\x1f\x15\xc4\x89`), IDAT chunk chứa zlib compressed stream của 1 scanline RGBA, và IEND chunk với CRC (`\xaeB`\x82`).
- **Strategy & Factory Pattern**: Sử dụng `select_preview_renderer()` như một Factory Method đóng gói logic phát hiện môi trường (`shutil.which("soffice")`, `pdftoppm`, `fitz`), tuân thủ Open/Closed Principle.
- **Dependency Injection**: Cho phép `JobOrchestrator` nhận `renderer` từ bên ngoài, giúp decoupling giữa business orchestration và thumbnail rendering adapter.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] `MINIMAL_PNG_BYTES` được đọc và xác thực thành công bởi `PIL.Image.open()` mà không phát sinh bất kỳ ngoại lệ nào (`cannot identify image file` được loại bỏ hoàn toàn).
- [ ] Tất cả ảnh thumbnail do `MockPreviewRenderer` sinh ra đều là file ảnh PNG hợp lệ, kích thước > 0 bytes và mở được bằng PIL / công cụ xử lý ảnh.
- [ ] `select_preview_renderer()` trả về `LibreOfficePreviewRenderer` khi `soffice` và công cụ chuyển PDF có sẵn, và tự động fallback về `MockPreviewRenderer` khi thiếu dependency.
- [ ] `JobOrchestrator` cho phép inject preview renderer qua constructor, hỗ trợ linh hoạt cho cả môi trường kiểm thử isolated và môi trường production runtime.
- [ ] Toàn bộ 134 bài kiểm thử hiện có tiếp tục vượt qua 100% (`pytest -q`).
- [ ] Thêm các test case mới xác thực tính hợp lệ của PNG fallback và selection review.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Kiểm tra tính hợp lệ của PNG fallback với PIL
PYTHONPATH=src pytest -v tests/ingest/test_renderer.py

# 2. Kiểm tra toàn bộ regression suite
PYTHONPATH=src pytest -q

# 3. Kiểm tra bytecode compilation
python3 -m compileall src tests

# 4. Kiểm tra smoke UI check
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py
```

### Manual QA
1. Dùng PIL nạp trực tiếp `MINIMAL_PNG_BYTES` và kiểm tra `img.size == (1, 1)` và `img.format == "PNG"`.
2. Kiểm tra manifest và các file ảnh `slide_*.png` được tạo ra trong `previews/` của job workspace để đảm bảo không có file ảnh rỗng hay hỏng header.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/sub-specs/SDD-SUB-20260918-01-pptx-ingest-agy_b.md]]`
- **Related Sessions**: `[[.ai/specs/ADS-001/requirements.md]]`
- **Code Graph**: `autoslide.ingest.renderer -> autoslide.orchestrator.pipeline -> autoslide.ui.api`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
