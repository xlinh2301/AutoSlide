---
id: SDD-SUB-20260918-07
title: Defect Fixes - Explicit Slide Targeting, Async Repair Decision Path & Text Overflow Calibration
author: agent-coding
status: IMPLEMENTED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Resolve critical AutoSlide defects: (1) parse explicit slide index targets (e.g., 'slide 3' / 'trang 3') mapping to 0-based slide indices, (2) implement asynchronous background Repair decision rerun for remediation and verification, (3) tune visual overflow heuristics to eliminate false positives on standard text frames while preserving true clipping detection, and (4) add regression test suite for 'tạo title test cho slide 3' without modifying Phase 7."
decisions:
  - "Enhance target resolution in planner/builder/executor to accurately parse 1-based slide target mentions such as 'slide 3', 'slide 3:', 'trang 3', 'slide số 3' and match corresponding slide index (slide_index 3)."
  - "Update Workbench review decision endpoint (/api/v1/jobs/{job_id}/decision) to launch an asynchronous background repair pipeline task upon 'repair' decision action, transitioning through REPAIRING, EXECUTING, RENDERING, VERIFYING and AWAITING_USER_APPROVAL states."
  - "Refine QualityGate text bounding-box overflow calculation to account for text wrapping margins, paragraph heights, and line tolerances to prevent false positive defects on valid presentation titles and bodies."
  - "Create regression test cases in tests/integration/test_defect_fixes.py and planner tests covering 'tạo title test cho slide 3' against standard PPTX fixtures."
  - "Maintain Phase 7 reference ingestion contracts untouched."
affected_symbols:
  - "autoslide.orchestrator.pipeline.JobOrchestrator._resolve_plan"
  - "autoslide.orchestrator.pipeline.JobOrchestrator.run_repair"
  - "autoslide.quality.visual.VisualQualityGate.evaluate"
  - "autoslide.api.submit_decision"
risk_level: LOW
---

# 📝 Sub Spec: Defect Fixes — Explicit Slide Targeting, Async Repair Decision Path & Text Overflow Calibration

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Khắc phục các lỗi vận hành của AutoSlide gồm phân giải mục tiêu slide tường minh (ví dụ: "slide 3" -> slide index 3), kích hoạt chu trình sửa lỗi bất đồng bộ khi bấm Repair trên Review Gate, triệt tiêu cảnh báo giả tràn chữ (false-positive text overflow) nhưng vẫn giữ chuẩn phát hiện clipping thực, và bổ sung test hồi quy cho lệnh "tạo title test cho slide 3".
> **Quy chuẩn**: Giữ nguyên Phase 7 Reference Ingestion; tuân thủ strict Conventional Commits; pass 100% pytest, compileall, sanitizer-engine; khởi động lại demo server và kiểm thử E2E qua UI/API.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/IMPLEMENTED

---

## 1. Mục tiêu (Objective)
1. **Explicit Slide Targeting**:
   - Nhận diện chính xác các chỉ thị mục tiêu cụ thể như "slide 3", "slide 3:", "trang 3", "slide số 3" (đánh chỉ số từ 1 theo góc nhìn người dùng) và ánh xạ tới slide index 3 trong `DeckInventory` và `TaskPlan`.
   - Đảm bảo mutation chỉ áp dụng lên đúng slide được chỉ định, bảo toàn tuyệt đối các slide còn lại theo `FR-06`.
2. **Async Repair Decision Path**:
   - Khi API nhận review decision với action `repair` (`POST /api/v1/jobs/{job_id}/decision` với `{"decision": "repair"}`), hệ thống khởi chạy tiến trình `run_repair` chạy ngầm (asynchronous background task).
   - Trạng thái job chuyển tiếp mượt mà từ `AWAITING_USER_APPROVAL` sang `REPAIRING` $\rightarrow$ `EXECUTING` $\rightarrow$ `RENDERING` $\rightarrow$ `VERIFYING` $\rightarrow$ `AWAITING_USER_APPROVAL`.
3. **Calibrated Text Overflow Detection**:
   - Tinh chỉnh thuật toán đo kích thước ước tính và bounding box tolerance trong `autoslide.quality.visual` để không báo lỗi tràn chữ (false positive) cho các text box tiêu đề và nội dung thông thường có ngắt dòng hợp lệ.
   - Bảo toàn khả năng phát hiện text thực sự vượt quá mép slide (`BOUNDS_CLIPPING`) và lỗi tràn chữ nghiêm trọng (`TEXT_OVERFLOW`).
4. **Regression Tests & Demo Server Verification**:
   - Thêm bộ kiểm thử hồi quy cho câu lệnh: `"tạo title test cho slide 3"` trên template PPTX mẫu.
   - Giữ nguyên Phase 7 không thay đổi.
   - Chạy `pytest`, `compileall`, `sanitizer-engine`, restart demo server, và thực hiện e2e verification.

---

## 2. Tiêu chí Chấp nhận (Acceptance Criteria)
- [x] Câu lệnh `"tạo title test cho slide 3"` chỉnh sửa chính xác tiêu đề slide 3 mà không tác động slide 1 hoặc slide 2.
- [x] Gọi `POST /api/v1/jobs/{job_id}/decision` với action `repair` thực thi quy trình khắc phục bất đồng bộ và trả về response tức thì.
- [x] Không còn false positive text-overflow trên các template và test fixture chuẩn.
- [x] Phase 7 code và spec không bị chỉnh sửa sai lệch.
- [x] 100% pytest pass (115/115 tests), `python3 -m compileall src tests` sạch lỗi, `sanitizer-engine pre-commit` pass.
- [x] Demo server được khởi động lại thành công và kiểm tra job PPTX qua UI/API hoạt động trơn tru.
- [x] Phát tín hiệu `AGENT_FINISH` với status `READY_FOR_QA`.
