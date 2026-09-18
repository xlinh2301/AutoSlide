---
id: SDD-SUB-20260918-01
title: Phase 2 PPTX Ingest & Inventory with Stable Fingerprints and Preview Manifest
author: agy_b
status: IMPLEMENTED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Validate PPTX OPC packages, construct deterministic slide/shape/run inventory with composite fingerprints, and generate preview thumbnails without modifying original inputs."
decisions:
  - "Parse PPTX OPC packages using standard Python zipfile and xml.etree to avoid heavy unmanaged C-dependencies while ensuring full OOXML structure visibility."
  - "Compute deterministic composite target fingerprints (slide index + shape type + shape name + normalized text + geometry) to uniquely identify slide objects across edits."
  - "Provide a pluggable preview renderer interface with LibreOffice/PyMuPDF adapter and headless mock adapter for hermetic, fast testing."
  - "Preserve original template immutability by saving inventories (inventory.json) and thumbnails (previews/) exclusively within the job workspace."
affected_symbols:
  - "autoslide.ingest.models.DeckInventory"
  - "autoslide.ingest.models.ShapeInventoryItem"
  - "autoslide.ingest.models.PreviewManifest"
  - "autoslide.ingest.validator.validate_pptx_package"
  - "autoslide.ingest.fingerprint.compute_shape_fingerprint"
  - "autoslide.ingest.parser.PPTXIngestor"
  - "autoslide.ingest.renderer.BasePreviewRenderer"
  - "autoslide.ingest.renderer.LibreOfficePreviewRenderer"
risk_level: LOW
---

# 📝 Sub Spec: Phase 2 PPTX Ingest & Inventory with Stable Fingerprints and Preview Manifest

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Xác thực gói OPC PPTX, từ chối file hỏng/không hỗ trợ, xây dựng inventory slide/shape/text-run có fingerprint định danh bền vững và tạo preview manifest qua renderer an toàn mà không biến đổi file gốc.
> **Quyết định then chốt**: Sử dụng parser OOXML thuần Python; tính fingerprint tổ hợp ổn định; kiến trúc renderer đa tầng (LibreOffice CLI + PyMuPDF/pdftoppm + Mock); lưu trữ toàn bộ output trong job workspace.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/IMPLEMENTED

---

## 1. Mục tiêu (Objective)
Cung cấp lát cắt ingestion (Phase 2) cho AutoSlide:
1. **Kiểm định gói OPC**: Kiểm tra cấu trúc Open Packaging Conventions (OPC) của file `.pptx` (chứa `[Content_Types].xml`, `_rels/.rels`, `ppt/presentation.xml`), bắt và từ chối các file lỗi nén, hỏng XML, hoặc file mã hóa/không hỗ trợ với lỗi chi tiết.
2. **Trích xuất Inventory có cấu trúc**: Bóc tách danh sách slide, shape (`sp`, `pic`, `tbl`, `graphicFrame`, `grpSp`), placeholder, text runs (`text`, font, size, bold, color), bounds hình học (`x, y, cx, cy`), z-order, và bảng/biểu đồ.
3. **Fingerprint định danh bền vững**: Tạo mã băm SHA-256 composite cho từng đối tượng trên slide để theo dõi đối tượng xuyên suốt quá trình lập kế hoạch và biên tập ở các Phase tiếp theo.
4. **Tạo Preview Manifest**: Sinh ảnh thumbnail slide (PNG) bằng renderer adapter an toàn (hỗ trợ LibreOffice headless + Poppler/PyMuPDF, có mock adapter cho unit tests) và xuất `previews/manifest.json`.
5. **Bảo toàn tính bất biến**: Giữ nguyên vẹn 100% file gốc tải lên; toàn bộ artifact sinh ra nằm trong thư mục workspace của job (`<data_root>/jobs/<job_id>/`).

