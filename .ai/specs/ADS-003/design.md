# 📐 Technical Design: Real Local Agent Engine, Full-Deck Live Preview & Tool Calling Workspace (ADS-003)

> **Feature ID:** ADS-003  
> **Title:** Real Local Agent Engine, Full-Deck Live Preview & Tool Calling Workspace  
> **Status:** APPROVED  
> **Architect:** Centralized Orchestrator  
> **Created Date:** 2026-09-20  

---

## 1. Kiến Trúc Tổng Quan (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AutoSlide Studio Web UI                          │
│                                                                             │
│  ┌───────────────────────┐  ┌────────────────────────────────────────────┐  │
│  │     Filmstrip Track   │  │              Dual-Column Canvas            │  │
│  │ [Slide 1] [Slide 2].. │  │  ┌──────────────────┐ ┌─────────────────┐ │  │
│  └───────────────────────┘  │  │ Before (Original)│ │ After (Modified)│ │  │
│                             │  │   [Slide 1 Img]  │ │  [Slide 1 Img]  │ │  │
│  ┌───────────────────────┐  │  │   [Slide 2 Img]  │ │[Slide 2 Mod ⚡] │ │  │
│  │ Persistent Chat Rail  │  │  └──────────────────┘ └─────────────────┘ │  │
│  │ 🤖 Real Agent Stream  │  └────────────────────────────────────────────┘  │
│  │ ⚡ Tool Call Cards    │                                                   │
│  └───────────────────────┘                                                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / SSE / REST
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend Services                           │
│                                                                             │
│  ┌──────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐ │
│  │  Local Agent Runner  │  │  Tool Calling Engine │  │ Full-Deck Renderer │ │
│  │  (agy / LLM stream)  │  │  (Schemas & Actions) │  │ (LibreOffice/PyMu) │ │
│  └──────────┬───────────┘  └──────────┬──────────┘  └──────────┬─────────┘ │
│             │                         │                        │            │
│             ▼                         ▼                        ▼            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                 DeckMutator & OOXML Execution Engine                  │  │
│  │            (edit_text, add_slide, reorder, style, analyze)            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi Tiết Các Khối Thiết Kế (Module Design)

### 2.1. Real Local Agent Engine (`autoslide.agent.engine`)
- **Vai trò**: Thay thế mock clarification bằng engine AI có khả năng suy luận, hiểu ngữ cảnh và gọi tool.
- **Cơ chế Runtime**:
  - `AgentEngine`: Quản lý prompt hệ thống (system persona chuyên gia PowerPoint, hiểu cấu trúc JSON deck), lịch sử trò chuyện (`ChatTurn`), và vòng lặp Tool Calling (`tool_calls`).
  - Hỗ trợ cả Local CLI Subprocess (`agy`, `claude`) và tiêu chuẩn OpenAI-compatible / Anthropic / Gemini Tool Calling endpoint cục bộ.
  - Phản hồi dạng streaming hoặc structured JSON kèm danh sách tool calls.

### 2.2. Tool Calling Registry (`autoslide.agent.tools`)
Định nghĩa danh sách các tools có sẵn cho Agent:
```python
TOOLS = [
    {
        "name": "edit_slide_text",
        "description": "Edit or replace text within a specific shape or title on a slide",
        "parameters": {
            "type": "object",
            "properties": {
                "slide_index": {"type": "integer", "description": "1-based slide index"},
                "target": {"type": "string", "description": "Shape name, role ('title', 'body'), or existing text substring"},
                "new_text": {"type": "string", "description": "The replacement or formatted text"}
            },
            "required": ["slide_index", "target", "new_text"]
        }
    },
    {
        "name": "add_slide",
        "description": "Add a new slide to the presentation with title and content",
        "parameters": {
            "type": "object",
            "properties": {
                "layout": {"type": "string", "enum": ["title_and_content", "two_column", "section_header", "blank"]},
                "title": {"type": "string"},
                "content_bullets": {"type": "array", "items": {"type": "string"}},
                "insert_at_index": {"type": "integer", "description": "Optional 1-based position to insert at"}
            },
            "required": ["title", "content_bullets"]
        }
    },
    {
        "name": "delete_slide",
        "description": "Delete a slide from the presentation",
        "parameters": {
            "type": "object",
            "properties": {
                "slide_index": {"type": "integer", "description": "1-based slide index"}
            },
            "required": ["slide_index"]
        }
    },
    {
        "name": "reorder_slide",
        "description": "Move a slide from one position to another",
        "parameters": {
            "type": "object",
            "properties": {
                "from_index": {"type": "integer"},
                "to_index": {"type": "integer"}
            },
            "required": ["from_index", "to_index"]
        }
    },
    {
        "name": "update_slide_style",
        "description": "Update visual style, colors, or theme of a slide",
        "parameters": {
            "type": "object",
            "properties": {
                "slide_index": {"type": "integer"},
                "theme": {"type": "string", "enum": ["modern_dark", "clean_light", "corporate_blue", "vibrant_accent"]},
                "layout_type": {"type": "string"}
            },
            "required": ["slide_index", "theme"]
        }
    },
    {
        "name": "analyze_slide_content",
        "description": "Inspect slide text and numbers to perform calculations, analysis, or summaries",
        "parameters": {
            "type": "object",
            "properties": {
                "slide_index": {"type": "integer", "description": "1-based slide index, or 0 for entire presentation"},
                "query": {"type": "string", "description": "Analysis or calculation question"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for fresh factual information or statistics to include in slides",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }
]
```

