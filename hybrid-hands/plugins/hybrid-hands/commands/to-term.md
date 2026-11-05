---
description: Chuyển phiên Claude Code đang do Paseo giữ về cửa sổ Terminal
allowed-tools: Bash
---

Chạy đúng một lệnh sau bằng tool Bash, và đó là hành động cuối của lượt này:

```sh
cc-switch term --self
```

Nếu `cc-switch` không có trong `PATH`, dùng đường dẫn tuyệt đối tới `bin/cc-switch` mà hook SessionStart in ra, ví dụ `<đường dẫn tuyệt đối>/bin/cc-switch term --self`.

Không làm việc khác: không đọc hay sửa file, không chạy lệnh thứ hai, không hỏi lại.

Sau khi lệnh trả về, trả lời đúng một câu ngắn: cửa sổ Terminal sẽ mở sau khi lượt này xong, và đừng gửi tin cho agent từ Paseo cho tới khi chuyển lại.

Nếu lệnh báo lỗi, báo nguyên văn thông báo lỗi và gợi ý trong đó; không tự sửa hay chạy lại.
