# 📋 Feature Requirements: Real Local Agent Engine, Full-Deck Live Preview & Tool Calling Workspace (ADS-003)

> **Feature ID:** ADS-003  
> **Title:** Real Local Agent Engine, Full-Deck Live Preview & Tool Calling Workspace  
> **Status:** APPROVED  
> **Scope:** Replace mock/heuristic conversation with real local Agent CLI / Tool Calling runtime, render all slides with Before/After parity, live visual change highlighting, allowlisted slide/deck tools, and end-to-end computer-use browser QA.  
> **Author:** Centralized Orchestrator  
> **Created Date:** 2026-09-20  

---

## 1. Bối cảnh & Vấn đề Cần Giải Quyết (Problem Statement)

Hiện tại, hệ thống AutoSlide Studio đang gặp các giới hạn trải nghiệm nghiêm trọng:
1. **Chatbot dựa trên quy tắc/mẫu giả định (Mock / Heuristic Clarification Loop)**: Chatbot hiện tại sử dụng engine phân loại cứng nhắc, lặp lại câu hỏi làm rõ khuôn mẫu (như *"What should the new text on slide 1 be?"*) kể cả khi người dùng cung cấp câu trả lời, không có khả năng hiểu ngữ cảnh tự nhiên, phân tích hay tính toán.
2. **Thiếu kết nối với Real Agent Runtime & Tool Calling**: Người dùng không được tương tác với một AI Agent thông minh thực sự có khả năng suy luận, hiểu ngôn ngữ tự nhiên và tự động triệu hồi các Tools để sửa đổi slide, tìm kiếm web hay phân tích nội dung.
3. **Hiển thị Slide đơn lẻ và thiếu tính trực quan Before / After**: Khi import bài thuyết trình, giao diện chưa hiển thị đầy đủ tất cả các slide; chưa có cơ chế hiển thị song song 2 cột Before và After (ban đầu Before == After), và chưa highlight rõ ràng vị trí thay đổi (Visual Diff) trên slide ở cột After sau khi sửa.

---

## 2. Mục tiêu Năng lực (Feature Objectives)

1. **Tích hợp Real Local Agent Engine**:
   - Thay thế toàn bộ logic mock clarification bằng runtime AI Agent thực thụ (Local CLI / Subprocess Runner / Tool Calling Streaming Engine).
   - Cho phép người dùng trò chuyện tự nhiên, yêu cầu chỉnh sửa, phân tích số liệu, tính toán, tóm tắt bài thuyết trình, hoặc tìm kiếm thông tin bên ngoài.
2. **Hệ thống Tool Calling hoàn chỉnh (First-Class Agent Toolset)**:
   - Cung cấp bộ công cụ an toàn và chuẩn hóa cho Agent:
     * `edit_slide_text(slide_index, shape_id_or_target, new_text)`
     * `add_slide(layout, title, content_bullets)`
     * `delete_slide(slide_index)`
     * `reorder_slide(from_index, to_index)`
     * `update_slide_style(slide_index, theme, layout_type)`
     * `analyze_slide_content(slide_index_or_all, query)` (tính toán, đếm, phân tích logic)
     * `search_web(query)` (nghiên cứu web và dẫn nguồn)
   - Hiển thị trực quan Tool Call Cards trong dòng chat khi Agent kích hoạt tool.
3. **Hiển thị Toàn bộ Slide & Dual-Column Live Render (Before / After Parity)**:
   - Khi import PPTX: Tự động render 100% tất cả các slide thành ảnh preview chất lượng cao.
   - Cột Bên Trái (Before): Hiển thị toàn bộ slide của tệp gốc ban đầu.
   - Cột Bên Phải (After): Ban đầu giống hệt Before (Before == After).
   - Khi Agent gọi tool sửa slide: Cột After lập tức cập nhật re-render slide bị sửa đổi và kích hoạt **Visual Highlight** (viền màu kèm badge "Modified") tại slide/vùng bị sửa.
4. **Kiểm thử Trình duyệt Thực tế (Computer Use / Playwright E2E UI QA)**:
   - Mô phỏng 100% hành vi người dùng thực tế trên trình duyệt bằng Playwright.

---

## 3. User Stories (Ma Trận Yêu Cầu Người Dùng)

