---
description: Xem hoặc bật/tắt mode parallel-subagents của repo sau khi người dùng chốt
argument-hint: "[on|off]"
allowed-tools: Bash
---

Chạy đúng lệnh sau bằng tool Bash tại cwd repo hiện tại:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" parallel-subagents $ARGUMENTS
```

Không đối số chỉ xem trạng thái. Chỉ chạy on/off khi người dùng đã chốt cho repo đó; không tự bật và không tự ghi config bằng logic riêng.

In kết quả lệnh. Nếu đã đổi mode thành công, nhắc mở phiên mới để hook nạp luật.
Nếu lệnh báo lỗi, báo thông báo lỗi; không tự sửa config hay chạy lại.
