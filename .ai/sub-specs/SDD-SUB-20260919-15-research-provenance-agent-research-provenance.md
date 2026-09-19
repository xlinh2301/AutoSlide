---
id: SDD-SUB-20260919-15
title: Research, Generated Content and Provenance Approval
author: agent-research-provenance
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/ADS-002/requirements.md]]"
summary: "Implement research and content generation services, structured provenance tracking, URL validation/redaction, and source approval gating for conversational slide modifications."
decisions:
  - "Create autoslide.content.models defining ContentOrigin, SourceRecord, ResearchResult, GeneratedContent, and ProvenanceRecord."
  - "Create autoslide.conversation.provenance with ProvenanceStore to attach and query content origins, track destination targets, and validate plan operations against approved sources."
  - "Create autoslide.content.research with ResearchService providing bounded search and structured content generation through CLI runtime adapters, with URL validation, sensitive data redaction, and claim synthesis."
  - "Enforce strict Source Approval Gating: content sourced from unapproved or rejected web sources is filtered out and prohibited from entering an executable TaskPlan/EditPlan."
  - "Enhance RuntimeAdapter / BaseRuntimeAdapter in autoslide.runtime.adapters with search and generation helpers supporting structured JSON parsing, timeout bounds, and output sanitization."
affected_symbols:
  - "autoslide.content.models.ContentOrigin"
  - "autoslide.content.models.SourceRecord"
  - "autoslide.content.models.ResearchResult"
  - "autoslide.content.models.GeneratedContent"
  - "autoslide.content.models.ProvenanceRecord"
  - "autoslide.conversation.provenance.ProvenanceStore"
  - "autoslide.content.research.ResearchService"
  - "autoslide.runtime.adapters.BaseRuntimeAdapter"
risk_level: LOW
---

# 📝 Sub Spec: Research, Generated Content and Provenance Approval

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: Hiện thực hóa Task 4 trong kế hoạch Always-on Agent Chat (`ADS-002`): cung cấp dịch vụ tra cứu thông tin (`ResearchService.search`), sinh nội dung AI (`ResearchService.generate`), lưu trữ nguồn gốc và liên kết slide (`ProvenanceStore`), chuẩn hóa và làm sạch dữ liệu URL/redaction, và áp dụng cổng phê duyệt nguồn (`Source Approval Gate`) ngăn chặn các nguồn chưa được duyệt hoặc bị từ chối đưa vào `TaskPlan`.
> **Quyết định then chốt**: Mô hình hóa Pydantic cho `ContentOrigin` (`USER`, `WEB`, `AI_GENERATED`) và `ProvenanceRecord`; tích hợp `ResearchService` tương tác qua runtime adapter với giới hạn timeout và schema JSON chặt chẽ; chặn triệt để mọi nội dung lấy từ nguồn web chưa duyệt (`approved == False`) trước khi chuyển vào kế hoạch thực thi.
> **Rủi ro**: #risk/LOW | **Trạng thái**: #status/DRAFT

---

## 1. Mục tiêu (Objective)

Hiện thực hóa Task 4 trong kế hoạch Always-on Agent Chat (`ADS-002`):
1. **Dịch vụ Tra cứu và Nghiên cứu (`ResearchService.search`)**:
   - Nhận truy vấn tìm kiếm từ người dùng hoặc agent trong phiên hội thoại.
   - Điều phối qua runtime adapter để thực hiện tìm kiếm web an toàn, có giới hạn thời gian (bounded timeout) và kích thước kết quả.
   - Chuẩn hóa các bản ghi nguồn (`SourceRecord`) với URL hợp lệ (HTTP/HTTPS), tiêu đề, tóm tắt, thời điểm truy xuất và trích xuất các luận điểm/luận cứ (`claims`).
   - Tự động che giấu (redact) các thông tin nhạy cảm (API keys, token, mật khẩu) trong dữ liệu trả về.
2. **Dịch vụ Sinh nội dung (`ResearchService.generate`)**:
   - Nhận prompt yêu cầu tạo văn bản/nội dung cho slide.
   - Gắn nhãn nguồn gốc xuất xứ `ContentOrigin(kind="AI_GENERATED", runtime_name=...)` minh bạch, phân biệt rõ với nội dung từ web và từ người dùng.
