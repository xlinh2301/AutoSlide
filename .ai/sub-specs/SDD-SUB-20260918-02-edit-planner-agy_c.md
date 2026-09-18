---
id: SDD-SUB-20260918-02
title: Phase 3 Edit Planner: TaskPlan Schema, Operation Vocabulary, Prompt Builder & Policy Gate
author: agy_c
status: IMPLEMENTED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Define versioned TaskPlan JSON schema, allowlisted edit operation vocabulary, prompt payload builder, and ambiguity/low-confidence policy gate with golden and rejection-matrix tests."
decisions:
  - "Model edit operations as strongly-typed discriminated unions in Pydantic v2 with explicit preservation rules, confidence metrics, and postcondition assertions."
  - "Enforce an allowlisted operation vocabulary (replace_text, format_text, replace_image, move_resize_shape, duplicate_slide, delete_slide) and reject arbitrary code or freeform scripts."
  - "Construct self-contained, token-optimized prompt payloads combining user instruction, compact slide inventory with fingerprints, and strict schema definitions without provider API keys."
  - "Implement a deterministic PolicyGate validating confidence thresholds (>=0.80), target scope boundaries, known operation types, and explicit clarification flags before handoff to execution."
affected_symbols:
  - "autoslide.planner.models.TaskPlan"
  - "autoslide.planner.models.EditOperation"
  - "autoslide.planner.models.TargetScope"
  - "autoslide.planner.models.PreservationRule"
  - "autoslide.planner.vocabulary.OperationType"
  - "autoslide.planner.builder.PromptPayloadBuilder"
  - "autoslide.planner.policy.PolicyGate"
  - "autoslide.planner.policy.PolicyEvaluationResult"
  - "autoslide.planner.errors.PolicyViolationError"
  - "autoslide.planner.errors.AmbiguousTargetError"
  - "autoslide.planner.errors.LowConfidenceError"
  - "autoslide.planner.errors.UnknownOperationError"
risk_level: LOW
---

# 📝 Sub Spec: Phase 3 Edit Planner — TaskPlan Schema, Operation Vocabulary, Prompt Builder & Policy Gate

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thiết lập hợp đồng định hình kế hoạch biên tập (`TaskPlan`), từ vựng thao tác cho phép (allowlisted edit operations), bộ sinh prompt payload nạp context gọn nhẹ, và cổng kiểm duyệt chính sách (`PolicyGate`) ngăn chặn câu lệnh mơ hồ, thao tác không an toàn hoặc độ tin cậy thấp.
> **Quyết định then chốt**: Pydantic v2 discriminated unions; từ vựng whitelist cố định; prompt builder phi secret không đòi hỏi API key; policy gate từ chối code tự do và kế hoạch thiếu mục tiêu rõ ràng.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/IMPLEMENTED

---

## 1. Mục tiêu (Objective)
Cung cấp lát cắt lập kế hoạch (Phase 3) cho AutoSlide:
1. **Versioned TaskPlan Schema**: Khai báo JSON Schema phiên bản `1.0` mô tả cấu trúc kế hoạch sửa đổi PPTX dạng typed (mục tiêu `target_scope`, danh sách `operations`, yêu cầu bảo toàn `preserve`, độ tin cậy `confidence`, và điều kiện hậu nghiệm `postconditions`).
2. **Allowlisted Edit Vocabulary**: Định nghĩa tập từ vựng thao tác cho phép gồm:
   - `replace_text`: Thay thế nội dung text run / paragraph.
   - `format_text`: Đổi thuộc tính font size, bold, italic, color, alignment.
   - `replace_image`: Thay thế ảnh nhúng theo media reference hoặc placeholder.
   - `move_resize_shape`: Điều chỉnh vị trí hoặc kích thước hình học bounding box.
   - `duplicate_slide`: Nhân bản slide mẫu.
   - `delete_slide`: Xóa slide thừa khi có yêu cầu rõ ràng.
