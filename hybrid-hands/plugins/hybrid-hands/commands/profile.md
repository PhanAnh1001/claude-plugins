---
description: Xem hoặc đổi profile vai của repo (claude-mono, gpt-mono, hybrid)
argument-hint: "[claude-mono|gpt-mono|hybrid|set] [--json]"
allowed-tools: Bash, AskUserQuestion
---

Không đối số thì chỉ xem profile và bảng vai hiệu lực. Có tên profile thì đặt profile đó cho repo hiện tại. `set` không kèm tên thì hỏi chọn từ danh sách rồi đặt. Chạy bằng tool Bash tại cwd repo hiện tại theo đúng một trong ba luồng dưới đây. Lệnh chỉ ghi khoá `profile` trong `.claude/hybrid-hands.json` của repo; không sửa cấu hình global, credential hay settings.

## 1. Không đối số hoặc chỉ `--json`: chỉ xem

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile $ARGUMENTS
```

In kết quả (profile, nguồn `[plugin|global|repo]`, ô từng vai). Không hỏi và không ghi cấu hình. Lệnh báo thiếu profile thì in thông báo và gợi ý `/hybrid-hands:profile set`.

## 2. Có tên profile: đặt ngay

Khi `$ARGUMENTS` là đúng một trong `claude-mono`, `gpt-mono`, `hybrid` (có thể kèm `--json`), coi đó là xác nhận của người dùng và chạy:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile set $ARGUMENTS
```

Sau đó chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile` để in bảng vai mới, rồi chuyển sang bước nhắc ở mục 4.

## 3. Chỉ có `set`: chọn từ danh sách

1. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile --json` để biết profile hiện tại; lỗi thiếu profile thì coi như chưa có, không dừng.
2. Gọi AskUserQuestion một câu, header `Profile`, `multiSelect: false`, hỏi “Đặt profile nào cho repo này?”. Ba lựa chọn, thêm hậu tố “(đang dùng)” vào nhãn của profile hiện tại:
   - `claude-mono`: “Chỉ Claude v1: brain Opus high, code Opus low, thu thập/Chrome Sonnet low/medium.”
   - `gpt-mono`: “Brain/code GPT sol high/low, thu thập GPT terra low, Chrome Claude v2 Sonnet low/medium.”
   - `hybrid`: “Như gpt-mono, thêm super brain Claude v2 Opus high ở phiên chính.”
   Mô tả là bảng mặc định của plugin; ô ghi đè `profiles.<tên>.<vai>` hiện ra ở bảng in sau khi đặt.
3. Hủy, không chọn, chọn đúng profile đang dùng hoặc Other ngoài ba tên thì báo “Không đổi profile” rồi dừng, không ghi.
4. Chạy đúng một lệnh `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile set <tên đã chọn>` (bỏ hậu tố hiển thị), rồi chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile` để in bảng vai mới. Lựa chọn là xác nhận để ghi, không hỏi lại.

## 4. Sau khi đặt

- Nhắc: “Profile mới áp dụng cho phiên mở sau; mở phiên mới từ bàn giao, không đổi model giữa phiên.” Phiên đang chạy giữ vai và model cũ.
- Nếu cwd là worktree (`git rev-parse --git-dir` khác `--git-common-dir`), nhắc thêm: file cấu hình vừa ghi chỉ thuộc worktree này; muốn mọi worktree dùng chung thì đặt ở checkout chính và commit `.claude/hybrid-hands.json`.
- Lệnh nào báo lỗi thì in thông báo lỗi rồi dừng; không tự sửa file cấu hình hay chạy lại.
