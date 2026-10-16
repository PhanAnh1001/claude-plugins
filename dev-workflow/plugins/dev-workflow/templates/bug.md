---
id: bug-<YYYY-MM-DD>-<slug>
title: <Mô tả ngắn lỗi>
status: draft
owner: <người điều tra>
last-reviewed: <YYYY-MM-DD>
severity: <critical|major|minor|trivial>
lane: <L1|L2|L3>
---

# Lỗi: <Mô tả ngắn lỗi>

## Tóm tắt

- **Triệu chứng:** <người dùng thấy gì, ở đâu>.
- **Nguyên nhân gốc:** <một câu, kèm commit gây lỗi nếu tìm được>.
- **Là regression:** <có/không — từ commit <sha>>.
- **Phương án đề xuất:** <một câu>; ảnh hưởng <N> file.
- **Việc người đọc cần làm:** duyệt phương án ở mục 3 (cổng duyệt) để agent bắt đầu sửa.

## 1. Hiện tượng

### 1.1 Triệu chứng

<Mô tả đầy đủ: môi trường, dữ liệu, thông báo lỗi, tần suất.>

### 1.2 Cách tái hiện

1. <bước 1>
2. <bước 2>
3. **Kết quả thực tế:** <...>; **kết quả mong đợi:** <...>.

### 1.3 Test đỏ

- **Test:** `<tests/.../test_x.py::test_...>`
- **Lệnh:** `<lệnh chạy test, từ gốc repo>`
- **Đầu ra (đỏ đúng lý do — AssertionError trên hành vi sai, không phải ImportError):**

```text
<dán vài dòng đầu ra quan trọng>
```

## 2. Phân tích

### 2.1 Lịch sử Git

| Commit | Ngày | Nội dung | Liên quan |
|---|---|---|---|
| <sha> | <YYYY-MM-DD> | <thông điệp> | <gây lỗi / fix cũ / revert> |

Lệnh đã dùng: `git log -L <...>`, `git blame <file>`.

### 2.2 Nguyên nhân gốc

<Giải thích cơ chế gây lỗi, trích file:dòng bằng đường dẫn tương đối.>

## 3. Phương án sửa

| Phương án | Mô tả | Rủi ro | File bị đổi |
|---|---|---|---|
| <A> | <...> | <...> | <...> |

**Đề xuất:** <phương án và lý do>.

## 4. Cổng duyệt

- **Quyết định:** <duyệt phương án A | yêu cầu điều tra thêm>
- **Người duyệt:** <tên>
- **Ngày:** <YYYY-MM-DD>

## 5. Kết quả sau sửa

- **Test đỏ → xanh:** <lệnh và kết quả>.
- **Gate:** <lệnh và kết quả>.
- **Tài liệu đã cập nhật:** <đường dẫn>.
