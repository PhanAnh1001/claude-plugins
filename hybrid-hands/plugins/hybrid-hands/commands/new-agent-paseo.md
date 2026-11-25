---
description: Mở agent Paseo mới ở tab mới cùng workspace (chọn GPT v1, Claude v1 hoặc Claude v2; context mới hoặc mang context phiên hiện tại); đổi repo sang gpt-mono + subagent native
argument-hint: "[--brain gpt-v1|claude-v1|claude-v2] [--context new|current] [--model M] [--effort E] [--workspace WKS_ID] [--prompt \"...\"] [--title \"...\"] [--dry-run]"
allowed-tools: Bash, AskUserQuestion, Write
---

## 1. Chọn agent và context

Gọi AskUserQuestion đúng MỘT lần, gồm các câu còn thiếu (đã có trong `$ARGUMENTS` thì bỏ câu đó; đủ cả hai thì bỏ bước này), mỗi câu `multiSelect: false`:

- Câu “Mở agent Paseo nào?”, header `Agent` (khi thiếu `--brain`):
  - `GPT v1`: “gpt-6.1-sol high trên gói ChatGPT chính (provider Paseo codex), mode full-access.” → `--brain gpt-v1`
  - `Claude v1`: “claude-opus-5-5 high trên tài khoản Claude v1 (~/.claude), mode bypassPermissions.” → `--brain claude-v1`
  - `Claude v2`: “claude-opus-5-5 high trên tài khoản Claude v2 (~/.claude-hand), mode bypassPermissions.” → `--brain claude-v2`
- Câu “Phiên mới mang context nào?”, header `Context` (khi thiếu `--context`):
  - `Context mới`: “Không truyền thêm gì; phiên mới tự đọc AGENTS.md và bàn giao trong repo.” → `--context new`
  - `Context phiên hiện tại`: “Viết bản bàn giao từ phiên này rồi gửi kèm cho phiên mới.” → `--context current`

Huỷ hoặc không chọn thì báo “Không mở agent” rồi dừng, không chạy gì. Lựa chọn là xác nhận, không hỏi lại.

## 2. Bàn giao (chỉ khi context phiên hiện tại)

Dùng tool Write ghi file `/tmp/new-agent-paseo-<YYYYMMDD-HHMMSS>.md` (≤ 100 000 byte, thường 1–3 trang), viết tiếng Việt, mở đầu bằng tóm tắt, theo thứ tự:

1. **Mục tiêu** đang theo đuổi và yêu cầu gần nhất của người dùng (trích nguyên văn nếu ngắn).
2. **Đã xong:** commit/SHA, file đã sửa, kết quả test thật.
3. **Đang dở:** việc chưa xong, file đang sửa, lỗi đang gặp.
4. **Quyết định đã chốt** và luật người dùng nhắc trong phiên.
5. **Việc tiếp theo** đề xuất.
6. **Lưu ý:** file của phiên khác không được đụng, chỗ dễ sai.

Không chép secret, token, `.env`, dữ liệu cá nhân khách hay transcript thô; chỉ nhắc đường dẫn.

## 3. Chạy

Chạy đúng một lệnh bằng tool Bash tại cwd repo hiện tại, thêm cờ vừa chọn nếu `$ARGUMENTS` chưa có; context phiên hiện tại thì thêm `--context-file <file vừa ghi>`:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/new-agent-paseo" $ARGUMENTS
```

Lệnh đặt profile `gpt-mono`, bật `ext_hand.native.{claude,codex}=auto`, mở phiên Paseo ở tab mới cùng workspace (kèm bàn giao nếu có) và kiểm phiên không có phiên cha; lỗi trước khi mở phiên thì tự khôi phục `.claude/hybrid-hands.json`. Chi tiết tham số ở skill `new-agent-paseo`.

Không tự làm lại từng bước, không sửa script, không chạy lệnh thứ hai. Sandbox chặn (daemon Paseo cục bộ, ghi file cấu hình) thì xin quyền chạy ngoài sandbox.

## 4. Sau khi chạy

Báo ngắn agentId, provider/model, context đã gửi (mới hoặc đường dẫn file bàn giao) và nhắc commit `.claude/hybrid-hands.json` nếu file đổi. Lệnh báo lỗi thì in nguyên văn thông báo lỗi; không tự sửa hay chạy lại.
