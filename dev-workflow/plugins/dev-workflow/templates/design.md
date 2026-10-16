---
id: design-<feature>
title: Thiết kế kỹ thuật <tên tính năng>
status: draft
owner: <người chịu trách nhiệm>
last-reviewed: <YYYY-MM-DD>
lane: <L2|L3>
implements: [<FR-feature-001>, <NFR-feature-001>]
---

# Thiết kế kỹ thuật <tên tính năng>

## Tóm tắt

- **Mục đích:** <một câu: thiết kế này hiện thực những yêu cầu nào, giải quyết vấn đề gì>.
- **Phạm vi:** <module/service bị đổi>; ngoài phạm vi: <những gì cố ý không làm>.
- **Quyết định chính:** <quyết định 1>; <quyết định 2> (chi tiết ở ADR <ADR-NNNN> nếu có).
- **Ảnh hưởng:** <API/schema/contract thay đổi>, <migration cần chạy>, <rủi ro lớn nhất>.
- **Việc người đọc cần làm:** duyệt mục 2–3, chuyển `status` sang `approved` (cổng 2) trước khi làm `plan.md`.

## 1. Bối cảnh

### 1.1 Yêu cầu liên quan

| ID | Tóm tắt yêu cầu | Ghi chú thiết kế |
|---|---|---|
| <FR-feature-001> | <yêu cầu> | <cách đáp ứng> |
| <E-feature-001> | <ca lỗi bắt buộc xử lý> | <cách xử lý> |

### 1.2 Hiện trạng

<Mô tả code/luồng hiện tại, trích file liên quan bằng đường dẫn tương đối.>

## 2. Thiết kế

### 2.1 Kiến trúc và luồng

<Thành phần, trách nhiệm, luồng dữ liệu. Có thể kèm sơ đồ mermaid.>

### 2.2 API và contract

| Endpoint/hàm | Đầu vào | Đầu ra | Thay đổi |
|---|---|---|---|
| <`POST /api/...`> | <schema> | <schema> | <mới/sửa/xoá> |

### 2.3 Dữ liệu và migration

<Bảng/cột mới, chỉ mục, migration `NNN_<tên>.sql`, cách rollback.>

### 2.4 Xử lý lỗi

<Ánh xạ từng `E-<feature>-NNN` sang mã lỗi/thông báo.>

## 3. Quyết định và phương án đã cân nhắc

| Quyết định | Phương án chọn | Phương án loại | Lý do |
|---|---|---|---|
| <D1> | <chọn> | <loại> | <vì sao> |

## 4. Kiểm chứng

- **Test:** <unit/integration cần có, đặt tên chứa ID, ví dụ `test_FR_feature_001_...`>.
- **Tiêu chí xong:** <các `SC-<feature>-NN` phải đạt>.
- **Đo lường (nếu L3):** <chỉ số, ngưỡng, cách đo>.

## 5. Rủi ro và câu hỏi mở

- [ ] <OQ-1: câu hỏi cần stakeholder trả lời>
- <Rủi ro: mô tả, cách giảm thiểu>
