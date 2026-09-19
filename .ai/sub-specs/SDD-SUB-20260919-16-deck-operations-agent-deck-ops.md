---
id: SDD-SUB-20260919-16
title: Deck Structure and Arbitrary Supported Content Operations
author: agent-deck-ops
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement conversational deck structure operations (AddSlideOp, DeleteSlideOp, DuplicateSlideOp, ReorderSlideOp, AddContentOp) with OOXML mutators, index normalization, bounds validation, and postcondition verification."
decisions:
  - "Extend OperationType in vocabulary.py with ADD_SLIDE, REORDER_SLIDE, and ADD_CONTENT."
  - "Define AddSlideOp, DeleteSlideOp, DuplicateSlideOp, ReorderSlideOp, AddContentOp, and ContentBlock data models in planner/models.py and content/models.py."
  - "Implement low-level PresentationML OOXML mutators in mutator.py for adding blank/template slides with content blocks, reordering slide sequences in sldIdLst, and appending text/shape content with bounded coordinates."
  - "Integrate conversational deck operations into PPTXExecutor.execute in engine.py with 1-indexed normalization, shape fingerprint tracking, rollback safeguards, and structural diff computation."
  - "Explicitly reject unsupported content types and out-of-bounds operations through structured errors and review state preservation."
affected_symbols:
  - "autoslide.planner.vocabulary.OperationType"
  - "autoslide.planner.models.AddSlideOp"
  - "autoslide.planner.models.DeleteSlideOp"
  - "autoslide.planner.models.DuplicateSlideOp"
  - "autoslide.planner.models.ReorderSlideOp"
  - "autoslide.planner.models.AddContentOp"
  - "autoslide.content.models.ContentBlock"
  - "autoslide.executor.mutator.apply_add_slide"
  - "autoslide.executor.mutator.apply_reorder_slide"
  - "autoslide.executor.mutator.apply_add_content"
  - "autoslide.executor.engine.PPTXExecutor"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Deck Structure and Arbitrary Supported Content Operations

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa Task 5 trong kế hoạch Always-on Agent Chat (`ADS-002`): hỗ trợ các thao tác thay đổi cấu trúc bài thuyết trình (`AddSlideOp`, `DeleteSlideOp`, `DuplicateSlideOp`, `ReorderSlideOp`) và thêm khối nội dung hỗ trợ (`AddContentOp`) một cách tất định (deterministic), bảo đảm tính toàn vẹn gói OOXML, chuẩn hóa chỉ mục slide, kiểm tra bounding box và đối soát xuất xứ/nguồn gốc dữ liệu.
> **Quyết định then chốt**: Mở rộng từ vựng `OperationType` và mô hình `TaskPlan`/`EditOperation`; phát triển mutator OOXML trực tiếp trên PresentationML cho `add_slide`, `reorder_slide`, `add_content`; chuẩn hóa chỉ mục slide 1-indexed; từ chối dứt khoát các loại content block chưa hỗ trợ; duy trì giao diện thực thi duy nhất qua `PPTXExecutor.execute`.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 5 trong kế hoạch Always-on Agent Chat (`ADS-002`):
1. **Từ vựng & Mô hình Thao tác Cấu trúc Slide (`OperationType` & `models.py`)**:
   - Mở rộng enum `OperationType`: `ADD_SLIDE`, `REORDER_SLIDE`, `ADD_CONTENT` bên cạnh `DELETE_SLIDE` và `DUPLICATE_SLIDE` đã có.
   - Định nghĩa mô hình `ContentBlock` hỗ trợ các loại nội dung (`text`, `paragraph`, `bullet_list`) gắn kèm `ContentOrigin` (`USER`, `WEB`, `AI_GENERATED`).
   - Định nghĩa các typed operation models:
     - `AddSlideOp(source_slide_index: int | None, insert_at_index: int, layout_ref: str | None, content: list[ContentBlock])`
     - `DeleteSlideOp(slide_index: int)`
     - `DuplicateSlideOp(source_slide_index: int, insert_at_index: int | None)`
     - `ReorderSlideOp(slide_index: int, new_index: int)`
     - `AddContentOp(target_slide_index: int, content: ContentBlock, bounds: BoundingBox | None)`
