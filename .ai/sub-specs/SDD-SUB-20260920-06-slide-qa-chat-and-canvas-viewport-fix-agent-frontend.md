---
id: SDD-SUB-20260920-06
title: Slide Content Q&A Chatbot, Professional Filmstrip (16:9) & Dual-Canvas Viewport Fix
author: agent-frontend
status: COMPLETED # DRAFT | REVIEW | APPROVED | COMPLETED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Khắc phục triệt để lỗi UX/UI không thấy slide (mở rộng Filmstrip lên 16:9 chuyên nghiệp, xóa chồng chéo placeholder) và sửa Chatbot trả lời thông minh nội dung slide (giải quyết câu lặp lại vô nghĩa)."
decisions: 
  - "Nâng cấp Filmstrip Navigator: Thay đổi kích thước thumbnail từ 24x14px cực nhỏ lên chuẩn Studio 130x73px (16:9) hiển thị sắc nét từng trang slide như Google Slides/PowerPoint."
  - "Sửa lỗi Canvas Viewport: Xóa bỏ sự xung đột che khuất giữa slide-frame và deck-slides-list; tự động ẩn Placeholder 'Awaiting AI Mutations' và 'No Presentation Loaded' ngay khi session deck được tải; slide active chiếm vị trí trung tâm nổi bật."
  - "Nâng cấp Agent Chat Engine (Slide Content Q&A): Bổ sung khả năng nhận diện các câu hỏi tra cứu slide ('slide 1 có gì', 'nội dung slide X', 'tóm tắt slide X'); trích xuất chi tiết tiêu đề, các đoạn văn bản và số liệu thực tế từ PPTX để trả lời trực tiếp thay vì lặp lại câu mặc định."
  - "Đấu nối Real Agent Runtime cho các câu hỏi mở về bài thuyết trình."
affected_symbols: 
  - "autoslide.agent.engine.AgentEngine"
  - "autoslide.agent.tools.AgentToolRegistry"
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.css.workbench.css"
  - "autoslide.ui.static.js.workbench.js"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Slide Content Q&A Chatbot, Professional Filmstrip & Dual-Canvas Viewport Fix

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Khắc phục dứt điểm 2 lỗi người dùng phản hồi: (1) Giao diện không thấy slide do Filmstrip quá nhỏ (24x14px) và Canvas bị Placeholder che khuất; (2) Chatbot bị kẹt phản hồi cứng nhắc lặp lại khi người dùng hỏi "slide 1 có gì".
> **Quyết định then chốt**:
> - Tăng kích thước thumbnail Filmstrip lên chuẩn 16:9 chuyên nghiệp (130x73px) có thể đọc được nội dung.
> - Đồng bộ hóa Canvas: Hiển thị ngay ảnh slide active (1280x720) ở cả cột Before và After ngay khi upload thành công, ẩn triệt để các empty/awaiting placeholders.
> - Mở rộng `AgentEngine` hỗ trợ Q&A nội dung slide: Trích xuất trực tiếp toàn bộ văn bản, bullet points của slide mục tiêu để giải đáp chính xác câu hỏi của người dùng.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

1. **Khắc phục lỗi hiển thị Slide trên giao diện (Viewport & Filmstrip Fix)**:
   - **Filmstrip**: Kích thước thumbnail hiện tại chỉ có `24px x 14px` (quá nhỏ, không thể nhìn thấy gì). Cần tăng lên **130px x 73px** (chuẩn 16:9), border-radius 6px, background #18181b, border 1px solid rgba(255,255,255,0.1), flex-direction column, padding 0.4rem, gap 0.35rem.
   - **Canvas Area**: Tự động ẩn ngay `beforePlaceholder`, `beforeIngestState`, và `afterPlaceholder` ngay khi tệp PPTX được nạp. Khung `beforeImg` và `afterImg` lập tức hiển thị slide active với `z-index: 5` và `display: block`.

