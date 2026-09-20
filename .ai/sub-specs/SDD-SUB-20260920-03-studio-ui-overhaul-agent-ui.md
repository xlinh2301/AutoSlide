---
id: SDD-SUB-20260920-03
title: Dual-Column Canvas, Visual Change Highlights & Tool Calling Chat Rail
author: agent-ui
status: COMPLETED # DRAFT | REVIEW | APPROVED | MERGED | COMPLETED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Nâng cấp giao diện Studio với Dual-Column Canvas hiển thị toàn bộ slide Trước/Sau, Visual Change Highlights cho slide sửa đổi, và Chat Rail kết nối Real Agent Engine với các thẻ Tool Calling trực quan."
decisions: 
  - "Xây dựng Dual-Column Canvas hiển thị toàn bộ danh sách slide cho cả 2 cột Before (Gốc) và After (Chỉnh sửa), ban đầu Before == After 100%."
  - "Triển khai Visual Change Highlights với viền phát sáng (luminous border), huy hiệu MODIFIED, và overlays trên slide bị thay đổi ở cột After."
  - "Tích hợp Chat Rail với endpoint POST /api/v1/sessions/{session_id}/chat để hội thoại tự nhiên với Real Agent Engine và tự động reload deck qua GET /api/v1/sessions/{session_id}/deck."
  - "Thiết kế các component ToolCallingCard và ToolResultCard hiển thị sinh động trạng thái thực thi tool (name, arguments, status, affected slides) trong dòng chat."
  - "Đồng bộ hóa tương tác giữa Filmstrip và Canvas: click chọn slide cuộn mượt đến vị trí slide tương ứng trong Canvas và ngược lại."
affected_symbols: 
  - "autoslide.ui.templates.index.html"
  - "autoslide.ui.static.css.workbench.css"
  - "autoslide.ui.static.js.workbench.js"
  - "tests.ui.test_studio_ui"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Dual-Column Canvas, Visual Change Highlights & Tool Calling Chat Rail

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Nâng cấp toàn diện AutoSlide Studio Web UI đáp ứng đầy đủ yêu cầu của Task 3 trong feature `ADS-003`: Dual-Column Canvas hiển thị toàn bộ slide song song (Before / After), cơ chế Visual Change Highlight (viền màu phát sáng và badge MODIFIED) trên cột After, Chat Rail kết nối trực tiếp với Real Agent Engine qua `POST /api/v1/sessions/{session_id}/chat`, các thẻ Tool Calling (`ToolCallingCard` & `ToolResultCard`) trực quan, và đồng bộ điều hướng mượt mà giữa Filmstrip và Canvas.
> **Quyết định then chốt**:
> - Hiển thị 100% slide ở cả 2 cột Before và After với dữ liệu từ `GET /api/v1/sessions/{session_id}/deck`.
> - Tự động cập nhật delta preview và highlight slide thay đổi ngay sau khi Agent kết thúc tool call.
> - Hỗ trợ các thẻ hiển thị tool call và kết quả tool call trong chat stream.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/COMPLETED

---

## 1. Mục tiêu (Objective)

Hiện thực hóa **Task 3** trong kế hoạch phát triển `ADS-003` (Dual-Column Canvas, Visual Change Highlights & Tool Calling Chat Rail):

1. **Dual-Column Canvas (Before / After Parity)**:
   - Thay thế chế độ hiển thị 1 slide đơn lẻ bằng Canvas 2 cột song song hiển thị toàn bộ danh sách slide của bài thuyết trình:
     * Cột Bên Trái (**Before / Original Deck**): Hiển thị toàn bộ slide của tệp ban đầu (`before_url` từ `GET /api/v1/sessions/{session_id}/deck`).
     * Cột Bên Phải (**After / Live Modified Deck**): Hiển thị toàn bộ slide sau khi áp dụng các thay đổi (`after_url`). Ban đầu khi vừa upload, Before == After 100%.
   - Hỗ trợ cuộn độc lập hoặc cuộn đồng bộ trực quan giữa 2 cột.

2. **Visual Change Highlights & Badges**:
   - Khi một hoặc nhiều slide bị thay đổi bởi Agent Tool Call (dựa vào `modified_slide_indices` và `modified: true` từ API):
     * Cột After kích hoạt viền phát sáng (luminous outline / neon-amber border glow) trên slide frame bị sửa đổi.
     * Hiển thị huy hiệu `MODIFIED` nổi bật trên góc slide item.
     * Cập nhật tức thời ảnh After mới (`after_url?t=timestamp`) mà không ảnh hưởng tới cột Before.

