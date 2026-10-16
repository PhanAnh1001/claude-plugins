---
id: CR-<YYYYMMDD>-<NNN>
title: <Tên yêu cầu thay đổi>
status: draft
owner: <người đề xuất>
last-reviewed: <YYYY-MM-DD>
affects: [<FR-feature-001>, <docs/.../spec.md>]
---

# CR-<YYYYMMDD>-<NNN>: <Tên yêu cầu thay đổi>

## Tóm tắt

- **Thay đổi:** <một câu: đổi gì, từ đâu sang đâu>.
- **Lý do:** <ai yêu cầu, vì sao>.
- **Mức ảnh hưởng:** <N> tài liệu, <N> ID, <N> file code, <N> test; làn đề xuất <L1|L2>.
- **Rủi ro lớn nhất:** <mô tả>.
- **Việc người đọc cần làm:** đọc báo cáo ảnh hưởng (mục 1) rồi ghi quyết định ở mục 3.
  Agent **không** sửa tài liệu hay code trước khi CR được duyệt.

## 1. Báo cáo ảnh hưởng

### 1.1 Tài liệu bị ảnh hưởng

| Tài liệu | Mục | Thay đổi dự kiến |
|---|---|---|
| <docs/.../spec.md> | <mục> | <sửa/thêm/xoá> |

### 1.2 ID yêu cầu bị ảnh hưởng

| ID | Hiện tại | Sau thay đổi | Loại |
|---|---|---|---|
| <FR-feature-001> | <nội dung cũ> | <nội dung mới> | <sửa/mới/bỏ> |

### 1.3 Code bị ảnh hưởng

| File | Lý do | Ước lượng |
|---|---|---|
| <src/...> | <vì sao phải đổi> | <giờ> |

### 1.4 Test bị ảnh hưởng

| Test | Hành động |
|---|---|
| <tests/...::test_FR_feature_001_...> | <sửa/thêm/xoá> |

## 2. Phương án

| Phương án | Ưu điểm | Nhược điểm | Ước lượng |
|---|---|---|---|
| <A> | <...> | <...> | <giờ> |
| <B> | <...> | <...> | <giờ> |

**Đề xuất:** <phương án và lý do>.

## 3. Phê duyệt

- **Quyết định:** <duyệt | từ chối | cần làm rõ>
- **Người duyệt:** <tên>
- **Ngày:** <YYYY-MM-DD>
- **Ghi chú:** <điều kiện kèm theo>
