---
id: SDD-SUB-20260919-11
title: Slide Preview Renderer Bug Fix, Valid PNG Fallback, and Selection Review
author: agent-render-fix
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Replace corrupted MINIMAL_PNG_BYTES with valid PNG standard byte stream, implement resilient preview fallback mechanisms, review and establish intelligent preview renderer selection across pipeline and ingest, and add regression tests."
decisions:
  - "Replace hardcoded MINIMAL_PNG_BYTES in autoslide.ingest.renderer with a verified, valid 1x1 RGBA PNG byte stream passing PIL.Image.open / verify."
  - "Introduce select_preview_renderer() factory in autoslide.ingest.renderer with host capability detection (LibreOffice + pdftoppm / PyMuPDF) and resilient fallback to MockPreviewRenderer with valid PNG."
  - "Allow optional fallback_to_mock flag or graceful degradation in LibreOfficePreviewRenderer when headless conversion fails or external binaries are absent."
  - "Update JobOrchestrator and PPTXIngestor to accept configurable renderer via dependency injection, utilizing select_preview_renderer() instead of hardcoded MockPreviewRenderer."
  - "Preserve full backwards compatibility with existing regression tests while providing robust preview rendering across testing and live environments."
affected_symbols:
  - "autoslide.ingest.renderer.MINIMAL_PNG_BYTES"
  - "autoslide.ingest.renderer.select_preview_renderer"
  - "autoslide.ingest.renderer.BasePreviewRenderer"
  - "autoslide.ingest.renderer.MockPreviewRenderer"
  - "autoslide.ingest.renderer.LibreOfficePreviewRenderer"
  - "autoslide.ingest.parser.PPTXIngestor"
  - "autoslide.orchestrator.pipeline.JobOrchestrator"
  - "autoslide.api.create_app"
  - "tests.ingest.test_renderer"
risk_level: LOW
---

# 📝 Sub Spec: Slide Preview Renderer Bug Fix, Valid PNG Fallback, and Selection Review

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Sửa lỗi binary data của `MINIMAL_PNG_BYTES` thành định dạng PNG chuẩn hợp lệ (mở được bằng PIL/trình duyệt), bổ sung cơ chế fallback preview an toàn, chuẩn hóa selection logic cho renderer dựa trên năng lực môi trường host (LibreOffice + pdftoppm/fitz), và bổ sung kiểm thử hồi quy.
> **Quyết định then chốt**: Chuẩn hóa byte PNG 1x1 hợp lệ; Thêm hàm `select_preview_renderer()` tự động nhận diện runtime; Cho phép DI renderer vào `JobOrchestrator` và `PPTXIngestor`; Bổ sung fallback an toàn không làm gãy pipeline khi render ngoại vi gặp sự cố.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

1. **Khắc phục lỗi Invalid PNG**: Thay thế `MINIMAL_PNG_BYTES` trong `src/autoslide/ingest/renderer.py` vốn có checksum/chunk lỗi (`PIL.UnidentifiedImageError: cannot identify image file`) bằng chuỗi byte PNG 1x1 RGBA chuẩn, hợp lệ 100% khi giải mã bằng thư viện PIL và trình duyệt.
2. **Review & Cải tiến Renderer Selection**:
   - Thay thế hardcoded `MockPreviewRenderer` trong `JobOrchestrator` bằng renderer configurable qua constructor dependency injection và factory `select_preview_renderer()`.
   - Cung cấp hàm chọn lựa renderer thông minh `select_preview_renderer(prefer_real: bool = True)` tự động kiểm tra sự tồn tại của `soffice` và công cụ chuyển PDF (`pdftoppm` hoặc `fitz`).
   - Hỗ trợ Dependency Injection (DI) cho `create_app`, `JobOrchestrator`, và `PPTXIngestor` để caller có thể chỉ định renderer tùy ý.
3. **Cơ chế Fallback An toàn (Resilient Fallback)**:
   - Khi renderer thực tế (`LibreOfficePreviewRenderer`) gặp lỗi không mong muốn hoặc thiếu binary phụ thuộc trong quy trình xử lý, tùy chọn `fallback_to_mock=True` tự động chuyển tiếp sang mock renderer sinh ảnh PNG hợp lệ thay vì làm đứt gãy toàn bộ pipeline chỉnh sửa slide.
4. **Kiểm thử & Bằng chứng**:
   - Bổ sung unit tests kiểm tra tính hợp lệ của PNG fallback (PIL verify).
   - Kiểm tra hành vi của `select_preview_renderer()` trong các điều kiện môi trường khác nhau.
   - Bảo toàn và mở rộng test suite (140/140 passed).

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Host Linux hiện tại có sẵn `soffice` (`/usr/bin/soffice`) và `pdftoppm` (`/usr/bin/pdftoppm`).
- [x] **Giả định**: Thư viện `PIL` (`Pillow`) có sẵn trong môi trường Python để kiểm chứng tính toàn vẹn của PNG.
- [x] **Rủi ro**: Việc thay đổi renderer mặc định trong `JobOrchestrator` có thể ảnh hưởng đến tốc độ chạy của unit tests nếu tests gọi trực tiếp `JobOrchestrator` mà không mock renderer.
  - *Kết quả xử lý*: `JobOrchestrator` nhận `renderer` qua DI với fallback mặc định `MockPreviewRenderer` cho các unit test nội bộ (giữ test suite nhanh), trong khi `create_app` tự động chọn `select_preview_renderer()` cho môi trường live.
