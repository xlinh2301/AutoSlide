---
id: SDD-SUB-20260918-08
title: Preview Diff and Targeted Slide or Region Editing
author: orchestrator
status: APPROVED
main_spec: "[[.ai/specs/ADS-001/requirements.md]]"
summary: "Add a Git-style before/after preview, slide-scoped and region-scoped prompts, and explicit all-slides editing without changing the original deck."
decisions:
  - "Render each changed slide before and after execution and expose a side-by-side diff model with changed-region overlays."
  - "A prompt may target one slide, a user-selected region, or the complete deck; no target means the planner must preserve current behavior and request clarification when ambiguous."
  - "Region selection is represented in slide-local coordinates and passed as structured scope to the planner, not embedded only in free-form text."
  - "The original PPTX remains immutable; preview artifacts are job-scoped and downloadable with the final deck."
affected_symbols:
  - "autoslide.api"
  - "autoslide.jobs.models"
  - "autoslide.orchestrator.pipeline"
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.js.workbench.js"
risk_level: MEDIUM
---

# 📝 Sub Spec: Preview Diff and Targeted Slide or Region Editing

> [!ABSTRACT]
> **Mục tiêu**: Cho phép người dùng xem slide gốc và slide sau chỉnh sửa cạnh nhau, highlight khác biệt, sửa một slide/vùng được click chọn hoặc áp dụng prompt cho toàn bộ deck.
> **Trạng thái**: #status/APPROVED | **Rủi ro**: #risk/MEDIUM

## 1. Mục tiêu (Objective)

Deliver one vertical workbench slice that makes edit scope explicit and reviewable:

1. Users can choose `current slide`, `selected region`, or `all slides` before submitting a prompt.
2. Users can click-drag a rectangle on a rendered slide to create a slide-local region scope.
3. After rendering, the UI shows original on the left and updated on the right, with overlay/highlight information for changed objects or pixels.
4. The API and planner carry scope as structured data while preserving backward compatibility for existing prompt-only jobs.

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] Existing render/preview artifacts and structural diff are reused where available.
- [x] Coordinates are normalized to the rendered slide viewport and converted to slide EMU/native coordinates server-side.
- [ ] `[UNKNOWN]`: Exact browser-side rendering format may be PNG URLs or data URLs; preserve the existing artifact contract if already present.
- [ ] Risk: pixel diffs can over-report anti-aliasing; structural object diff is authoritative for intended edits and pixel diff is visual evidence.
- [ ] Risk: region scope may contain no resolvable object; return review/clarification rather than guessing.

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/jobs/models.py` | Modify | Add backward-compatible edit scope/diff preview models. |
| `src/autoslide/api.py` | Modify | Accept optional `scope` and expose preview/diff metadata. |
| `src/autoslide/orchestrator/pipeline.py` | Modify | Pass scope into planning/execution and generate preview diff artifacts. |
| `src/autoslide/ui/templates/index.html` | Modify | Add slide selector, all-slides option, region selection canvas and side-by-side preview. |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Implement scope state, drag/click region selection, preview navigation and highlight overlays. |
| `src/autoslide/ui/static/css/workbench.css` | Modify | Style diff panes, overlays and target controls. |
| `tests/api/*`, `tests/integration/*`, `tests/ui/*` | Add/Modify | Cover scope contract, diff generation and UI state behavior. |

### Phân tích Logic Cốt lõi

- Scope must be explicit and typed: `deck`, `slide`, or `region`.
- Preview pairs are keyed by slide number and include original/updated image URLs, changed object refs, and overlay boxes.
- A single-slide prompt remains the default when a slide target is present in natural language; an explicit UI scope takes precedence and is recorded in the job event.
- All-slide mode must not silently narrow to one slide; planner payload includes `scope.kind = deck` and acceptance checks include every affected slide.

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] Existing prompt-only job creation remains backward compatible.
- [x] User can select one slide and submit a prompt; API event records the slide scope.
- [x] User can drag a region on a slide preview; region coordinates are sent as structured scope.
- [x] User can select all slides and submit one prompt; planner receives deck scope.
- [x] Completed jobs expose original/updated preview pairs and changed-region highlights.
- [x] Structural diff remains available alongside visual diff and original PPTX is unchanged.
- [x] Ambiguous/unresolvable region target transitions to review/clarification.

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated

```bash
pytest -q
python3 -m compileall src tests
sanitizer-engine pre-commit
```

### Manual QA

1. Start the local workbench and upload `Template Weekly Report.pptx`.
2. Select slide 3, prompt a title change, and verify the diff shows only slide 3.
3. Drag a rectangle over a slide region, submit a prompt, and verify the event contains normalized/native coordinates.
4. Select all slides, submit one prompt, and verify the preview navigator contains all changed slide pairs.
5. Verify left pane is original, right pane is updated, and overlays identify changed regions.

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: existing ADS-001 design sections 3.1, 3.2, 3.6 and 4.
- **Related Sessions**: Phase 6 local workbench and defect-fix session 07.
- **Code Graph**: pending implementation scan.

---
*Approval recorded from user response: `ok`.*
