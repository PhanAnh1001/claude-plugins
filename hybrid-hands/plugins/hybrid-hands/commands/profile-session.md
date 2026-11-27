---
description: Xem hoặc đổi profile vai riêng cho phiên đang chạy (claude-mono v1/v2, gpt-mono, hybrid)
argument-hint: "[claude-mono [v1|v2]|claude-mono-v2|gpt-mono|hybrid|set|clear] [--json]"
allowed-tools: Bash, AskUserQuestion
---

Profile riêng phiên chỉ áp dụng cho phiên đang chạy, ưu tiên trên profile cấu hình (phiên → repo → global → plugin). Không ghi `.claude/hybrid-hands.json`; phiên mới vẫn dùng profile cấu hình (đổi profile cấu hình bằng [`/hybrid-hands:profile`](profile.md)). Chạy bằng tool Bash tại cwd repo hiện tại theo đúng một trong các luồng dưới đây.

## 1. Không đối số hoặc chỉ `--json`: chỉ xem

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile session $ARGUMENTS
```

In kết quả. Không hỏi và không ghi.

## 2. Có tên profile: đặt ngay

Khi `$ARGUMENTS` là đúng một trong `claude-mono`, `claude-mono v1`, `claude-mono v2`, `claude-mono-v1`, `claude-mono-v2`, `gpt-mono`, `hybrid` (có thể kèm `--json`), coi đó là xác nhận và chạy:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile session $ARGUMENTS
```

Sau đó chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile` để in bảng vai hiệu lực, rồi sang mục 5.

## 3. Chỉ có `set`: chọn từ danh sách

1. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile session --json` để biết profile hiện tại.
2. Gọi AskUserQuestion một câu, header `Profile`, `multiSelect: false`, hỏi “Đặt profile nào riêng cho phiên này?”. Bốn lựa chọn, thêm hậu tố “(đang dùng)” vào nhãn của profile hiện tại:
   - `claude-mono v1`: “Chỉ Claude v1: brain Opus high, code Opus low, thu thập/Chrome Sonnet low/medium.”
   - `claude-mono v2`: “Như claude-mono nhưng mọi vai dùng Claude tài khoản v2.”
   - `gpt-mono`: “Brain/code GPT sol high/low, thu thập GPT terra low, Chrome Claude v2 Sonnet low/medium.”
   - `hybrid`: “Như gpt-mono, thêm super brain Claude v2 Opus high ở phiên chính.”
3. Hủy, không chọn, chọn đúng profile đang dùng hoặc Other ngoài bốn lựa chọn thì báo “Không đổi profile” rồi dừng, không ghi.
4. Chạy đúng một lệnh `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile session <lựa chọn>` (bỏ hậu tố hiển thị; `claude-mono v2` truyền nguyên hai từ), rồi chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile`. Lựa chọn là xác nhận để ghi, không hỏi lại.

## 4. `clear`: về profile cấu hình

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" profile session --clear
```

## 5. Sau khi đặt

- Nhắc: “Profile riêng phiên áp dụng ngay cho giao việc (`pick/run --role`) và hook của phiên này; model của chính phiên không đổi; phiên mới vẫn dùng profile cấu hình.”
- Lệnh báo lỗi (ví dụ ngoài phiên Claude/Codex) thì in thông báo lỗi rồi dừng; không tự sửa file hay chạy lại.
