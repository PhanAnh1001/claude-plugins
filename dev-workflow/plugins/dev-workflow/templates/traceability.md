---
id: traceability
title: Ma trận truy vết
generated-by: dev-workflow trace_check.py
last-reviewed: <YYYY-MM-DD>
---

# Ma trận truy vết

## Tóm tắt

- **Nguồn:** sinh tự động bởi `dev-workflow trace_check.py` từ SRS, plan và test. Không sửa tay; chạy lại với `--write`.
- **Số ID:** <N> (<E: n, FR: n, NFR: n, SC: n>).
- **Thiếu task:** <N> (bắt buộc với: FR).
- **Thiếu test:** <N> (bắt buộc với: FR).
- **ID định nghĩa trùng** (lỗi): <N>.
- **Miễn trừ:** <N>.
- **ID mồ côi** (được tham chiếu nhưng không định nghĩa): <N>.
- **ID sai định dạng** (cảnh báo): <N>.
- **Việc cần làm:** Sửa ID trùng và bổ sung task (`covers:` trong plan) hoặc test (ID trong tên test/comment) cho các ID ở mục 2, hoặc ghi miễn trừ có lý do vào `[trace].waivers`.

## 1. Ma trận truy vết

| ID | Định nghĩa | Task | Test |
|---|---|---|---|
| `<FR-feature-001>` | `<docs/.../srs/spec.md:12>` | `<T-feature-01>` (xong) | `<tests/test_feature.py>` |
| `<FR-feature-002>` | `<docs/.../srs/spec.md:13>` | `<T-feature-02>` | — |
| `<FR-feature-003>` | `<docs/.../srs/spec.md:14>` | — | — |

## 2. Lỗi và thiếu liên kết

### 2.1 Thiếu task

- Không có.

### 2.2 Thiếu test

- `<FR-feature-002>`

### 2.3 ID định nghĩa trùng

- `<FR-feature-004>`: `<docs/.../srs/spec.md:15>`, `<docs/.../srs/flows.md:8>`

## 3. Miễn trừ

| ID | Lý do |
|---|---|
| `<FR-feature-003>` | <Chỉ kiểm bằng UAT thủ công> |

## 4. Cảnh báo

### 4.1 ID mồ côi

- `<FR-feature-009>`: `<docs/.../dev/plan.md:20>`

### 4.2 ID sai định dạng

Định dạng đúng: `<TYPE>-<feature>-NNN` (feature kebab-case chữ thường, NNN 2–3 chữ số).

- `<FR-Feature-1>`: `<docs/.../srs/spec.md:16>`