3. **Tool Calling Chat Rail & Synchronized Navigation**:
   - Nâng cấp Chat Rail kết nối với endpoint `POST /api/v1/sessions/{session_id}/chat` của Real Agent Engine (đã hoàn thành trong Task 1).
   - Hiển thị trực quan các thẻ tương tác gọi công cụ của Agent:
     * `ToolCallingCard`: Hiển thị tên tool (ví dụ `edit_slide_text`, `add_slide`, `analyze_slide_content`), tham số thực thi, và biểu tượng trạng thái đang chạy.
     * `ToolResultCard`: Hiển thị kết quả thực thi (thành công / cảnh báo / số slide bị tác động).
   - Tự động kích hoạt tải lại deck state (`GET /api/v1/sessions/{session_id}/deck`) sau khi Agent phản hồi có `modified_slide_indices`.
   - Đồng bộ hóa chặt chẽ giữa **Filmstrip** và **Canvas**:
     * Nhấp vào một slide trên Filmstrip sẽ cuộn mượt (smooth scroll) Canvas đến đúng vị trí slide đó.
     * Nhấp vào slide trong Canvas sẽ đồng bộ active state lên Filmstrip và cập nhật `chatSelectionContext`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [x] **Giả định**:
  - Endpoint `POST /api/v1/sessions/{session_id}/chat` đã hoạt động ổn định và trả về `assistant_message`, `tool_calls`, `modified_slide_indices`.
  - Endpoint `GET /api/v1/sessions/{session_id}/deck` trả về danh sách đầy đủ `DeckSlideState` với `before_url`, `after_url`, `modified`, `title`.
  - Toàn bộ frontend tuân thủ nguyên tắc Zero External Dependencies (không CDN, không web font ngoài, thuần túy HTML/CSS/Vanilla JS).
- [x] **Rủi ro**:
  - Bài thuyết trình có nhiều slide (ví dụ >20 slide) có thể làm chậm giao diện nếu DOM được render lại hoàn toàn sau mỗi tin nhắn chat.
  - *Biện pháp giải quyết*: Áp dụng kỹ thuật Diffing / Update tại chỗ cho các slide item: chỉ thay đổi thuộc tính `src` của `<img>` và toggle class `modified` trên các slide có `modified: true`, không xóa và dựng lại toàn bộ DOM container nếu số lượng slide không đổi.
