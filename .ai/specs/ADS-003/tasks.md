# 📋 Task Breakdown: Real Local Agent Engine, Full-Deck Live Preview & Tool Calling Workspace (ADS-003)

> **Feature ID:** ADS-003  
> **Status:** APPROVED  
> **Scheduler:** Kahn DAG Wave Scheduler  

---

## 🌊 DAG Wave Execution Plan

```
Wave 1 (Parallel Independent Foundation):
┌──────────────────────────────────────────────┐  ┌─────────────────────────────────────────────┐
│ Task 1: Real Agent Engine & Toolset Dispatch │  │ Task 2: Full-Deck Ingest & Dual Render Sync │
│ Branch: agent/agent-engine                   │  │ Branch: agent/full-deck-render              │
└──────────────────────┬───────────────────────┘  └──────────────────────┬──────────────────────┘
                       │                                                 │
                       └────────────────────────┬────────────────────────┘
                                                ▼
Wave 2 (UI Studio Overhaul):
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Task 3: Dual-Column Canvas, Visual Change Highlights & Tool Calling Chat Rail                 │
│ Branch: agent/ui-studio-overhaul                                                              │
└───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                ▼
Wave 3 (End-to-End Verification & Gate):
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Task 4: Computer-Use Browser E2E Automation, Documentation & Release Evidence                 │
│ Branch: agent/browser-computer-use-qa                                                         │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Chi Tiết Các Nhiệm Vụ (Task Specifications)

### Wave 1: Nền Tảng Agent & Render

#### 🔹 Task 1: Real Agent Engine & Toolset Dispatcher
- **Assigned Agent**: `agent-backend`
- **Worktree**: `worktree/agent-engine`
- **Scope**:
  1. Tạo `src/autoslide/agent/engine.py` quản lý Agent runtime (system persona, history, tool calling loop, analysis, calculation, streaming).
  2. Tạo `src/autoslide/agent/tools.py` định nghĩa JSON Schema và thực thi 7 tools cốt lõi:
     - `edit_slide_text(slide_index, target, new_text)`
     - `add_slide(layout, title, content_bullets, insert_at_index)`
     - `delete_slide(slide_index)`
     - `reorder_slide(from_index, to_index)`
     - `update_slide_style(slide_index, theme, layout_type)`
     - `analyze_slide_content(slide_index, query)`
     - `search_web(query)`
  3. Tích hợp endpoint `POST /api/v1/sessions/{session_id}/chat` gọi trực tiếp `AgentEngine`.
  4. Viết unit tests tại `tests/agent/test_agent_engine.py` và `tests/agent/test_agent_tools.py`.

#### 🔹 Task 2: Full-Deck Ingest & Dual-Column Live Render Engine
- **Assigned Agent**: `agent-render`
- **Worktree**: `worktree/full-deck-render`
- **Scope**:
  1. Cập nhật `src/autoslide/ingest/` và `src/autoslide/jobs/workspace.py` để xuất preview 100% tất cả slide khi upload.
  2. Cung cấp API `GET /api/v1/sessions/{session_id}/deck` trả về danh sách đầy đủ slides (Before URLs & After URLs).
  3. Cung cấp cơ chế Delta Re-render: khi `working.pptx` bị sửa bởi tool, chỉ re-render các slide bị sửa và đánh dấu `modified: true`.
  4. Viết unit tests tại `tests/render/test_full_deck_render.py`.

---

### Wave 2: Giao Diện Studio & Tương Tác

#### 🔹 Task 3: Dual-Column Canvas, Visual Change Highlights & Tool Calling Chat Rail
- **Assigned Agent**: `agent-ui`
- **Worktree**: `worktree/ui-studio-overhaul`
- **Scope**:
  1. Nâng cấp `src/autoslide/ui/templates/index.html` và `src/autoslide/ui/static/css/workbench.css`:
     - Cột Trái (Before): Hiển thị toàn bộ slide của tệp gốc.
     - Cột Phải (After): Hiển thị toàn bộ slide đã chỉnh sửa (ban đầu Before == After).
     - Visual Highlight: Viền xanh/vàng phát sáng và huy hiệu `MODIFIED` trên slide bị thay đổi ở cột After.
  2. Nâng cấp `src/autoslide/ui/static/js/workbench.js`:
     - Chat Rail hiển thị streaming message từ Agent thực tế.
     - Thẻ Tool Calling (`ToolCallingCard` & `ToolResultCard`) hiển thị trực quan khi Agent gọi tool.
     - Đồng bộ cuộn và tương tác click slide giữa Filmstrip và Canvas.
  3. Viết UI contract tests tại `tests/ui/test_studio_ui.py`.

---

### Wave 3: Kiểm Thử Trình Duyệt Thực Tế & Release Gate

#### 🔹 Task 4: Computer-Use Browser E2E Automation, Documentation & Release Evidence
- **Assigned Agent**: `agent-browser-qa`
- **Worktree**: `worktree/browser-computer-use-qa`
- **Scope**:
  1. Xây dựng kịch bản Playwright E2E mô phỏng góc nhìn người dùng tại `scripts/e2e_computer_use_qa.py` và `tests/ui/test_computer_use_e2e.py`.
  2. Thực hiện toàn bộ luồng kiểm thử:
     - Tải tệp PPTX $\rightarrow$ kiểm tra hiển thị 100% slide 2 cột (Before == After).
     - Gõ prompt chat yêu cầu Agent sửa text $\rightarrow$ Agent gọi tool $\rightarrow$ After cập nhật và highlight.
     - Gõ prompt yêu cầu thêm slide $\rightarrow$ Agent gọi tool $\rightarrow$ After thêm slide mới.
     - Gõ prompt yêu cầu tính toán / phân tích $\rightarrow$ Agent trả lời chính xác số liệu.
     - Tải tệp PPTX hoàn thiện về máy.
  3. Cập nhật `README.md` và `.ai/reports/ADS-003-evidence.md`.
  4. Đóng gói bản phát hành `ADS-003`.
