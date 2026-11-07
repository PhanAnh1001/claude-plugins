# hybrid-hands

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai theo 3 tầng Opus / Sol / dsh, bật theo từng dự án thay cho `parallel-subagents`: Opus (brain) chạy trên gói Claude chính; Sol là phiên phụ Codex trên tài khoản ChatGPT riêng; việc code/tài liệu tự chứa mặc định giao hand ngoài `dsh` trên gói subscription thứ hai để giữ hạn mức gói chính.
- **Thành phần:**
  - hand ngoài: lệnh `hand-ext` (mặc định chỉ `dsh` — DeepSeek V4.1 Flash trên gói OpenCode Go — trong `order`; `codex`, `claude`, `claude-main`, `gemini` chỉ khai báo để gọi tường minh; sổ token `output/llm/hand_usage.json`, sổ USD Go toàn máy `~/.hybrid-hands/go_usage.jsonl` và sổ Codex `~/.hybrid-hands/codex_usage.jsonl`, lệnh `hand-ext usage`), skill `ext-hand`;
  - hand Claude: agent `hybrid-hands:hand` (gói chính) cho việc cần tool riêng của Claude Code, lệnh trả phí của dự án, hoặc khi `hand-ext` thoát 7;
  - phiên phụ: lệnh `side-session` (mặc định mở phiên Sol Codex `gpt-6.1-sol` effort high, có ngữ cảnh brain riêng cho gói việc dài; hợp đồng bàn giao `.done`), skill `side-session`; lệnh `hh-ps` xem cây phiên Claude → subagent → lượt hand ngoài; lệnh `cc-switch` chuyển một phiên Claude qua lại giữa terminal và Paseo mà không để transcript rẽ nhánh; skill `paseo` theo dõi từ điện thoại;
  - hook SessionStart (khuôn brief, luật chọn hand, luật hạn mức) và UserPromptSubmit (bản ngắn).
- **Luật hạn mức:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; dsh 429 quá tải với `--backend auto` thì giữ patch nếu ≥ ngưỡng (mặc định 30 dòng) và chạy tiếp dsh, patch nhỏ thì codex `gpt-6.1-sol` effort low, vẫn quá tải thì `failed` giữ patch/worktree; dsh hết hạn mức thật thì Sol dùng `hand-ext run --backend codex --effort medium`, Sol hết hạn mức thì task về Opus hoặc chờ reset, `hand-ext` thoát 7 thì dùng hand Claude; sau mỗi lượt báo backend, token, % hạn mức (Claude/Codex) hoặc % Go 5h/tuần kèm USD ước tính, thời điểm reset.
- **Luật dữ liệu:** phiên phụ Sol được đọc secret và dữ liệu khách hàng như Opus; luật dưới áp cho hand ngoài (dsh, gemini, codex dùng làm hand): không giao hand ngoài việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude. Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được. Không hiện giá trị `.env` áp cho mọi tầng.
- **Luật test tối thiểu:** brain ghi mức test trong KIỂM CHỨNG của brief; mặc định hand chỉ viết test tối thiểu đủ chứng minh thay đổi đúng (1 test đường chính + tối đa 1-2 case biên/lỗi quan trọng, ưu tiên thêm assert vào test sẵn có). Mức "kỹ" chỉ gồm ĐÚNG 2 nhóm: (1) tính năng tạo hứng thú, giữ chân khiến người dùng trả tiền; (2) bảo mật chống tấn công từ ngoài. Hai nhóm này test đủ nhánh/biên/lỗi và kiểm chứng thực tế bằng luồng thật; nhóm (1) đo bằng event analytics + feature flag/A-B, chỉ đọc số tổng hợp không có thông tin cá nhân, nhóm (2) chạy SAST, quét dependency, DAST staging.
- **Cách ly worktree:** `hand-ext run` mặc định chạy hand trong git worktree sạch (chỉ file tracked + thay đổi chưa commit/untracked không bị ignore; `.env` bị ignore không có trong workspace), lưu `changes.patch` rồi áp về cwd gốc; xem mục 5.3.
- **Bật theo dự án:** cài ở scope project trong thư mục dự án, tắt `parallel-subagents` ở scope project (xem mục 3).
- **Việc cần làm lần đầu:** `hand-ext setup`, người dùng tự đăng nhập từng backend (mục 5), rồi `hand-ext doctor`.

## Ba tầng Opus / Sol / dsh

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

Opus gom nhiều việc L0 vào một phiên Sol (mỗi task một phiên), mở bằng `side-session start --provider codex`, chờ `<handoff_dir>/<tên>.done` bằng Monitor rồi đọc `side-session handoff`. L2/L3 do Opus viết spec/plan, người dùng duyệt, Opus cắt thành gói cỡ L1 giao các phiên Sol (tối đa `max_parallel`). Việc sáng tạo giao `hybrid-hands:hand`; trong phiên Sol gọi `hand-ext run --backend claude-main` (thoát 7 khi máy đã dùng ≥5% hạn mức tuần Claude trong ngày hoặc không tính được, khi đó ghi yêu cầu vào bàn giao để Opus quyết).

## 1. Cây thư mục

```text
hybrid-hands/
├── .claude-plugin/marketplace.json     # marketplace hybrid-hands-local
├── README.md
├── paseo-hh-tree/                      # plugin Paseo hiện cây phiên trong app
├── tests/                              # test của hand-ext, side-session, hh-ps, cc-switch
└── plugins/hybrid-hands/
    ├── .claude-plugin/plugin.json
    ├── agents/hand.md                  # hand Claude
    ├── bin/hand-ext, bin/side-session, bin/hh-ps, bin/cc-switch  # vào PATH của tool Bash khi plugin bật
    ├── lib/hand_ext/ (backends/: codex | claude | claude-main | dsh; day_budget.py, isolation.py), lib/side_session/, lib/hh_ps/, lib/cc_switch/
    ├── commands/to-paseo.md, commands/to-term.md  # slash command chuyển phiên hai chiều
    ├── hooks/hooks.json
    ├── scripts/session-start-policy.sh, scripts/inject-policy.sh
    ├── skills/ext-hand/, skills/side-session/, skills/paseo/
    └── templates/hand-brief.md, ext-hand-preamble.md, dsh-hand.yml, side-session-prompt.md, side-session-prompt-codex.md
```

## 2. Cài đặt

Chạy trong thư mục dự án (`<thư-mục-repo>` là nơi clone repo claude-plugins):

```sh
claude plugin marketplace add <thư-mục-repo>/hybrid-hands
claude plugin install hybrid-hands@hybrid-hands-local --scope project
claude plugin validate <thư-mục-repo>/hybrid-hands
```

`bin/` của plugin nằm trong PATH của tool Bash khi plugin bật; hook SessionStart vẫn in đường dẫn tuyệt đối tới `bin/` để brain gọi được nếu PATH thiếu.

