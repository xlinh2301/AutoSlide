---
id: SDD-SUB-20260920-01
title: Real Local Agent Engine, Toolset Dispatcher & Chat Endpoint
author: agent-backend
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Implement Real Local Agent Engine with multi-turn conversation, intelligent tool calling loop, 7 core slide manipulation/analysis tools, and wire to POST /api/v1/sessions/{session_id}/chat."
decisions: 
  - "Construct AgentEngine supporting structured system persona, multi-turn message history, and an iterative tool-calling loop (evaluating tool calls, executing mutators, and streaming/returning final assistant responses)."
  - "Define ToolRegistry declaring standardized OpenAI/JSON-Schema specifications for 7 tools: edit_slide_text, add_slide, delete_slide, reorder_slide, update_slide_style, analyze_slide_content, and search_web."
  - "Implement tool dispatchers interfacing safely with OOXML DeckMutator, DeckInventory, and web search fallback without corrupting underlying presentation files."
  - "Expose POST /api/v1/sessions/{session_id}/chat endpoint returning assistant messages, executed tool calls, and modified slide indices, updating ConversationSession state and history."
affected_symbols: 
  - "autoslide.agent.engine.AgentEngine"
  - "autoslide.agent.engine.AgentTurnResponse"
  - "autoslide.agent.engine.ToolCallRequest"
  - "autoslide.agent.engine.ToolCallResult"
  - "autoslide.agent.tools.ToolRegistry"
  - "autoslide.agent.tools.SlideToolset"
  - "autoslide.agent.tools.execute_tool"
  - "autoslide.api.chat_session_agent"
risk_level: LOW
---

# 📝 Sub Spec: Real Local Agent Engine, Toolset Dispatcher & Chat Endpoint

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Thay thế cơ chế mock/heuristic clarification bằng Real Local Agent Engine có năng lực suy luận tự nhiên, hiểu ngữ cảnh và tự động kích hoạt bộ 7 Tools chỉnh sửa/phân tích slide; đồng thời tích hợp endpoint `POST /api/v1/sessions/{session_id}/chat`.
> **Quyết định then chốt**: Xây dựng `AgentEngine` và `ToolRegistry` theo chuẩn Tool Calling; tích hợp với OOXML `DeckMutator` an toàn; lưu vết `ChatTurn` và `tool_calls` trong `ConversationSession`.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

Hiện thực hóa **Task 1** trong kế hoạch phát triển `ADS-003` (Real Local Agent Engine & Toolset Dispatcher):
1. **Real Local Agent Engine (`autoslide.agent.engine`)**:
   - Quản lý prompt hệ thống (System Persona chuyên gia PowerPoint / Slide Designer), duy trì lịch sử hội thoại nhiều lượt (`ChatTurn`), và điều phối vòng lặp gọi công cụ (Tool Calling Loop).
   - Có khả năng hiểu ngôn ngữ tự nhiên, phân tích logic, tính toán số liệu trên slide, và giải thích nội dung.
   - Hỗ trợ cả chế độ thực thi local deterministic runner / adapter lẫn LLM API streaming / tool calling.
2. **Toolset Registry & Dispatcher (`autoslide.agent.tools`)**:
   - Định nghĩa JSON Schema chuẩn mực cho 7 công cụ slide/deck:
     * `edit_slide_text(slide_index: int, target: str, new_text: str)`
     * `add_slide(layout: str, title: str, content_bullets: list[str], insert_at_index: int | None)`
     * `delete_slide(slide_index: int)`
     * `reorder_slide(from_index: int, to_index: int)`
     * `update_slide_style(slide_index: int, theme: str, layout_type: str | None)`
     * `analyze_slide_content(slide_index: int, query: str)`
     * `search_web(query: str)`
   - Cung cấp dispatcher kết nối trực tiếp với OOXML `DeckMutator` trên file `working/presentation.pptx` của session/job workspace, đảm bảo không làm hỏng cấu trúc file.
3. **Tích hợp API Endpoint (`autoslide.api`)**:
   - Cung cấp route `POST /api/v1/sessions/{session_id}/chat`:
     * Tiếp nhận message từ User.
     * Kích hoạt `AgentEngine.step(session, message, deck_context)`.
     * Tự động dispatch các tool calls, thực thi mutations trên deck, lấy danh sách `modified_slide_indices`.
     * Cập nhật và lưu `ConversationSession` (turns, state, tool call history).
     * Trả về payload gồm: `assistant_message`, `tool_calls`, `modified_slide_indices`, `state`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: `JobWorkspace` đã có sẵn tại `autoslide.jobs.workspace` và cung cấp đường dẫn đến `working/presentation.pptx` và `baseline/presentation.pptx`.
- [x] **Giả định**: `DeckMutator` và các OOXML mutators trong `autoslide.executor.mutator` hỗ trợ chỉnh sửa text, add slide, reorder slide, và style.
- [x] **Giả định**: `ConversationSession` và `SessionStore` từ `autoslide.conversation` cho phép lưu trữ an toàn các lượt chat và snapshot trạng thái.
- [x] **Rủi ro**: Khi Agent gọi nhiều tool liên tiếp trong một turn, thứ tự thực thi mutation có thể ảnh hưởng đến slide indices (ví dụ: `delete_slide` hoặc `add_slide` làm dịch chuyển index).
  - *Biện pháp*: Dispatcher thực thi tuần tự và cập nhật lại context inventory sau mỗi mutation có thay đổi cấu trúc deck.
