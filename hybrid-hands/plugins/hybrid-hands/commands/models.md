---
description: Xem hoặc cấu hình model ba tầng theo repo sau khi người dùng chốt
argument-hint: "[set FLAGS|unset brain|side|hand] [--dry-run] [--json] [--cwd PATH]"
allowed-tools: Bash
---

Xem model/effort/account ba tầng brain, phiên phụ và hand theo repo; chỉ lưu hoặc gỡ override khi người dùng đã nêu thay đổi cụ thể.

Chạy đúng lệnh sau bằng tool Bash tại cwd repo hiện tại, giữ nguyên các đối số người dùng truyền:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models $ARGUMENTS
```

Không đối số gọi `hand-ext models` để xem. Có đối số chuyển nguyên `models <args>` cho CLI; không tự thêm cờ hoặc suy ra thay đổi. Chỉ chạy `set`/`unset` khi người dùng yêu cầu thay đổi cụ thể; `unset` chỉ nhận cả tầng `brain|side|hand`.

In kết quả lệnh. Ghi thành công thì nhắc: “mở phiên mới để áp dụng”; không đổi model/account phiên đang chạy. Dry-run không ghi cấu hình.
Nếu lệnh báo lỗi, báo thông báo lỗi; không tự sửa config hay chạy lại.
