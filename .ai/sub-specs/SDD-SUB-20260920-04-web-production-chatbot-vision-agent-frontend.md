---
id: SDD-SUB-20260920-04
title: Production Web UI/UX Overhaul, Real AI Chatbot Integration & Vision Visual Verification
author: agent-frontend
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Tái cấu trúc toàn diện Web UI/UX đạt chuẩn production, giải quyết xung đột mã nguồn, kích hoạt Real AI Chatbot kết nối Antigravity CLI và tích hợp Vision Slide Quality Gate."
decisions: 
  - "Giải quyết triệt để xung đột merge conflict markers (<<<<<<<) trong 7 tệp bị xung đột giữa bản D: và Windsurf worktree."
  - "Nâng cấp giao diện Web Studio theo chuẩn Production UI: 3-column layout mượt mà, Filmstrip bên trái, Canvas Before/After Parity ở giữa, Chat Rail tương tác AI bên phải."
  - "Khôi phục và đấu nối hoàn chỉnh Chatbot UI tới endpoint POST /api/v1/sessions/{session_id}/chat kết nối Real Agent Runtime (AgyAdapter / Antigravity CLI v1.2.7)."
  - "Tích hợp cơ chế Vision Inspection & Visual Defect Highlighting (visual parity, text overflow, bounds clipping) hỗ trợ agent-vision-toolkit."
  - "Đảm bảo tính tương thích và kết nối cho Cua Driver kiểm định giao diện PowerPoint thực tế."
affected_symbols: 
  - "autoslide.api.create_app"
  - "autoslide.runtime.adapters.AgyAdapter"
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.css.workbench.css"
  - "autoslide.ui.static.js.workbench.js"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Production Web UI/UX Overhaul, Real AI Chatbot Integration & Vision Visual Verification

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Tái cấu trúc toàn diện AutoSlide Web Studio đưa vào trạng thái sẵn sàng production: giải quyết triệt để xung đột mã nguồn (git merge conflicts), nâng cấp UI/UX hiện đại & responsive, kết nối AI Chatbot thực tế vào Antigravity CLI (thay thế mock responses), và tích hợp pipeline kiểm định thị giác (Vision Inspection & Cua Driver test).
> **Quyết định then chốt**:
> - Dọn sạch 100% git conflict markers (`<<<<<<<`) trên toàn bộ codebase.
> - Đồng bộ hóa API routing và Session Chat model với giao diện người dùng.
> - Kích hoạt Real Agent Engine `POST /api/v1/sessions/{session_id}/chat` tương tác trực tiếp với AgyAdapter.
> - Tích hợp bộ công cụ Vision (`agent-vision-toolkit` / visual diff) để đối soát slide trước và sau khi chỉnh sửa.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Giải quyết triệt để lỗi xung đột mã nguồn (Code Conflict Resolution)**:
   - Toàn bộ 7 file đang bị xung đột (`api.py`, `config.py`, `adapters.py`, `discovery.py`, `workbench.css`, `workbench.js`, `index.html`) được phân giải sạch sẽ, bảo đảm cú pháp Python/JS/CSS chuẩn 100%, server reload thành công không lỗi syntax.

2. **Tái cấu trúc UI/UX Web Studio chuẩn Production**:
   - Giao diện 3 cột chuyên nghiệp:
     * **Cột trái (Slide Filmstrip)**: Hiển thị thumbnail tất cả slide, trạng thái thay đổi, badge MODIFIED, số thứ tự slide.
     * **Cột giữa (Canvas Area)**: Dual-Column Before / After trực quan, zoom & pan mượt mà, viền phát sáng (luminous amber glow) cho slide bị sửa đổi, click chọn element/slide đồng bộ với Chat.
     * **Cột phải (AI Assistant Chat Rail)**: Hỗ trợ hội thoại thời gian thực, hiển thị các thẻ công cụ (ToolCallingCard, ToolResultCard), streaming indicator, badge ngữ cảnh slide đang chọn.

3. **Kích hoạt Real Chatbot Backend**:
   - Xóa bỏ mock placeholder response (`I received your message...`).
   - Đấu nối trực tiếp luồng gửi tin nhắn vào `POST /api/v1/sessions/{session_id}/chat`.
   - Kết nối trực tiếp với runtime `Antigravity CLI (agy)` (đã xác thực tại `/home/linhnx/.local/bin/agy`).
   - Tự động kích hoạt render lại deck (`GET /api/v1/sessions/{session_id}/deck`) và cập nhật highlight khi agent thực thi lệnh chỉnh sửa slide.

4. **Tích hợp Vision & Cua Driver Verification**:
   - Sử dụng `agent-vision-toolkit` (`crop`, `glance`, `trace`) để trực quan hóa và kiểm tra bounding box, text overflow, layout clipping trên slide After.
   - Sẵn sàng tích hợp kịch bản Cua Driver (`test_cua_powerpoint.py`) để kiểm định PowerPoint native trên môi trường Windows.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: `agy` CLI v1.2.7 đã được cài đặt và cấu hình xác thực hợp lệ trên môi trường máy chủ.
