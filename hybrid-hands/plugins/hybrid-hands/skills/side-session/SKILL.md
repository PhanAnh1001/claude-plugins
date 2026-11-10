---
name: side-session
description: Mở và quản lý phiên phụ (phiên Sol Codex mặc định, hoặc Claude Code/dsh chạy riêng, có ngữ cảnh brain riêng) bằng lệnh side-session cho gói việc dài nhiều bước - khi nào mở, viết prompt giao việc, start/ls/watch/handoff/stop, cờ --model/--effort, hợp đồng bàn giao .done, đọc tóm tắt bàn giao, account v1/v2/v… và guard v1 5%/ngày, hand ngoài dsh trong worktree, Chrome khi việc cần trình duyệt, đồng bộ bằng ListAgents/SendMessage khi provider claude. Từ khoá kích hoạt - "phiên phụ", "side session", "side-session", "mở phiên mới", "phiên song song", "giao gói việc dài", "bàn giao", "handoff".
---

Tóm tắt cập nhật 0.35.0: cấu hình global và repo quyết định lựa chọn phiên/hand theo tài khoản.

Cấu hình ưu tiên: mặc định plugin → global `~/.hybrid-hands/config.json` (đổi đường dẫn bằng `HYBRID_HANDS_CONFIG`) → repo `.claude/hybrid-hands.json` → cờ CLI. Dict merge sâu; list/scalar thay nguyên. Global thiếu thì bỏ qua; global hỏng báo lỗi kèm đường dẫn và dừng. `hand-ext config --json` in cấu hình hiệu lực, nguồn từng key và đường dẫn file đã đọc. `ext_hand.claude_accounts` và `ext_hand.backends.*` đặt được ở global. Dưới Paseo, biến `HYBRID_HANDS_CONFIG` phải có trong môi trường daemon mới có tác dụng.

`main_session` áp cho `side-session start --main`: `provider` mặc định `codex`, `codex_model`/`codex_effort` mặc định `gpt-6.1-sol`/`high`, `claude_model`/`claude_effort`/`claude_account` mặc định `claude-opus-5-5`/`high`/`v1`. `side_session` có các key tương ứng, gồm `provider`, `codex_model`, `codex_effort` và các key `claude_*`. Cờ `--provider`, `--model`, `--effort`, `--account` ghi đè cấu hình; `--resume` mặc định provider Claude và giữ account của state. `main_session` không áp cho phiên người dùng tự mở bằng `claude`.

Cả hai mục có `transport` cho Claude: mặc định `paseo`, chọn `screen` tường minh trong cấu hình (không có cờ `--transport`). Paseo lỗi thì báo lỗi, không tự lùi về screen. Phiên Claude qua Paseo nhận `CLAUDE_CONFIG_DIR` theo account. Template Sol chính nhận model/effort thực tế, đường dẫn tuyệt đối tới bin/skill và khuôn brief.


Mở main Sol high: `side-session start --main --name sol-main`; đường Codex cần daemon Paseo. Main Claude: `side-session start --main --provider claude --account v2` (hoặc v1/v…), mặc định qua Paseo; chọn `main_session.transport=screen` nếu cần screen. Cả hai không dùng `--worktree`, không handoff/watchdog, không chiếm slot phiên phụ.


## Chọn hand theo tài khoản

Phiên chính mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… hoặc Sol 6.1 high. Phiên phụ mặc định Sol 6.1 high, có thể là Opus 5.5 high đúng tài khoản v1/v2/v… . Đổi model/account: mở phiên mới từ bàn giao, không dùng `/model` giữa phiên.

Mặc định `ext_hand.order`: dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus 5.5 low) → claude-v2 (Opus 5.5 low). `claude_accounts` lấy từ mặc định plugin → global `~/.hybrid-hands/config.json` → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình. `claude-main` và `claude` chỉ là alias tương thích lần lượt của `claude-v1` và `claude-v2`.

Luôn chạy `hand-ext pick --json` trước để biết backend/model/effort/account, `native`/`native_reason` và lý do bỏ qua, kể cả trước native v1 để giữ chặn ≥5%/ngày (thiếu nguồn cũng chặn). Cùng account và tools chọn đúng model/effort mới native; khác account hoặc thiếu capability dùng `hand-ext run --backend auto`. Không tự áp native cho account khác.