3. **Prompt Payload Builder**: Ghép nối `user_instruction`, `DeckInventory` (kèm stable object fingerprints từ Phase 2), danh mục thao tác hợp lệ và quy định bảo toàn thành payload tinh gọn cho các Agent CLI runtime (Codex, Gemini, Claude) mà không thu thập/nhúng API key của nhà cung cấp.
4. **Ambiguity & Policy Gate**: Bộ thẩm định chính sách tự động từ chối (hard-reject / mark `requires_review`):
   - Kế hoạch chứa code tự do (Python/Bash/JS snippet) thay vì JSON schema.
   - Thao tác ngoài từ vựng cho phép (`UnknownOperationError`).
   - Mục tiêu mơ hồ không khớp fingerprint nào trên slide (`AmbiguousTargetError`).
   - Độ tin cậy dưới ngưỡng quy định (`confidence < 0.80`) (`LowConfidenceError`).
   - Phạm vi chỉnh sửa vi phạm quy tắc bảo toàn (ví dụ: yêu cầu sửa slide 2 nhưng plan sửa cả slide 1 và slide 3 không mong muốn).
5. **Golden & Rejection Test Matrices**: Bộ test fixture đối chiếu các case kế hoạch mẫu hợp lệ (golden plans) và ma trận các case vi phạm cần bị chặn.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [x] **Giả định**: Phase 2 `DeckInventory` đã cung cấp đầy đủ thông tin hình học, text-runs, z-order và stable composite fingerprints cho từng shape.
- [x] **Giả định**: Module planner hoàn toàn độc lập với executor (Phase 4), chỉ sinh và kiểm định contract dữ liệu `TaskPlan` mà không thực hiện mutation trực tiếp lên file nhị phân PPTX.
- [ ] **Rủi ro**: LLM runtime có thể sinh ra output chứa markdown fence (ví dụ: ````json ... ````) hoặc kèm text đệm $\rightarrow$ *Giải pháp*: Xây dựng hàm trích xuất/chuẩn hóa JSON payload an toàn trước khi nạp vào Pydantic validator.
- [ ] **Rủi ro**: Prompt payload quá dài nếu slide deck có hàng trăm shape $\rightarrow$ *Giải pháp*: `PromptPayloadBuilder` hỗ trợ chế độ compact inventory (rút gọn chỉ giữ lại cấu trúc text, shape type, slide index và fingerprint cần thiết).

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/planner/__init__.py` | Create | Export các interface chính của module planner |
| `src/autoslide/planner/vocabulary.py` | Create | Khai báo Enum `OperationType`, `PreservationRuleType`, và các hằng số từ vựng cho phép |
| `src/autoslide/planner/models.py` | Create | Khai báo Pydantic models: `TargetReference`, `TargetScope`, `BaseOperation`, `ReplaceTextOp`, `FormatTextOp`, `ReplaceImageOp`, `MoveResizeShapeOp`, `DuplicateSlideOp`, `DeleteSlideOp`, `TaskPlan` |
| `src/autoslide/planner/errors.py` | Create | Định nghĩa các exception: `PlannerError`, `PolicyViolationError`, `AmbiguousTargetError`, `LowConfidenceError`, `UnknownOperationError`, `MalformedPlanError` |
| `src/autoslide/planner/builder.py` | Create | `PromptPayloadBuilder` tổng hợp instruction, deck inventory, guidelines thành context payload |
| `src/autoslide/planner/policy.py` | Create | `PolicyGate` kiểm định độ tin cậy, tính toàn vẹn phạm vi mục tiêu, và phát hiện vi phạm bảo toàn |
| `tests/planner/__init__.py` | Create | Package init cho planner tests |
| `tests/planner/test_models.py` | Create | Kiểm thử serialize/deserialize `TaskPlan`, schema validation, và typed operations |
| `tests/planner/test_builder.py` | Create | Kiểm thử `PromptPayloadBuilder` sinh prompt gọn, chuẩn xác, không chứa secrets |
| `tests/planner/test_policy_gate.py` | Create | Kiểm thử `PolicyGate` với ma trận golden plans và rejection matrix (low confidence, unknown op, ambiguous ref, arbitrary code) |
| `tests/fixtures/planner_samples.py` | Create | Fixtures định nghĩa các payload instruction mẫu, golden plan valid và bad plan payloads |

### Phân tích Logic Cốt lõi:
- **Discriminated Union Schema**:
  ```python
  EditOperation = Annotated[
      Union[
          ReplaceTextOp,
          FormatTextOp,
          ReplaceImageOp,
          MoveResizeShapeOp,
          DuplicateSlideOp,
          DeleteSlideOp,
      ],
      Field(discriminator="op"),
  ]
  ```
- **Policy Gate Invariants**:
  - `confidence >= 0.80`: Kế hoạch dưới ngưỡng này tự động đặt `requires_review = True` hoặc ném `LowConfidenceError` nếu gọi ở chế độ strict.
  - `target_scope`: Mọi target `object_ref` trong `operations` bắt buộc phải nằm trong `target_scope` đã khai báo và tồn tại trong `DeckInventory`.
  - `zero arbitrary code`: Bất kỳ payload nào chứa text không phải JSON hoặc cố ý chèn shell/python commands đều bị từ chối ngay lập tức.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [x] Schema `TaskPlan` serialize/deserialize 100% hợp lệ với Pydantic v2, có trường `schema_version == "1.0"`.
- [x] Mọi operation thuộc tập allowlist (`replace_text`, `format_text`, `replace_image`, `move_resize_shape`, `duplicate_slide`, `delete_slide`) đều có schema định hình chặt chẽ kèm danh sách `preserve` và `postconditions`.
- [x] `PromptPayloadBuilder` tạo payload đầy đủ thông tin hướng dẫn, inventory rút gọn, không chứa API key hoặc đường dẫn nhạy cảm của host.
- [x] `PolicyGate` bắt và từ chối 100% các trường hợp vi phạm:
  - Operation type không nằm trong allowlist $\rightarrow$ `UnknownOperationError`.
  - Target tham chiếu đến fingerprint không tồn tại $\rightarrow$ `AmbiguousTargetError`.
  - Confidence < 0.80 $\rightarrow$ đánh dấu `requires_review: True` hoặc `LowConfidenceError`.
  - Bất kỳ format code tự do / script snippet $\rightarrow$ `MalformedPlanError` / `PolicyViolationError`.
- [x] Ma trận kiểm thử Golden plans (ít nhất 5 kịch bản phổ biến) pass 100%.
- [x] Ma trận Rejection matrix (ít nhất 6 kịch bản sai lệch/vi phạm) được phát hiện chính xác.
- [x] Toàn bộ test suite (Phase 1 + Phase 2 + Phase 3) đạt 100% passing rate trên pytest, `compileall` sạch và `sanitizer-engine pre-commit` pass.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)
### Automated
```bash
# 1. Chạy các unit test của module planner
pytest -v tests/planner

