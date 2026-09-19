---
id: SDD-SUB-{{date}}-{{num}}
title: [Tên Task / Feature / Bugfix]
author: [AI Agent / User Name]
status: DRAFT # DRAFT | REVIEW | APPROVED | MERGED
main_spec: "[[.ai/specs/path-to-main-spec]]"
summary: "[1 câu tóm tắt mục tiêu - Dành cho AI đọc nhanh]"
decisions: 
  - "[Quyết định 1]"
  - "[Quyết định 2]"
affected_symbols: 
  - "[Tên Class/Hàm 1]"
  - "[Tên Class/Hàm 2]"
risk_level: LOW # LOW | MEDIUM | HIGH
---

# 📝 Sub Spec: [Tên Task / Feature / Bugfix]

> [!ABSTRACT] Tóm tắt cho AI
> **Mục tiêu**: {{summary}}
> **Quyết định then chốt**: {{decisions}}
> **Rủi ro**: #risk/{{risk_level}} | **Trạng thái**: #status/{{status}}

---

## 1. Mục tiêu (Objective)
Mô tả ngắn gọn kết quả cuối cùng cần đạt được.

## 2. Giả định & Rủi ro (Assumptions & Risks)
- [ ] **Giả định**: ...
- [ ] **Rủi ro**: ...
- [ ] **`[UNKNOWN]`**: [UNKNOWN: Lý do chưa rõ]

## 3. Đặc tả Sửa đổi (Surgical Changes)
| File Path | Action | Detail |
| :--- | :--- | :--- |
| `path/to/file` | Modify | Chi tiết thay đổi |

### Phân tích Logic Cốt lõi:
- [Tại sao làm vậy?]
- [Sử dụng Pattern nào?]

## 4. Tiêu chí Chấp nhận (Acceptance Criteria)
- [ ] [Điều kiện 1]
- [ ] [Điều kiện 2]

## 5. Kế hoạch Kiểm tra (Verification Plan)
### Automated
```bash
# Lệnh chạy test
```

### Manual QA
1. [Bước 1]
2. [Bước 2]

## 6. Kết nối Tri thức (Intelligence Context)
- **Impact Analysis**: `[[.ai/walkthroughs/impact-report-ID]]`
- **Related Sessions**: `[[.ai/walkthroughs/session-ID]]`
- **Code Graph**: [Link tới Graphify node nếu có]

---
*Tài liệu này được tối ưu hóa cho truy vấn AI-Native.*
