---
name: side-session
description: Mở và quản lý phiên phụ (phiên Sol Codex mặc định, hoặc Claude Code/dsh chạy riêng, có ngữ cảnh brain riêng) bằng lệnh side-session cho gói việc dài nhiều bước - khi nào mở, viết prompt giao việc, start/ls/watch/handoff/stop, cờ --model/--effort, hợp đồng bàn giao .done, đọc tóm tắt bàn giao, backend claude-main và chặn 5%/ngày, hand ngoài dsh trong worktree, Chrome khi việc cần trình duyệt, đồng bộ bằng ListAgents/SendMessage khi provider claude. Từ khoá kích hoạt - "phiên phụ", "side session", "side-session", "mở phiên mới", "phiên song song", "giao gói việc dài", "bàn giao", "handoff".
---

# Phiên phụ (side-session)

## Tóm tắt

- **Dùng khi:** gói việc dài nhiều bước cần ngữ cảnh brain riêng (L1 trở lên, L0 gom nhiều việc vào một phiên), ví dụ cả một tính năng hay một chương; việc ngắn thì giao hand.
- **Giới hạn:** tối đa `max_parallel` phiên (mặc định 2) theo mục `side_session` của `.claude/hybrid-hands.json`; bàn giao ghi ở `handoff_dir` (mặc định `docs/work-in-progress/handoffs`), xong thì tạo `<handoff_dir>/<tên>.done`; phiên phụ ngoài (`dsh`) chỉ chạy trong worktree.
- **Chuỗi bước:** viết prompt giao việc → `side-session start --provider codex` (thử `--dry-run` trước) → chờ `<handoff_dir>/<tên>.done` bằng Monitor, không hỏi trạng thái → đọc `handoff` → Sol review code, Opus review spec/plan/giải pháp → `stop`. Xem toàn cảnh phiên chính, phiên phụ, subagent và hand ngoài bằng `hh-ps` (`--watch 5`, `--json`).

Nếu `side-session` không có trong PATH, gọi bằng đường dẫn tuyệt đối `${CLAUDE_PLUGIN_ROOT}/bin/side-session`.

## Ba tầng và lane

| Tầng | Vai trò |
|---|---|
| Opus (brain, gói Claude chính) | Thư ký, solution architect, BA, product manager; phân lane, viết spec/plan L2/L3, duyệt tóm tắt, đọc bàn giao, không đọc diff task đã giao Sol |
| Sol (phiên phụ Codex `gpt-6.1-sol` effort high, tài khoản ChatGPT riêng, `CODEX_HOME` `~/.codex-hand`) | Lead tech, lead QA, quyền ngang Opus; viết spec L1, review code mọi hand mình giao, gọi `hand-ext` cho dsh |
| dsh (gói OpenCode Go) | Dev, tester |
| Hand Opus `low` (`hybrid-hands:hand`) | Việc sáng tạo: UI design, mockup, design token, câu chữ; phần code hoá giao dsh |

| Lane | Ai viết spec/plan | Ai duyệt | Ai làm | Ai review code |
|---|---|---|---|---|
| L0 (sửa nhanh) | Không viết spec | Không duyệt | dsh | Sol |
| L1, không có lựa chọn giải pháp | Sol | Không duyệt, Opus đọc bàn giao | dsh | Sol |
| L1 có lựa chọn giải pháp, hoặc thuộc mức kỹ | Sol, mở đầu bằng tóm tắt quyết định 1 trang | Opus đọc tóm tắt | dsh | Sol |
| L2/L3 | Opus | Người dùng | Opus cắt thành các gói cỡ L1, giao các phiên Sol | Sol |

Opus gom nhiều việc L0 vào một phiên Sol; mỗi task một phiên, xong thì Sol ghi bàn giao và đóng phiên, không giữ phiên qua nhiều task. L2/L3: Opus viết spec/plan, người dùng duyệt, Opus cắt thành gói cỡ L1 giao các phiên Sol (tối đa `max_parallel`).

## 1. Prompt giao việc

Viết vào file trong scratchpad, theo khuôn brief 7 mục, thêm:
- Mục tiêu cuối và tiêu chí xong; phiên phụ được tự chia hand theo policy của dự án.
- PHẠM VI GHI tách khỏi các phiên khác (hai phiên không ghi cùng file); nếu cần tách hẳn thì dùng `--worktree`.
- Luật cấm chép nguyên văn (cấm đọc `.env`; luật chi phí, ngưỡng duyệt; không commit/push nếu dự án quy định vậy).
- Yêu cầu ghi tóm tắt bàn giao vào `handoff_dir` khi xong hoặc khi dừng giữa chừng.

## 2. Lệnh

