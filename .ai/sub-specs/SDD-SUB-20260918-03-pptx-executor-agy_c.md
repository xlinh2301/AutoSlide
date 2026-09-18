---
id: SDD-SUB-20260918-03
title: "Phase 4 PPTX Executor: Deterministic Mutations, Checkpointing, Structural Diff & Safe Rollback"
author: agy_c
status: IMPLEMENTED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Execute validated TaskPlans against PPTX packages deterministically with run-level text preservation, geometry updates, structural diff generation, atomic checkpoints, and rollback safety."
decisions:
  - "Directly manipulate PresentationML OOXML structures using zipfile and xml.etree to preserve unmutated themes, layouts, shapes, and media relationships without opaque third-party side-effects."
  - "Resolve targeted shapes deterministically by matching composite fingerprints extracted dynamically from the working copy before each mutation step."
  - "Generate machine-readable structural diffs (StructuralDiff) comparing before and after DeckInventories to explicitly audit intended changes versus unintended collateral modifications."
  - "Execute mutations inside an atomic transaction pattern that records per-operation checkpoints in the job workspace and safely rolls back to the prior valid checkpoint on any validation failure."
affected_symbols:
  - "autoslide.executor.engine.PPTXExecutor"
  - "autoslide.executor.diff.StructuralDiffEngine"
  - "autoslide.executor.models.StructuralDiff"
  - "autoslide.executor.models.ExecutionResult"
  - "autoslide.executor.errors.ExecutorError"
  - "autoslide.executor.errors.TargetNotFoundError"
  - "autoslide.executor.errors.MutationRollbackError"
risk_level: LOW
---

# 📝 Sub Spec: Phase 4 PPTX Executor — Deterministic Mutations, Checkpointing, Structural Diff & Safe Rollback

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thực thi các thao tác trong `TaskPlan` đã qua kiểm duyệt (`PolicyGate`) lên file PPTX làm việc một cách tất định (deterministic), bảo toàn định dạng font/màu sắc/layout của các đối tượng không sửa đổi, tạo checkpoint theo từng bước, kiểm định tính toàn vẹn của file xuất ra, sinh diff cấu trúc trước/sau và hỗ trợ rollback an toàn khi phát sinh lỗi.
> **Quyết định then chốt**: Thao tác trực tiếp trên cây OOXML PresentationML (`xml.etree` + `zipfile`); đối soát fingerprint động; sinh báo cáo diff cấu trúc dạng máy đọc (`StructuralDiff`); lưu trữ checkpoint liên kết vào `JobWorkspace`.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/IMPLEMENTED

---

## 1. Mục tiêu (Objective)
Cung cấp lát cắt thực thi (Phase 4) cho AutoSlide:
1. **Deterministic PPTX Executor (`PPTXExecutor`)**:
   - Nhận vào `TaskPlan` đã được `PolicyGate` phê duyệt, file PPTX gốc và `JobWorkspace`.
   - Sao chép file gốc vào `working/presentation.pptx` để bảo toàn tuyệt đối file input.
   - Áp dụng tuần tự từng thao tác trong `operations`:
     - `replace_text`: Thay thế text trong `a:r/a:t` hoặc `a:p`, bảo toàn font (`a:rPr/a:latin`), size (`sz`), màu sắc (`a:srgbClr`), style (`b`, `i`).
     - `format_text`: Cập nhật thuộc tính định dạng text run (`sz`, `b`, `i`, `color`, `typeface`).
     - `move_resize_shape`: Cập nhật thẻ tọa độ `a:xfrm` (`a:off` `x, y`, `a:ext` `cx, cy`).
     - `duplicate_slide`: Nhân bản phần slide XML và cập nhật relationships (`p:sldIdLst`, `presentation.xml.rels`, `[Content_Types].xml`).
     - `delete_slide`: Xóa slide XML và gỡ bỏ reference tương ứng.