2. **Trình Biến đổi OOXML PresentationML Cấp thấp (`mutator.py`)**:
   - `apply_add_slide`: Thêm slide mới vào gói PPTX (dựa trên layout/slide mẫu hoặc cấu trúc cơ bản), cấp phát relationship ID mới (`rId`), cập nhật `presentation.xml.rels`, `p:sldIdLst` trong `presentation.xml` và `[Content_Types].xml`, đồng thời chèn các khối nội dung `content` ban đầu.
   - `apply_reorder_slide`: Thay đổi thứ tự các thẻ `<p:sldId>` trong `<p:sldIdLst>` từ vị trí `slide_index` sang `new_index` (chuẩn hóa 1-indexed bounds).
   - `apply_add_content`: Thêm shape mới (`p:sp`) chứa text/paragraph vào slide XML tại `target_slide_index` với tọa độ EMU hợp lệ (`BoundingBox`) hoặc vị trí mặc định an toàn.
   - `apply_delete_slide` & `apply_duplicate_slide`: Hoàn thiện và đối soát tính toàn vẹn relationship và content types.
3. **Bộ Điều phối Thực thi Tất định (`PPTXExecutor` trong `engine.py`)**:
   - `PPTXExecutor.execute(task_plan, input_path, workspace) -> ExecutionResult` là giao diện duy nhất thực thi mutation.
   - Chuẩn hóa và kiểm tra hợp lệ các chỉ mục slide trước và sau từng bước thao tác.
   - Hỗ trợ kiểm tra bounds, preservation rules và xác nhận postconditions (số lượng slide, thứ tự slide, provenance references).
   - Rollback an toàn về checkpoint hợp lệ khi gặp lỗi validation hoặc thao tác không hợp lệ.
4. **Xử lý Nội dung Chưa hỗ trợ (Unsupported Content Handling)**:
   - Từ chối các khối nội dung không nằm trong allowlist (ví dụ: raw binary, macro, flash) và báo lỗi rõ ràng để chuyển sang trạng thái review thay vì đoán mò làm hỏng file.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Gói OOXML PPTX tuân thủ chuẩn OpenXML PresentationML (`[Content_Types].xml`, `ppt/presentation.xml`, `ppt/_rels/presentation.xml.rels`, `ppt/slides/slideN.xml`).
- [x] **Giả định**: `PPTXExecutor.execute` tạo bản sao cô lập tại `working/presentation.pptx` và ghi checkpoint nguyên tử sau mỗi operation.
- [ ] **Rủi ro**: Việc reorder hoặc xóa/thêm slide có thể làm lệch chỉ mục slide của các operation tiếp theo trong cùng một `TaskPlan`.
  - *Biện pháp*: Executor theo dõi và cập nhật inventory hiện thời (`current_inventory`) sau mỗi bước thao tác; chuẩn hóa chỉ mục slide 1-indexed trong khoảng `1..N`.
- [ ] **Rủi ro**: Thêm slide mới từ đầu (scratch) thiếu slide layout/master relationships có thể gây lỗi mở file trên PowerPoint.
  - *Biện pháp*: Khi `source_slide_index` hoặc `layout_ref` có sẵn, kế thừa layout relationships từ slide nguồn; nếu tạo slide trắng, liên kết đến slideLayout đầu tiên trong presentation rels.