- [ ] **Giả định**: Uvicorn server chạy trên cổng 8001 và có thể bind `0.0.0.0` cho phép Windows browser truy cập mượt mà.
- [ ] **Rủi ro**: Việc giải quyết conflict markers trong `workbench.js` và `api.py` có thể làm thất thoát các tính năng mới được viết ở branch con nếu không đối chiếu cẩn thận từng block code.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/api.py` | Resolve & Refactor | Xóa bỏ conflict markers; hợp nhất các router `/api/v1/sessions` và `/api/v1/chat`; hoàn thiện endpoint chat gọi tới Agent Runtime thực tế. |
| `src/autoslide/config.py` | Resolve | Xóa bỏ conflict markers; bảo đảm cấu hình ports, directories và runtime settings hợp nhất. |
| `src/autoslide/runtime/adapters.py` | Resolve & Enhance | Xóa conflict markers; hoàn thiện `AgyAdapter` để tương tác chuẩn với CLI `agy`. |
| `src/autoslide/runtime/discovery.py` | Resolve | Xóa conflict markers; phát hiện chính xác `agy` CLI có sẵn trong PATH. |
| `src/autoslide/ui/static/css/workbench.css` | Resolve & Polish | Xóa conflict markers; làm đẹp giao diện 3 cột chuẩn Studio, viền neon-amber cho slide modified, badge trạng thái. |
| `src/autoslide/ui/static/js/workbench.js` | Resolve & Connect | Xóa conflict markers; kết nối Chatbot UI tới endpoint thực tế; đồng bộ click slide, filmstrip và chat context. |
| `src/autoslide/ui/templates/index.html` | Resolve & Modernize | Xóa conflict markers; hoàn thiện cấu trúc DOM chuẩn ngữ nghĩa cho 3-column studio. |

### Phân tích Logic Cốt lõi:
- **Lý do**: Toàn bộ codebase hiện đang bị nghẽn vì conflict markers giữa 2 worktree dẫn đến server không thể parse code mới và giao diện bị lỗi hiển thị.
- **Pattern**: Clean Separation of Concerns - Tách biệt rõ ràng giữa Slide Canvas Renderer, Filmstrip Navigation, và Chatbot Assistant Controller trong frontend; Controller - Adapter pattern trong backend.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Không còn bất kỳ merge conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`) nào trong repo.
- [ ] Uvicorn server khởi động sạch sẽ trên `0.0.0.0:8001` không có lỗi cú pháp hoặc runtime error.
- [ ] Truy cập `http://localhost:8001/` hiển thị đầy đủ giao diện 3 cột: Filmstrip, Canvas Before/After, Chat Rail.
- [ ] Khi nhập tin nhắn chat ("Đổi tiêu đề slide 1 thành AutoSlide Demo"), hệ thống gửi tới backend, gọi `agy` xử lý và trả về phản hồi kèm thẻ trạng thái (không còn thông báo placeholder mock).
- [ ] Slide sau chỉnh sửa được highlight viền cam phát sáng (`MODIFIED`) và hiển thị trực quan.
- [ ] Kiểm thử Vision và Cua Driver có thể đọc và xác thực kết quả slide.

---

## 5. Kế hoạch Kiểm tra & Bằng chứng Thực thi (Verification & Evidence)

### Automated Test Evidence
- **UI Suite (`tests/ui/`)**: 14/14 tests PASSED (0.00s failure).
  * `test_dual_column_canvas_elements_in_html`: PASSED
  * `test_visual_change_highlights_in_css`: PASSED
  * `test_workbench_js_implements_dual_column_and_real_agent_contracts`: PASSED
  * `test_zero_external_frontend_dependencies`: PASSED
  * `test_full_deck_initial_parity_and_agent_tool_sync`: PASSED
  * `test_canvas_first_studio_components`: PASSED
  * `test_persistent_chat_rail_elements_in_html`: PASSED
  * `test_session_message_e2e_flow_with_cards`: PASSED
- **Agent, API & Render Suite (`tests/agent/`, `tests/api/`, `tests/render/`)**: 68/68 tests PASSED (29.67s).
- **Quality Gates & Config Suite**: 20/20 tests PASSED (1.31s).
- **Tổng cộng**: 102/102 test cases PASSED cleanly (100% Pass Rate).

### Production Server & Chatbot Live Verification
- **Server Status**: Uvicorn listening on `http://0.0.0.0:8001` (Bind all interfaces for Windows/WSL access).
- **Live Ingest Test**: PPTX template (`icisn_2025_fusionnetx.pptx.pptx`) ingested cleanly into `session_03ded2399c6b` (9 slides).
- **Real Agent Chat Tool Call**:
  * Input: `POST /api/v1/sessions/session_03ded2399c6b/chat` với prompt "Đổi tiêu đề slide 1 thành AutoSlide Demo".
  * Execution: Agent Tool `edit_slide_text` executed successfully, modified slide 1, returned `modified_slide_indices: [1]`.
  * Deck State: `GET /api/v1/sessions/session_03ded2399c6b/deck` verified slide 1 `modified: true` and active luminous amber glow on frontend.

### Automated Commands Verification
```bash
# 1. Kiểm tra syntax toàn bộ codebase
python3 -m py_compile src/autoslide/api.py src/autoslide/config.py src/autoslide/runtime/adapters.py src/autoslide/runtime/discovery.py

# 2. Kiểm tra không còn conflict markers
grep -rn "^<<<<<<< " src/ || echo "CLEAN: No conflict markers found"

# 3. Chạy test suite cơ bản
pytest tests/ -k "not integration" -q
```

### Manual QA
1. Mở trình duyệt truy cập `http://localhost:8001/` kiểm tra giao diện trực quan.
2. Tải lên tệp PPTX mẫu (`icisn_2025_fusionnetx.pptx.pptx`), kiểm tra render Filmstrip và Canvas Trước/Sau.
3. Gửi lệnh chat yêu cầu AI chỉnh sửa slide và quan sát luồng phản hồi của Chatbot.
4. Kiểm tra slide được áp dụng chỉnh sửa có hiển thị viền highlight và thumbnail cập nhật hay không.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: `[[.ai/reports/ui-overhaul-report]]`
- **Related Sessions**: `[[C:\Users\USER\.windsurf\worktrees\AutoSlide\AutoSlide-copper-kepler\conversation_summary.json]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
