---
name: side-session
description: Mở và quản lý phiên phụ (phiên Claude Code hoặc Codex chạy riêng, có ngữ cảnh brain riêng) bằng lệnh side-session cho gói việc dài nhiều bước - khi nào mở, viết prompt giao việc, start/ls/watch/handoff/stop, đọc tóm tắt bàn giao, dự phòng provider codex hoặc hand ngoài dsh trong worktree, Chrome khi việc cần trình duyệt, đồng bộ bằng ListAgents/SendMessage. Từ khoá kích hoạt - "phiên phụ", "side session", "side-session", "mở phiên mới", "phiên song song", "giao gói việc dài", "bàn giao", "handoff".
---

# Phiên phụ (side-session)

## Tóm tắt

- **Dùng khi:** gói việc dài nhiều bước (ước trên 1 giờ) cần ngữ cảnh brain riêng, ví dụ cả một tính năng hay một chương; việc ngắn thì giao hand.
- **Giới hạn:** tối đa `max_parallel` phiên (mặc định 2) theo mục `side_session` của `.claude/hybrid-hands.json`; bàn giao ghi ở `handoff_dir` (mặc định `docs/work-in-progress/handoffs`); phiên phụ ngoài (`dsh`) chỉ chạy trong worktree.
- **Chuỗi bước:** viết prompt giao việc → `side-session start` (thử `--dry-run` trước) → theo dõi `ls`/`watch` → đọc `handoff` → brain review → `stop`. Xem toàn cảnh phiên chính, phiên phụ, subagent và hand ngoài bằng `hh-ps` (`--watch 5`, `--json`).

Nếu `side-session` không có trong PATH, gọi bằng đường dẫn tuyệt đối `${CLAUDE_PLUGIN_ROOT}/bin/side-session`.

## 1. Prompt giao việc

Viết vào file trong scratchpad, theo khuôn brief 7 mục, thêm:
- Mục tiêu cuối và tiêu chí xong; phiên phụ được tự chia hand theo policy của dự án.
- PHẠM VI GHI tách khỏi các phiên khác (hai phiên không ghi cùng file); nếu cần tách hẳn thì dùng `--worktree`.
- Luật cấm chép nguyên văn (cấm đọc `.env`; luật chi phí, ngưỡng duyệt; không commit/push nếu dự án quy định vậy).
- Yêu cầu ghi tóm tắt bàn giao vào `handoff_dir` khi xong hoặc khi dừng giữa chừng.

## 2. Lệnh

- Mở: `side-session start --name <tên> --prompt-file <file> [--worktree [--base <nhánh>]] [--provider claude|codex|dsh] [--chrome|--no-chrome] [--budget-exempt|--force-budget] [--max-tokens N] [--hours H] [--brain <tên brain>] [--dry-run]` (`--prompt "<text>"` cho prompt ngắn).
- Mở lại phiên Claude đã dừng: `side-session start --name <tên> --resume [--prompt-file <file>] [--max-tokens N] [--chrome|--no-chrome] [--budget-exempt|--force-budget]`; giữ `uuid`, `dir`, `handoff`, `worktree`, `parent_session` của state cũ, đặt `started` mới và `tokens_used` về 0. Prompt mặc định nhắc đọc lại việc đang dở (không ghép lại khối bàn giao); có `--prompt-file` thì ghép trailer như start. Không dùng với `--prompt`, `--worktree`, `--base` hay provider khác `claude`; state thiếu, provider khác `claude` hoặc screen `side-<tên>` còn sống thì thoát 2.
- Danh sách: `side-session ls`. Theo dõi: `side-session watch --name <tên> [--once]` (chạy nền bằng `run_in_background`, không tự viết vòng chờ).
- Gắn vào phiên đang chạy: `side-session attach [<tên>]` mở screen của phiên phụ bằng `screen -x <pid.tên>` (không cần config, chạy được từ thư mục bất kỳ); bỏ tên thì in menu đánh số, Enter làm mới, chọn số để gắn, `q` để thoát; detach bằng Ctrl-a d rồi menu hiện lại.
- Bàn giao: `side-session handoff <tên>` in tóm tắt bàn giao; brain đọc, tự review diff của phiên phụ trước khi báo người dùng.
- Dừng: `side-session stop <tên>` sau khi đã đọc bàn giao.

## 3. Dự phòng và đồng bộ

- **Provider:** mặc định `claude`; khi hết hạn mức gói Claude hoặc phiên claude lỗi, dùng `--provider codex` (chạy trên đăng nhập gói của Codex, không dùng API key) hoặc hand ngoài `dsh` (xem mục 4, không API key).
- **Đồng bộ:** phiên phụ hiện trong ListAgents; gửi SendMessage trước khi ghi file chung, dùng tài nguyên trả phí hay Chrome, và sau mỗi commit. Hai phiên không ghi cùng một file.

## 4. Chrome và hand ngoài

- **Khi dùng `--chrome`:** chỉ khi việc thật sự cần trình duyệt có phiên đăng nhập sẵn (kiểm UI web, thao tác trang cần Chrome của người dùng); việc code/tài liệu bình thường để mặc định `--no-chrome` cho nhẹ ngữ cảnh. `--chrome` chỉ dùng với provider `claude`; provider khác thoát 2. `--no-chrome` để đè `claude_args` đang bật Chrome.
- **Khi dùng provider `dsh`:** việc code/test/tài liệu tự chứa dài, cần thêm một hand ngoài song song trên gói thứ hai (OpenCode Go, không API key), nhất là khi hạn mức Claude căng. Bắt buộc `--worktree` — hand ngoài chỉ làm trong worktree, không đụng cây chính — và prompt sau khi ghép template phải chép nguyên văn mục `LUẬT BẮT BUỘC` (cấm đọc `.env`/API key, không commit, không xoá `output/llm/`...). `start` ghi prompt ra `<state_dir>/<tên>.prompt.md` rồi chạy `hand-ext run ... --label side:<tên>` trong screen; `watch` đọc token từ sổ lượt `hand-ext` (vào + ra, không tính cached) và chép `report.md` thành bàn giao khi lượt xong.
- **Trần ngày:** `side_session.budget_check_cmd` chạy ở `start` (mã khác 0 → thoát 4, trừ `--budget-exempt`/`--force-budget`) và mỗi vòng `watch` (mã 20 và không `budget_exempt` → `daystop`). `--budget-exempt` ghi vào state để `watch` cũng miễn; `--force-budget` chỉ bỏ qua lần `start` đó.

## 5. Cấu hình đếm token

- `side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ `claude`, đường dẫn tính từ repo; `start`/`--resume` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`.
- `side_session.token_file` (mặc định `""`) là đường dẫn tính từ repo tới file status line ghi, có placeholder `{uuid}`, ví dụ `sessions/ops/runs/{uuid}.tokens` (một số nguyên một dòng). Khi đặt và provider `claude`, `ls`/`watch` đọc số nguyên không âm trong file thay vì cộng transcript; file thiếu hoặc nội dung hỏng tính 0, không rơi về transcript. Dùng khi trần của repo tính theo `context_window.total_input_tokens + total_output_tokens` của status line.
- `side_session.enforce_token_cap` (mặc định `true`): đặt `false` thì `watch` vẫn đếm token và giữ cảnh báo 80 %, nhưng khi chạm trần chỉ in cảnh báo "over cap" mỗi vòng và giữ phiên `running` thay vì dừng `capped`; `ls` vẫn thêm ` !` sau cột `TOKENS/CAP` khi chạm trần; trần ngày/USD qua `budget_check_cmd` không đổi.