3. **Quản lý Nguồn gốc & Xuất xứ (`ProvenanceStore`)**:
   - Lưu trữ ánh xạ giữa nội dung được trích dẫn (`content_ref`), nguồn gốc xuất xứ (`ContentOrigin`), và vị trí đích trên bài thuyết trình (`TargetReference` / slide index).
   - Cho phép truy vấn lịch sử nguồn gốc theo slide index hoặc content identifier.
4. **Cổng Phê duyệt Nguồn (`Source Approval Gating`)**:
   - Kiểm soát trạng thái phê duyệt của từng `SourceRecord` (`approved: bool`).
   - Ngăn chặn triệt để các khối nội dung dựa trên nguồn bị từ chối (`rejected`) hoặc chưa được phê duyệt (`unapproved`) được chuyển vào `TaskPlan` hoặc đưa tới `PPTXExecutor`.

---

## 2. Giả định & Rủi ro (Assumptions & Risks)

- [ ] **Giả định**: `ConversationSession` và `SourceRecord` đã được định nghĩa ban đầu ở Task 1; `autoslide.runtime.adapters` cung cấp cơ chế thực thi process an toàn không can thiệp API key trên host.
- [ ] **Giả định**: Các runtime CLI (Gemini/Antigravity/Codex/Claude) có thể trả về cấu trúc JSON hoặc văn bản có thể parse được theo định dạng chuẩn đã định nghĩa.
- [ ] **Rủi ro**: Dữ liệu web tìm kiếm có thể chứa URL độc hại (javascript:, file://) hoặc payload nhạy cảm.
  - *Biện pháp*: Kiểm tra scheme URL nghiêm ngặt (chỉ cho phép `http://` và `https://`), làm sạch nội dung qua `Redactor` trước khi lưu vào session checkpoint.
- [ ] **Rủi ro**: Runtime CLI phản hồi chậm hoặc bị treo khi tìm kiếm web.
  - *Biện pháp*: Thiết lập timeout nghiêm ngặt cho mỗi tác vụ tìm kiếm/sinh nội dung và có cơ chế fallback an toàn (trả về lỗi có cấu trúc thay vì treo ứng dụng).
- [ ] **`[UNKNOWN]`**: Mức độ sâu của trích xuất claim tự động: hiện tại dựa vào cấu trúc JSON do runtime trả về hoặc regex/JSON parser nội bộ.

---

## 3. Đặc tả Sửa đổi (Surgical Changes)

| File Path | Action | Detail |
| :--- | :--- | :--- |
| `src/autoslide/content/models.py` | Create | Định nghĩa các Pydantic models: `ContentOrigin`, `SourceRecord`, `ResearchResult`, `GeneratedContent`, `ProvenanceRecord` |
| `src/autoslide/conversation/provenance.py` | Create | Định nghĩa `ProvenanceStore` quản lý lưu vết nguồn gốc, liên kết mục tiêu và kiểm tra hợp lệ nguồn duyệt cho plan |
| `src/autoslide/content/research.py` | Create | Định nghĩa `ResearchService` (search, generate, apply_source_decision, filter_plan_operations) với URL validation và redaction |
| `src/autoslide/runtime/adapters.py` | Modify | Bổ sung phương thức hỗ trợ search/structured generation cho `BaseRuntimeAdapter` và `FakeRuntimeAdapter` |
| `tests/content/test_models.py` | Create | Kiểm thử cấu trúc models, URL validation, và serialization của `ContentOrigin`, `SourceRecord`, `ResearchResult` |
| `tests/content/test_provenance.py` | Create | Kiểm thử `ProvenanceStore`, ánh xạ `attach`, truy vấn theo slide và kiểm tra nguồn duyệt cho plan |
| `tests/content/test_research.py` | Create | Kiểm thử `ResearchService` (search, generate, sanitization/redaction, source approval gating, rejection handling) |

### Phân tích Logic Cốt lõi:
- **Separation of Concerns & Single Responsibility**:
  - `autoslide.content.models` đóng gói hợp đồng dữ liệu thuần túy và schema validation (Pydantic v2).
  - `autoslide.conversation.provenance` chịu trách nhiệm lưu vết liên kết (provenance graph) và kiểm duyệt quy tắc an toàn (gating rules).
  - `autoslide.content.research` chịu trách nhiệm tích hợp logic nghiệp vụ tìm kiếm, chuẩn hóa và lọc nguồn.
- **Fail-Safe Source Approval Gate**:
  - Khi người dùng từ chối một nguồn web (`approved = False`), toàn bộ các thao tác `EditOperation` trong plan phụ thuộc vào nguồn đó sẽ bị loại bỏ hoặc đánh dấu yêu cầu điều chỉnh, đảm bảo không có dữ liệu unapproved nào lọt tới `PPTXExecutor`.

---

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)

