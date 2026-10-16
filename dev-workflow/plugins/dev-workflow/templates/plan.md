---
id: plan-<feature>
title: Kế hoạch <tên tính năng>
status: draft
owner: <người chịu trách nhiệm>
last-reviewed: <YYYY-MM-DD>
lane: <L1|L2|L3>
covers: [<FR-feature-001>, <FR-feature-002>]
---

# Kế hoạch <tên tính năng>

## Tóm tắt

- **Mục tiêu:** <kết quả cuối cùng, đo được>.
- **Đầu vào:** SRS <đường dẫn>, thiết kế <đường dẫn design.md hoặc "không cần ở L0–L1">.
- **Quy mô:** <N> task, ước lượng tổng <X> giờ (đã nhân hệ số estimate của repo).
- **Rủi ro chính:** <rủi ro lớn nhất và cách xử lý>.
- **Việc người đọc cần làm:** duyệt danh sách task và `covers:`, chuyển `status` sang `approved` (cổng 3).

## Việc cần làm

Mọi việc đều là một dòng ô tích (không dùng gạch đầu dòng trơn hay đoạn văn cho việc): checkbox, mã
`T-<feature>-NN`, mô tả, `covers:` các ID yêu cầu, ước lượng.

- **Xong việc:** agent tick `[x]` ngay khi task đã làm xong và gate/kiểm chứng đã chạy xanh,
  không tick trước.
- **Bỏ qua việc:** xoá hẳn dòng nếu việc không còn ý nghĩa; nếu cần giữ vết quyết định thì ghi
  `- [-] ~~T-<feature>-NN <mô tả việc>~~ — bỏ qua: <lý do>`. Script truy vết bỏ qua dòng này, nên
  `covers:` trên đó không được tính; ID bị bỏ phải có task khác cover hoặc mở CR.
- **Hoàn thành:** chuyển `status: completed` khi không còn ô `[ ]` nào, kể cả phần Kiểm chứng
  (`[x]` là xong, `[-]` là bỏ qua).

### 1. <Nhóm việc 1, ví dụ: dữ liệu và migration>

- [ ] T-<feature>-01 <mô tả việc> — covers: <FR-feature-001> — estimate: <2h>
- [ ] T-<feature>-02 <mô tả việc> — covers: <FR-feature-001>, <E-feature-001> — estimate: <1h>

### 2. <Nhóm việc 2, ví dụ: API và giao diện>

- [ ] T-<feature>-03 <mô tả việc> — covers: <FR-feature-002> — estimate: <3h>

## Kiểm chứng

- [ ] Gate của repo xanh (`[gate].commands` trong `.claude/dev-workflow.toml`).
- [ ] Mỗi FR trong `covers` có test chứa ID (`test_FR_<feature>_NNN_...` hoặc comment `FR-<feature>-NNN`).
- [ ] `dw trace` thoát 0; `traceability.md` đã cập nhật bằng `dw trace --write`.
- [ ] Tài liệu theo `[docs_map]` đã cập nhật cho mọi file code bị đổi.
- [ ] Đạt tiêu chí <SC-feature-01>.

## Ghi chú và quyết định trong lúc làm

- <YYYY-MM-DD>: <quyết định/thay đổi so với kế hoạch và lý do>.