- [x] **`[UNKNOWN]`**: [UNKNOWN: Hành vi khi không có API key LLM môi trường ngoài]
  - *Giải pháp đề xuất*: `AgentEngine` hỗ trợ chế độ Local Heuristic/Regex-Semantic Parser fallback thông minh cho 7 tools cốt lõi bên cạnh Remote/Local LLM Tool Calling Runner để đảm bảo toàn bộ unit test và local execution hoạt động deterministic 100% không phụ thuộc internet/API key.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/agent/__init__.py` | Create | Package initialization & exports cho `AgentEngine`, `ToolRegistry`, `SlideToolset` |
| `src/autoslide/agent/engine.py` | Create | `AgentEngine` điều phối hội thoại, prompt engineering, tool calling loop, analysis & calculation |
| `src/autoslide/agent/tools.py` | Create | `ToolRegistry`, JSON schemas và implementation cho 7 slide tools, dispatching tới OOXML mutator |
| `src/autoslide/api.py` | Modify | Thêm/cập nhật route `POST /api/v1/sessions/{session_id}/chat` kết nối `AgentEngine` |
| `tests/agent/__init__.py` | Create | Package marker cho tests của Agent module |
| `tests/agent/test_agent_engine.py` | Create | Unit tests cho `AgentEngine`: conversation history, reasoning, calculation, tool-calling loop |
| `tests/agent/test_agent_tools.py` | Create | Unit tests cho 7 tools: schema validation, tool execution trên sample presentation, OOXML mutation |
| `tests/api/test_agent_chat_api.py` | Create | Integration tests cho endpoint `POST /api/v1/sessions/{session_id}/chat` |

### Phân tích Logic Cốt lõi:
- **Tại sao cần ToolRegistry độc lập?** Tách biệt định nghĩa schema (dành cho LLM function calling) và logic thực thi (dispatcher) giúp hỗ trợ đa dạng runtime (`agy`, `claude`, `codex`, local model) mà không bị phụ thuộc vào định dạng riêng lẻ.
- **Sử dụng Pattern nào?** Command Pattern (cho Tool definitions & execution) kết hợp với Strategy / Adapter Pattern (cho LLM backend runtime) và Registry Pattern.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1.1**: `ToolRegistry.get_tools_schema()` trả về danh sách 7 tools với đầy đủ JSON schema hợp lệ (parameters, types, descriptions, required fields).
- [ ] **AC-1.2**: Tool `edit_slide_text` thay đổi đúng text của shape/title trên slide chỉ định và trả về kết quả thành công kèm slide index bị ảnh hưởng.
- [ ] **AC-1.3**: Tool `add_slide` thêm slide mới vào presentation với layout, title, content_bullets được truyền vào và trả về slide index mới.
- [ ] **AC-1.4**: Tool `delete_slide` xóa slide chỉ định khỏi presentation một cách an toàn.
- [ ] **AC-1.5**: Tool `reorder_slide` đổi vị trí slide từ `from_index` sang `to_index`.
- [ ] **AC-1.6**: Tool `update_slide_style` cập nhật theme/color style cho slide chỉ định.
- [ ] **AC-1.7**: Tool `analyze_slide_content` đọc nội dung slide, thực hiện phân tích/tính toán số liệu và trả về kết quả chính xác.
- [ ] **AC-1.8**: Tool `search_web` tìm kiếm thông tin và trả về kết quả tóm tắt kèm nguồn dẫn.
- [ ] **AC-1.9**: `AgentEngine.process_message()` xử lý yêu cầu người dùng, sinh phản hồi tự nhiên, kích hoạt đúng tool khi có yêu cầu thay đổi/phân tích deck.
- [ ] **AC-1.10**: Endpoint `POST /api/v1/sessions/{session_id}/chat` tiếp nhận tin nhắn, thực thi Agent workflow, cập nhật `ConversationSession`, và trả về `assistant_message`, `tool_calls`, `modified_slide_indices`.
- [ ] **AC-1.11**: Toàn bộ unit tests tại `tests/agent/` và `tests/api/test_agent_chat_api.py` chạy qua 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# Chạy focused test suite cho Agent Engine & Toolset
pytest tests/agent/test_agent_engine.py tests/agent/test_agent_tools.py tests/api/test_agent_chat_api.py -q -v

# Chạy toàn bộ test suite để đảm bảo không có hồi quy
pytest tests/ -q
```

### Manual QA
1. Khởi tạo một session mới với tệp PPTX mẫu qua `POST /api/v1/sessions`.
2. Gửi tin nhắn `POST /api/v1/sessions/{session_id}/chat` với nội dung *"Sửa tiêu đề slide 1 thành 'Báo Cáo Tài Chính Q3'"*.
3. Xác nhận response trả về có `tool_calls` chứa `edit_slide_text`, `modified_slide_indices: [1]`, và nội dung slide 1 trong file `working/presentation.pptx` đã được cập nhật chính xác.
4. Gửi tiếp tin nhắn yêu cầu phân tích/tính toán số liệu và kiểm tra câu trả lời của Agent.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: Là hạt nhân xử lý logic và công cụ của tính năng `ADS-003`, cung cấp API và dữ liệu cho Task 2 (`Full-Deck Ingest & Dual Render Sync`), Task 3 (`UI Studio Overhaul`), và Task 4 (`Browser Computer-Use QA`).
- **Related Sessions**: `[[.ai/specs/ADS-003/requirements.md]]`, `[[.ai/specs/ADS-003/design.md]]`, `[[.ai/specs/ADS-003/tasks.md]]`.
- **Code Graph**: `autoslide.agent` $\rightarrow$ `autoslide.executor.mutator`, `autoslide.conversation`, `autoslide.jobs.workspace`, `autoslide.api`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
