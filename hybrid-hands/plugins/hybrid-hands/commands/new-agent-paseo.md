---
description: Mở agent Paseo mới ở tab mới cùng workspace (chọn GPT v1, Claude v1 hoặc Claude v2); đổi repo sang gpt-mono + subagent native
argument-hint: "[--brain gpt-v1|claude-v1|claude-v2] [--model M] [--effort E] [--workspace WKS_ID] [--prompt \"...\"] [--title \"...\"] [--dry-run]"
allowed-tools: Bash, AskUserQuestion
---

## 1. Chọn agent

Nếu `$ARGUMENTS` đã có `--brain` thì bỏ qua bước này. Nếu chưa, gọi AskUserQuestion đúng một câu, header `Agent`, `multiSelect: false`, hỏi “Mở agent Paseo nào?”, ba lựa chọn:

- `GPT v1`: “gpt-6.1-sol high trên gói ChatGPT chính (provider Paseo codex), mode full-access.” → `--brain gpt-v1`
- `Claude v1`: “claude-opus-5-5 high trên tài khoản Claude v1 (~/.claude), mode bypassPermissions.” → `--brain claude-v1`
- `Claude v2`: “claude-opus-5-5 high trên tài khoản Claude v2 (~/.claude-hand), mode bypassPermissions.” → `--brain claude-v2`

Huỷ hoặc không chọn thì báo “Không mở agent” rồi dừng, không chạy gì. Lựa chọn là xác nhận, không hỏi lại.

## 2. Chạy

Chạy đúng một lệnh bằng tool Bash tại cwd repo hiện tại (thêm `--brain …` vừa chọn nếu `$ARGUMENTS` chưa có):

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/new-agent-paseo" $ARGUMENTS
```

Lệnh đặt profile `gpt-mono`, bật `ext_hand.native.{claude,codex}=auto`, mở phiên Paseo ở tab mới cùng workspace và kiểm phiên không có phiên cha; lỗi trước khi mở phiên thì tự khôi phục `.claude/hybrid-hands.json`. Chi tiết tham số ở skill `new-agent-paseo`.

Không tự làm lại từng bước, không sửa script, không chạy lệnh thứ hai. Sandbox chặn (daemon Paseo cục bộ, ghi file cấu hình) thì xin quyền chạy ngoài sandbox.

## 3. Sau khi chạy

Báo ngắn agentId, provider/model của phiên mới và nhắc commit `.claude/hybrid-hands.json` theo luật repo. Lệnh báo lỗi thì in nguyên văn thông báo lỗi; không tự sửa hay chạy lại.