2. **Khắc phục lỗi Chatbot lặp lại vô nghĩa (Slide Q&A Engine)**:
   - Khi người dùng hỏi: *"slide 1 có gì"*, *"nội dung slide 1"*, *"tóm tắt slide 2"*, regex phân loại chính xác câu hỏi tra cứu slide và định tuyến tới `analyze_slide_content(slide_index=...)`.
   - `analyze_slide_content` trích xuất tiêu đề, đoạn văn bản, bullet points và số lượng shape.
   - `AgentEngine` trả về kết quả phân tích trực tiếp:
     *"Nội dung trên Slide {slide_index} bao gồm:\n• Tiêu đề: ...\n• Nội dung chi tiết: ...\n• Số lượng thành phần: ... shapes."*
     (hoàn toàn không lặp lại câu canned template).

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: Slide preview images 1280x720 đã được sinh thành công trong backend (đã kiểm chứng `before/1.png` - 17.5KB).
- [x] **Rủi ro**: Việc ẩn `afterPlaceholder` ban đầu đã đảm bảo khi có AI mutations vẫn kích hoạt được hiệu ứng `highlight-overlay-layer` và viền hổ phách phát sáng.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/agent/engine.py` | Q&A Intent Routing | Thêm pattern nhận diện câu hỏi về slide; trích xuất nội dung thực tế của slide từ PPTX và trả lời chi tiếp trực tiếp. |
| `src/autoslide/agent/tools.py` | Enhance Slide Reading | Cải tiến `analyze_slide_content` để trích xuất tiêu đề, bullet points, shape count; trả về văn bản format tự nhiên. |
| `src/autoslide/ui/static/css/workbench.css` | Filmstrip & Canvas Fix | Tăng kích thước `.filmstrip-thumb-preview` lên `130px x 73px`; `.filmstrip-item` chuyển sang column; `.slide-frame img` gán `z-index: 5`. |
| `src/autoslide/ui/static/js/workbench.js` | Instant Render Sync | Khi `renderDualColumnDeck` được gọi, lập tức ẩn `beforePlaceholder`, `afterPlaceholder`, `beforeIngestState`, nạp `loadPreviewImage` cho active slide. |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] Khi upload file PPTX, trên thanh Filmstrip hiển thị ngay các thumbnail kích thước lớn (130x73px) có thể nhìn rõ nội dung slide.
- [x] Khung Canvas trung tâm hiển thị ngay lập tức Slide 1 (ảnh 1280x720), không bị che bởi "No Presentation Loaded" hay "Awaiting AI Mutations".
- [x] Khi gõ tin nhắn: *"slide 1 có gì"* hoặc *"nội dung slide 1"*, Chatbot trả lời chi tiết tiêu đề và các nội dung văn bản có trên Slide 1 (KHÔNG CÒN câu lặp lại vô nghĩa).
- [x] Kiểm thử tự động đạt 100% pass rate.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/agent/ tests/ui/ tests/api/ -q
# Kết quả thực tế: 75 passed, 1 skipped, 2 warnings in 44.16s (100% pass)
```

### Manual QA
1. Mở `http://localhost:8001/`.
2. Tải lên tệp `icisn_2025_fusionnetx.pptx.pptx`.
3. Kiểm tra Filmstrip thumbnail kích thước 130x73px hiển thị rõ ràng.
4. Kiểm tra Slide 1 hiển thị sắc nét ở cả hai cột Before và After.
5. Gửi tin nhắn *"slide 1 có gì"* vào Chatbot và kiểm tra câu trả lời chi tiết.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Design Framework**: `[[.ai/skills/taste-skill/SKILL.md]]`
- **Sub-Specs liên quan**: `[[.ai/sub-specs/SDD-SUB-20260920-04-web-production-chatbot-vision-agent-frontend.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-05-taste-ui-slide-renderer-agent-frontend.md]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*

