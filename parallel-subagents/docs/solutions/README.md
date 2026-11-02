# Giải pháp của plugin parallel-subagents

## Tóm tắt

- **Mục đích:** bản đồ các giải pháp đang áp dụng trong plugin; mỗi giải pháp một file, chỉ mô tả trạng thái hiện hành.
- **Số lượng:** 1 nhóm, 2 nhánh, 2 file.
- **Cách dùng:** thêm/sửa/xóa theo skill `summary-first-docs:documenting-solutions`; mỗi file có đúng một dòng ở cây dưới.

## Cây giải pháp

### brain-hand-policy: luật điều phối brain/hand bơm vào context

- **handoff:** khi nào tiếp việc cho hand cũ, khi nào sinh hand mới
  - [cache-aware-handoff.md](brain-hand-policy/handoff/cache-aware-handoff.md): SendMessage khi cache nóng; nguội và >80k (hoặc >200k) thì hand mới với brief gọn.
- **long-commands:** cách chạy lệnh lâu
  - [long-command-isolation.md](brain-hand-policy/long-commands/long-command-isolation.md): lệnh >4 phút giao hand riêng ngữ cảnh nhỏ.
