---
id: SDD-SUB-20260920-07
title: Canva-Style Slide Content Rendering (Body Text, Bullets, White/Dark Themes) & Dynamic Chatbot Intelligence
author: agent-frontend
status: APPROVED # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Áp dụng phong cách Canva Clone (nền trắng chuyên nghiệp / dark theme linh hoạt) vẽ toàn bộ nội dung text, gạch đầu dòng, chỉ số thực tế từ PPTX lên slide; đồng thời nâng cấp Chatbot phản hồi hội thoại thông minh, xóa bỏ câu lặp vô nghĩa."
decisions: 
  - "Canva-Style Slide Rendering: Trích xuất 100% nội dung chữ (tiêu đề, phân đoạn, bullet points, danh sách, số liệu) từ từng slide trong file PPTX (`ppt/slides/slide*.xml`)."
  - "Vẽ nội dung thực tế thay thế wireframe: Thay thế các hình hộp xám tĩnh bằng typography phân cấp rõ ràng (Category Badge, Bold Title, Multi-line Content Cards, Bullet Lists với dấu `•`, Key Metrics, Footer) theo chuẩn Canva Clone."
  - "Hỗ trợ Theme Trắng / Tối (Canva White by Default): Slide render với nền trắng trang nhã (#ffffff), viền tinh tế (#e2e8f0), chữ sắc nét (#0f172a / #334155 / #64748b), hoặc chế độ Dark (#18181b) nếu chọn theme tối."
  - "Nâng cấp Chatbot Trí tuệ Hội thoại (Dynamic Chat Engine): Loại bỏ các câu trả lời tĩnh lặp lại cứng nhắc; tích hợp context slide đang chọn và khả năng sinh câu trả lời tự nhiên, linh hoạt cho mọi câu hỏi như 'hi', 'bạn là ai', 'tư vấn giúp tôi'."
  - "Sửa nhãn ngữ cảnh UI: Chỉ hiển thị huy hiệu '🎯 Slide X' khi câu hỏi hoặc thao tác thực sự nhắm vào slide cụ thể, không gắn nhầm vào các câu chào hỏi hay câu hỏi chung."
affected_symbols: 
  - "autoslide.ingest.renderer.generate_mock_slide_card"
  - "autoslide.ingest.renderer._extract_slide_titles_and_shapes"
  - "autoslide.ingest.renderer.MockPreviewRenderer"
  - "autoslide.agent.engine.AgentEngine"
  - "autoslide.ui.static.js.workbench.js"
  - "autoslide.ui.static.css.workbench.css"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Canva-Style Slide Content Rendering & Dynamic Chatbot Intelligence

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Giải quyết dứt điểm 2 phản hồi của người dùng:
> 1. Slide chỉ hiện tiêu đề, nội dung bên dưới là hình xám rỗng: Áp dụng kiến trúc hiển thị từ Canva Clone (`https://github.com/Davronov-Alimardon/canva-clone`), trích xuất toàn bộ text/bullet points từ PPTX và vẽ trực tiếp nội dung thật lên Canvas (mặc định nền trắng thanh lịch phong cách Canva hoặc dark theme).
> 2. Chatbot bị lặp lại: Người dùng gõ "hi", "bạn là ai" thì bot lặp lại nguyên một câu giới thiệu vô nghĩa kèm tag "🎯 Slide 1": Cải tiến Chat Engine và UI để xử lý hội thoại mượt mà, linh hoạt và theo ngữ cảnh bài thuyết trình.
> **Quyết định then chốt**:
> - Nâng cấp hàm bóc tách `_extract_slide_titles_and_shapes` thành `_extract_slide_content`: Bóc tách đầy đủ Tiêu đề (`title`), Danh sách nội dung (`bullet_points`), Phân đoạn (`paragraphs`), và Chỉ số (`metrics`).
> - Nâng cấp `generate_mock_slide_card`: Vẽ trực tiếp các khối văn bản thực tế, chia 1 hoặc 2 cột thẻ bài phong cách Canva, font chữ rõ ràng, có ngắt dòng (word-wrap) tự động.
> - Cải tạo `AgentEngine`: Kết nối bộ xử lý hội thoại tự nhiên theo ngữ cảnh bài thuyết trình hiện tại (session summary, slide count, slide text) thay vì hardcoded static string lặp lại.
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Hiển thị đầy đủ nội dung slide (Canva Presentation Renderer)**:
   - Thay thế toàn bộ các hình hộp placeholder bằng nội dung văn bản thực tế từ bài thuyết trình.
   - Định dạng typography chuẩn Canva Presentation:
     - Nền slide trắng thanh lịch (`#ffffff`), viền mỏng (`#e2e8f0`), đổ bóng nhẹ (`rgba(0,0,0,0.06)`).
     - Badge số trang & chuyên mục: `#f1f5f9` với chữ `#475569`.
     - Tiêu đề slide: Font chữ đậm kích thước lớn, màu `#0f172a`.
     - Thẻ nội dung / Bullet points: Khung thẻ bo góc (`#f8fafc`), viền `#e2e8f0`, chữ `#1e293b` với bullet `#3b82f6` hoặc `#f59e0b`.
     - Tự động ngắt dòng văn bản (Word-wrap) để không bị tràn chữ ra ngoài slide 16:9.
   - Khi slide được AI chỉnh sửa (`is_modified=True`), hiển thị viền hổ phách phát sáng (`#f59e0b`) và dải ruy-băng `MODIFIED` ở góc trên.