# 2. Chạy toàn bộ regression suite (Foundation + Ingest + Planner)
pytest -q

# 3. Kiểm tra cú pháp và bytecode compilation
python3 -m compileall src tests

# 4. Kiểm tra bảo mật và rò rỉ secrets
sanitizer-engine pre-commit
```

### Manual QA
1. Cung cấp một instruction: *"Update slide 1 title to 'Q4 Financial Review' and set font size to 36"*.
2. Nạp inventory của deck mẫu 2 slide từ Phase 2.
3. Chạy `PromptPayloadBuilder.build_payload(...)` và kiểm tra prompt payload sinh ra.
4. Nạp payload kết quả vào `PolicyGate.evaluate(...)` và xác nhận verdict `APPROVED` với `requires_review: False`.
5. Thử nghiệm một plan giả mạo chứa op `"execute_bash_script"` và kiểm tra `PolicyGate` từ chối với `UnknownOperationError`.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Module mới độc lập dưới `src/autoslide/planner/`, kế thừa `DeckInventory` từ `src/autoslide/ingest/models.py`.
- **Related Sessions**: Phase 1 Foundation Runtime (commits `51a0535` $\rightarrow$ `f127001`), Phase 2 PPTX Ingest (commit `d16c062`).
- **Code Graph**: `autoslide.planner` $\rightarrow$ consumes `autoslide.ingest.models.DeckInventory` $\rightarrow$ consumed by Phase 4 `autoslide.executor`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
