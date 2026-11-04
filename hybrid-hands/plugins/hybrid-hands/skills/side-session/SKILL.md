---
name: side-session
description: Mở và quản lý phiên phụ (phiên Claude Code hoặc Codex chạy riêng, có ngữ cảnh brain riêng) bằng lệnh side-session cho gói việc dài nhiều bước - khi nào mở, viết prompt giao việc, start/ls/watch/handoff/stop, đọc tóm tắt bàn giao, dự phòng provider codex, đồng bộ bằng ListAgents/SendMessage. Từ khoá kích hoạt - "phiên phụ", "side session", "side-session", "mở phiên mới", "phiên song song", "giao gói việc dài", "bàn giao", "handoff".
---

# Phiên phụ (side-session)

## Tóm tắt

- **Dùng khi:** gói việc dài nhiều bước (ước trên 1 giờ) cần ngữ cảnh brain riêng, ví dụ cả một tính năng hay một chương; việc ngắn thì giao hand.
- **Giới hạn:** tối đa `max_parallel` phiên (mặc định 2) theo mục `side_session` của `.claude/hybrid-hands.json`; bàn giao ghi ở `handoff_dir` (mặc định `docs/work-in-progress/handoffs`).
- **Chuỗi bước:** viết prompt giao việc → `side-session start` (thử `--dry-run` trước) → theo dõi `ls`/`watch` → đọc `handoff` → brain review → `stop`.

Nếu `side-session` không có trong PATH, gọi bằng đường dẫn tuyệt đối `${CLAUDE_PLUGIN_ROOT}/bin/side-session`.

## 1. Prompt giao việc

Viết vào file trong scratchpad, theo khuôn brief 7 mục, thêm:
- Mục tiêu cuối và tiêu chí xong; phiên phụ được tự chia hand theo policy của dự án.
- PHẠM VI GHI tách khỏi các phiên khác (hai phiên không ghi cùng file); nếu cần tách hẳn thì dùng `--worktree`.
- Luật cấm chép nguyên văn (cấm đọc `.env`; luật chi phí, ngưỡng duyệt; không commit/push nếu dự án quy định vậy).
- Yêu cầu ghi tóm tắt bàn giao vào `handoff_dir` khi xong hoặc khi dừng giữa chừng.

## 2. Lệnh

- Mở: `side-session start --name <tên> --prompt-file <file> [--worktree [--base <nhánh>]] [--provider claude|codex] [--max-tokens N] [--hours H] [--brain <tên brain>] [--dry-run]` (`--prompt "<text>"` cho prompt ngắn).
- Danh sách: `side-session ls`. Theo dõi: `side-session watch --name <tên> [--once]` (chạy nền bằng `run_in_background`, không tự viết vòng chờ).
- Bàn giao: `side-session handoff <tên>` in tóm tắt bàn giao; brain đọc, tự review diff của phiên phụ trước khi báo người dùng.
- Dừng: `side-session stop <tên>` sau khi đã đọc bàn giao.

## 3. Dự phòng và đồng bộ

- **Provider:** mặc định `claude`; khi hết hạn mức gói Claude hoặc phiên claude lỗi, dùng `--provider codex` (chạy trên đăng nhập gói của Codex, không dùng API key).
- **Đồng bộ:** phiên phụ hiện trong ListAgents; gửi SendMessage trước khi ghi file chung, dùng tài nguyên trả phí hay Chrome, và sau mỗi commit. Hai phiên không ghi cùng một file.
