---
id: SDD-SUB-20260918-04
title: "Phase 5 Quality Gates: Structural Acceptance, Visual Findings, Bounded Repair & Human Review"
author: agy_c
status: DRAFT
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Implement two-tier quality gates combining structural diff verification, visual defect/overflow analysis, bounded repair loop policy, and human review escalations."
decisions:
  - "Separate structural acceptance gate from visual validation gate so that VLM or heuristics are not the sole authority for data preservation."
  - "Model visual findings and defects as strongly-typed records (VisualFinding) with severity levels (INFO, WARNING, ERROR, CRITICAL) and deterministic geometric evidence."
  - "Bound repair attempts (max 3 cycles) to prevent infinite repair loops, automatically transitioning to AWAITING_USER_APPROVAL when repair budget is exhausted."
  - "Emit machine-readable evidence files (artifacts/quality_report.json, artifacts/visual_findings.json) into the job workspace before marking a job accepted."
affected_symbols:
  - "autoslide.quality.structural.StructuralAcceptanceGate"
  - "autoslide.quality.visual.VisualQualityGate"
  - "autoslide.quality.repair.RepairLoopController"
  - "autoslide.quality.models.VisualFinding"
  - "autoslide.quality.models.FindingSeverity"
  - "autoslide.quality.models.QualityReport"
  - "autoslide.quality.models.RepairDecision"
  - "autoslide.quality.errors.QualityGateError"
  - "autoslide.quality.errors.StructuralRejectionError"
  - "autoslide.quality.errors.MaxRepairAttemptsExceededError"
risk_level: LOW
---

# 📝 Sub Spec: Phase 5 Quality Gates — Structural Acceptance, Visual Findings, Bounded Repair & Human Review

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Xây dựng hệ thống cổng chất lượng 2 tầng (Two-Tier Quality Gates) gồm thẩm định cấu trúc (`StructuralAcceptanceGate`) và thẩm định thị giác (`VisualQualityGate`), phát hiện các khiếm khuyết text tràn/cắt xén (`overflow`/`clipping`), kiểm soát vòng lặp sửa lỗi có chặn trên (`bounded repair loop`, tối đa 3 lần), và chuyển tiếp trạng thái duyệt (`AWAITING_USER_APPROVAL`) khi cần can thiệp.
> **Quyết định then chốt**: Phân lập hoàn toàn gate cấu trúc và gate thị giác; ghi nhận finding có định danh severity (`CRITICAL`, `ERROR`, `WARNING`, `INFO`); lưu trữ bằng chứng máy đọc (`artifacts/quality_report.json`).
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)
Cung cấp lát cắt kiểm soát chất lượng & sửa lỗi (Phase 5) cho AutoSlide:
1. **Structural Acceptance Gate (`StructuralAcceptanceGate`)**:
   - Thẩm định `StructuralDiff` từ Phase 4:
     - Khẳng định 100% các intended changes đã diễn ra.
     - Khẳng định `unintended_changes` rỗng (zero collateral damage) đối với các shape và slide ngoài `target_scope`.
     - Kiểm tra tính toàn vẹn gói đầu ra qua `validate_pptx_package`.
     - Nếu phát hiện vi phạm bảo toàn: đánh dấu `REJECTED` hoặc chuyển giao repair loop.
2. **Visual Quality Gate & Findings Contract (`VisualQualityGate`)**:
   - Tận dụng preview renderer từ Phase 2 (`LibreOfficePreviewRenderer` / `MockPreviewRenderer`) để sinh preview ảnh của các slide đã sửa.
   - Thẩm định các khiếm khuyết hình ảnh/bố cục:
     - `TEXT_OVERFLOW`: Chiều dài text vượt quá dung lượng ước tính của bounding box.
     - `BOUNDS_CLIPPING`: Shape tràn ra ngoài phạm vi slide dimensions (`cx, cy`).
     - `MISSING_TARGET`: Đối tượng biến mất ngoài ý muốn.
     - `RENDER_FAILURE`: Lỗi trong quá trình kết xuất hình ảnh.
   - Sinh danh sách `VisualFinding` với các cấp độ: `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
3. **Bounded Repair Loop Controller (`RepairLoopController`)**:
   - Quản lý ngân sách sửa lỗi (mặc định tối đa 3 lần thử: `max_repair_attempts = 3`).
   - Nếu phát hiện finding sửa được (ví dụ `TEXT_OVERFLOW` $\rightarrow$ sinh chỉ thị format giảm `font_size` hoặc nới `bounds`):
     - Sinh `RepairDecision(action="REPAIR", repair_instruction=...)` để gửi ngược lại cho Planner (Phase 3).
   - Nếu vượt quá số lần sửa hoặc phát hiện lỗi không thể tự sửa:
     - Sinh `RepairDecision(action="ESCALATE_REVIEW", reason=...)` chuyển job sang trạng thái `AWAITING_USER_APPROVAL`.
4. **Evidence & Quality Report Delivery**:
   - Tạo file báo cáo tổng hợp `artifacts/quality_report.json` và `artifacts/visual_findings.json` lưu trong job workspace.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [x] **Giả định**: Phase 4 `PPTXExecutor` đã cung cấp `StructuralDiff` và file PPTX working copy đã qua kiểm tra toàn vẹn cơ bản.
- [x] **Giả định**: Host hỗ trợ render headless (hoặc sử dụng `MockPreviewRenderer` trong môi trường CI/test độc lập).
- [ ] **Rủi ro**: Ước tính text overflow có thể sai lệch giữa các font chữ khác nhau $\rightarrow$ *Giải pháp*: Kết hợp công thức ước lượng diện tích glyph ký tự (EMU character width approximation) cùng tỷ lệ khung hình bounding box.
- [ ] **Rủi ro**: Vòng lặp repair có thể lặp vô tận nếu mô hình liên tục thử các sửa đổi không hiệu quả $\rightarrow$ *Giải pháp*: Chặn cứng ngưỡng `max_attempts` và theo dõi lịch sử lỗi (repair history tracking) để phát hiện lặp lại cùng một lỗi.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/quality/__init__.py` | Create | Export các interface chính của module quality gates |
| `src/autoslide/quality/models.py` | Create | Khai báo Pydantic models: `FindingSeverity`, `FindingCategory`, `VisualFinding`, `GateVerdict`, `QualityReport`, `RepairDecision` |
| `src/autoslide/quality/errors.py` | Create | Định nghĩa các exception: `QualityGateError`, `StructuralRejectionError`, `MaxRepairAttemptsExceededError` |
| `src/autoslide/quality/structural.py` | Create | `StructuralAcceptanceGate` kiểm tra `unintended_changes` và tính toàn vẹn gói |
| `src/autoslide/quality/visual.py` | Create | `VisualQualityGate` kiểm tra text overflow, shape clipping, missing shapes, render failures |
| `src/autoslide/quality/repair.py` | Create | `RepairLoopController` theo dõi ngân sách sửa lỗi, tạo prompt hướng dẫn sửa và quyết định escalate |
| `tests/quality/__init__.py` | Create | Package init cho quality tests |
| `tests/quality/test_structural_gate.py` | Create | Kiểm thử `StructuralAcceptanceGate` với diff sạch vs diff có collateral change |
| `tests/quality/test_visual_gate.py` | Create | Kiểm thử `VisualQualityGate` phát hiện text overflow, clipping ngoài slide, và render error |
| `tests/quality/test_repair_controller.py` | Create | Kiểm thử `RepairLoopController` quản lý attempt counter, tạo repair instructions, và escalate review khi chạm ngưỡng |
| `tests/fixtures/quality_samples.py` | Create | Fixtures sinh mock structural diffs, overflow inventory decks, và visual findings |

