---
description: Đổi repo sang gpt-mono + subagent native rồi mở phiên Paseo main brain ở tab mới (brain gpt, claude-v1 hoặc claude-v2)
argument-hint: "[--brain gpt|claude-v1|claude-v2] [--model M] [--effort E] [--workspace WKS_ID] [--prompt \"...\"] [--title \"...\"] [--dry-run]"
allowed-tools: Bash
---

Chạy đúng một lệnh sau bằng tool Bash tại cwd repo hiện tại:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/open-gpt-brain" $ARGUMENTS
```

Lệnh đặt profile `gpt-mono`, bật `ext_hand.native.{claude,codex}=auto`, mở phiên Paseo main brain ở tab mới cùng workspace và kiểm phiên không có phiên cha; lỗi trước khi mở phiên thì tự khôi phục `.claude/hybrid-hands.json`. Chi tiết tham số ở skill `open-gpt-brain`.

Không làm việc khác: không tự làm lại từng bước, không sửa script, không hỏi lại. Sandbox chặn (daemon Paseo cục bộ, ghi file cấu hình) thì xin quyền chạy ngoài sandbox.

Sau khi lệnh trả về, báo ngắn agentId, provider/model của phiên mới và nhắc commit `.claude/hybrid-hands.json` theo luật repo. Nếu lệnh báo lỗi, in nguyên văn thông báo lỗi; không tự sửa hay chạy lại.
