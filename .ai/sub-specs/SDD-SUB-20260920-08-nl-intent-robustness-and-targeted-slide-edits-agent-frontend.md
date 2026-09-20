---
id: SDD-SUB-20260920-08
title: Robust Natural Language Edit Intent Routing, Conversational Context Memory & Instant Slide Mutation
author: agent-frontend
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Khắc phục triệt để lỗi Chatbot chỉ hứa suông ('Dạ được chứ') mà không thực thi: Mở rộng bộ phân loại Intent sửa slide tiếng Việt tự nhiên ('sửa lại title slide 1 là ABC đi'), ghi nhớ ngữ cảnh hội thoại ('sửa đi', 'ok sửa đi') và thực thi ngay tool edit_slide_text / update_slide_style kèm re-render Canvas."
decisions: 
  - "Mở rộng toàn diện Regex Intent Sửa Slide: Nhận diện trọn vẹn các biến thể ngôn ngữ tự nhiên tiếng Việt như 'sửa lại', 'đổi lại', 'title', 'tiêu đề', 'là ABC đi', 'thành ABC', tự động bóc tách từ đệm cuối câu ('đi', 'nhé', 'nha', 'với', 'luôn', 'ngay')."
  - "Kế thừa Slide Context từ Active Session: Khi câu lệnh sửa không ghi rõ số slide (ví dụ 'sửa lại title là ABC'), tự động sử dụng `selected_slide_index` hoặc slide active hiện tại."
  - "Bộ nhớ Ngữ cảnh Hội thoại (Conversational Contextual Confirmation): Khi người dùng gửi các câu lệnh xác nhận ('sửa đi', 'ok sửa đi', 'sao cũng đc', 'custom sao cho đẹp'), Engine tra cứu lượt hội thoại trước trong `session.turns` để thực thi ngay thao tác sửa tiêu đề hoặc làm đẹp giao diện slide (`update_slide_style`)."
  - "Phản xạ Thực thi Trực quan (Instant Visual Mutation): Khi tool `edit_slide_text` hoặc `update_slide_style` chạy thành công, cập nhật file PPTX, gọi `render_slide_delta` làm mới ngay ảnh preview Before/After trên Canvas với viền hổ phách phát sáng và nhãn MODIFIED."
affected_symbols: 
  - "autoslide.agent.engine.AgentEngine._plan_tool_calls"
  - "autoslide.agent.engine.AgentEngine.process_message"
  - "autoslide.agent.tools.SlideToolset.edit_slide_text"
  - "autoslide.agent.tools.SlideToolset.update_slide_style"
  - "autoslide.ui.static.js.workbench.js"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Robust Natural Language Edit Intent Routing & Instant Slide Mutation

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Người dùng yêu cầu: *"sửa lại title slide 1 là ABC đi"*, *"custom sao cho đẹp tí"*, *"sửa đi"*, *"ok sửa đi"*. Hiện tại Chatbot chỉ trả lời dạng text hứa suông mà không gọi tool `edit_slide_text` / `update_slide_style`. Sub-Spec này mở rộng bộ phân loại Intent đa dạng, ghi nhớ ngữ cảnh hội thoại và đảm bảo 100% lệnh sửa được thực thi và cập nhật trực quan trên Canvas.
> **Quyết định then chốt**:
> - Regex Edit linh hoạt: Hỗ trợ cú pháp tiếng Việt phong phú (`sửa lại`, `đổi lại`, `cập nhật`, `thay`), hỗ trợ cả từ `title` lẫn `tiêu đề`, liên từ `là` và `thành`, bóc tách hậu tố ngữ khí (`đi`, `nhé`, `nha`, `với`).
> - Tự động định tuyến ngữ cảnh: Khi user nói *"sửa đi"*, *"ok sửa đi"* sau khi bot hỏi lại, bot trích xuất ngay giá trị đề xuất trước đó và thực thi tool ngay.
> - Hỗ trợ intent làm đẹp *"custom sao cho đẹp"*: Định tuyến tới `update_slide_style` với theme `canva_clean` hoặc `modern_dark`.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