### 2.3. Full-Deck Live Render & Visual Diff Engine (`autoslide.ingest.renderer`)
- **Ingest Ban Đầu**:
  - Khi tệp PPTX được tải lên, trích xuất toàn bộ slide, lưu bản sao `baseline.pptx` và `working.pptx`.
  - Sinh ảnh preview cho tất cả slide: `slide_1.png`, `slide_2.png`, ...
  - Cung cấp danh sách slide cho UI để render cả cột Before và After. Ban đầu `before_slides == after_slides`.
- **Live Re-render & Visual Highlighting**:
  - Khi một tool sửa đổi `working.pptx` (ví dụ `edit_slide_text` trên slide 1), hệ thống re-render slide 1, sinh `after_slide_1.png`.
  - Trả về payload cập nhật:
    ```json
    {
      "modified_slide_indices": [1],
      "slides": [
        {"index": 1, "before_url": "/api/v1/jobs/.../preview/1.png", "after_url": "/api/v1/jobs/.../after/1.png", "modified": true},
        {"index": 2, "before_url": "/api/v1/jobs/.../preview/2.png", "after_url": "/api/v1/jobs/.../preview/2.png", "modified": false}
      ]
    }
    ```
  - UI tự động highlight slide 1 ở cột After (viền xanh neon/vàng kèm huy hiệu `Modified`).

### 2.4. Giao Diện Studio & Chatbot Mới (`workbench.js` / `index.html` / `workbench.css`)
- **Dual-Column Canvas**:
  - Cột Trái (Original Deck): Hiển thị toàn bộ slide gốc theo dạng lưới/danh sách cuộn.
  - Cột Phải (Live Modified Deck): Hiển thị toàn bộ slide sau khi chỉnh sửa, cập nhật tức thì sau mỗi tool call.
- **Chat Rail Thường Trực**:
  - Hiển thị tin nhắn của User và AI Agent dưới dạng hội thoại tự nhiên mượt mà.
  - Thẻ Tool Calling (`ToolCallingCard`): Hiển thị animation quay khi tool đang chạy và icon tích xanh khi hoàn thành.
  - Nút Download PPTX hoàn thiện được ghim nổi bật ở thanh công cụ và trong chat.

---

## 3. Data Models & API Contract

### Endpoints:
1. `POST /api/v1/sessions`: Tạo session mới từ file PPTX tải lên $\rightarrow$ trả về `session_id`, `job_id`, và `initial_slides` (danh sách preview tất cả slide).
2. `POST /api/v1/sessions/{session_id}/chat`: Gửi tin nhắn tự nhiên cho Agent $\rightarrow$ Agent phản hồi streaming/text, tự động gọi tool, cập nhật deck, và trả về `assistant_message`, `tool_calls`, `modified_slides`.
3. `GET /api/v1/sessions/{session_id}/deck`: Lấy trạng thái hiện tại của toàn bộ slide (Before & After preview URLs, danh sách slide modified).
4. `GET /api/v1/jobs/{job_id}/artifacts/presentation.pptx`: Tải tệp PPTX đã sửa về máy.