- [ ] **Rủi ro**: Tọa độ bounding box của nội dung mới vượt quá kích thước slide (`cx`, `cy`).
  - *Biện pháp*: Validate bounding box so với `SlideDimensions` (mặc định 16:9 widescreen 12192000 x 6858000 EMU), tự động kẹp (clamp) hoặc áp dụng layout defaults.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/planner/vocabulary.py` | Modify | Thêm `ADD_SLIDE`, `REORDER_SLIDE`, `ADD_CONTENT` vào `OperationType` enum và `ALLOWLISTED_OPERATIONS`. |
| `src/autoslide/content/models.py` | Modify | Bổ sung model `ContentBlock` với `block_type`, `text`, `origin: ContentOrigin | None`, `metadata`. |
| `src/autoslide/planner/models.py` | Modify | Thêm `AddSlideOp`, `ReorderSlideOp`, `AddContentOp` vào `EditOperation` Union discriminator; import `ContentBlock` và `BoundingBox`. |
| `src/autoslide/executor/mutator.py` | Modify | Cung cấp hàm `apply_add_slide`, `apply_reorder_slide`, `apply_add_content` thao tác trên PresentationML XML và relationships. |
| `src/autoslide/executor/engine.py` | Modify | Mở rộng luồng dispatch operation trong `PPTXExecutor.execute` để hỗ trợ các ops mới, kiểm tra slide bounds và postconditions. |
| `tests/executor/test_conversation_operations.py` | Create | Tạo bộ kiểm thử TDD toàn diện cho add, delete, duplicate, reorder slide, add content, unsupported content, and rollback. |

### Phân tích Logic Cốt lõi:
- **Nguyên tắc Bảo toàn OOXML (Lossless Manipulation)**: Thao tác trực tiếp trên cây XML qua `xml.etree.ElementTree` với đầy đủ namespace mapping (`p`, `a`, `r`, `ct`, `pr`), không qua trung gian các thư viện bên ngoài có thể gây mất format ẩn.
- **Tính Tất định & Khôi phục Checkpoint**: Mỗi bước thao tác đều tạo bản ghi checkpoint nguyên tử (`OP_ADD_SLIDE_1`, `OP_REORDER_SLIDE_2`,...). Nếu bất kỳ thao tác nào gặp lỗi hoặc package không vượt qua kiểm định `validate_pptx_package`, executor rollback về checkpoint an toàn gần nhất.
- **Ranh giới Bounded Context**: Chỉ can thiệp vào các module `vocabulary.py`, `models.py`, `mutator.py`, `engine.py` và tạo file test chuyên biệt `test_conversation_operations.py`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] `AddSlideOp`: Thêm slide mới thành công tại chỉ mục mong muốn (đầu, giữa, cuối deck), hỗ trợ chèn content blocks ban đầu, cập nhật `p:sldIdLst`, `rels`, và `[Content_Types].xml`.
- [ ] `DeleteSlideOp`: Xóa slide hợp lệ, giảm slide count, xóa sạch file slide và rels mồ côi trong gói zip.
- [ ] `DuplicateSlideOp`: Nhân bản chính xác slide nguồn tới vị trí chỉ định với relationship ID độc lập.
- [ ] `ReorderSlideOp`: Di chuyển vị trí slide từ `slide_index` đến `new_index` trong presentation XML mà không làm thay đổi nội dung các slide.
- [ ] `AddContentOp`: Thêm shape văn bản với tọa độ xác định (`bounds`) hoặc mặc định vào slide mục tiêu.
- [ ] `Unsupported Content Handling`: Ném ngoại lệ hoặc trả về lỗi cấu trúc có kiểm soát khi gặp khối nội dung không hỗ trợ, không làm hỏng deck.
- [ ] `Immutability & Checkpoints`: File input gốc bất biến 100%, các checkpoint hợp lệ được lưu trong `workspace.checkpoints`.
- [ ] `Structural Diff`: `StructuralDiffEngine` phản ánh chính xác các slide thêm/xóa/sửa đổi.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Chạy bộ kiểm thử chuyên sâu cho conversational deck operations
pytest tests/executor/test_conversation_operations.py -v

# 2. Chạy toàn bộ regression suite của executor, planner và quality
pytest tests/executor tests/planner tests/quality -q

# 3. Chạy kiểm tra lint & syntax
python3 -m py_compile src/autoslide/planner/vocabulary.py src/autoslide/planner/models.py src/autoslide/executor/mutator.py src/autoslide/executor/engine.py
```

### Manual QA
1. Khởi tạo `TaskPlan` chứa chuỗi thao tác liên hoàn: `AddSlideOp` $\rightarrow$ `AddContentOp` $\rightarrow$ `DuplicateSlideOp` $\rightarrow$ `ReorderSlideOp` $\rightarrow$ `DeleteSlideOp`.
2. Chạy `PPTXExecutor.execute` và kiểm tra file đầu ra: số lượng slide, thứ tự slide và nội dung hiển thị chuẩn xác.
3. Kiểm tra artifact `structural_diff.json` và xác nhận tính toàn vẹn qua `validate_pptx_package`.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/walkthroughs/impact-report-ADS-002-deck-ops]]`
- **Related Sessions**: `[[.ai/walkthroughs/session-20260919-deck-operations]]`
- **Code Graph**: `autoslide.executor.engine.PPTXExecutor -> autoslide.executor.mutator`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