2. **Khắc phục Chatbot lặp lại vô nghĩa (Intelligent Conversational Chatbot)**:
   - Khi nhận được các câu chào ("hi", "hello", "bạn là ai", "bạn có thể làm gì"): Bot trả lời tự nhiên, thân thiện và giới thiệu ngắn gọn khả năng với tư cách là trợ lý thuyết trình chuyên nghiệp, tóm lược nhanh số slide hiện có trong deck nếu đã nạp.
   - Trả lời thông minh theo ngữ cảnh: Nếu người dùng hỏi chung chung về slide, bot tóm lược nội dung slide active hiện tại.
   - Sửa UI chat: Không tự động chèn huy hiệu `🎯 Slide 1` vào bong bóng chat khi câu hỏi là câu chào hoặc câu hỏi chung không có slide target.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**: File PPTX được nạp vào chứa các thẻ XML `a:p` và `a:t` trong `ppt/slides/slide*.xml`, có thể trích xuất trực tiếp bằng `zipfile` và `xml.etree.ElementTree` mà không cần thư viện ngoài.
- [x] **Rủi ro**: Slide có quá nhiều chữ có thể bị tràn nếu không chia cột hoặc cắt tỉa hợp lý $\rightarrow$ Giải pháp: Chia tối đa 2 cột thẻ hoặc tối đa 4-6 bullet points nổi bật nhất kèm ellipsis nếu quá dài.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/renderer.py` | Extract Full Text & Canva Card Draw | Bóc tách toàn bộ `paragraphs`/`bullet_points` từ XML; vẽ thẻ slide Canva nền trắng (`#ffffff`) với văn bản thực tế, bullet points, word-wrapping, và badge trạng thái. |
| `src/autoslide/agent/engine.py` | Dynamic Conversational Engine | Xử lý hội thoại tự nhiên đa dạng (greetings, persona, capability overview, deck context); không lặp lại 1 câu duy nhất. |
| `src/autoslide/ui/static/js/workbench.js` | Chat Context & Presentation Sync | Chỉ hiển thị tag `🎯 Slide X` khi tin nhắn thực sự liên quan đến thao tác/tra cứu slide; đồng bộ tức thì giao diện Canva. |
| `src/autoslide/ui/static/css/workbench.css` | Canva Presentation Canvas Styling | Căn chỉnh khung slide preview bóng bẩy, viền tinh tế, tương phản cao, đúng chuẩn Canva Presentation. |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Slide preview hiển thị đầy đủ tiêu đề VÀ các dòng nội dung / gạch đầu dòng thực tế của file PowerPoint đã upload.
- [ ] Giao diện slide có nền trắng thanh lịch chuẩn Canva Presentation, typography rõ nét, dễ đọc.
- [ ] Người dùng chat "hi", "bạn là ai", hoặc "bạn làm được gì": Bot trả lời tự nhiên, đa dạng, không bị lặp lại 1 câu duy nhất.
- [ ] Không gắn nhầm tag `🎯 Slide 1` cho các tin nhắn hội thoại chung.
- [ ] Toàn bộ 96+ tests tự động chạy pass 100%.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/ingest/ tests/agent/ tests/ui/ tests/api/ -q
```

### Manual QA
1. Mở `http://localhost:8001/`.
2. Tải lên file PowerPoint mẫu.
3. Xác nhận trên slide hiển thị đầy đủ các dòng chữ/gạch đầu dòng thực tế (không phải các ô xám rỗng).
4. Chat: "hi" $\rightarrow$ Kiểm tra câu trả lời tự nhiên.
5. Chat: "bạn là ai" $\rightarrow$ Kiểm tra câu trả lời giới thiệu trợ lý AI AutoSlide mà không lặp lại câu trước.
6. Chat: "slide 1 có gì" $\rightarrow$ Kiểm tra trả lời chi tiết nội dung slide 1.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Reference Framework**: [Davronov-Alimardon/canva-clone](https://github.com/Davronov-Alimardon/canva-clone)
- **UI Design System**: `[[.ai/skills/taste-skill/SKILL.md]]`
- **Sub-Specs liên quan**: `[[.ai/sub-specs/SDD-SUB-20260920-05-taste-ui-slide-renderer-agent-frontend.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-06-slide-qa-chat-and-canvas-viewport-fix-agent-frontend.md]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