### Phân tích Logic Cốt lõi:
- **Two-Tier Quality Validation**:
  ```python
  # 1. Structural Gate:
  structural_result = structural_gate.evaluate(structural_diff)
  if not structural_result.passed:
      # Collateral change detected
  
  # 2. Visual Gate:
  visual_findings = visual_gate.evaluate(working_pptx, inventory, preview_manifest)
  
  # 3. Decision Matrix:
  if has_critical_findings(visual_findings) or not structural_result.passed:
      decision = repair_controller.decide(attempt, visual_findings, structural_result)
  ```
- **Text Overflow & Bounds Clipping Heuristics**:
  - `is_clipped = (shape.bounds.x + shape.bounds.cx > slide.cx) or (shape.bounds.y + shape.bounds.cy > slide.cy)`
  - `estimated_text_width = char_count * font_size_emu * 0.55`
  - Nếu `estimated_text_width > bounds.cx * line_capacity` $\rightarrow$ Flag `TEXT_OVERFLOW`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [ ] `StructuralAcceptanceGate` chấp thuận (verdict `PASSED`) các diff chỉ chứa intended changes và từ chối (verdict `FAILED`) khi có unintended changes ngoài scope.
- [ ] `VisualQualityGate` phát hiện chính xác shape tràn ra ngoài kích thước slide (`BOUNDS_CLIPPING`) và text vượt kích thước box (`TEXT_OVERFLOW`).
- [ ] `RepairLoopController` sinh `RepairDecision` với hành động `REPAIR` kèm gợi ý sửa khi `attempt < max_attempts`.
- [ ] `RepairLoopController` sinh hành động `ESCALATE_REVIEW` khi `attempt >= max_attempts` (ngăn chặn lặp vô tận).
- [ ] Báo cáo chất lượng `artifacts/quality_report.json` và `artifacts/visual_findings.json` được sinh đầy đủ trong job workspace.
- [ ] Toàn bộ test suite (Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5) đạt 100% passing rate trên pytest, `compileall` sạch và `sanitizer-engine pre-commit` pass.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)
### Automated
```bash
# 1. Chạy các unit test của module quality gates
pytest -v tests/quality

# 2. Chạy toàn bộ regression suite (Foundation + Ingest + Planner + Executor + Quality)
pytest -q

# 3. Kiểm tra cú pháp và bytecode compilation
python3 -m compileall src tests

# 4. Kiểm tra bảo mật và rò rỉ secrets
sanitizer-engine pre-commit
```

### Manual QA
1. Khởi tạo một task plan cố ý làm tràn text (chuỗi 500 ký tự vào title box nhỏ).
2. Chạy `VisualQualityGate.evaluate(...)` và kiểm tra finding `TEXT_OVERFLOW` được ghi nhận.
3. Chạy `RepairLoopController.decide(...)` lần 1 $\rightarrow$ xác nhận sinh repair instruction giảm font size.
4. Giả lập thử lại lần 3 $\rightarrow$ xác nhận chuyển sang `ESCALATE_REVIEW` với trạng thái `AWAITING_USER_APPROVAL`.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Module mới độc lập dưới `src/autoslide/quality/`, consumes `autoslide.executor.models.StructuralDiff` và `autoslide.ingest.models.DeckInventory`.
- **Related Sessions**: Phase 1 Foundation (`f127001`), Phase 2 Ingest (`d16c062`), Phase 3 Planner (`9615c2f`), Phase 4 Executor (`e361799`).
- **Code Graph**: `autoslide.executor` $\rightarrow$ `autoslide.quality` $\rightarrow$ consumed by Phase 6 `autoslide.api` / Workbench.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