| ID | User Story | Tiêu chí Nghiệm thu Cốt lõi |
|:---|:---|:---|
| **US-01** | **Trò chuyện với Agent Thực thụ**: Người dùng trò chuyện tự nhiên với Agent trong Chat Rail, Agent trả lời thông minh, không bị lặp câu hỏi khuôn mẫu. | Tích hợp Local Agent Runner; hỗ trợ hội thoại đa lượt, phân tích ngữ cảnh và streaming text. |
| **US-02** | **Tự động Gọi Tool Sửa Slide**: Khi người dùng yêu cầu (ví dụ: *"Sửa tiêu đề slide 1 thành Báo cáo Q3"*, *"Thêm slide kết luận"*), Agent tự động kích hoạt tool tương ứng. | Agent sinh tool call hợp lệ; backend thực thi OOXML mutation an toàn và trả kết quả cho Agent. |
| **US-03** | **Phân tích & Tính toán Số liệu**: Người dùng yêu cầu Agent phân tích nội dung, đếm chữ, tính toán tổng doanh số trong slide. | Agent sử dụng tool `analyze_slide_content` để đọc dữ liệu thô và trả lời chính xác. |
| **US-04** | **Xem Toàn bộ Slide & Before/After Sync**: Khi tải file PPTX lên, toàn bộ slide được hiển thị ở cả 2 cột Before và After (ban đầu giống nhau 100%). | Render toàn bộ slide; filmstrip và canvas hiển thị đầy đủ danh sách slide. |
| **US-05** | **Visual Highlight khi Thay đổi**: Sau khi Agent thực thi tool sửa slide, cột After cập nhật ngay và hiển thị viền/badge đánh dấu slide thay đổi. | Re-render slide bị ảnh hưởng; hiển thị highlight viền và thông tin thay đổi. |
| **US-06** | **Tải xuống Slide Hoàn thiện**: Người dùng xem xét kết quả và tải file PPTX đã sửa về máy. | Cung cấp link download PPTX hợp lệ; file gốc được bảo toàn không ghi đè. |

---

## 4. Functional Requirements (FR)

- **FR-01 (Agent Runtime)**: Cung cấp `LocalAgentEngine` có khả năng giao tiếp với LLM / Local CLI runtime (`agy`, `claude`, `codex`, hoặc OpenRouter/Local LLM) với hỗ trợ Function/Tool Calling.
- **FR-02 (Tool Registry)**: Định nghĩa `ToolRegistry` chuẩn hóa định dạng JSON schema cho tất cả các thao tác slide (`edit_slide_text`, `add_slide`, `delete_slide`, `reorder_slide`, `update_slide_style`, `analyze_slide_content`, `search_web`).
- **FR-03 (Full-Deck Ingest & Preview)**: Module Ingest tự động xuất hình ảnh (thumbnails và high-res) cho 100% số slide trong deck khi tải lên.
- **FR-04 (Dual-Column Synchronization)**: Giao diện Studio hiển thị 2 cột Before (Deck gốc) và After (Deck chỉnh sửa). Ban đầu Before == After.
- **FR-05 (Live Delta Re-render & Visual Highlight)**: Sau mỗi tool mutation, hệ thống chỉ re-render các slide bị thay đổi, cập nhật After frame và gắn cờ trực quan `modified: true`.
- **FR-06 (Chat Streaming & Tool Cards)**: Giao diện Chatbot hiển thị hội thoại mượt mà kèm các Card trực quan khi Agent gọi tool (`ToolCallingCard`, `ToolResultCard`).
- **FR-07 (Computer Use Browser E2E QA)**: Bộ kịch bản Playwright E2E mô phỏng thao tác người dùng: upload PPTX, kiểm tra toàn bộ slide Before==After, chat yêu cầu sửa/thêm slide/tính toán, xác nhận Agent gọi tool, xác nhận After cập nhật và highlight.

---

## 5. Tiêu chí Nghiệm thu Tổng thể (Acceptance Criteria)

- [ ] **AC-01**: Tải lên tệp PPTX hiển thị toàn bộ slide ở cả cột Before và After (Before == After 100%).
- [ ] **AC-02**: Chatbot kết nối với Real Local Agent Engine, phản hồi tự nhiên, hỗ trợ giải thích, phân tích và tính toán số liệu trên slide.
- [ ] **AC-03**: Khi người dùng yêu cầu chỉnh sửa/thêm/xóa/đổi style slide, Agent tự động gọi đúng tool trong Toolset.
- [ ] **AC-04**: Tool call được hiển thị trực quan trong Chat Rail (tên tool, tham số, trạng thái).
- [ ] **AC-05**: Sau khi tool hoàn tất, cột After tự động cập nhật và highlight rõ ràng slide bị sửa đổi.
- [ ] **AC-06**: Người dùng có thể tải về tệp PPTX đã sửa đổi với định dạng OOXML nguyên vẹn.
- [ ] **AC-07**: Toàn bộ kịch bản Playwright E2E mô phỏng góc nhìn người dùng thực tế vượt qua 100% không có lỗi.
