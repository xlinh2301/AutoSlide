---
id: SDD-SUB-20260920-09
title: Multi-turn Conversational Beautify, Session URL Persistence & Computer Use Visual Verification
author: agent-frontend
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Khắc phục triệt để lỗi hội thoại lặp ('sửa slide 1' -> 'sửa cho đẹp hơn' -> 'sửa đi'), lưu ngữ cảnh active slide, bổ sung URL parameter ?session_id=... cho session persistence và kiểm thử thị giác tự động mô phỏng Computer Use bằng Chrome headless."
decisions: 
  - "Mở rộng bộ intent beautify_patterns bắt trọn các biến thể 'sửa cho đẹp hơn', 'làm đẹp hơn', 'cho đẹp tí', 'đẹp hơn đi', 'chỉnh đẹp'."
  - "Lưu slide_index mục tiêu trong session/history để các câu lệnh tiếp nối như 'sửa cho đẹp hơn', 'sửa đi' tự động kế thừa slide 1 thay vì bị bỏ rơi."
  - "Cho phép confirm_patterns kích hoạt ngay update_slide_style(slide_index, 'clean_light') nếu lệnh trước đó là ý định làm đẹp."
  - "Hỗ trợ URL param ?session_id=... trong workbench.js để khôi phục tức thì toàn bộ Canvas khi tải lại trang hoặc kiểm tra bằng browser automation."
  - "Bổ sung trích xuất title từ PPTX trong get_session_deck API để deck card header luôn hiển thị tên slide thật thay vì để trống."
  - "Kiểm thử tự động chụp ảnh màn hình bằng Chrome headless (mô phỏng Computer Use) và view_file kiểm tra kết quả."
affected_symbols: 
  - "autoslide.agent.engine.AgentEngine._plan_tool_calls"
  - "autoslide.agent.engine.AgentEngine.process_message"
  - "autoslide.api.get_session_deck"
  - "static/js/workbench.js"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Multi-turn Conversational Beautify, Session URL Persistence & Computer Use Visual Verification

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Khắc phục triệt để lỗi hội thoại lặp ('sửa slide 1' -> 'sửa cho đẹp hơn' -> 'sửa đi'), lưu ngữ cảnh active slide, bổ sung URL parameter ?session_id=... cho session persistence và kiểm thử thị giác tự động mô phỏng Computer Use bằng Chrome headless.
> **Quyết định then chốt**: Mở rộng beautify regex, kế thừa slide context qua các lượt hội thoại, auto-load session bằng URL query param, và chụp ảnh browser đối soát.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)
- Khi người dùng tương tác tự nhiên:
  1. *"sửa slide 1"* $\rightarrow$ Ghi nhận Slide 1 là mục tiêu đang chọn.
  2. *"sửa cho đẹp hơn"* $\rightarrow$ Nhận diện ngay ý định `update_slide_style(slide_index=1, theme='clean_light')`.
  3. *"sửa đi"* hoặc *"ok sửa đi"* $\rightarrow$ Kích hoạt thực thi ngay lập tức, sinh ra ảnh delta `after/1.png` có viền amber glow và badge MODIFIED.
- Khi người dùng tải lại trang hoặc mở link `http://localhost:8001/?session_id=...`, giao diện tự động khôi phục toàn bộ Canvas Dual-Column và Filmstrip.
- Kiểm thử thị giác tự động mô phỏng Computer Use bằng Chrome headless chụp ảnh trình duyệt thực tế, lưu tại `computer_use_verified_delayed.png` và đối soát bằng thị giác.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [x] **Giả định**: Session API `/api/v1/sessions/{id}/deck` trả về đầy đủ mảng slide kèm link ảnh preview.
- [x] **Rủi ro**: Regex có thể xung đột giữa lệnh hỏi nội dung và lệnh sửa nếu không phân lớp thứ tự ưu tiên chính xác.
- [x] **`[UNKNOWN]`**: Môi trường WSL không có sẵn X11 server cục bộ nên sử dụng Windows Chrome binary headless để chụp ảnh giao diện người dùng.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/agent/engine.py` | Modify | Mở rộng `beautify_patterns` nhận diện `sửa cho đẹp hơn`, `làm đẹp hơn`, `đẹp hơn`; truy vết `last_mentioned_slide` qua các lượt trước; hỗ trợ `confirm_patterns` chạy beautify tool. |
| `src/autoslide/api.py` | Modify | Điền fallback title trong `get_session_deck` từ `_extract_slide_titles_and_shapes` nếu shape title rỗng. |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Đọc `new URLSearchParams(window.location.search).get("session_id")` khi `DOMContentLoaded` để tự động load deck & chat history. |
| `tests/agent/test_agent_engine.py` | Modify | Bổ sung test case chuỗi hội thoại `sửa slide 1` $\rightarrow$ `sửa cho đẹp hơn` $\rightarrow$ `sửa đi`. |

### Phân tích Logic Cốt lõi:
1. **Truy vết Active Slide trong Lịch sử Hội thoại**:
   Khi một tin nhắn chỉ đề cập `sửa cho đẹp hơn` mà không nói rõ slide số mấy, engine quét ngược các lượt trước trong `session.turns` để tìm slide index gần nhất (`sửa slide 1` $\rightarrow$ slide 1).
2. **Beautify Intent Expansion**:
   Bổ sung các mẫu câu:
   - `(?:sửa|chỉnh|làm|thay|biến)\s*(?:lại\s+)?(?:cho\s+)?(?:nó\s+)?(?:đẹp|xịn|pro|canva|chuyên nghiệp|bắt mắt)\s*(?:hơn|tí|chút|nhé|nha|đi)?`
3. **Session URL Restoration**:
   Cho phép người dùng hoặc công cụ browser automation mở thẳng `/?session_id=session_xxx` để xem ngay trạng thái hiện tại.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [x] Chuỗi lệnh *"sửa slide 1"* $\rightarrow$ *"sửa cho đẹp hơn"* kích hoạt ngay tool `update_slide_style(slide_index=1, theme='clean_light')`.
- [x] Chuỗi lệnh *"sửa slide 1"* $\rightarrow$ *"sửa đi"* kích hoạt ngay tool làm đẹp cho Slide 1.
- [x] Truy cập `/?session_id=...` tự động nạp deck và render danh sách slide lên Canvas.
- [x] Ảnh chụp màn hình từ Chrome headless xác nhận Slide 1 hiển thị đầy đủ tiêu đề, nội dung và sau khi sửa có viền MODIFIED.
- [x] Toàn bộ test suite chạy pass 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/agent/ tests/ui/ tests/ingest/ tests/api/ -q
```

### Computer Use Visual Verification
1. Dùng Windows Chrome headless mở `http://localhost:8001/?session_id=session_35ff18352cee`.
2. Gửi lệnh *"sửa cho đẹp hơn"* qua API chat.
3. Chụp ảnh màn hình toàn trang `computer_use_verified.png`.
4. Dùng `view_file` xem lại ảnh xác thực giao diện thực tế.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/specs/ADS-003/design.md]]`
- **Related Sessions**: `[[.ai/sub-specs/SDD-SUB-20260920-08-nl-intent-robustness-and-targeted-slide-edits-agent-frontend.md]]`