- [ ] **AC-1**: `SourceRecord` và `ContentOrigin` được mô hình hóa đầy đủ bằng Pydantic v2. `SourceRecord` chỉ chấp nhận URL hợp lệ thuộc giao thức `http://` hoặc `https://`. Mọi URL không hợp lệ bị từ chối với `ValueError`.
- [ ] **AC-2**: Toàn bộ kết quả tìm kiếm và sinh nội dung từ `ResearchService` được lọc qua `Redactor`, đảm bảo không chứa secrets, private tokens hay credentials trong dữ liệu lưu trữ.
- [ ] **AC-3**: `GeneratedContent` luôn mang nhãn `ContentOrigin(kind="AI_GENERATED")` cùng thông tin runtime/model rõ ràng, phân biệt với nguồn `USER` và `WEB`.
- [ ] **AC-4**: `ProvenanceStore.attach` lưu trữ chính xác liên kết giữa `content_ref`, `ContentOrigin` và `TargetReference`. Cho phép truy vấn lại danh sách provenance theo `slide_index` và `content_ref`.
- [ ] **AC-5**: `ResearchService.search` trả về `ResearchResult` với danh sách `SourceRecord` chuẩn hóa (id, url, title, summary, claims, approved=False mặc định).
- [ ] **AC-6**: Cổng duyệt nguồn (`Source Approval Gating`):
  - Phương thức kiểm tra nguồn (`validate_plan_sources` hoặc `filter_plan_operations`) ngăn chặn việc chuyển giao các thao tác sửa đổi dựa trên nguồn chưa được duyệt (`approved: False`) sang `READY_FOR_EXECUTION`.
  - Hỗ trợ cập nhật quyết định duyệt nguồn (`apply_source_decision`) và cập nhật danh sách nguồn của phiên.
- [ ] **AC-7**: Bổ sung đầy đủ unit tests trong `tests/content/` đạt 100% pass và đảm bảo không phá vỡ bất kỳ test suite nào hiện có.

---

## 5. Kế hoạch Kiểm tra (Verification Plan)

### Automated
```bash
# 1. Kiểm tra biên dịch bytecode
python3 -m compileall src tests

# 2. Chạy bộ unit tests mới cho Content & Research & Provenance
pytest tests/content/ -q -v

# 3. Chạy toàn bộ regression test suite của Conversation & API
pytest tests/conversation tests/api tests/planner -q
```

### Manual QA
1. Khởi tạo một `ResearchService` với `FakeRuntimeAdapter` mô phỏng trả về kết quả tìm kiếm có URL hợp lệ và thông tin nhạy cảm, xác nhận URL được chuẩn hóa và thông tin nhạy cảm bị che giấu.
2. Tạo bản ghi sinh nội dung qua `ResearchService.generate` và kiểm tra nhãn `kind == "AI_GENERATED"`.
3. Gắn thông tin nguồn gốc vào slide 1 qua `ProvenanceStore.attach` và truy vấn lại qua `list_by_slide(1)`.
4. Tạo một `TaskPlan` liên kết với nguồn web chưa được duyệt, kích hoạt bước kiểm tra phê duyệt nguồn và xác nhận plan bị từ chối hoặc các thao tác unapproved bị loại bỏ.
5. Cập nhật phê duyệt nguồn thành `approved = True`, xác nhận plan vượt qua cổng kiểm tra phê duyệt nguồn thành công.

---

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: Tiếp nối `SDD-SUB-20260919-12` (Conversation Models & Store), `SDD-SUB-20260919-13` (Clarification Service), và `SDD-SUB-20260919-14` (Session API). Cung cấp nền tảng provenance và approval gating cho Task 5 (Deck Operations) và Task 6 (Chatbot UI).
- **Related Sessions**: `docs/superpowers/plans/2026-09-19-always-on-agent-chat.md`, `task-4-brief.md`
- **Code Graph**: `autoslide.content.research.ResearchService` $\rightarrow$ `autoslide.conversation.provenance.ProvenanceStore` $\rightarrow$ `autoslide.content.models` $\rightarrow$ `autoslide.runtime.adapters.BaseRuntimeAdapter`.

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
