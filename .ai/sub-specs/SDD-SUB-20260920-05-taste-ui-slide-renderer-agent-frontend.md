---
id: SDD-SUB-20260920-05
title: Anti-Slop UI/UX Redesign (Linear-Style Minimalist) & High-Fidelity Slide Content Card Renderer
author: agent-frontend
status: APPROVED # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-003/requirements.md]]"
summary: "Khắc phục triệt để lỗi upload không hiện slide bằng High-Fidelity PIL Slide Content Renderer, và nâng cấp toàn diện UI/UX Web Studio theo chuẩn Leonxlnx/taste-skill (Linear-Style Minimalist)."
decisions: 
  - "Thay thế 1x1 transparent PNG (MINIMAL_PNG_BYTES) trong MockPreviewRenderer bằng Rich PIL Slide Canvas Renderer: tự động vẽ slide canvas 16:9 với tiêu đề thực tế, khối văn bản, số thứ tự slide, và layout blocks từ PPTX."
  - "Áp dụng Anti-Slop Frontend Framework từ Leonxlnx/taste-skill: Design Read cho AutoSlide Studio theo phong cách Linear-style Minimalist (Dark/Light neutral tokens, viền 1px sắc nét, font chữ phân cấp rõ ràng, loại bỏ gradient màu mè rẻ tiền)."
  - "Thiết kế lại Filmstrip & Dual Canvas: Thẻ slide hiển thị rõ nội dung thực tế (Title, excerpt text, số lượng shapes), thumbnail sắc nét, badge MODIFIED phát sáng tinh tế."
  - "Nâng cấp Chat Rail: Giao diện chat chuẩn công cụ năng suất (productivity tool), hiển thị rõ ràng ngữ cảnh slide đang chọn, thanh cuộn mượt mà và các tool cards trực quan."
affected_symbols: 
  - "autoslide.ingest.renderer.MockPreviewRenderer"
  - "autoslide.ingest.renderer.select_preview_renderer"
  - "autoslide.ui.static.css.workbench.css"
  - "autoslide.ui.static.js.workbench.js"
  - "autoslide.ui.templates.index.html"
risk_level: MEDIUM # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: Anti-Slop UI/UX Redesign & High-Fidelity Slide Content Card Renderer

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Giải quyết tận gốc lỗi "upload lên không hiện slide" và tái thiết kế UI/UX Web Studio đạt chuẩn Anti-Slop cao cấp theo bộ kỹ năng `Leonxlnx/taste-skill`.
> **Design Read**: AutoSlide Studio - Công cụ AI Slide Co-Pilot chuyên nghiệp dành cho người dùng kỹ thuật và thuyết trình viên, ngôn ngữ thiết kế Linear-style Minimalist, nền dark/light neutral zinc cao cấp, viền 1px sắc nét, mật độ thông tin cao (High Visual Density), thẻ slide hiển thị trực quan nội dung văn bản thực tế thay vì hình ảnh rỗng.
> **Dials**: `DESIGN_VARIANCE: 6` | `MOTION_INTENSITY: 4` | `VISUAL_DENSITY: 5`
> **Rủi ro**: #risk/MEDIUM | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

1. **Khắc phục lỗi hiển thị Slide khi Upload (Root Cause Fix)**:
   - Hiện tại máy chủ không có LibreOffice/soffice nên hệ thống fallback về `MockPreviewRenderer` - sinh ra ảnh 1x1 transparent PNG (`MINIMAL_PNG_BYTES`), khiến trình duyệt hiển thị khung rỗng.
   - **Giải pháp**: Xây dựng **High-Fidelity PIL Slide Content Renderer** trực tiếp bằng `Pillow` và `python-pptx`. Khi render preview:
     * Trích xuất tiêu đề slide (`title`), các đoạn văn bản chính (`body text`), số lượng shapes, layout slide.
     * Vẽ ảnh preview tỉ lệ chuẩn 16:9 (1280x720 hoặc 1920x1080) với typography cao cấp, nền thẻ trang nhã, thẻ số thứ tự slide (Slide Badge), và bố cục nội dung thực tế.
     * Trình duyệt và người dùng nhìn thấy ngay nội dung thực tế của từng slide trong bài thuyết trình.