2. **Atomic Checkpointing & Verification**:
   - Sau mỗi operation (hoặc batch hoàn tất), ghi checkpoint vào `checkpoints/` thông qua `workspace.write_checkpoint(stage, working_pptx_path)`.
   - Kiểm định tính toàn vẹn gói OPC bằng `validate_pptx_package` sau mỗi lần đóng gói zip.
3. **Structural Before/After Diff Engine (`StructuralDiffEngine`)**:
   - Đối chiếu `DeckInventory` trước và sau khi thực thi.
   - Liệt kê rõ ràng:
     - `intended_changes`: Các thuộc tính thay đổi khớp với `TaskPlan`.
     - `unintended_changes`: Các thay đổi ngoài phạm vi kế hoạch (phát hiện vi phạm bảo toàn).
     - `added_slides` / `removed_slides` / `modified_shapes`.
   - Ghi kết quả vào `artifacts/structural_diff.json`.
4. **Safe Rollback**:
   - Nếu bất kỳ operation nào gặp lỗi (lỗi XML, không tìm thấy target, hoặc corrupt package), executor tự động khôi phục working copy về checkpoint hợp lệ gần nhất và ném `MutationRollbackError`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [x] **Giả định**: `TaskPlan` đã được `PolicyGate` kiểm định (Phase 3) và file gốc đã qua `validate_pptx_package` (Phase 2).
- [x] **Giả định**: Module executor tập trung vào mutation cấu trúc và package integrity, không phụ thuộc vào GUI hay headless visual renderer (Phase 5).
- [ ] **Rủi ro**: Text run bị phân mảnh (split across multiple `a:r` elements in OOXML) $\rightarrow$ *Giải pháp*: Xây dựng thuật toán gộp run / phân phối chuỗi thay thế an toàn vào run đầu tiên và dọn dẹp các run rỗng tiếp theo để bảo toàn thuộc tính định dạng run chính.
- [ ] **Rủi ro**: Slide duplication có thể làm trùng lặp relationship ID (`rId`) $\rightarrow$ *Giải pháp*: Bộ cấp phát ID tuần tự mới (`rId{max+1}`) và đăng ký đầy đủ trong `[Content_Types].xml` và `ppt/_rels/presentation.xml.rels`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/executor/__init__.py` | Create | Export các interface chính của module executor |
| `src/autoslide/executor/models.py` | Create | Khai báo Pydantic models: `PropertyChange`, `ShapeDiff`, `SlideDiff`, `StructuralDiff`, `ExecutionResult` |
| `src/autoslide/executor/errors.py` | Create | Định nghĩa các exception: `ExecutorError`, `TargetNotFoundError`, `MutationRollbackError`, `UnintendedMutationError` |
| `src/autoslide/executor/mutator.py` | Create | Các hàm mutation trực tiếp trên OOXML ElementTree: `apply_replace_text`, `apply_format_text`, `apply_move_resize`, `apply_duplicate_slide`, `apply_delete_slide` |
| `src/autoslide/executor/diff.py` | Create | `StructuralDiffEngine` so sánh `DeckInventory` trước và sau, phân loại intended vs unintended modifications |
| `src/autoslide/executor/engine.py` | Create | `PPTXExecutor` điều phối quy trình: copy working file, duyệt operations, ghi checkpoint, đối soát diff, và rollback khi lỗi |
| `tests/executor/__init__.py` | Create | Package init cho executor tests |
| `tests/executor/test_mutator.py` | Create | Kiểm thử mutation chi tiết từng loại operation (text replace, format, move/resize, duplicate, delete) |
| `tests/executor/test_diff.py` | Create | Kiểm thử `StructuralDiffEngine` phát hiện đúng intended và unintended changes |
| `tests/executor/test_engine.py` | Create | Kiểm thử toàn diện `PPTXExecutor` với checkpointing, immutability của original input, package validation và rollback khi gặp lỗi |
| `tests/fixtures/executor_samples.py` | Create | Fixtures sinh các presentation mẫu, plan thực thi và checkpoint test cases |

### Phân tích Logic Cốt lõi:
- **Run-Level Text Mutation Strategy**:
  ```python
  # Phân bổ text thay thế vào text body:
  # 1. Tìm shape có fingerprint khớp.
  # 2. Xác định text run đích hoặc paragraph.
  # 3. Ghi text mới vào a:t đầu tiên, giữ nguyên thuộc tính a:rPr (font size, bold, italic, color).
  # 4. Xóa text trong các run thừa trong phạm vi run_range.
  ```
- **Structural Diff Auditing**:
  ```python
  # Đối chiếu snapshot DeckInventory trước và sau:
  # - Khẳng định các shape nằm ngoài target_scope có SHA-256 fingerprint hoàn toàn bất biến.
  # - Ghi nhận mọi sự sai khác ngoài target_scope vào unintended_changes.
  ```

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [x] `PPTXExecutor.execute(...)` áp dụng thành công các operations: `replace_text`, `format_text`, `move_resize_shape`, `duplicate_slide`, `delete_slide`.
- [x] `replace_text` giữ nguyên 100% thuộc tính định dạng font, cỡ chữ, in đậm/nghiêng và màu sắc của run gốc.
- [x] File template gốc trong `input/` không bị thay đổi (giữ nguyên SHA-256 ban đầu); toàn bộ mutation diễn ra trên bản sao `working/`.
- [x] Checkpoint hợp lệ được sinh ra sau mỗi giai đoạn thông qua `JobWorkspace.write_checkpoint(...)`.
- [x] File PPTX kết quả vượt qua kiểm định `validate_pptx_package` và mở được dưới dạng zip hợp lệ.
- [x] `StructuralDiffEngine` sinh `artifacts/structural_diff.json` phân định chính xác `intended_changes` và `unintended_changes`.
- [x] Khi xảy ra lỗi giữa chừng, executor tự động rollback về checkpoint hợp lệ trước đó và ném `MutationRollbackError`.
- [x] Toàn bộ test suite (Phase 1 + Phase 2 + Phase 3 + Phase 4) đạt 100% passing rate trên pytest, `compileall` sạch và `sanitizer-engine pre-commit` pass.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)
### Automated
```bash
# 1. Chạy các unit test của module executor
pytest -v tests/executor