- [x] **`[UNKNOWN]`**: Yêu cầu cụ thể của User đối với hành vi mặc định khi `soffice` bị timeout: có nên fail fast qua `RenderError` hay fallback sang placeholder?
  - *Kết quả xử lý*: `LibreOfficePreviewRenderer` mặc định `fallback_to_mock=False` giữ nguyên contract ném `RenderError` khi gọi độc lập, và hỗ trợ `fallback_to_mock=True` khi được wrap qua factory `select_preview_renderer`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/renderer.py` | Modify | Cập nhật `MINIMAL_PNG_BYTES` thành byte stream PNG 1x1 RGBA chuẩn; Bổ sung `fallback_to_mock` cho `LibreOfficePreviewRenderer`; Bổ sung `select_preview_renderer` |
| `src/autoslide/ingest/__init__.py` | Modify | Export `select_preview_renderer` và `MINIMAL_PNG_BYTES` |
| `src/autoslide/orchestrator/pipeline.py` | Modify | Nhận `renderer: BasePreviewRenderer | None` trong `JobOrchestrator.__init__` và sử dụng `self.renderer` xuyên suốt pipeline |
| `src/autoslide/api.py` | Modify | Hỗ trợ DI `renderer` trong `create_app`, mặc định dùng `select_preview_renderer()` |
| `tests/ingest/test_renderer.py` | Modify | Thêm 6 test case mới kiểm tra `MINIMAL_PNG_BYTES` hợp lệ bằng PIL, mock preview validity, fallback handling, `select_preview_renderer` selection, và DI orchestrator |

### Phân tích Logic Cốt lõi:
- **Valid PNG Standards**: Chuỗi byte PNG tuân thủ RFC 2083: Signature (`\x89PNG\r\n\x1a\n`), IHDR chunk với CRC chính xác (`\x1f\x15\xc4\x89`), IDAT chunk chứa zlib compressed stream của 1 scanline RGBA, và IEND chunk với CRC (`\xaeB\x60\x82`).
- **Strategy & Factory Pattern**: Sử dụng `select_preview_renderer()` như một Factory Method đóng gói logic phát hiện môi trường (`shutil.which("soffice")`, `pdftoppm`, `fitz`), tuân thủ Open/Closed Principle.
- **Dependency Injection**: Cho phép `JobOrchestrator` và `create_app` nhận `renderer` từ bên ngoài, giúp decoupling giữa business orchestration và thumbnail rendering adapter.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] `MINIMAL_PNG_BYTES` được đọc và xác thực thành công bởi `PIL.Image.open()` mà không phát sinh bất kỳ ngoại lệ nào (`cannot identify image file` được loại bỏ hoàn toàn).
- [x] Tất cả ảnh thumbnail do `MockPreviewRenderer` sinh ra đều là file ảnh PNG hợp lệ, kích thước > 0 bytes và mở được bằng PIL / công cụ xử lý ảnh.
- [x] `select_preview_renderer()` trả về `LibreOfficePreviewRenderer` khi `soffice` và công cụ chuyển PDF có sẵn, và tự động fallback về `MockPreviewRenderer` khi thiếu dependency.
- [x] `JobOrchestrator` cho phép inject preview renderer qua constructor, hỗ trợ linh hoạt cho cả môi trường kiểm thử isolated và môi trường production runtime.
- [x] Toàn bộ test suite vượt qua 100% (140/140 passed).
- [x] Thêm các test case mới xác thực tính hợp lệ của PNG fallback và selection review.

---

## 5. Kế hoạch Kiểm tra & Kết quả Thực tế (Verification Plan & Results)

### Automated Tests Execution
```bash
# 1. Kiểm tra tính hợp lệ của PNG fallback với PIL và renderer tests
PYTHONPATH=src pytest -v tests/ingest/test_renderer.py
# -> Result: 10/10 PASSED in 0.69s

# 2. Kiểm tra toàn bộ regression suite
PYTHONPATH=src pytest -q
# -> Result: 140 passed, 1 warning in 166.12s

# 3. Kiểm tra bytecode compilation
python3 -m compileall src tests
# -> Result: 0 errors, 100% clean compilation

# 4. Kiểm tra smoke UI check
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py
# -> Result: All 7 smoke checks passed OK
```

### Manual QA
1. Dùng PIL nạp trực tiếp `MINIMAL_PNG_BYTES`: `im.size == (1, 1)`, `im.format == "PNG"`, `im.mode == "RGBA"`, `im.verify()` thành công.
2. Kiểm tra manifest và các file ảnh `slide_*.png` được tạo ra trong `previews/` của job workspace: 100% file ảnh hợp lệ, decode được bởi PIL.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/sub-specs/SDD-SUB-20260918-01-pptx-ingest-agy_b.md]]`
- **Related Sessions**: `[[.ai/specs/ADS-001/requirements.md]]`
- **Code Graph**: `autoslide.ingest.renderer -> autoslide.orchestrator.pipeline -> autoslide.ui.api`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