## 3. Chuyển qua lại với parallel-subagents

Trong thư mục dự án:

```sh
# dùng hybrid-hands cho dự án này
claude plugin disable parallel-subagents@parallel-subagents-local --scope project
claude plugin enable hybrid-hands@hybrid-hands-local --scope project
# quay lại parallel-subagents
claude plugin disable hybrid-hands@hybrid-hands-local --scope project
claude plugin enable parallel-subagents@parallel-subagents-local --scope project
```

Hai plugin không nên bật cùng lúc (hai policy brain/hand chồng nhau). Cơ sở: `enabledPlugins` đặt được ở mọi file settings ([settings reference](https://code.claude.com/docs/en/settings-reference.md#enabledplugins), 11/2026) và khoá cùng tên ở scope cao hơn ghi đè scope thấp hơn, thứ tự managed > dòng lệnh > project local > project > user ([settings precedence](https://code.claude.com/docs/en/settings.md#settings-precedence), 11/2026). Scope project ghi vào `.claude/settings.json` (commit, áp cho cả nhóm); muốn chỉ áp cho máy mình thì dùng `--scope local`.

## 4. Cấu hình dự án `.claude/hybrid-hands.json`

```json
{
  "ext_hand": {
    "order": ["dsh"],
    "timeout_min": 60,
    "max_tokens": null,
    "sandbox": "workspace-write",
    "ledger": "output/llm/hand_usage.json",
    "quota_state": "output/llm/hand_quota.json",
    "runs_dir": "output/llm/hand-ext",
    "isolation": "worktree",
    "worktree_root": "~/.hybrid-hands/worktrees",
    "go_usage": {
      "ledger": "~/.hybrid-hands/go_usage.jsonl",
      "monthly_limit_usd": 100
    },
    "backends": {
      "codex": { "home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "high", "price_per_mtok": { "input": 2.00, "cached": 0.10, "output": 10.00 } },
      "claude": { "config_dir": "~/.claude-hand", "model": "claude-opus-5-5", "effort": "medium", "max_turns": 80 },
      "claude-main": { "config_dir": "~/.claude", "model": "claude-opus-5-5", "effort": "low", "max_day_pct": 5 },
      "dsh": { "home": "~/.dsh-hand", "key_file": "~/.dsh-hand/go.key", "browser_dir": "~/.dsh-hand/browser", "model": "deepseek-v4.1-flash", "effort": "high", "base_url": "https://opencode.ai/inference/go/openai/v1", "go_price_per_mtok": { "input": 0.30, "cached_input": 0.006, "output": 1.20 }, "capacity_wait_min_lines": 30, "capacity_wait_seconds": 180 },
      "gemini": { "home": "~/.gemini-hand", "model": "gemini-4-carbon" }
    }
  },
  "side_session": {
    "max_parallel": 2,
    "handoff_dir": "docs/work-in-progress/handoffs",
    "codex_model": "gpt-6.1-sol",
    "codex_effort": "high"
  },
  "ps": {
    "session_meta_globs": ["docs/work-in-progress/*.meta"]
  }
}
```

Tên khoá chuẩn theo `lib/hand_ext/constants.py` (mặc định), `lib/side_session/` và `lib/hh_ps/`; thiếu file thì dùng các giá trị mặc định trên. `ps.session_meta_globs` (mặc định rỗng) là danh sách glob tương đối repo trỏ tới file `<TÊN>.meta` của launcher riêng (dạng `key=value`: `uuid=`, `cap_usd=` là trần token, `started=`, `screen_pid=`, `exempt=` chỉ là miễn trần ngày, trần token vẫn hiện); `hh-ps` dùng để hiện trần token và tỉ lệ. `<PL>` được thay bằng thư mục plugin. `codex`, `claude`, `claude-main` và `gemini` chỉ khai báo trong `backends`, không nằm trong `order` mặc định; gọi tường minh bằng `--backend codex|claude|claude-main|gemini` khi cần. `claude-main` trỏ gói chính `~/.claude`, mặc định `claude-opus-5-5`/`low`, chỉ dùng cho việc sáng tạo và chặn khi máy đã dùng từ `max_day_pct` (mặc định 5%) hạn mức tuần Claude trong ngày. Sổ Go nằm ngoài repo (mặc định `~/.hybrid-hands/go_usage.jsonl`, bản tóm tắt cạnh đó); đổi bằng `go_usage.ledger`, còn biến `HYBRID_HANDS_STATE_DIR` đổi thư mục mặc định (dùng cho test). Sổ Codex nằm cạnh sổ Go (mặc định `~/.hybrid-hands/codex_usage.jsonl`, cũng theo `HYBRID_HANDS_STATE_DIR`; xem mục 5.2). `backends.dsh.capacity_wait_min_lines` (mặc định 30) và `capacity_wait_seconds` (mặc định 180; 0 để test) điều khiển dự phòng 429; `backends.codex.price_per_mtok` (`{input,cached,output}` USD/1M) mặc định là giá API `gpt-6.1-sol` Standard context ≤272k: 2,00 / 0,10 / 10,00 ([OpenAI pricing](https://developers.openai.com/api/docs/pricing), 11/2026); USD Codex chỉ là ước tính vì gói ChatGPT không tính tiền theo token; đặt null thì USD Codex là null.

`ext_hand.isolation` nhận `worktree` (mặc định khi cwd là git repo) hoặc `none`; cờ `--isolation` ghi đè cho một lượt. `ext_hand.worktree_root` là thư mục chứa worktree tạm, mặc định `~/.hybrid-hands/worktrees` (nếu không khai báo thì đi theo `HYBRID_HANDS_STATE_DIR`); đường dẫn tương đối tính từ git toplevel. Không nên đặt `worktree_root` trong repo trừ khi thư mục đó bị ignore. Cwd không phải git repo mà isolation là mặc định thì lượt chạy rơi về `none` kèm cảnh báo trong report; nếu `worktree` được yêu cầu tường minh (config hoặc cờ) mà không tạo được worktree sạch thì `run` thoát 2, không âm thầm chạy trong repo gốc.

### 4.1 Phiên phụ: Sol Codex, Chrome, phiên cha, trần ngày, hand ngoài

`side-session start` mặc định `--provider codex`: mở phiên Sol trên Codex với `--dangerously-bypass-approvals-and-sandbox` (không sandbox, không hỏi phê duyệt, toàn quyền ghi và mạng); `--model`/`--effort` mặc định `side_session.codex_model`/`codex_effort` (`gpt-6.1-sol`/`high`). `--resume` vẫn mặc định `claude`. Phiên Sol ghi `<handoff_dir>/<tên>.md` rồi tạo `<handoff_dir>/<tên>.done`; `ls`/`watch` báo `done`, Opus chờ file `.done` bằng Monitor. Các cờ khác:
- `--chrome` / `--no-chrome`: mặc định theo `claude_args` (mặc định `--no-chrome`). `--chrome` thay mọi `--no-chrome` trong argv claude bằng `--chrome` và ghi `chrome` vào state; chỉ dùng với provider `claude`, provider khác in lỗi và thoát 2.
- `--provider claude|dsh`: `claude` mở phiên Claude Code (ListAgents/SendMessage); `dsh` chạy hand ngoài trong screen bằng `hand-ext run --backend dsh --brief <state_dir>/<tên>.prompt.md --label side:<tên> --cwd <worktree> [--timeout-min <giờ×60>] [--model M] [--effort E]`; không truyền `--max-tokens` vì hand-ext tính cả token đọc cache, trần do `watch` canh (không tính cached). Bắt buộc `--worktree` (thiếu thoát 2); prompt sau khi ghép template phải có mục `LUẬT BẮT BUỘC` (thiếu thoát 2). `watch`/`ls` đọc token của lượt `hand-ext` nhãn `side:<tên>` bắt đầu từ `state.started` (vào + ra, không tính cached); khi lượt kết thúc, chép `report.md` thành `<handoff_dir>/<tên>.md` nếu chưa có và đặt `stopped` (ok) hoặc `dead` (lỗi).
- `--budget-exempt` / `--force-budget`: bỏ qua trần ngày ở lần `start` này; `--budget-exempt` ghi `budget_exempt=True` và cũng miễn mã 20 khi `watch`, còn `--force-budget` chỉ bỏ qua một lần.
- Mọi phiên ghi `parent_session` = `CLAUDE_CODE_SESSION_ID` của phiên gọi; môi trường phiên con bỏ `CLAUDE_CODE_CHILD_SESSION`.

`side_session.budget_check_cmd` (mặc định `[]` = tắt) là argv của lệnh kiểm trần ngày, chạy không qua shell, timeout 30 s; phần tử đầu là đường dẫn tương đối thì tính từ repo (ví dụ `["scripts/day-budget.sh", "status"]`). `start`: mã khác 0 (kể cả lỗi không chạy được lệnh) in stdout của lệnh rồi từ chối, thoát 4, trừ khi có `--budget-exempt` hoặc `--force-budget`. `watch`: chạy lại mỗi vòng; mã 20 và state không `budget_exempt` thì dừng phiên với trạng thái `daystop`. `side-session ls` thêm cột `CHROME`.

Với phiên phụ `codex`, argv có `-c model_auto_compact_token_limit=272000`: Codex tự nén context, `watch` không dừng `capped` theo tổng token tiêu. `TOKENS/CAP` hiển thị `last_token_usage` cuối (input gồm cached + output) trên 272000, không có dấu ` !`; tổng token cộng dồn chỉ để báo cáo.

`side_session.codex_model`/`codex_effort` (mặc định `gpt-6.1-sol`/`high`) là model/effort cho provider `codex` (Sol) và được chuyển tiếp cho hand-ext khi có `--model`/`--effort`; `--model`/`--effort` của `start` đè cho một lượt.

`side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ provider `claude`, đường dẫn tương đối tính từ repo; `start` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`, ví dụ để phiên phụ ghi số liệu cho lệnh trần ngày.

## 5. Backend của hand ngoài

Lệnh: `hand-ext setup|doctor [--backend B|all] [--cwd D]`, `hand-ext run --brief F|- [--backend B|auto] [--browser] [--label L] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`, `hand-ext status`, `hand-ext usage [--json]`, `hand-ext report`, `hand-ext measure --runs <dir> [--runs <dir>...] [--backend B] [--since D]`. Mã thoát: 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập. `--browser` chỉ dùng với backend `dsh`: `--backend auto --browser` chỉ xét `dsh`, còn `--backend` khác `dsh` kèm `--browser` thoát 2. Backend `opencode` đã gỡ ở 0.19.0: `order` cũ còn tên này thì `run --backend auto` bỏ qua kèm dòng `bỏ qua opencode: backend 'opencode' không hỗ trợ (đã gỡ, dùng dsh)`, còn `--backend opencode` thoát 2. `claude-main` không nằm trong `order`, chỉ gọi tường minh cho việc sáng tạo. Với `--backend auto`, dsh 429 quá tải được xử lý theo ngưỡng patch/`capacity_wait_*` (mục 5.2), không ghi quota và không chuyển backend; patch nhỏ chạy lại bằng codex low. Mỗi lượt codex ghi sổ `codex_usage.jsonl` (mục 5.2).

| Backend | Gói | Người dùng tự đăng nhập | Theo dõi hạn mức | Rủi ro tính tiền |
|---|---|---|---|---|
| `codex` | ChatGPT | `CODEX_HOME=~/.codex-hand codex login --device-auth` | `used_percent`, `resets_at` từ sự kiện của `codex exec --json`; sổ `~/.hybrid-hands/codex_usage.jsonl` giữ riêng cửa sổ 5h/7d và USD ước tính | đăng nhập API key thì tính tiền; `doctor` chặn, hand gỡ biến `OPENAI_API_KEY`; thiếu `price_per_mtok` thì USD null, không bịa giá |
| `claude` | Claude tài khoản thứ hai | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` | lỗi hết hạn mức trong stream, `hand-ext status` | dùng nhầm tài khoản chính thì ăn hạn mức brain; hook repo vẫn chạy |
| `claude-main` | Gói Claude CHÍNH `~/.claude`; `claude-opus-5-5`, effort `low`; chỉ việc sáng tạo | đã đăng nhập sẵn, không đăng nhập thêm | % tuần Claude máy này đã dùng trong ngày so với `max_day_pct`; `hand-ext status` | dùng cho việc không sáng tạo sẽ ăn hạn mức brain; từ 5%/ngày hoặc không tính được thì thoát 7, ghi yêu cầu vào bàn giao để Opus quyết |
| `dsh` | OpenCode Go qua DeepSeek Harness (`dsh --profile headless`, DeepSeek V4.1 Flash, reasoning `high` mặc định; `--effort max` cho việc thiết kế nhiều phần); tuỳ chọn `--browser` qua Playwright MCP cô lập | cài `npm install -g @deepseek-ai/dsh@latest`; người dùng tự chép API key Go từ OpenCode Console vào `~/.dsh-hand/go.key` (một dòng) rồi `chmod 600 ~/.dsh-hand/go.key`; cài trình duyệt theo mục 5.1 nếu dùng `--browser` | lỗi `QUOTA`/`RATE_LIMIT` trong sự kiện `turn_end`, `hand-ext status`; USD ước tính trong sổ Go toàn máy (mục 5.2); 429 quá tải có nhánh riêng, không ghi quota | Extra Usage bật hoặc Console còn credit thì tính tiền khi hết hạn mức: phải TẮT Extra Usage, để credit 0; metadata models.dev ghi 0910 nhưng OpenCode báo Go đã phục vụ 1017 dưới cùng id; dsh luôn đọc `<cwd>/.env` nên hand khởi chạy dsh từ `~/.dsh-hand/launch` và trỏ workspace sang repo bằng patch `templates/dsh-hand.yml`; không được tạo `~/.dsh-hand/.env`; dsh bản developer preview, `doctor` chỉ đạt với bản đã đọc mã nguồn (0.2.1-rc.5) |
| `gemini` | dự kiến | chưa có | chưa có | Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI |

### 5.1 Trình duyệt cho `dsh` (`--browser`)

`--browser` mặc định tắt. Khi bật, `hand-ext` ghi thêm một patch riêng cho lượt chạy tại `<runs_dir>/<run_id>/browser.patch.json` và truyền nó bằng `--patch` sau patch chung; file `~/.dsh-hand/hand.patch.yml` không bị sửa. Patch này thêm MCP server stdio `@deepseek-ai/dsh-mcp-client` tên `playwright`, chạy `node <browser_dir>/node_modules/@playwright/mcp/cli.js --headless --isolated --browser chromium --blocked-origins "<5 origin TikTok>" --output-dir <runs_dir>/<run_id>/browser`; env của server chỉ có `PLAYWRIGHT_BROWSERS_PATH=<browser_dir>/ms-playwright` (dsh tự lọc biến dạng key/token và `DSH_*`, nên key Go không sang tiến trình MCP).

Cài một lần (thư mục mặc định `~/.dsh-hand/browser`, đổi bằng `backends.dsh.browser_dir`):

```sh
npm install --prefix ~/.dsh-hand/browser @playwright/mcp@0.0.83
PLAYWRIGHT_BROWSERS_PATH=~/.dsh-hand/browser/ms-playwright \
  ~/.dsh-hand/browser/node_modules/.bin/playwright install chromium
```

`hand-ext doctor --backend dsh` có dòng `browser` báo thiếu `cli.js`/`ms-playwright` nhưng không làm doctor fail vì trình duyệt là tuỳ chọn.

Giới hạn: chỉ duyệt trang công khai; không đăng nhập, không tạo tài khoản, không điền form, không mua, không vượt captcha; không mở TikTok; không tải hay chạy file tải về. `--blocked-origins` chặn request tới 5 origin TikTok nhưng tài liệu Playwright ghi rõ nó không phải ranh giới bảo mật và không chặn redirect, nên luật trong prompt mới là lớp chính. `--isolated` giữ profile trình duyệt trong bộ nhớ; thư mục `<run>/browser` chỉ chứa output (ảnh, snapshot) của lượt chạy.

### 5.2 Mức đã dùng gói OpenCode Go

OpenCode Go tính hạn mức bằng USD theo tháng cho từng model: cửa sổ 5 giờ dùng 20% hạn mức tháng, tuần 50%, tháng 100%. DeepSeek V4.1 Flash có hạn mức tháng **$100**; giá peak mỗi 1 triệu token là **input $0,30**, **cached read $0,006**, **output $1,20**, còn off-peak bằng một nửa. Nguồn: <https://opencode.ai/docs/go/> (đọc 04/11/2026; nguyên văn "Usage limits are defined as monthly dollar amounts." và "5-hour — 20% of the monthly limit; weekly — 50%; and monthly — 100%."). Go Plus dùng cùng bảng giá với hạn mức tháng $200, đổi bằng `go_usage.monthly_limit_usd`.

Mỗi lượt `dsh` ghi một dòng (bản ghi cũ của backend `opencode` đã gỡ ở 0.19.0 vẫn được tính) vào sổ toàn máy `~/.hybrid-hands/go_usage.jsonl` (không theo repo, vì hạn mức theo tài khoản): `run_id`, `ended`, `backend`, `model`, `tokens`, `cost_usd`, `cost_source` (`exact`/`estimated`/`unknown`), `cwd_basename` (chỉ tên thư mục, không đường dẫn tuyệt đối). Bản tóm tắt `go_usage_summary.json` cạnh sổ được ghi lại sau mỗi lượt và bởi `hand-ext usage [--json]`; mỗi model có ba cửa sổ trượt 5 giờ / 7 ngày / 30 ngày với `used_usd`, `limit_usd`, `percent`, `estimated`, cộng `updated_at`.

Cách tính chi phí: nếu backend kịp lộ `opencode.allowance` thì cộng số thật (`exact`); nếu không thì ước tính `(input − cached_input) × giá input + cached_input × giá cached + output × giá output`, chia 1 triệu. Bản dsh 0.2.1-rc.5 bỏ metadata cost của pi-ai nên hiện tại mọi lượt là `estimated` theo giá peak; thiếu `go_price_per_mtok` thì `cost_usd = null`, `cost_source = unknown`.

**Sổ Codex:** mỗi lượt backend `codex` kết thúc ghi đúng một dòng JSON vào `~/.hybrid-hands/codex_usage.jsonl` (mặc định theo `HOME`, hoặc `$HYBRID_HANDS_STATE_DIR/codex_usage.jsonl` khi đặt; test đổi `HOME` được). Schema `schema=1`: `run_id`, `ended`, `model`, `effort`, `tokens {input,cached_input,output}`, `cost_usd`, `cost_source` (`estimated`/`unknown`), `codex_home` chỉ basename (ví dụ `.codex-hand`), `windows {"5h": {"used_percent","resets_at"} | null, "7d": {...} | null}` phân loại bằng `window_minutes` (300 = 5h, 10080 = tuần), không chỉ cửa sổ lớn nhất; có gói chỉ có primary tuần, cửa sổ không có mẫu là null. Rollout cũ thiếu độ dài mới dùng primary=5h/secondary=tuần. Giá ở `backends.codex.price_per_mtok` = `{input,cached,output}` USD/1M; thiếu hoặc bất hợp lệ thì `cost_usd = null`, `cost_source = unknown` (không bịa giá); đủ thì `(input−cached_input)×input + cached_input×cached + output×output` chia 1e6 và `cost_source = estimated`. Không ghi hội thoại, prompt hay absolute path; không dùng tài khoản `~/.codex`. Lỗi ghi sổ chỉ cảnh báo, không làm fail lượt.

**Dự phòng 429 quá tải (chỉ `--backend auto` với dsh):** nhận diện bằng `is_capacity_error`/`CAPACITY_PATTERN` (không phải quota thật). Hand-ext đếm patch do hand tạo tính từ baseline isolation (không tính thay đổi có sẵn của người dùng), tổng dòng thêm+xoá, gồm file mới và staged. Nếu ≥ `backends.dsh.capacity_wait_min_lines` (mặc định 30): giữ đúng worktree, chờ `backends.dsh.capacity_wait_seconds` (mặc định 180; 0 trong test), chạy tiếp dsh với prompt thêm "đã có patch, làm tiếp", tối đa 2 lần chạy tiếp (tổng 3). Vẫn 429: `failed`, giữ `changes.patch` và worktree, không áp patch dở về source, không chuyển codex dù số dòng giảm. Patch dưới ngưỡng (kể cả rỗng): bỏ patch dsh trong worktree, không áp source, chạy lại brief gốc bằng codex `gpt-6.1-sol` effort `low` (kể cả CLI có `--model`/`--effort` khác; codex không cần nằm trong `order`). `--browser` không fallback codex: `failed`, giữ worktree và patch, ghi lý do. Lỗi đếm patch hoặc `isolation=none`: fail-closed, giữ dữ liệu, không reset source. Khi đã giữ patch lớn, mọi lượt chạy tiếp không thành công cũng giữ worktree/patch, không áp source hoặc chuyển codex; quota thật vẫn được ghi. `--backend dsh` tường minh và quota thật giữ hành vi cũ; mỗi lần chạy lại vẫn ghi registry, ledger và sổ Go/Codex riêng.

Cửa sổ của Go **có thể không trượt**: OpenCode chưa công bố mốc reset, nên số của `hand-ext usage`, `hand-ext status` và statusline chỉ là ước tính để biết đang ở đâu; **OpenCode Console là nguồn chuẩn**. `hand-ext status` in thêm bảng Go khi đã có tóm tắt; khối cuối mỗi `run` in `hạn mức: ~x% 5h, ~y% tuần (ước tính)`.

### 5.3 Cách ly worktree (mặc định)

Vì hook của Claude Code không chạy trong dsh/codex/gemini, hàng rào chắc nhất là secret không tồn tại trong thư mục hand làm việc. Khi `isolation=worktree` (mặc định nếu cwd là git repo), `hand-ext run`:

1. Tạo worktree detached tại `HEAD` dưới `worktree_root` (mặc định `~/.hybrid-hands/worktrees/<repo>-<run-id>`), ngoài repo.
2. Chép trạng thái làm việc: áp `git diff HEAD --binary` của file tracked rồi chép các file untracked **không bị ignore** (`git ls-files --others --exclude-standard`). File bị ignore như `.env`, `*.demo.env` không bao giờ được chép, nên không có trong workspace. Lớp chặn thứ hai: untracked có basename giống secret (`.env`, `*.env`, `*.pem`, `*.key`, `id_rsa*`, `.netrc`, `.npmrc`, `.pypirc`; trừ `.env.example`/`.env.sample`/`.env.template`/`*.env.example`) bị bỏ qua dù repo quên ignore, và symlink untracked chỉ được chép khi là đường dẫn tương đối, đích resolve nằm trong repo và không giống secret; tên bị bỏ được ghi vào report.
3. Chạy backend với cwd/worktree (dsh nhận worktree qua `HAND_EXT_DSH_WORKSPACE`).
4. Sau run, chụp trạng thái worktree bằng một git index riêng, ghi diff nhị phân vào `<runs_dir>/<run-id>/changes.patch`, rồi áp về cwd gốc bằng `git apply --check` + `git apply`. Xung đột thì không ghi đè thay đổi người dùng: report ghi `xung đột` kèm danh sách file, patch vẫn nằm trong thư mục lượt chạy. Patch rỗng thì bỏ qua áp.
5. Dọn worktree (`git worktree remove --force` + `git worktree prune`) kể cả khi timeout/lỗi; patch vẫn được lưu. `--keep-worktree` giữ worktree để kiểm tra; `--no-apply` chỉ lưu patch, không áp.

Cờ `--isolation none` tắt cách ly cho một lượt (chỉ dùng khi biết repo không có secret/dữ liệu khách hàng). Cwd không phải git repo và isolation là mặc định: chạy trực tiếp `none` kèm cảnh báo trong report. `--isolation worktree` tường minh mà không tạo được worktree sạch (không phải git repo, HEAD chưa có commit, đường dẫn đã tồn tại, lỗi git) thì thoát 2. Worktree được tạo từ `HEAD` nhưng có thay đổi chưa commit, nên hand thấy đúng trạng thái làm việc; hand không thấy file bị ignore hay file untracked nghi bí mật.

### 5.4 Dữ liệu mỗi lượt và lệnh đo

Từ 0.22.0, mỗi thư mục `<runs_dir>/<run_id>/` có thêm `brief.md` (brief nhận vào, kể cả khi đọc từ stdin), `prompt.md` (prompt đầy đủ gửi backend), `meta.json` (`base_commit`, `dirty`, `dirty_files`, `plugin_version`, `backend`, `model`, `label`) và `changes.base.patch` khi repo nguồn có thay đổi chưa commit; `events.jsonl` có thêm `ts` ISO 8601 để tính thời gian từng lệnh. Lượt cũ thiếu meta hoặc `ts` vẫn đếm được dòng; cột thời gian lệnh test để `-`, `plugin_version` là `unknown`.

`hand-ext measure --runs <dir> [--runs <dir>...] [--backend dsh] [--since YYYY-MM-DD]` đọc các thư mục lượt (nhận cả `runs_dir` lẫn một thư mục lượt), đếm dòng thêm test/code/docs từ `changes.patch`: Test nếu nằm trong `tests/`, `test/`, `__tests__/`, `spec/` hoặc tên dạng `test_*`, `*_test.*`, `*.spec.*`, `*.test.*`, `*.bats`; Docs nếu là `.md`, `.rst`, `.txt` hoặc nằm trong `docs/`; còn lại là Code (ưu tiên Test trước Docs). Lệnh test nhận `pytest`, `unittest`, `bats`, `npm test`, `npx vitest`, `go test`, `cargo test`; thời gian một lệnh là `ts` của `tool_result` trừ `ts` của `tool_call` cùng id. Kết quả in bảng theo lượt (tên, version, backend, dòng test/code/docs, % test/(test+code), số lệnh test, tổng giây lệnh test, giây lượt) rồi gộp theo `plugin_version` (tổng dòng, % test, trung bình/trung vị dòng test). `--backend` lọc theo `meta.json`, thiếu meta thì suy ra từ hậu tố tên lượt; `--since` lọc theo ngày bắt đầu của lượt.

## 6. Theo dõi phiên và hand: `hh-ps`

`hh-ps [--since 6h] [--all] [--ended] [--full] [--json] [--watch N] [--count K] [--cwd D] [--main-session UUID]` vẽ cây chỉ đọc: phiên Claude → subagent → lượt `hand-ext run` do phiên đó gọi, với phiên phụ lồng dưới phiên cha. Dạng text gọn để vừa pane hẹp cạnh khung chat (mục tiêu sau khi thêm khối USD/%: dòng con ≤ 100 cột, dòng phiên ≤ 92 cột hiển thị; mẫu dưới đây dài nhất 82 cột, test biên dài nhất 91 cột); pane `hh-tree-pane` dùng đúng định dạng này.

- Dòng đầu ghi số phiên sống/ẩn và `since`; dòng thứ hai là chú giải `▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · $ ước tính theo giá niêm yết · % = phần hạn mức tuần đã dùng`.
- Dòng phiên: `<dấu> <tên>  <im|giờ dừng>  <trạng thái>  <USD>  <% tuần>` (trạng thái nằm ở ô giờ xong của dòng con, trống khi phiên đã kết thúc). Dấu `▶` là phiên chính (theo `CLAUDE_CODE_SESSION_ID` hoặc `--main-session`), `●` phiên sống khác, `○` phiên đã kết thúc (cột thời gian là giờ kết thúc, không có trạng thái). `<im>` là thời gian từ lần hoạt động cuối. Trạng thái phiên tối đa 4 ký tự (`busy`, `idle`; pane ghi `kẹt?` khi `busy` im quá 15 phút). Phiên phụ tên `phụ:<tên>`; tên cắt ở 16 cột. Không in cwd hay repo (JSON vẫn có `cwd`); trần token và tỉ lệ chỉ có trong `--json`. Không hiện số token nào (kể cả `ctx` hay vào/cache/ra).
- Việc con của mỗi phiên (subagent, lượt hand ngoài và phiên phụ) theo một luật chung cho mọi phiên: mọi việc đang chạy (subagent chạy/im lặng, lượt hand chạy, phiên phụ sống) trước, rồi tối đa 3 việc xong hoặc lỗi gần nhất (giờ kết thúc giảm dần, xong và lỗi trộn chung), cuối cùng dòng `+N xong · M lỗi` đếm phần không hiện (bỏ vế bằng 0, không còn gì thì không in). `--full` liệt kê đủ mọi việc con. Pane `hh-tree-pane` dùng cùng luật (`RECENT_FINISHED_SHOWN = 3`).
- Phiên phụ là một việc con: `<dấu> phụ:<tên>  <im hoặc thời lượng>  <giờ dừng>  <USD>  <% tuần>  <tiêu đề tự động>`, dùng chung bảng cột với dòng phiên và dòng con nên USD và `%` bắt đầu cùng cột hiển thị ở mọi độ sâu; tên cắt 16 cột, tiêu đề lấy từ bản ghi `ai-title` cuối trong transcript phiên phụ (cắt 16 cột như mô tả hand, trống khi chưa có), việc của nó lồng thêm một cấp theo cùng luật.
- Dòng con: `<dấu> <loại>  <thời lượng>  <giờ xong>  <USD>  <% tuần>  <mô tả>  [trạng thái lỗi]`; ô số đứng trước nên pane hẹp cắt mô tả chứ không cắt số; trạng thái lỗi đứng sau mô tả để dòng ổn (đa số) không có khoảng trống trước mô tả, còn dòng có trạng thái thì mô tả được đệm cho trạng thái thẳng cột. Dấu `▶` đang chạy, `✓` xong ổn, `✗` lỗi hoặc mất. Trạng thái chữ chỉ in khi không ổn: `failed`, `quota` (= `quota_exhausted`), `mất` (lượt `running` mà pid đã chết), `im lặng` (subagent chưa xong, jsonl im quá 30 phút). Loại `hybrid-hands:hand` → `hand`, `opencode` → `oc`, loại khác cắt 8 cột; mô tả cắt 16 cột (`…`) vì cột đầu dùng chung với tên phiên (tên 16 cột + nhánh cây). USD ước tính theo giá niêm yết (USD/1M token, cache ghi 5m/1h, cache đọc 0,1× input; model lạ fallback theo họ Opus/Sonnet/Haiku; `<synthetic>` không tính); dưới `$0.01` ghi `<$0.01`, không dùng gì ghi `$0`, không có giá thì `-`. Lượt hand ngoài dùng giá Go cho backend `dsh`/`opencode`; backend khác không có USD. `%` là phần hạn mức **tuần** đã dùng, 1 chữ số thập phân (`12.3%`, khác 0 mà dưới 0.05% ghi `<0.1%`), theo đúng công thức statusline: Claude `USD / usd_per_pct` của `.statusline-week-split.json`, Go `USD / limit_usd` của cửa sổ `7d` trong `go_usage_summary.json`; số statusline đánh dấu ước tính có tiền tố `~`. Dòng Claude, subagent và lượt Go đều có `%` khi nguồn tuần có; hand backend khác và dòng thiếu nguồn để trống ô `%`.
- Giờ xong là `HH:MM` theo giờ máy (khác ngày với lúc vẽ: `dd/mm HH:MM`); việc đang chạy và phiên sống để trống. Thời lượng: `30s`, `45p`, `2g3p`, từ một ngày chỉ ghi `1ng`.
- Cột cách nhau hai dấu cách; dòng phiên, dòng phiên phụ và dòng con dùng chung một bảng cột, đệm theo độ rộng hiển thị lớn nhất của từng cột (tính cả nhánh cây hai cột, ký tự tổ hợp = 0, ký tự rộng Đông Á = 2, không tính mã màu), nên khối USD và `%` bắt đầu cùng cột hiển thị ở mọi độ sâu; cột thời gian/thời lượng căn phải.

Mặc định chỉ hiện cây của phiên đang sống: cây mà mọi phiên đã kết thúc và không còn subagent hay lượt hand ngoài đang chạy bị ẩn, dòng đầu ghi số phiên bị ẩn (`3 sống, ẩn 1 đã kết thúc: --ended để xem`); phiên phụ đã kết thúc dưới một phiên sống vẫn hiện, lượt hand ngoài không rõ phiên gọi giữ nguyên; `--ended` hiện lại mọi phiên đã kết thúc trong khoảng `--since`. Mặc định chỉ lấy project của git toplevel cwd (mọi phiên đang sống vẫn hiện); `--since` (m/h/d) lọc phiên/subagent/lượt đã xong; `--all` lấy mọi project; `--watch N` vẽ lại mỗi N giây (tối thiểu 2), dừng bằng Ctrl-C hoặc `--count K`; màu chỉ bật khi stdout là TTY và tắt bằng `NO_COLOR`. Ví dụ:

```text
Phiên Claude (2 sống / 2 phiên) · since 1g
▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · $ ước tính theo giá niêm yết · % = phần hạn mức tuần đã dùng
└ ▶ cha           1p  busy      $0.42  0.4% tuần
  ├ ● phụ:RV-12   1p           <$0.01  0.0% tuần   Tiêu đề tự động
  ├ ✓ hand        1p  14:59     $0.02  0.1% tuần   việc con
  └ ✓ dsh        48p  14:58     $0.78  1.6% tuần   lượt hand
```

Phiên phụ được tìm ở mọi repo: `hh-ps` nạp `.claude/hybrid-hands.json` và state phiên phụ (`side_session.state_dir`) của repo cwd và của repo chứa từng phiên đang liệt kê (cwd → `git rev-parse --git-common-dir`, nên worktree quy về repo chính; mỗi thư mục chỉ gọi git một lần). Vì vậy phiên phụ của repo khác vẫn lồng dưới phiên cha, kể cả khi đã dừng; config hỏng ở repo khác bị bỏ qua.
 `--main-session <UUID>` đè phiên chính lấy từ `CLAUDE_CODE_SESSION_ID`; id không đúng dạng UUID thì argparse báo lỗi.

Nguồn: `~/.claude/sessions/<pid>.json` (hoặc `CLAUDE_CONFIG_DIR`) đối chiếu `os.kill(pid, 0)`, transcript `~/.claude/projects/<slug>/<sessionId>.jsonl` (tìm theo tên file trên mọi slug; `customTitle` cuối cùng thắng), subagent `.../<sessionId>/subagents/agent-*.meta.json|.jsonl` (`finished` khác true và jsonl im quá 30 phút → "im lặng"), và sổ lượt đang chạy `~/.hybrid-hands/runs/<run_id>.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Không đọc file `.key`, không in nội dung tin nhắn/prompt hay socket token, không gửi mạng. Khối hạn mức chỉ đọc cửa sổ **tuần** từ cache không chứa key: `$CLAUDE_HOME/.statusline-go-usage.json` (tổng Go toàn tài khoản và giờ reset tuần), `$CLAUDE_HOME/.statusline-cache.json` (rate_limits tuần của Claude), `$CLAUDE_HOME/.statusline-week-split.json` (tách máy này/máy khác, `usd_per_pct`, ước tính 0.1) và USD máy này phát sinh sau mốc cache lấy tươi từ transcript `$CLAUDE_HOME/projects/**/*.jsonl` bằng `usage_ledger.py` của statusline (định vị qua `$CLAUDE_HOME/plugins/installed_plugins.json`, không có thì thư mục `statusline/` cùng repo; test đổi bằng `HH_PS_STATUSLINE_LEDGER`), không gọi được thì lùi về `$CLAUDE_HOME/.statusline-local-usage.json` (USD từng lượt gọi). Go máy này = USD sổ `go_usage` trong cửa sổ `reset tuần - 7 ngày` ÷ `7d.limit_usd` của `go_usage_summary.json`; Claude máy này/máy khác lấy đúng `local`/`other` của statusline. Cache quá hạn reset bị coi là đã reset (không hiện số cũ như số hiện tại). `--json` in schema `schema`, `generated_at`, `since_seconds`, `cwd`, `all_projects`, `main_session_id`, `hidden_ended_sessions` (số phiên bị ẩn, 0 khi có `--ended`), `limits[]`, `sessions[]` (mỗi phiên có `subagents[]`, `hand_runs[]`), `orphan_runs[]` và `totals`; mỗi phần tử `limits` là `{plan, window, this_machine_pct, other_pct, total_pct, resets_at, source, estimated}` với `window` luôn là `tuần` (không còn kỳ 5h/tháng; `estimated` = số có dấu `~` như statusline; `other_pct`/`total_pct` là `null` khi thiếu cache tổng, máy khác âm được kẹp về 0); mỗi phiên, subagent và lượt hand có `ended_at` (ISO-8601 giờ máy, `null` khi còn chạy hoặc không biết mốc kết thúc) và `usage` (`{read, cache_read, cache_write, out, usd, week_pct, week_pct_estimated}`, `null` khi không có số; `cache_write`/`usd`/`week_pct` là `null` khi nguồn không có, `week_pct_estimated` bật khi statusline đánh dấu `~`), phiên có thêm `ai_title` (tiêu đề tự động của phiên phụ, `""` khi chưa có); lượt `running` mà pid đã chết hiện `mất`. Phiên phụ có `parent_session` khớp một phiên đang hiện được vẽ lồng dưới phiên cha (kể cả phiên phụ lồng nhau), và `--json` thêm ba trường `parent_session`, `side_name`, `provider` cho mỗi phiên.

## 7. Chuyển phiên giữa terminal và Paseo: `cc-switch`

`cc-switch term [--agent ID|--session SID] [--dry-run] [-- <đối số thêm cho claude>]` lấy agent Paseo provider `claude` của project hiện tại (hoặc chọn theo id/tiền tố/session), chờ `paseo wait` nếu agent đang chạy, từ chối nếu đã có TUI `claude` sống cùng session, rồi `chdir` vào cwd agent và `exec claude --resume <sid> [--model <model>]`. Sau đó đừng gửi tin cho agent từ Paseo cho tới khi chuyển lại.

`cc-switch paseo [--session SID] [--dry-run]` lấy transcript sửa gần nhất có dòng `user` trong project (hoặc session chỉ định), từ chối nếu TUI còn sống (phải `/exit` trước), rồi `paseo agent reload <id>` nếu đã có agent, không thì `paseo import <sid> --provider claude --cwd <cwd> --json`. Xong thì mở Paseo trên điện thoại để tiếp tục. `cc-switch term` ghi sổ bàn giao ở `~/.hybrid-hands/cc-switch/handoff.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`); `cc-switch paseo` không có `--session` dùng phiên trong sổ nếu transcript còn và xoá mục sau khi nạp lại/import thành công. `cc-switch status [--all]` in bảng id/title/status Paseo/session/TUI và nơi đang giữ (`terminal`, `paseo`, `không`).

**Chuyển chính phiên TUI đang mở:** `cc-switch paseo --self [--idle-sec 20] [--exit-timeout 30] [--dry-run]` dùng ngay bên trong phiên Claude Code TUI, không cần `/exit` bằng tay. Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, tìm pid TUI đang mở qua sổ `~/.claude/sessions/<pid>.json` (nhiều pid thì chọn pid là tổ tiên của tiến trình gọi bằng `ps -o ppid=`), rồi tách một tiến trình nền độc lập; log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại pid vẫn là TUI của session, gửi SIGTERM và chờ TUI thoát tối đa `--exit-timeout` giây (không SIGKILL), rồi chạy đúng luồng `cc-switch paseo --session <sid>`. Lệnh cha trả về ngay và in pid TUI, thời gian chờ, đường log cùng cách quay lại (`cc-switch term`); đừng gõ hay nhấn Enter cho tới khi TUI tự đóng. `--dry-run` chỉ in kế hoạch, không tách tiến trình; `--self` không đi cùng `--session` (sai cách dùng, thoát 2).

**Chuyển chính phiên Paseo về terminal:** `cc-switch term --self [--idle-sec 20] [--app Terminal|iTerm] [--dry-run]` dùng bên trong phiên Claude Code do Paseo giữ (agent Paseo provider `claude`). Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, từ chối nếu phiên đã mở trong terminal, tìm agent Paseo theo session (không có thì báo "phiên không do Paseo giữ" và gợi ý `cc-switch term --session`), và chỉ chạy trên macOS. `--dry-run` in kế hoạch gồm session/agent rút gọn, cwd, app, lệnh sẽ chạy trong cửa sổ và đường log. Không dry-run: lệnh tách một tiến trình nền rồi in hướng dẫn đừng gửi tin cho agent từ Paseo cho tới khi chạy `/to-paseo` hoặc `cc-switch paseo`; cửa sổ sẽ mở sau khi lượt hiện tại xong. Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại không còn TUI sống cho session, rồi ghi `cd <cwd> && exec <bin/cc-switch> term --session <sid>` vào `~/.hybrid-hands/cc-switch/term-<sid8>.command` (quyền 700) và chạy `open -a Terminal` (hoặc `iTerm`) với file đó — đúng luồng `cc-switch term` hiện có: ghi sổ bàn giao và `exec claude --resume`. Log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Cách mở bằng `open` không cần quyền Automation của macOS. `--self` không đi cùng `--agent`/`--session` và không nhận đối số sau `--` (sai cách dùng, thoát 2).

**Slash command `/to-paseo` và `/to-term`:** plugin có hai lệnh trong `commands/`; mỗi lệnh chỉ chạy đúng một lệnh `cc-switch paseo --self` hoặc `cc-switch term --self` bằng tool Bash làm hành động cuối, rồi trả lời một câu ngắn. Nếu `cc-switch` không có trong `PATH`, dùng đường dẫn tuyệt đối mà hook SessionStart in ra. Chưa kiểm hai slash command chạy được bên trong agent Paseo (cần máy có Terminal.app).

**Vì sao phải reload:** tiến trình `claude` do Paseo giữ hội thoại trong bộ nhớ. Lượt làm ở terminal ghi tiếp vào cùng transcript; nếu Paseo trả lời mà không reload, nó dựa vào lịch sử cũ và ghi một nhánh rẽ. Lần `--resume` sau đi theo lá mới nhất nên lượt terminal bị mất khỏi ngữ cảnh. `paseo agent reload` khởi lại tiến trình lười, resume từ transcript nên thấy đủ lượt terminal. `cc-switch` chỉ đọc các trường agent đã khai báo và không đọc `.key`; việc ghi trạng thái là do `paseo`.

Mã thoát: 2 sai cách dùng (kể cả `--self` đi cùng `--agent`/`--session` hoặc có đối số sau `--`) và `term --self` trên hệ điều hành không phải macOS, 3 không tìm thấy agent/transcript hoặc pid TUI (kể cả session không do Paseo giữ), 4 TUI còn sống, không xác định được pid, hoặc không mở được cửa sổ terminal (`open` lỗi), 5 lệnh `paseo` lỗi.

## 8. Xem cây trên Paseo

Plugin `hh-tree` trong `paseo-hh-tree/` hiện cây phiên Claude → subagent → lượt hand ngoài trong app Paseo (desktop và điện thoại): panel cạnh từng agent, màn hình đầy đủ mở từ sidebar, và ô cài đặt đường dẫn `hh-ps`; dữ liệu tự làm mới mỗi 5 giây. Đầu mỗi panel có khối hạn mức lấy từ `hh-ps --json`: mỗi gói (Claude, Go) một dòng **tuần**, tách `máy này`, `máy khác` (tổng tài khoản trừ máy này) và `tổng`, kèm giờ reset tuần khi cache có; mỗi dòng phiên/subagent/lượt hand có USD, `% tuần`, thời gian chạy và giờ kết thúc. Khi cache statusline cũ hơn 30 phút và có `usd_per_pct`, dòng tuần Claude ngoại suy thêm `USD máy này phát sinh sau mốc cache / usd_per_pct` vào `máy này` và `tổng` (không thấp hơn số cache, tối đa 100), `máy khác` giữ nguyên, dòng vẫn đánh dấu ước tính `~`; USD đó lấy tươi từ transcript qua `usage_ledger.py` của statusline (lùi về sổ `.statusline-local-usage.json` khi không gọi được) và `source` của dòng trong `hh-ps --json` mang thêm `+extrapolated` khi đã ngoại suy; số ngoại suy có thể thấp hơn thực tế nếu máy khác dùng Claude sau mốc cache, và sai số còn phụ thuộc độ đúng của USD/1% ghim. Xem `paseo-hh-tree/OVERVIEW.md` để biết cách cài, cách đặt đường dẫn `hh-ps` và những dữ liệu plugin chỉ đọc trên máy.

### 8.1 Bật % sống cho phiên Paseo

Wrapper `bin/claude-tee` đứng giữa Paseo và `claude` để dòng tuần Claude lấy **mẫu % sống** thay vì chờ statusline ghi cache: nó chuyển tiếp nguyên luồng stream-json, bắt sự kiện `rate_limit_event`, rồi ghi mẫu mới nhất của `seven_day`/`five_hour` (`utilization`, `resets_at`, `ts`) vào `$CLAUDE_CONFIG_DIR/.hh-claude-rate-limit.json` (mặc định `~/.claude/.hh-claude-rate-limit.json`). File trạng thái chỉ có `version`, `updated_at` và `windows`; **không** lưu nội dung hội thoại, `session_id`, prompt hay token.

Khi mẫu `seven_day` mới hơn mtime `.statusline-cache.json` (hoặc không có cache), `hh-ps`/`hh-tree` dùng thẳng mẫu làm `total_pct` tuần, **không ngoại suy**, và `source` trong `--json` bắt đầu bằng `rate_limit_event` (thêm `+week_split` khi có summary); máy này = `local` của summary + USD phát sinh sau mốc cache ÷ `usd_per_pct`, máy khác = `max(tổng − máy này, 0)`. Mẫu cũ hơn cache thì giữ đường cache/ngoại suy cũ. Wrapper chỉ ghi được khi `claude` chạy với `--output-format stream-json` (Paseo chạy như vậy); phiên TUI ngoài Paseo vẫn dùng cache statusline.

Cấu hình trong `~/.paseo/config.json` — thử provider riêng `claude-tee` trước, chạy một agent thử rồi mới ghi đè provider `claude`:

```json
{
  "agents": {
    "providers": {
      "claude-tee": {
        "extends": "claude",
        "command": ["<đường dẫn tuyệt đối tới plugin>/bin/claude-tee"]
      }
    }
  }
}
```

Sau khi sửa: `paseo reload`, rồi `paseo run --provider claude-tee ...` để kiểm. Muốn mọi agent `claude` đi qua wrapper thì đổi khối trên thành `"claude": {"command": ["<đường dẫn tuyệt đối tới plugin>/bin/claude-tee"]}` (bỏ `extends`) và `paseo reload`. Nếu `claude` trên `PATH` trỏ nhầm vào wrapper, đặt `env.HH_CLAUDE_REAL` của provider thành đường dẫn `claude` thật. Cách gỡ: bỏ provider `claude-tee`/khôi phục `command` cũ của `claude`, `paseo reload`; có thể xoá `.hh-claude-rate-limit.json`, `hh-ps` tự quay lại đọc cache statusline.

## 9. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