# 2. Chạy toàn bộ regression suite (Foundation + Ingest + Planner + Executor)
pytest -q

# 3. Kiểm tra cú pháp và bytecode compilation
python3 -m compileall src tests

# 4. Kiểm tra bảo mật và rò rỉ secrets
sanitizer-engine pre-commit
```

### Manual QA
1. Khởi tạo một fixture deck mẫu có 2 slide với tiêu đề, text box và hình ảnh.
2. Lập một `TaskPlan` cập nhật tiêu đề slide 1 và điều chỉnh kích thước text box.
3. Chạy `PPTXExecutor.execute(plan, workspace)` và kiểm tra file `working/presentation.pptx`, `checkpoints/`, cùng `artifacts/structural_diff.json`.
4. So sánh `inventory` trước và sau để xác minh slide 2 hoàn toàn không bị ảnh hưởng.
5. Thử nghiệm một plan cố tình truyền target sai để kiểm chứng cơ chế rollback về checkpoint trước đó.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Module mới độc lập dưới `src/autoslide/executor/`, consumes `autoslide.planner.models.TaskPlan` và `autoslide.ingest.parser.PPTXIngestor`.
- **Related Sessions**: Phase 1 Foundation Runtime (`51a0535` $\rightarrow$ `f127001`), Phase 2 PPTX Ingest (`d16c062`), Phase 3 Edit Planner (`9615c2f`).
- **Code Graph**: `autoslide.planner` $\rightarrow$ `autoslide.executor` $\rightarrow$ consumed by Phase 5 `autoslide.quality`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
