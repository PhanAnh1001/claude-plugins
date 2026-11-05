---
description: Chuyển phiên Claude Code đang mở trong terminal sang Paseo
allowed-tools: Bash
---

Chạy đúng một lệnh sau bằng tool Bash, và đó là hành động cuối của lượt này:

```sh
cc-switch paseo --self
```

Nếu `cc-switch` không có trong `PATH`, dùng đường dẫn tuyệt đối tới `bin/cc-switch` mà hook SessionStart in ra, ví dụ `<đường dẫn tuyệt đối>/bin/cc-switch paseo --self`.

Không làm việc khác: không đọc hay sửa file, không chạy lệnh thứ hai, không hỏi lại.

Sau khi lệnh trả về, trả lời đúng một câu ngắn: đừng gõ hay nhấn Enter cho tới khi TUI tự đóng, rồi mở Paseo trên điện thoại để tiếp tục.

Nếu lệnh báo lỗi, báo nguyên văn thông báo lỗi và gợi ý trong đó; không tự sửa hay chạy lại.