- Mở: `side-session start --name <tên> --prompt-file <file> [--worktree [--base <nhánh>]] [--provider claude|codex|dsh] [--model M] [--effort E] [--chrome|--no-chrome] [--budget-exempt|--force-budget] [--max-tokens N] [--hours H] [--brain <tên brain>] [--dry-run]` (`--prompt "<text>"` cho prompt ngắn). Provider mặc định là `codex` (Sol); `--model`/`--effort` mặc định theo `side_session.codex_model`/`codex_effort` (`gpt-6.1-sol`/`high`), truyền cho codex hoặc hand-ext. `--resume` mặc định `claude`.
- Mở lại phiên Claude đã dừng: `side-session start --name <tên> --resume [--prompt-file <file>] [--max-tokens N] [--chrome|--no-chrome] [--budget-exempt|--force-budget]`; giữ `uuid`, `dir`, `handoff`, `worktree`, `parent_session` của state cũ, đặt `started` mới và `tokens_used` về 0. Prompt mặc định nhắc đọc lại việc đang dở (không ghép lại khối bàn giao); có `--prompt-file` thì ghép trailer như start. Không dùng với `--prompt`, `--worktree`, `--base` hay provider khác `claude`; state thiếu, provider khác `claude` hoặc screen `side-<tên>` còn sống thì thoát 2.
- Danh sách: `side-session ls`. Theo dõi: `side-session watch --name <tên> [--once]` (chạy nền bằng `run_in_background`, không tự viết vòng chờ). `ls`/`watch` báo `done` khi thấy `<handoff_dir>/<tên>.done`; Opus chờ file này bằng Monitor, không hỏi trạng thái.
- Gắn vào phiên đang chạy: `side-session attach [<tên>]` mở screen của phiên phụ bằng `screen -x <pid.tên>` (không cần config, chạy được từ thư mục bất kỳ); bỏ tên thì in menu đánh số, Enter làm mới, chọn số để gắn, `q` để thoát; detach bằng Ctrl-a d rồi menu hiện lại.
- Bàn giao: `side-session handoff <tên>` in tóm tắt bàn giao. Sol review code của mọi hand mình giao; Opus review spec, plan, giải pháp của Sol và đọc bàn giao (Tóm tắt, kết quả test), không đọc diff của task đã giao Sol. Việc Opus tự giao hand thì Opus tự review như cũ.
- Dừng: `side-session stop <tên>` sau khi đã đọc bàn giao.

## 3. Dự phòng và đồng bộ

- **Provider:** mặc định `codex` cho phiên Sol (đăng nhập ChatGPT riêng qua `CODEX_HOME=~/.codex-hand`, không API key); `--provider claude` cho phiên Claude Code, `--provider dsh` cho hand ngoài (xem mục 4). Codex chạy `-a never -s workspace-write` có mạng và `writable_roots` gồm worktree, `handoff_dir`, `runs_dir`, sổ/quota, state và `~/.claude` để gọi `hand-ext`.
- **Đồng bộ:** phiên `claude` hiện trong ListAgents; gửi SendMessage trước khi ghi file chung, dùng tài nguyên trả phí hay Chrome, và sau mỗi commit. Phiên Sol (Codex) không có ListAgents/SendMessage: đồng bộ bằng file `<handoff_dir>/<tên>.done` và bàn giao. Hai phiên không ghi cùng một file.

## 4. Chrome và hand ngoài

- **Khi dùng `--chrome`:** chỉ khi việc thật sự cần trình duyệt có phiên đăng nhập sẵn (kiểm UI web, thao tác trang cần Chrome của người dùng); việc code/tài liệu bình thường để mặc định `--no-chrome` cho nhẹ ngữ cảnh. `--chrome` chỉ dùng với provider `claude`; provider khác thoát 2. `--no-chrome` để đè `claude_args` đang bật Chrome.
- **Khi dùng provider `dsh`:** việc code/test/tài liệu tự chứa dài, cần thêm một hand ngoài song song trên gói thứ hai (OpenCode Go, không API key), nhất là khi hạn mức Claude căng; dsh hết hạn mức thì Sol dùng `hand-ext run --backend codex --effort medium`, Sol hết hạn mức thì task về Opus hoặc chờ reset. Việc sáng tạo trong phiên Sol gọi `hand-ext run --backend claude-main`; backend này thoát 7 khi máy đã dùng ≥5% hạn mức tuần Claude trong ngày (hoặc không tính được), khi đó ghi yêu cầu vào bàn giao để Opus quyết. Bắt buộc `--worktree` — hand ngoài chỉ làm trong worktree, không đụng cây chính — và prompt sau khi ghép template phải chép nguyên văn mục `LUẬT BẮT BUỘC` (cấm đọc `.env`/API key, không commit, không xoá `output/llm/`...). `start` ghi prompt ra `<state_dir>/<tên>.prompt.md` rồi chạy `hand-ext run ... --label side:<tên>` trong screen; `watch` đọc token từ sổ lượt `hand-ext` (vào + ra, không tính cached) và chép `report.md` thành bàn giao khi lượt xong.
- **Trần ngày:** `side_session.budget_check_cmd` chạy ở `start` (mã khác 0 → thoát 4, trừ `--budget-exempt`/`--force-budget`) và mỗi vòng `watch` (mã 20 và không `budget_exempt` → `daystop`). `--budget-exempt` ghi vào state để `watch` cũng miễn; `--force-budget` chỉ bỏ qua lần `start` đó.

## 5. Cấu hình đếm token

- `side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ `claude`, đường dẫn tính từ repo; `start`/`--resume` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`.
- `side_session.token_file` (mặc định `""`) là đường dẫn tính từ repo tới file status line ghi, có placeholder `{uuid}`, ví dụ `sessions/ops/runs/{uuid}.tokens` (một số nguyên một dòng). Khi đặt và provider `claude`, `ls`/`watch` đọc số nguyên không âm trong file thay vì cộng transcript; file thiếu hoặc nội dung hỏng tính 0, không rơi về transcript. Dùng khi trần của repo tính theo `context_window.total_input_tokens + total_output_tokens` của status line.
- `side_session.codex_model`/`codex_effort` (mặc định `gpt-6.1-sol`/`high`) là model/effort cho provider `codex` và Sol; `--model`/`--effort` đè cho một lượt.
- `side_session.enforce_token_cap` (mặc định `true`): đặt `false` thì `watch` vẫn đếm token và giữ cảnh báo 80 %, nhưng khi chạm trần chỉ in cảnh báo "over cap" mỗi vòng và giữ phiên `running` thay vì dừng `capped`; `ls` vẫn thêm ` !` sau cột `TOKENS/CAP` khi chạm trần; trần ngày/USD qua `budget_check_cmd` không đổi.