1. **Nhận diện và thực thi lệnh sửa nội dung tự nhiên**:
   - Khi người dùng gửi *"sửa lại title slide 1 là ABC đi"*, *"đổi tiêu đề slide 1 thành ABC"*, hoặc *"sửa title slide 1 là ABC"*:
     - Bóc tách chính xác: `slide_index = 1`, `target = 'title'`, `new_text = 'ABC'`.
     - Thực thi ngay lập tức tool `edit_slide_text`.
     - Cập nhật slide 1 trên file PowerPoint và sinh lại ảnh Canvas After với tiêu đề "ABC" kèm viền MODIFIED màu hổ phách.
2. **Ghi nhớ ngữ cảnh hội thoại cho các câu lệnh nối tiếp**:
   - Khi người dùng nói *"sửa đi"*, *"ok sửa đi"*, *"làm đi"*:
     - Quét lịch sử hội thoại gần nhất (`session.turns`) để tìm câu lệnh sửa chưa thực hiện hoặc vừa được đề xuất, kích hoạt ngay tool tương ứng.
3. **Xử lý yêu cầu làm đẹp / custom giao diện**:
   - Khi người dùng nói *"custom sao cho đẹp tí"*, *"làm đẹp slide 1"*, *"sao cũng đc"*:
     - Thực thi `update_slide_style(slide_index=active_slide, theme='canva_clean')`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: `SlideToolset.edit_slide_text` và `update_slide_style` đã có sẵn trong `autoslide.agent.tools`, chỉ cần `_plan_tool_calls` nhận diện đúng và gọi.
- [x] **Rủi ro**: Chuỗi văn bản mới có thể dính các từ cảm thán nếu không lọc sạch $\rightarrow$ Đã bổ sung hàm làm sạch chuỗi `_clean_target_text()`.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/agent/engine.py` | Robust Intent Routing & Context Memory | Mở rộng patterns sửa slide; thêm logic quét turns trước khi user gửi lệnh ngắn ('sửa đi', 'ok sửa đi'); lọc hậu tố ngữ khí ('đi', 'nhé', 'với'). |
| `src/autoslide/agent/tools.py` | Theme & Visual Polish Support | Đảm bảo `update_slide_style` hỗ trợ theme `canva_clean` / `modern_dark` và kích hoạt re-render slide delta. |
| `tests/agent/test_agent_engine.py` | Comprehensive Intent Tests | Thêm các ca kiểm thử: "sửa lại title slide 1 là ABC đi", "sửa đi", "custom sao cho đẹp", "đổi tiêu đề slide 1 là ABC". |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] Lệnh *"sửa lại title slide 1 là ABC đi"* kích hoạt ngay tool `edit_slide_text(slide_index=1, new_text='ABC')`.
- [x] Lệnh *"sửa lại title slide 1 là ABC"* kích hoạt ngay tool `edit_slide_text(slide_index=1, new_text='ABC')`.
- [x] Lệnh *"sửa đi"*, *"ok sửa đi"* sau khi đề xuất sửa kích hoạt thực thi thay đổi ngay lập tức.
- [x] Lệnh *"custom sao cho đẹp tí"* kích hoạt `update_slide_style` và làm mới ảnh Canvas.
- [x] Toàn bộ 101+ tests tự động chạy pass 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/agent/ tests/ui/ tests/ingest/ tests/api/ -q
# Kết quả thực tế: 101 passed, 1 skipped, 2 warnings in 34.35s (100% pass)
```

### Manual QA
1. Mở `http://localhost:8001/`.
2. Tải file `icisn_2025_fusionnetx.pptx.pptx`.
3. Gõ: *"sửa lại title slide 1 là ABC đi"* $\rightarrow$ Tool Card `edit_slide_text` COMPLETED và Slide 1 trên Canvas đổi tiêu đề thành "ABC" với viền hổ phách.
4. Gõ: *"custom sao cho đẹp tí"* $\rightarrow$ Tool Card `update_slide_style` COMPLETED.
5. Gõ: *"ok sửa đi"* $\rightarrow$ Thực thi ngay lệnh sửa tiêu đề tương ứng.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Main Spec**: `[[.ai/specs/ADS-003/requirements.md]]`
- **Sub-Specs liên quan**: `[[.ai/sub-specs/SDD-SUB-20260920-06-slide-qa-chat-and-canvas-viewport-fix-agent-frontend.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-07-canva-slide-body-rendering-and-dynamic-chat-agent-frontend.md]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