---

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [x] **Giả định**: File PPTX hợp lệ tuân thủ tiêu chuẩn ECMA-376 / ISO/IEC 29500 (OOXML PresentationML).
- [x] **Giả định**: Host Linux đã có `soffice` (LibreOffice) và `pdftoppm` / `fitz` cho tác vụ render thực tế, nhưng test suite phải chạy độc lập được bằng `MockPreviewRenderer` khi cần.
- [ ] **Rủi ro**: Slide phức tạp có shape lồng nhau (`p:grpSp`) hoặc SmartArt/Chart nhúng có thể có cấu trúc XML sâu $\rightarrow$ *Giải pháp*: Xử lý duyệt đệ quy (recursive traversal) an toàn với depth limit (tối đa 10 levels) và phân loại fallback `UNKNOWN` / `GRAPHIC_FRAME` thay vì ném unhandled exception.
- [ ] **Rủi ro**: LibreOffice headless có thể bị timeout hoặc sinh process zombie $\rightarrow$ *Giải pháp*: Kế thừa cơ chế subprocess timeout bounded (30s) và cô lập `user-installation` profile tạm như đã quy định trong `ADS-001`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/__init__.py` | Create | Export các interface chính của ingest module |
| `src/autoslide/ingest/models.py` | Create | Khai báo Pydantic models: `DeckInventory`, `SlideInventoryItem`, `ShapeInventoryItem`, `BoundingBox`, `TextRunInfo`, `PreviewManifest`, `SlidePreview` |
| `src/autoslide/ingest/errors.py` | Create | Định nghĩa các exception: `InvalidPackageError`, `CorruptPackageError`, `UnsupportedPackageError`, `RenderError` |
| `src/autoslide/ingest/validator.py` | Create | Kiểm tra zip integrity, required OPC content types và presentation rels |
| `src/autoslide/ingest/fingerprint.py` | Create | Thuật toán tính composite object fingerprint định danh bền vững |
| `src/autoslide/ingest/parser.py` | Create | Bộ phân tích `PPTXIngestor` đọc shape tree, text runs, bounds, placeholders từ OOXML |
| `src/autoslide/ingest/renderer.py` | Create | `BasePreviewRenderer`, `LibreOfficePreviewRenderer` (với timeout và isolated user profile), và `MockPreviewRenderer` |
| `tests/ingest/test_validator.py` | Create | Kiểm thử validation với valid, corrupt (bad zip, malformed XML), và unsupported inputs |
| `tests/ingest/test_inventory.py` | Create | Kiểm thử inventory trích xuất shapes, text runs, placeholders, bounds, và tính ổn định của fingerprints |
| `tests/ingest/test_renderer.py` | Create | Kiểm thử preview manifest, render adapter contract, và timeout/fallback handling |
| `tests/fixtures/pptx_samples.py` | Create | Helper sinh fixtures PPTX động (valid multi-slide deck, table/shapes, corrupt zip, unsupported encrypted) |

### Phân tích Logic Cốt lõi:
- **Clean Architecture & Hexagonal Ports**:
  - `PPTXIngestor` đóng vai trò Use Case / Domain Service, không phụ thuộc vào framework HTTP hay API layer.
  - `BasePreviewRenderer` là Output Port (SPI), `LibreOfficePreviewRenderer` là Secondary Adapter.
- **Stable Fingerprinting Strategy**:
  - `fingerprint = sha256(f"{slide_index}:{shape_type}:{shape_name}:{normalized_text}:{bounds.x}:{bounds.y}:{bounds.cx}:{bounds.cy}")`
  - Đảm bảo ngay cả khi XML internal IDs (`p:cNvPr id="..."`) thay đổi khi save, đối tượng vẫn được định danh chính xác.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [x] Từ chối 100% các file input không phải zip, zip rỗng, zip thiếu `[Content_Types].xml`, hoặc XML không hợp lệ bằng `CorruptPackageError` hoặc `InvalidPackageError`.
- [x] Trích xuất đầy đủ slide count, slide dimensions, shape types (`sp`, `pic`, `tbl`, `graphicFrame`, `grpSp`), text runs (text, font size, bold/italic flag) và bounding boxes (`x, y, cx, cy`).
- [x] Composite fingerprint của một shape giữ nguyên giá trị khi parse lặp lại cùng một file (deterministic snapshot).
- [x] Renderer adapter sinh đúng số lượng preview tương ứng với số slide, ghi ảnh PNG vào thư mục `previews/` của job workspace và sinh `manifest.json`.
- [x] File template gốc trong `workspace.root / "input"` không bị ghi đè, sửa đổi hay truncate.
- [x] Toàn bộ test suite (cũ + mới) đạt 100% passing rate trên pytest, `compileall` sạch và `sanitizer-engine pre-commit` không phát hiện rò rỉ secret.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)
### Automated
```bash
# 1. Chạy các unit test của module ingest
pytest -v tests/ingest

# 2. Chạy toàn bộ regression suite (Foundation + Ingest)
pytest -q

# 3. Kiểm tra cú pháp và bytecode compilation
python3 -m compileall src tests

# 4. Kiểm tra bảo mật và rò rỉ secrets
sanitizer-engine pre-commit
```

### Manual QA
1. Khởi tạo một fixture deck mẫu có 2 slide với tiêu đề, text box và hình ảnh.
2. Chạy `PPTXIngestor.ingest(pptx_path, workspace)` và kiểm tra file `artifacts/inventory.json` cùng `previews/manifest.json` được tạo trong workspace.
3. So sánh sha256 của file input trước và sau ingestion để chứng minh tính bất biến tuyệt đối.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Module mới độc lập dưới `src/autoslide/ingest/`, không làm ảnh hưởng các route API Foundation hiện tại của Phase 1.
- **Related Sessions**: Phase 1 Foundation Runtime (commits `51a0535` $\rightarrow$ `f127001`).
- **Code Graph**: `autoslide.ingest` $\rightarrow$ consumes `autoslide.jobs.workspace.JobWorkspace` $\rightarrow$ consumed by Phase 3 `autoslide.planner`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