2. **Nâng cấp UI/UX Anti-Slop theo chuẩn `Leonxlnx/taste-skill`**:
   - Loại bỏ các thành phần mặc định rẻ tiền (AI-purple gradients, generic glassmorphism lạm dụng).
   - Thiết lập bảng màu **Linear-Style Neutral Zinc**:
     * Nền: Dark `#09090b` / `#121215`, bề mặt card `#18181b` / `#27272a`, viền mảnh `1px solid rgba(255,255,255,0.08)`.
     * Điểm nhấn: Neon-Amber `#f59e0b` / `#fbbf24` cho các slide `MODIFIED`, Indigo-Blue `#6366f1` cho hành động chính.
   - **Filmstrip bên trái**: Thumbnail slide sắc nét, hiển thị số slide, tiêu đề vắn tắt, badge trạng thái.
   - **Dual-Column Canvas ở giữa**: Thẻ Before & After hiển thị rõ ràng nội dung, viền phát sáng khi chỉnh sửa, cuộn mượt mà.
   - **Chat Rail bên phải**: Trải nghiệm gõ lệnh AI mượt mà, gợi ý hành động nhanh (Quick Prompts), thẻ Tool Call gọn gàng chuẩn devtool.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: `Pillow` (PIL) đã được cài đặt trong môi trường (`uv pip install pillow`).
- [ ] **Giả định**: `python-pptx` trích xuất được shape hierarchy và text paragraphs của tệp PPTX.
- [ ] **Rủi ro**: Font chữ hệ thống trên Linux/WSL có thể khác Windows, cần sử dụng font dự phòng an toàn (`DejaVuSans`, `Helvetica`, `Arial` hoặc PIL default font với bounding box chuẩn).

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/ingest/renderer.py` | Enhance Renderer | Bổ sung `ContentAwareSlideRenderer` dùng PIL vẽ canvas 16:9 chứa title, text excerpt, layout preview từ file PPTX; thay thế việc ghi 1x1 transparent PNG. |
| `src/autoslide/ui/static/css/workbench.css` | Anti-Slop Styling | Tái cấu trúc CSS theo chuẩn `taste-skill`: bảng màu Linear neutral zinc, border 1px tinh xảo, typography phân cấp, luminous amber outline cho modified slides. |
| `src/autoslide/ui/static/js/workbench.js` | UX Polish | Cải thiện hiệu ứng chuyển slide, filmstrip active indicator, empty states tinh tế, hiển thị lỗi upload rõ ràng. |
| `src/autoslide/ui/templates/index.html` | Layout Polish | Tinh chỉnh thanh công cụ trên cùng (header toolbar), filmstrip count, canvas parity controls, chat composer. |

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] Khi upload file PPTX (`icisn_2025_fusionnetx.pptx.pptx` hoặc bất kỳ file nào), tất cả slide trên Filmstrip và Dual Canvas hiển thị hình ảnh slide rõ ràng (có tiêu đề và nội dung slide), KHÔNG CÒN khung rỗng hay ảnh 1x1 trong suốt.
- [ ] Giao diện Web Studio đạt chuẩn Linear-Style Minimalist: hiện đại, sạch sẽ, không có layout vỡ hay text tràn.
- [ ] Khi gửi lệnh chat chỉnh sửa ("Đổi tiêu đề slide 1 thành AutoSlide Demo"), slide 1 ở cột After cập nhật nội dung mới và viền phát sáng amber nổi bật.
- [ ] Chạy kiểm thử unit test và UI test đạt 100% pass rate.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
uv run pytest tests/ui/ tests/ingest/ tests/api/ -q
```

### Manual QA
1. Mở `http://localhost:8001/` trong trình duyệt.
2. Tải lên tệp `icisn_2025_fusionnetx.pptx.pptx`.
3. Kiểm tra các slide trên Filmstrip và Canvas Trước/Sau có hiển thị tiêu đề và nội dung slide trực quan hay không.
4. Gửi tin nhắn qua Chat Rail để chỉnh sửa slide và quan sát cập nhật thời gian thực.

---

## 6. Kết nối Tri thức (Intelligence Context)

- **Design Framework**: `[[.ai/skills/taste-skill/SKILL.md]]`
- **Sub-Spec liên quan**: `[[.ai/sub-specs/SDD-SUB-20260920-04-web-production-chatbot-vision-agent-frontend.md]]`
- **Architecture Guidelines**: `[[AGENTS.md]]`

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
