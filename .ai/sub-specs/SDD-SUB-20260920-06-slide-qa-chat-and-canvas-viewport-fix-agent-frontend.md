---
id: SDD-SUB-20260920-06
title: Slide Content Q&A Chatbot, Professional Filmstrip (16:9) & Dual-Canvas Viewport Fix
author: agent-frontend
status: APPROVED # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Khắc phục triệt để lỗi UX/UI không thấy slide (mở rộng Filmstrip lên 16:9 chuyên nghiệp, xóa chồng chéo placeholder) và sửa Chatbot trả lời thông minh nội dung slide (giải quyết câu lặp lại vô nghĩa)."
decisions: 
  - "Nâng cấp Filmstrip Navigator: Thay đổi kích thước thumbnail từ 24x14px cực nhỏ lên chuẩn Studio 140x79px (16:9) hiển thị sắc nét từng trang slide như Google Slides/PowerPoint."
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
> - Tăng kích thước thumbnail Filmstrip lên chuẩn 16:9 chuyên nghiệp (140x79px) có thể đọc được nội dung.
> - Đồng bộ hóa Canvas: Hiển thị ngay ảnh slide active (1280x720) ở cả cột Before và After ngay khi upload thành công, ẩn triệt để các empty/awaiting placeholders.
> - Mở rộng `AgentEngine` hỗ trợ Q&A nội dung slide: Trích xuất trực tiếp toàn bộ văn bản, bullet points của slide mục tiêu để giải đáp chính xác câu hỏi của người dùng.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Khắc phục lỗi hiển thị Slide trên giao diện (Viewport & Filmstrip Fix)**:
   - **Filmstrip**: Kích thước thumbnail hiện tại chỉ có `24px x 14px` (quá nhỏ, không thể nhìn thấy gì). Cần tăng lên **140px x 79px** (chuẩn 16:9), có viền active màu xanh/indigo, hover mượt mà, hiển thị rõ số trang và hình ảnh slide thu nhỏ.
   - **Canvas Area**: Tự động ẩn ngay `beforePlaceholder`, `beforeIngestState`, và `afterPlaceholder` ngay khi tệp PPTX được nạp. Khung `beforeImg` và `afterImg` lập tức hiển thị slide 1 (Before == After ban đầu) với độ phân giải cao và viền sắc nét.

2. **Khắc phục lỗi Chatbot lặp lại vô nghĩa (Slide Q&A Engine)**:
   - Hiện tại khi người dùng hỏi: *"slide 1 có gì"*, regex không khớp nên rơi vào nhánh fallback mặc định:
     `Tôi đã ghi nhận yêu cầu: "slide 1 có gì". Tôi sẵn sàng thực hiện các thay đổi hoặc hỗ trợ thêm cho bài thuyết trình của bạn.`
   - **Giải pháp**:
     * Thêm cơ chế nhận diện câu hỏi tra cứu slide: `r"(?:slide|trang)\s*(\d+)?\s*(?:có gì|nội dung|viết gì|gồm những gì|là gì|thế nào)"` và các biến thể tương đương.
     * Khi phát hiện câu hỏi về slide `X`: Đọc trực tiếp nội dung các text shapes trên slide `X` từ tệp PPTX (`working_pptx_path`).
     * Trả về câu trả lời tự nhiên, tường minh:
       *"Trên Slide {X}, nội dung gồm có:\n- Tiêu đề: {title}\n- Các nội dung chính: {bullets/paragraphs}\n- Số lượng thành phần: {shape_count} objects."*
     * Hỗ trợ hỏi đáp tổng quan cả bài thuyết trình hoặc so sánh slide.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: Slide preview images 1280x720 đã được sinh thành công trong backend (đã kiểm chứng `before/1.png` - 17.5KB).
- [ ] **Rủi ro**: Việc ẩn `afterPlaceholder` ban đầu cần đảm bảo khi có AI mutations vẫn kích hoạt được hiệu ứng `highlight-overlay-layer` và viền hổ phách phát sáng.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/agent/engine.py` | Q&A Intent Routing | Thêm pattern nhận diện câu hỏi về slide; trích xuất nội dung thực tế của slide từ PPTX và trả lời chi tiết, thay thế fallback message. |
| `src/autoslide/agent/tools.py` | Enhance Slide Reading | Cải tiến `analyze_slide_content` để format kết quả phân tích slide đẹp mắt, dễ đọc với gạch đầu dòng rõ ràng. |
| `src/autoslide/ui/static/css/workbench.css` | Filmstrip & Canvas Fix | Tăng kích thước `.filmstrip-thumb-preview` lên `140px x 79px`; tối ưu `.slide-frame img` hiển thị nổi bật; loại bỏ che khuất của các lớp overlay. |
| `src/autoslide/ui/static/js/workbench.js` | Instant Render Sync | Khi `renderDualColumnDeck` được gọi, lập tức nạp `loadPreviewImage` cho slide 1, ẩn tất cả placeholder và hiển thị đồng thời cả slide viewer và deck list. |
| `src/autoslide/ui/templates/index.html` | Layout Balance | Cân đối bố cục giữa khung xem slide lớn (Hero Viewer) và danh sách slide toàn bộ deck. |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Khi upload file PPTX, trên thanh Filmstrip hiển thị ngay các thumbnail kích thước lớn (140x79px) có thể nhìn rõ nội dung slide.
- [ ] Khung Canvas trung tâm hiển thị ngay lập tức Slide 1 (ảnh 1280x720), không bị che bởi "No Presentation Loaded" hay "Awaiting AI Mutations".
- [ ] Khi gõ tin nhắn: *"slide 1 có gì"* hoặc *"nội dung slide 1"*, Chatbot trả lời chi tiết tiêu đề và các nội dung văn bản có trên Slide 1 (KHÔNG CÒN câu lặp lại vô nghĩa).
- [ ] Kiểm thử tự động đạt 100% pass rate.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/agent/ tests/ui/ tests/api/ -q
```

### Manual QA
1. Mở `http://localhost:8001/`.
2. Tải lên tệp `icisn_2025_fusionnetx.pptx.pptx`.
3. Kiểm tra Filmstrip thumbnail kích thước 140x79px hiển thị rõ ràng.
4. Kiểm tra Slide 1 hiển thị sắc nét ở cả hai cột Before và After.
5. Gửi tin nhắn *"slide 1 có gì"* vào Chatbot và kiểm tra câu trả lời chi tiết.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Design Framework**: `[[.ai/skills/taste-skill/SKILL.md]]`
- **Sub-Specs liên quan**: `[[.ai/sub-specs/SDD-SUB-20260920-04-web-production-chatbot-vision-agent-frontend.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-05-taste-ui-slide-renderer-agent-frontend.md]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
