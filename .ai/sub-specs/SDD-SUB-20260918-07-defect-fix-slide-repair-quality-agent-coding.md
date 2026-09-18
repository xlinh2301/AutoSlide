---
id: SDD-SUB-20260918-07
title: Defect Fixes - Explicit Slide Targeting, Async Repair Decision Path & Text Overflow Calibration
author: agent-coding
status: DRAFT
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Resolve critical AutoSlide defects: (1) parse explicit slide index targets (e.g., 'slide 3' / 'trang 3') mapping to 0-based slide indices, (2) implement asynchronous background Repair decision rerun for remediation and verification, (3) tune visual overflow heuristics to eliminate false positives on standard text frames while preserving true clipping detection, and (4) add regression test suite for 'tạo title test cho slide 3' without modifying Phase 7."
decisions:
  - "Enhance target resolution in planner/builder/executor to accurately parse 1-based slide target mentions such as 'slide 3', 'slide 3:', 'trang 3', 'slide số 3' and match corresponding slide index (slide_index 2)."
  - "Update Workbench review decision endpoint (/api/jobs/{job_id}/review) to launch an asynchronous background repair pipeline task upon 'repair' decision action, transitioning through REMEDIATING and VERIFYING states."
  - "Refine QualityGate text bounding-box overflow calculation to account for text wrapping margins, paragraph heights, and line tolerances to prevent false positive defects on valid presentation titles and bodies."
  - "Create regression test cases in tests/integration/test_defect_fixes.py and planner tests covering 'tạo title test cho slide 3' against standard PPTX fixtures."
  - "Maintain Phase 7 reference ingestion contracts untouched."
affected_symbols:
  - "autoslide.planner.builder.PromptPayloadBuilder"
  - "autoslide.planner.policy.PolicyGate"
  - "autoslide.quality.overflow"
  - "autoslide.quality.gate.QualityGate"
  - "autoslide.api"
  - "autoslide.workbench.app"
risk_level: LOW
---

# 📝 Sub Spec: Defect Fixes — Explicit Slide Targeting, Async Repair Decision Path & Text Overflow Calibration

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Khắc phục các lỗi vận hành của AutoSlide gồm phân giải mục tiêu slide tường minh (ví dụ: "slide 3" -> slide index 2), kích hoạt chu trình sửa lỗi bất đồng bộ khi bấm Repair trên Review Gate, triệt tiêu cảnh báo giả tràn chữ (false-positive text overflow) nhưng vẫn giữ chuẩn phát hiện clipping thực, và bổ sung test hồi quy cho lệnh "tạo title test cho slide 3".
> **Quy chuẩn**: Giữ nguyên Phase 7 Reference Ingestion; tuân thủ strict Conventional Commits; pass 100% pytest, compileall, sanitizer-engine; khởi động lại demo server và kiểm thử E2E qua UI/API.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)
1. **Explicit Slide Targeting**:
   - Nhận diện chính xác các chỉ thị mục tiêu cụ thể như "slide 3", "slide 3:", "trang 3", "slide số 3" (đánh chỉ số từ 1 theo góc nhìn người dùng) và ánh xạ tới slide index 2 (0-based) trong `DeckInventory` và `TaskPlan`.
   - Đảm bảo mutation chỉ áp dụng lên đúng slide được chỉ định, bảo toàn tuyệt đối các slide còn lại theo `FR-06`.
2. **Async Repair Decision Path**:
   - Khi API nhận review decision với action `repair` (`POST /api/jobs/{job_id}/review` với `{"decision": "repair"}`), hệ thống khởi chạy tiến trình `run_pipeline_task` hoặc `run_repair_task` chạy ngầm (asynchronous background task).
   - Trạng thái job chuyển tiếp mượt mà từ `NEEDS_REVIEW` sang `REMEDIATING` $\rightarrow$ `VERIFYING` $\rightarrow$ `ACCEPTED`/`NEEDS_REVIEW`.
3. **Calibrated Text Overflow Detection**:
   - Tinh chỉnh thuật toán đo kích thước ước tính và bounding box tolerance trong `autoslide.quality` để không báo lỗi tràn chữ (false positive) cho các text box tiêu đề và nội dung thông thường có ngắt dòng hợp lệ.
   - Bảo toàn khả năng phát hiện text thực sự vượt quá mép slide (clipping/out-of-bounds).
4. **Regression Tests & Demo Server Verification**:
   - Thêm bộ kiểm thử hồi quy cho câu lệnh: `"tạo title test cho slide 3"` trên template PPTX mẫu.
   - Giữ nguyên Phase 7 không thay đổi.
   - Chạy `pytest`, `compileall`, `sanitizer-engine`, restart demo server, và thực hiện e2e verification.

---

## 2. Đặc tả Kỹ thuật (Technical Specification)

### 2.1. Slide Target Extraction
- Hỗ trợ regex & rule-based target parsing trong `PromptPayloadBuilder` / `PolicyGate` / `TaskPlan`:
  - Pattern: `r'(?:slide|trang|slide\s+số)\s+(\d+)'` (case-insensitive).
  - Ánh xạ `slide_number` (1-indexed) thành `slide_index = slide_number - 1`.
  - Giới hạn `TargetScope` bao hàm `slide_indices: [slide_index]`.

### 2.2. Async Repair Path in API & Engine
- Trong `src/autoslide/api.py`:
  - Khi action là `repair`, tạo task bất đồng bộ trong background (`asyncio.create_task(engine.repair_job(job_id))` hoặc `pipeline.run_repair(...)`).
  - Gửi event `JOB_REPAIR_STARTED` qua `EventStream`.

### 2.3. Text Overflow Threshold Tuning
- Trong `src/autoslide/quality/` (hoặc module overflow detector):
  - Bổ sung padding margin và font metric correction hợp lý để loại bỏ false-positives khi text được ngắt dòng tự nhiên trong text box chuẩn.
  - Vẫn giữ cảnh báo khi `box.right > slide_width` hoặc `box.bottom > slide_height`.

---

## 3. Tiêu chí Chấp nhận (Acceptance Criteria)
- [ ] Câu lệnh `"tạo title test cho slide 3"` chỉnh sửa chính xác tiêu đề slide 3 (index 2) mà không tác động slide 1 hoặc slide 2.
- [ ] Gọi `POST /api/jobs/{job_id}/review` với action `repair` thực thi quy trình khắc phục bất đồng bộ và trả về response tức thì (không block).
- [ ] Không còn false positive text-overflow trên các template và test fixture chuẩn.
- [ ] Phase 7 code và spec không bị chỉnh sửa sai lệch.
- [ ] 100% pytest pass, `python3 -m compileall src tests` sạch lỗi, `sanitizer-engine pre-commit` pass.
- [ ] Demo server được khởi động lại thành công và kiểm tra job PPTX qua UI/API hoạt động trơn tru.
- [ ] Phát tín hiệu `AGENT_FINISH` với status `READY_FOR_QA`.

---

## 4. Kế hoạch Kiểm thử (Verification Plan)
```bash
# 1. Chạy pytest các suite liên quan
pytest tests/integration/test_defect_fixes.py tests/planner/ tests/quality/ -v

# 2. Chạy toàn bộ test suite
pytest -q

# 3. Compileall
python3 -m compileall src tests

# 4. Sanitizer
sanitizer-engine pre-commit

# 5. Khởi động demo server và test curl UI/API
```