- [ ] **`[UNKNOWN]`**:
  - [UNKNOWN: Hành vi đồng bộ cuộn giữa cột Before và cột After khi có thao tác `add_slide` hoặc `delete_slide` dẫn đến số lượng slide 2 cột lệch nhau]
  - *Giải pháp thiết kế*: Cột Before giữ nguyên danh sách slide gốc ban đầu; cột After hiển thị danh sách slide hiện tại. Khi cuộn tới slide index $i$, hệ thống định vị vị trí slide $i$ tương ứng trên cả 2 cột; nếu slide $i$ ở cột Before không tồn tại (do slide mới được thêm vào After), hiển thị card placeholder "Slide Mới Thêm (New Slide)".

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ui/templates/index.html` | Modify | Nâng cấp cấu trúc `canvas-diff-container` hỗ trợ Dual-Column Deck Canvas (danh sách slide 2 cột song song Before/After); bổ sung container cho Tool Calling Cards trong Chat Rail |
| `src/autoslide/ui/static/css/workbench.css` | Modify | Bổ sung styles cho Dual-Column Canvas grid, slide deck list 2 cột, luminous highlight viền xanh/amber (`slide-modified-glow`), badge `MODIFIED`, và styles cho `ToolCallingCard` & `ToolResultCard` |
| `src/autoslide/ui/static/js/workbench.js` | Modify | Tích hợp gửi tin nhắn tới `POST /api/v1/sessions/{session_id}/chat`; render `ToolCallingCard` & `ToolResultCard`; fetch và render toàn bộ slide từ `GET /api/v1/sessions/{session_id}/deck`; đồng bộ cuộn giữa Filmstrip và Canvas |
| `tests/ui/test_studio_ui.py` | Create | Bộ test contract UI kiểm thử: cấu trúc Dual-Column Canvas, hiển thị Before==After ban đầu, cơ chế Visual Change Highlight, rendering Tool Calling Cards, và Zero External Dependencies |

### Phân tích Logic Cốt lõi:
- **Tại sao cần Dual-Column Canvas hiển thị toàn bộ slide?**
  Trước đây giao diện chỉ hiển thị 1 slide duy nhất tại một thời điểm, khiến người dùng không có cái nhìn tổng quan về toàn bộ bài thuyết trình và không so sánh được ngay lập tức sự khác biệt giữa bài thuyết trình gốc và bài đã sửa đổi. Dual-Column Canvas cho phép quan sát song song toàn bộ deck Before và After.
- **Sử dụng Pattern nào?**
  * Container-Presentational Pattern cho các thành phần giao diện.
  * Reactive Event Synchronization Pattern cho việc đồng bộ trạng thái giữa Chat Rail, Filmstrip và Dual-Column Canvas.
  * Optimistic UI / Delta Invalidation Pattern cho việc cập nhật After slide thumbnails khi nhận được `modified_slide_indices`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [x] **AC-3.1**: Dual-Column Canvas hiển thị 2 cột song song rõ ràng: Cột Trái (Before / Original Deck) và Cột Phải (After / Live Modified Deck).
- [x] **AC-3.2**: Khi tải tệp PPTX lên, toàn bộ các slide được render và hiển thị đầy đủ trên cả cột Before và cột After với độ tương đồng 100% (Before == After, ban đầu không có slide nào bị đánh dấu modified).
- [x] **AC-3.3**: Khi Agent thực thi tool sửa đổi slide (ví dụ `edit_slide_text`, `update_slide_style`), slide bị sửa đổi ở cột After kích hoạt **Visual Change Highlight**: viền phát sáng nổi bật và huy hiệu `MODIFIED`.
- [x] **AC-3.4**: Chat Rail gửi tin nhắn tới endpoint `POST /api/v1/sessions/{session_id}/chat` và nhận phản hồi tự nhiên từ Real Agent Engine.
- [x] **AC-3.5**: Khi Agent gọi tool, Chat Rail hiển thị trực quan các thẻ `ToolCallingCard` (thể hiện tool name, parameters, status) và `ToolResultCard` (thể hiện kết quả thực thi và danh sách slide bị ảnh hưởng).
- [x] **AC-3.6**: Sau khi Agent hoàn tất tool calling và trả về `modified_slide_indices`, frontend tự động gọi `GET /api/v1/sessions/{session_id}/deck` để cập nhật thumbnail cột After và Filmstrip.
- [x] **AC-3.7**: Thao tác nhấp chọn slide trên Filmstrip tự động cuộn Canvas đến slide tương ứng, và nhấp vào slide trên Canvas tự động đồng bộ selection state trên Filmstrip.
- [x] **AC-3.8**: Toàn bộ giao diện tiếp tục tuân thủ nghiêm ngặt Zero External Frontend Dependencies (không dùng CDN, không gọi tài nguyên ngoài).
- [x] **AC-3.9**: Toàn bộ unit và contract tests tại `tests/ui/test_studio_ui.py` chạy qua 100% không có lỗi.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# Chạy bộ kiểm thử UI contract và behavior tests
pytest tests/ui/test_studio_ui.py tests/ui/test_ui_behavior.py tests/ui/test_conversation_ui.py -q -v

# Kiểm tra đảm bảo không có link CDN hoặc phụ thuộc ngoài trong HTML và CSS
pytest tests/ui/test_ui_behavior.py -k "test_zero_external_frontend_dependencies" -q -v
```

### Manual QA
1. Mở AutoSlide Studio trên trình duyệt, kéo thả tệp PPTX (ví dụ `demo.pptx` có 3 slide).
2. Xác nhận 100% số slide hiển thị đồng thời ở cả Cột Trái (Before) và Cột Phải (After) giống nhau hoàn toàn.
3. Trong Chat Rail, gõ tin nhắn: *"Sửa tiêu đề slide 1 thành 'Báo Cáo Tài Chính Q3'"*.
4. Quan sát Chat Rail: Thẻ `ToolCallingCard` xuất hiện với tool `edit_slide_text`, sau đó hiển thị `ToolResultCard` thành công.
5. Quan sát Cột Phải (After): Slide 1 được cập nhật ảnh mới, viền phát sáng kích hoạt và huy hiệu `MODIFIED` xuất hiện rõ ràng.
6. Nhấp vào slide 2 trên Filmstrip: Canvas tự động cuộn mượt đến vị trí slide 2 ở cả 2 cột.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Impact Analysis**: Là bước hoàn thiện trải nghiệm giao diện người dùng trung tâm của tính năng `ADS-003`, kết nối các năng lực từ Task 1 (`Real Agent Engine & Toolset Dispatcher`) và Task 2 (`Full-Deck Ingest & Dual Render Sync`), đồng thời là nền tảng trực quan cho Task 4 (`Computer-Use Browser E2E Automation`).
- **Related Sessions**: `[[.ai/specs/ADS-003/requirements.md]]`, `[[.ai/specs/ADS-003/design.md]]`, `[[.ai/specs/ADS-003/tasks.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-01-agent-engine-agent-backend.md]]`, `[[.ai/sub-specs/SDD-SUB-20260920-02-full-deck-render-agent-render.md]]`.
- **Code Graph**: `autoslide.ui` $\leftrightarrow$ `GET /api/v1/sessions/{session_id}/deck`, `POST /api/v1/sessions/{session_id}/chat`, `autoslide.jobs.workspace`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