| Phiên phụ | dsh | codex low | claude-v1 low | claude-v2 low | UI v1 low |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex | hand-ext | hand-ext | hand-ext claude-v1 |
| Opus v1 | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext | Native khi preflight v1 đủ; thiếu thì hand-ext claude-v1 |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext claude-v1 |

Sáng tạo UI mặc định claude-v1 low. Native v1 chỉ khi `hand-ext pick --json` thực trả `claude-v1`, model `claude-opus-5-5`, effort `low`, đúng account và đủ capability. Pick trả dsh/codex chưa chứng minh guard v1 đã qua: dùng `hand-ext run --backend claude-v1` để wrapper enforce guard, không sửa config/order hoặc suy guard pass. Guard chặn thì không spawn native v1; ghi yêu cầu để Opus quyết. Công việc theo order tiếp tục backend pick chọn.
Native Codex dùng `fork_turns=none`, brief tự chứa, luật dữ liệu nguyên văn; executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Không bật parallel-subagents, không đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota.

Review thấy lỗi: giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp theo order dsh → codex → claude-v1 → claude-v2. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; không tự đổi effort. Exit 8: đợi slot, không đổi backend/tự làm.


## Usage panel 0.26.0

`hh-ps --once` chạy một lần; `--json` giữ dữ liệu máy đọc, `--watch 5` theo dõi. Mặc định hiện đủ việc chạy/vừa xong theo `--since`, không gấp còn 3 việc và không ẩn cây đã xong (`--full`/`--ended` giữ tương thích). Mỗi dòng session/subagent/hand và phiên phụ mọi provider/backend có model, effort, USD~, quota tài khoản 5h/tuần, ended hoặc `đang chạy`, elapsed. Elapsed đang chạy tăng theo thời gian; ended cố định duration khi xong. Không hiện giờ bắt đầu trong text/panel/statusline; metadata/JSON vẫn giữ started. Thiếu nguồn hoặc legacy unknown hiện `?`, không bịa.

Giá chỉ từ [`config/model-prices.json`](../../config/model-prices.json), override bằng `HYBRID_HANDS_PRICING_FILE`; mỗi entry có source/price_date, file có verified_at. Mọi USD~ là ước tính offline trên gói subscription, không phải hoá đơn. Cache Claude dùng đúng giá cấu hình 5m/1h; không fallback theo họ/model khác. Nguồn giá công khai được xác minh ngày 2026-11-07 và lưu trong file canonical. Giá DeepSeek peak là ước tính bảo thủ. Không thêm bảng giá backend thứ hai.

Quota tài khoản lấy từ cache/sample sẵn có của đúng gói; thiếu 5h/tuần hiện `?`, tuyệt đối không suy token hay USD thành quota GPT. Phần riêng hand tuần chỉ thêm khi có nguồn và gắn nhãn riêng. Cả hai giao diện cây `hh-tree-pane` và `paseo-hh-tree` không hiện nhóm orphan hand-ext; `hh-ps` text/JSON vẫn giữ orphan.

Metadata mới giữ parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. `CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn đúng cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Sol Codex/Claude/dsh và mọi loại agent/backend. Hand nhận brief trực tiếp là executor: làm trong phạm vi được giao, không gọi hand-ext, không mở side-session hay giao tiếp phiên khác. Luật Sol bắt buộc delegate chỉ áp dụng vai trò Sol; dùng `hand-ext run --backend auto` trừ ngoại lệ native trên Paseo nêu trên.



Opus chia brief thành các gói L1 độc lập khác file, chủ động lấp tối đa `side_session.max_parallel` Sol (mặc định 4). MỖI SOL chia brief độc lập khác file và chạy nền tổng native + hand-ext tối đa `ext_hand.max_parallel` hand (mặc định 4), chờ đủ tất cả kết thúc rồi Sol review. Cùng file hoặc phụ thuộc phải tuần tự; không ép song song. Có thể 16 hand tổng khi 4 Sol độc lập; không phải cap toàn máy 4. `side_session.max_parallel` là số nguyên 1..6, mặc định 4; `ext_hand.max_parallel` vẫn là số nguyên 1..4, mặc định 4. Scope hand riêng mỗi Sol qua `HYBRID_HANDS_HAND_SCOPE` = uuid Sol, giữ nguyên `CODEX_HOME` và parent Claude session. Exit 8: đợi slot/tiến trình đang chạy kết thúc rồi thử lại; không đổi backend hay tự làm như lỗi hand.


# Phiên phụ (side-session)

Trừ native cùng tài khoản nêu trên, Sol **BẮT BUỘC giao code/test/tài liệu L0/L1** bằng `hand-ext run --backend auto` theo `ext_hand.order` của repo. Sol chỉ tự viết khi hand-ext thoát lỗi (ghi lý do và mã thoát vào bàn giao) hoặc việc cần secret/dữ liệu khách hàng theo luật dữ liệu. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.

Codex Sol và hand dùng chung `~/.codex-hand`: mỗi lượt hand override `model` bằng `-m`, `model_reasoning_effort` bằng `-c`, `sandbox_mode` bằng `-s`. Doctor không chặn nếu ba khóa thiếu/lệch và không ghi config; kiểm tra cài đặt, đăng nhập gói và khóa legacy không override như `service_tier` vẫn bắt buộc.

## Tóm tắt

- **Dùng khi:** gói việc dài nhiều bước cần ngữ cảnh brain riêng (L1 trở lên, L0 gom nhiều việc vào một phiên), ví dụ cả một tính năng hay một chương; việc ngắn thì giao hand.
- **Giới hạn:** tối đa `max_parallel` phiên (mặc định 4) theo mục `side_session` của `.claude/hybrid-hands.json`; bàn giao ghi ở `handoff_dir` (mặc định `docs/work-in-progress/handoffs`), xong thì tạo `<handoff_dir>/<tên>.done`; phiên phụ ngoài (`dsh`) chỉ chạy trong worktree.
- **Chuỗi bước:** viết prompt giao việc → `side-session start --provider codex` (thử `--dry-run` trước) → chờ `<handoff_dir>/<tên>.done` bằng Monitor, không hỏi trạng thái → đọc `handoff` → Sol review code, Opus review spec/plan/giải pháp → `stop`. Xem toàn cảnh phiên chính, phiên phụ, subagent và hand ngoài bằng `hh-ps` (`--once`, `--watch 5`, `--json`).

Nếu `side-session` không có trong PATH, gọi bằng đường dẫn tuyệt đối `${CLAUDE_PLUGIN_ROOT}/bin/side-session`.

## Ba tầng và lane

| Tầng | Vai trò |
|---|---|
| Opus (brain, gói Claude chính) | Thư ký, solution architect, BA, product manager; phân lane, viết spec/plan L2/L3, duyệt tóm tắt, đọc bàn giao, không đọc diff task đã giao Sol |
| Sol (phiên phụ Codex `gpt-6.1-sol` effort high, tài khoản ChatGPT riêng, `CODEX_HOME` `~/.codex-hand`) | Lead tech, lead QA, quyền ngang Opus; viết spec L1, review code mọi hand mình giao, gọi `hand-ext run --backend auto` theo `ext_hand.order` |
| dsh (gói OpenCode Go) | Dev, tester |
| Hand Opus `low` (`hybrid-hands:hand`) | Việc sáng tạo: UI design, mockup, design token, câu chữ; phần code hoá giao hand mặc định theo `ext_hand.order` (mặc định dsh → codex → claude-v1 → claude-v2) |

| Lane | Ai viết spec/plan | Ai duyệt | Ai làm | Ai review code |
|---|---|---|---|---|
| L0 (sửa nhanh) | Không viết spec | Không duyệt | hand theo `ext_hand.order` | Sol |
| L1, không có lựa chọn giải pháp | Sol | Không duyệt, Opus đọc bàn giao | hand theo `ext_hand.order` | Sol |
| L1 có lựa chọn giải pháp, hoặc thuộc mức kỹ | Sol, mở đầu bằng tóm tắt quyết định 1 trang | Opus đọc tóm tắt | hand theo `ext_hand.order` | Sol |
| L2/L3 | Opus | Người dùng | Opus cắt thành các gói cỡ L1, giao các phiên Sol | Sol |

Opus gom nhiều việc L0 vào một phiên Sol; mỗi task một phiên, xong thì Sol ghi bàn giao và đóng phiên, không giữ phiên qua nhiều task. L2/L3: Opus viết spec/plan, người dùng duyệt, Opus cắt thành gói cỡ L1 giao các phiên Sol (tối đa `max_parallel`).

### Worktree sparse (tuỳ chọn)

`side_session.worktree_sparse_exclude` là list pattern cú pháp gitignore, mặc định `[]` (checkout đủ như cũ). Khác rỗng thì `start --worktree` chạy `git worktree add --no-checkout …` → `git -C <wt> sparse-checkout set --no-cone --stdin` (dòng `/*` rồi `!<pattern>` mỗi pattern, truyền qua stdin) → `git -C <wt> checkout`; sparse chỉ ghi vào config riêng của worktree mới. Ví dụ: `"worktree_sparse_exclude": ["docs/assets/*-data/"]`. Pattern phải là chuỗi khác rỗng, không xuống dòng/NUL, không bắt đầu bằng `!`; sai thì báo lỗi trước khi tạo worktree. Cờ `--no-sparse` bỏ qua cấu hình. Bước sparse/checkout lỗi thì không launch agent và giữ nguyên worktree để xử lý.

## 1. Prompt giao việc

Viết vào file trong scratchpad, theo khuôn brief 7 mục, thêm:
- Mục tiêu cuối và tiêu chí xong; phiên phụ được tự chia hand theo policy của dự án.
- PHẠM VI GHI tách khỏi các phiên khác (hai phiên không ghi cùng file); nếu cần tách hẳn thì dùng `--worktree`.
- Luật cấm chép nguyên văn (cấm đọc `.env`; luật chi phí, ngưỡng duyệt; không commit/push nếu dự án quy định vậy).
- Yêu cầu ghi tóm tắt bàn giao vào `handoff_dir` khi xong hoặc khi dừng giữa chừng.

## 2. Lệnh

- Mở: `side-session start --name <tên> --prompt-file <file> [--worktree [--base <nhánh>]] [--provider claude|codex|dsh] [--model M] [--effort E] [--chrome|--no-chrome] [--budget-exempt|--force-budget] [--max-tokens N] [--hours H] [--brain <tên brain>] [--dry-run]` (`--prompt "<text>"` cho prompt ngắn). Provider mặc định là `codex` (Sol); `--model`/`--effort` mặc định theo `side_session.codex_model`/`codex_effort` (`gpt-6.1-sol`/`high`), truyền cho codex hoặc hand-ext. `--resume` mặc định `claude`.
- Mở lại phiên Claude đã dừng: `side-session start --name <tên> --resume [--prompt-file <file>] [--max-tokens N] [--chrome|--no-chrome] [--budget-exempt|--force-budget]`; giữ `uuid`, `dir`, `handoff`, `worktree`, `parent_session` của state cũ, đặt `started` mới và `tokens_used` về 0. Prompt mặc định nhắc đọc lại việc đang dở (không ghép lại khối bàn giao); có `--prompt-file` thì ghép trailer như start. Không dùng với `--prompt`, `--worktree`, `--base` hay provider khác `claude`; state thiếu, provider khác `claude` hoặc screen `side-<tên>` còn sống thì thoát 2.
- Danh sách: `side-session ls`. Theo dõi: `side-session watch --name <tên> [--once]` (chạy nền bằng `run_in_background`, không tự viết vòng chờ). `ls`/`watch` báo `done` sau khi kết thúc runtime/archive exact agent khi thấy `<handoff_dir>/<tên>.done`; Opus chờ file này bằng Monitor, không hỏi trạng thái.
- Gắn vào phiên đang chạy: `side-session attach [<tên>]` mở screen của phiên phụ bằng `screen -x <pid.tên>` (không cần config, chạy được từ thư mục bất kỳ); phiên Paseo thì chỉ in hướng dẫn mở app hoặc `paseo attach <agent-id>`. Bỏ tên thì in menu đánh số, Enter làm mới, chọn số để gắn, `q` để thoát; detach bằng Ctrl-a d rồi menu hiện lại.
- Bàn giao: `side-session handoff <tên>` in tóm tắt bàn giao. Sol review code của mọi hand mình giao; Opus review spec, plan, giải pháp của Sol và đọc bàn giao (Tóm tắt, kết quả test), không đọc diff của task đã giao Sol. Việc Opus tự giao hand thì Opus tự review như cũ.
- Dừng: `side-session stop <tên>` sau khi đã đọc bàn giao.

## 3. Dự phòng và đồng bộ

- **Provider:** mặc định `codex` cho phiên Sol (đăng nhập ChatGPT riêng qua `CODEX_HOME=~/.codex-hand`, không API key); `--provider claude` cho phiên Claude Code, `--provider dsh` cho hand ngoài (xem mục 4). Codex chạy `--dangerously-bypass-approvals-and-sandbox`: không sandbox, không hỏi phê duyệt, toàn quyền ghi và mạng (gọi được `hand-ext`, `git worktree add`).
- **Đồng bộ:** phiên `claude` hiện trong ListAgents; gửi SendMessage trước khi ghi file chung, dùng tài nguyên trả phí hay Chrome, và sau mỗi commit. ListAgents/SendMessage của Claude không phải native tools Codex; native child của Sol trên Paseo có tab/timeline theo ngoại lệ A ở trên. Đồng bộ Sol với brain vẫn bằng file `<handoff_dir>/<tên>.done` và bàn giao. Hai phiên không ghi cùng một file.

## 4. Chrome và hand ngoài

- **Khi dùng `--chrome`:** chỉ khi việc thật sự cần trình duyệt có phiên đăng nhập sẵn (kiểm UI web, thao tác trang cần Chrome của người dùng); việc code/tài liệu bình thường để mặc định `--no-chrome` cho nhẹ ngữ cảnh. `--chrome` chỉ dùng với provider `claude`; provider khác thoát 2. `--no-chrome` để đè `claude_args` đang bật Chrome.
- **Khi dùng provider `dsh`:** `side-session start --provider dsh` dành cho code/test/tài liệu tự chứa dài; bắt buộc cờ `--worktree` của side-session, không đụng cây chính. Prompt sau ghép phải có `LUẬT BẮT BUỘC` chép nguyên văn luật dữ liệu (cấm đọc `.env`/API key, không commit, không xoá `output/llm/`...). `start` ghi `<state_dir>/<tên>.prompt.md` rồi chạy `hand-ext run --backend dsh ... --label side:<tên>` trong screen; `watch` đọc token vào + ra, không cached, và chép report thành bàn giao khi lượt xong. Exit 7: doctor, ghi lý do để Opus quyết; exit 8: chờ slot.
- **Sáng tạo:** mặc định Claude v1 low. Sol dùng `hand-ext run --backend claude-v1`; wrapper giữ guard v1 ≥5%/ngày (thiếu nguồn cũng chặn), không vượt guard, ghi yêu cầu vào bàn giao để Opus quyết. Native cùng account chỉ dùng khi preflight v1 đầy đủ như mục chọn hand; cờ `--worktree` ở bullet dsh là của side-session.

- **Trần ngày:** `side_session.budget_check_cmd` chạy ở `start` (mã khác 0 → thoát 4, trừ `--budget-exempt`/`--force-budget`) và mỗi vòng `watch` (mã 20 và không `budget_exempt` → `daystop`). `--budget-exempt` ghi vào state để `watch` cũng miễn; `--force-budget` chỉ bỏ qua lần `start` đó.

## 5. Cấu hình đếm token

- `side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ `claude`, đường dẫn tính từ repo; `start`/`--resume` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`.
- `side_session.token_file` (mặc định `""`) là đường dẫn tính từ repo tới file status line ghi, có placeholder `{uuid}`, ví dụ `sessions/ops/runs/{uuid}.tokens` (một số nguyên một dòng). Khi đặt và provider `claude`, `ls`/`watch` đọc số nguyên không âm trong file thay vì cộng transcript; file thiếu hoặc nội dung hỏng tính 0, không rơi về transcript. Dùng khi trần của repo tính theo `context_window.total_input_tokens + total_output_tokens` của status line.
- `side_session.codex_model`/`codex_effort` (mặc định `gpt-6.1-sol`/`high`) là model/effort cho provider `codex` và Sol; `--model`/`--effort` đè cho một lượt.
- Provider `codex`: đường screen truyền `-c model_auto_compact_token_limit=272000` trong argv; đường Paseo không nhận key này trong `providerOptions` nên ghi cùng key top-level qua RPC native `config/value/write` của `codex app-server` (không tự sửa TOML, không đọc/in config). `watch` không dừng `capped` theo tổng token tiêu. `TOKENS/CAP` hiển thị context từ `last_token_usage` cuối (input đã gồm cached + output) trên 272000, không thêm ` !`; tổng token cộng dồn chỉ dùng báo cáo.
- `side_session.enforce_token_cap` (chỉ áp dụng provider khác `codex`, mặc định `true`): đặt `false` thì `watch` vẫn đếm token và giữ cảnh báo 80 %, nhưng khi chạm trần chỉ in cảnh báo "over cap" mỗi vòng và giữ phiên `running` thay vì dừng `capped`; `ls` vẫn thêm ` !` sau cột `TOKENS/CAP` khi chạm trần; trần ngày/USD qua `budget_check_cmd` không đổi.

## 6. Transport Paseo cho phiên Sol (Codex)

- **Khi nào:** `side-session start --provider codex` (mặc định) thử daemon Paseo trước khi tạo worktree. Endpoint lấy từ `PASEO_HOME`/`PASEO_HOST`, mặc định home; mọi bước sau dùng đúng endpoint đã lưu trong state (đổi endpoint thì `ls`/`watch` báo unknown và `stop` từ chối, không điều khiển nhầm agent).
- **Daemon sẵn sàng:** tạo workspace directory cho đúng cwd/worktree, rồi agent provider `codex-hand` với `CODEX_HOME=side_session.codex_home`, model/effort của phiên, `approval_policy=never`, `sandbox_mode=danger-full-access` (toàn quyền như đường screen); không truyền `modeId`. State lưu `transport=paseo`, agent id, workspace id, thread id (nếu daemon trả) và endpoint. Agent hiện trong app Paseo ngay khi tạo; điện thoại chỉ thấy sau khi app kết nối daemon đó (người dùng xác nhận trên UI).
- **Paseo không sẵn sàng:** daemon không kết nối được hoặc không tìm thấy `@getpaseo/cli` thì báo lỗi và dừng; không tự lùi về screen. `codex_profile` khác rỗng chưa hỗ trợ qua Paseo và báo lỗi. `--dry-run` chỉ in kế hoạch, không gọi daemon.
- **Tạo lỗi:** sau khi daemon đã nhận tạo workspace/agent mà lỗi thì thoát 1, tuyệt đối không mở screen để tránh hai writer; state vẫn ghi agent/workspace id nhận được. Timeout/protocol/không có agent id là `unknown`: giữ slot `max_parallel`, chặn dùng lại tên tới khi `stop`/reconcile, không tự retry và không mở watchdog. Chỉ lỗi daemon từ chối chắc chắn (ví dụ `AGENT_CREATE_FAILED`) mới là `error` không chiếm slot.
- **Theo dõi:** `ls`/`watch` đọc trạng thái agent khi `transport=paseo`: `running`/`initializing` là đang chạy, `idle` của Codex thành `idle_no_done` với warning thiếu `.done`, giữ slot/watch và chặn trùng tên (không tự gửi prompt); turn mới trở lại `running`, `error`/`closed` là dead; mất kết nối là unknown, không kết luận dead và không bỏ qua `max_parallel`. `ls` giữ nguyên `done`/`stopped`/`daystop` đã ghi, không hồi sinh thành `idle`/`running`; agent đã mất không còn chiếm slot. Screen dùng lifecycle rollout đã pin để nhận `idle_no_done`; metadata/token_count sau turn không đổi trạng thái. `.done` đóng screen hoặc cancel nếu đang chạy rồi archive exact agent Paseo và giải phóng slot; lỗi/timeout kết thúc runtime hoặc archive agent giữ active/watch để thử lại. Sau đó archive workspace do plugin tạo, kể cả private LOCAL, theo public `agent.workspaceId` và quy tắc membership/ownership ở mục archive bên dưới; giữ local shared/main/unknown, không suy từ cwd. Cảnh báo archive workspace không chặn `done`; `ls`/`watch` retry có giới hạn. Giữ hội thoại/state/worktree/artifact, không cleanup.
- **Điều khiển:** `attach <tên>` với phiên Paseo chỉ in hướng dẫn mở app hoặc `paseo attach <agent-id>` (không đụng screen). `stop` interrupt đúng agent đã lưu rồi dừng watchdog screen, giữ worktree và agent để xem lại.
- **Tương thích:** bridge Node `lib/side_session/paseo_bridge.mjs` import `dist/utils/client.js` và `dist/utils/daemon-target.js` của CLI cài sẵn, ghim hành vi theo `@getpaseo/cli` 0.15.0; không đọc/in credential, không hardcode đường dẫn NVM. Native compact của Codex ghi bằng RPC `config/value/write` qua `codex app-server` tạm (chỉ cấu hình, không tạo thread/turn, không đọc auth), không tự parse/format TOML và không in file.

## Chọn account Claude

`side-session start --provider claude --account v1|v2|v…` mở lead tech/QA đúng account (mặc định v1). `side-session start --main --provider claude --account v2` mở main Opus v2; `--main` riêng vẫn mở Sol high. Claude accounts lấy mặc định plugin → global `~/.hybrid-hands/config.json` → repo. Đổi model/account mở phiên mới từ bàn giao, không `/model`. Main báo trực tiếp người dùng, không bắt handoff/.done.

## Archive và giao lại (09/11/2026)

Thay Q4, side-session qua Paseo ở mọi provider ghi report/handoff rồi `.done`: archive exact child, sau đó archive workspace theo ownership/membership sau; không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Cảnh báo archive workspace không chặn trạng thái `done`; `ls`/`watch` retry có giới hạn. Giữ handoff, state, history, worktree, patch và report, không cleanup. Archive chỉ ẩn ở sidebar Paseo; các dòng done của hh-ps/panel giữ nguyên.

Giao lại bằng `side-session send --name NAME --prompt-file /ABS/FILE` cho mọi provider Paseo. Trình tự: restore workspace → unarchive cùng exact agent qua public send → gửi prompt, đặt state `running`, đổi tên `.done` cũ sang tên duy nhất để giữ lịch sử và khởi động lại watchdog. Không create agent trùng; thiếu cwd/worktree thì chặn. Khi ACK chưa rõ, trạng thái pending chặn gửi lại để tránh prompt trùng; lỗi xác định xảy ra trước khi gửi có thể retry. `start --resume` giữ tương thích hiện có. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts.

## Tên agent và workspace Paseo — 0.36.1

Tên agent và workspace của phiên phụ có dạng `<tên> · <loại> phụ`: ví dụ `qa · Sol phụ` (Codex), `qa · Opus v1 phụ`, `qa · Opus v2 phụ` (Claude theo account) hoặc `qa · dsh phụ`. Main và workspace shared giữ title hiện có.

Managed agent và workspace có dạng `<tên cha> › hand <backend> · <label>`, ví dụ `qa › hand codex · docs`. Cha được xác minh là main dùng `chính`, cha chưa xác định dùng `?` (ví dụ `? › hand dsh · docs`); không suy main từ cwd hay tên. Tên tối đa 60 ký tự; cắt label để giữ tiền tố cha và backend. Không đưa path, nội dung brief hay secret vào tên.

Naming áp dụng khi create, `side-session send` và managed followup; lặp lại cùng tên là idempotent, không tạo agent/workspace mới. Dùng API public Paseo 0.15.0: `createAgent` nhận `title`, đổi tên agent bằng `client.updateAgent(agentId, {name: title})` (đọc lại ở `.title`), đổi tên workspace bằng `client.setWorkspaceTitle(workspaceId, title)` (trả `{title}`). Workspace create chưa có title option nên đặt tên sau create. Hai method đổi tên không nằm trong required capabilities preflight: naming là best effort, lỗi chỉ cảnh báo, không chặn lifecycle; `ls`/`watch` retry hữu hạn, không chờ vô hạn hay tạo writer trùng.

Sửa tên cũ bằng các lệnh sau; mặc định dry-run, thêm `--apply` mới ghi:

```bash
side-session tidy --names --name qa
side-session tidy --names --name qa --apply
hand-ext managed names --cwd /ABS/REPO
hand-ext managed names --cwd /ABS/REPO --apply
```

`side-session tidy --names [--name NAME] [--apply]` chỉ sửa tên side-session do plugin sở hữu; bỏ `--name` để xét các phiên trong phạm vi state. `hand-ext managed names --cwd /ABS [--apply]` là thao tác tương đương cho managed hand. Dry-run không ghi; apply chỉ đổi tên agent/workspace plugin-owned được xác minh, chặn main, shared, foreign và workspace có member chưa rõ ownership. Không suy ownership từ title/cwd. Cả hai lặp an toàn và không archive. `side-session tidy` không có `--names` vẫn giữ contract archive hiện có; naming không đổi review gate, restore/send, IDs, history, worktree hay artifacts.


### Dọn worktree và disk guard

`side-session gc [--name NAME] [--json] [--fetch] [--apply] [--include-unmerged] [--prune-branches]` mặc định dry-run. `--name` giới hạn đúng gói; `--fetch` mới fetch origin, mặc định chỉ dùng refs sẵn có. Lệnh chỉ đọc metadata git/state/runtime và kích thước, không đọc nội dung file.

| Lớp | Điều kiện | Khi apply |
|---|---|---|
| A | Plugin-owned, kết thúc, runtime đã dừng/archive, sạch, đã merge hoặc patch tương đương base | Xoá worktree, giữ nhánh |
| B | Như A nhưng chưa merge | Chỉ xoá với `--include-unmerged`, giữ nhánh |
| C | File tracked bị sửa hoặc untracked không ignored | Giữ |
| D | Đang chạy hoặc metadata/runtime/base chưa rõ | Giữ |
| E | Không có ownership state chính xác của plugin | Chỉ báo cáo |

Base lấy từ state, legacy dùng `side_session.default_base`; xét base local và `origin/<base>` nếu có. Dry-run hiện ahead, tracked/ignored bytes và lý do giữ. Apply khoá repo, kiểm tra lại từng worktree rồi dùng `git worktree remove` không force. **Ignored bytes cũng bị xoá khi apply**, không thể khôi phục chúng từ nhánh. Mặc định giữ nhánh; `--prune-branches` chỉ thử `git branch -d` cho A. Nhật ký `<state_dir>/worktree-gc.jsonl` giữ branch/HEAD và bytes; khôi phục tracked commits bằng `git worktree add <dir> <branch>`, hoặc dùng SHA trong journal nếu nhánh đã bị prune và commit còn tồn tại.

`side_session.worktree_gc.auto` nhận `merged` (mặc định đã duyệt) hoặc `off`. Start worktree mới tự dọn chỉ lớp A; lỗi GC cảnh báo nhưng vẫn kiểm disk. Dry-run/resume/không tạo worktree không auto-GC. Nếu brief/session chỉ cho dry-run hoặc cần duyệt apply, tôn trọng giới hạn đó: dùng `auto=off` đã được người có thẩm quyền cấu hình, không khởi tạo worktree để lách giới hạn.

Disk guard kiểm ổ chứa worktree root: `disk_guard.warn_gb=20`, `block_gb=5` (đo GiB). `side-session start --worktree` và `hand-ext run` tạo isolated worktree bị chặn dưới ngưỡng với **exit 9**; `--ignore-disk-guard` chỉ dùng khi chủ động được phép vượt chặn.

`hand-ext gc [--cwd /ABS/REPO] [--json] [--apply]` cũng mặc định dry-run, chỉ dùng metadata ownership/registry/completion. Apply chỉ xoá worktree sạch đã kết thúc, recheck dưới khoá, không force; dirty/unknown/running hoặc managed execution chưa settled đều giữ. Detached HEAD đã dịch khỏi base ghi nhận cũng giữ. Journal ở `<machine_state_dir>/worktree-gc.jsonl`; không xoá report, patch hay `output/llm/`.

Sparse P4 **chưa có trong release này**: S0 đã được Sol review FAIL vì `isolation.prepare` làm mất excluded tracked paths trong baseline. `worktree_sparse_exclude` (thiết kế mặc định `[]`) và `--no-sparse` chỉ là thiết kế bị chặn, chưa dùng được. Hai pattern live-tiktok-games đã được duyệt ngày 10/11/2026; Opus chỉ cấu hình sau khi S0 đạt, không thử sparse trên repo thật trong gói hiện tại.

Sau merge gói, Sol xem `side-session gc --name <gói>` rồi chạy `side-session gc --name <gói> --apply` khi phạm vi brief/session cho phép. Nếu đang bị cấm apply hoặc cần người dùng duyệt, chỉ dry-run và bàn giao kết quả để duyệt; không tự apply. Archive Paseo và GC thư mục là hai thao tác riêng, không suy archive cho phép xoá.
