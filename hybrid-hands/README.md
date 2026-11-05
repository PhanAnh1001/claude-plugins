# hybrid-hands

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai, bật theo từng dự án thay cho `parallel-subagents`: brain chạy trên gói Claude chính; việc code/tài liệu tự chứa mặc định giao hand ngoài chạy trên gói subscription thứ hai (mặc định DeepSeek V4.1 Flash qua `dsh`/`opencode`) để giữ hạn mức gói chính.
- **Thành phần:**
  - hand ngoài: lệnh `hand-ext` (mặc định `dsh`, `opencode` — DeepSeek V4.1 Flash trên gói OpenCode Go — theo `order`; `codex`, `claude`, `gemini` chỉ khai báo để gọi tường minh; sổ token `output/llm/hand_usage.json` và sổ USD Go toàn máy `~/.hybrid-hands/go_usage.jsonl`, lệnh `hand-ext usage`), skill `ext-hand`;
  - hand Claude: agent `hybrid-hands:hand` (gói chính) cho việc cần tool riêng của Claude Code, lệnh trả phí của dự án, hoặc khi `hand-ext` thoát 7;
  - phiên phụ: lệnh `side-session` (phiên có ngữ cảnh brain riêng cho gói việc dài), skill `side-session`; lệnh `hh-ps` xem cây phiên Claude → subagent → lượt hand ngoài; lệnh `cc-switch` chuyển một phiên Claude qua lại giữa terminal và Paseo mà không để transcript rẽ nhánh; skill `paseo` theo dõi từ điện thoại;
  - hook SessionStart (khuôn brief, luật chọn hand, luật hạn mức) và UserPromptSubmit (bản ngắn).
- **Luật hạn mức:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; sau mỗi lượt báo backend, token, % hạn mức (Claude/Codex) hoặc % Go 5h/tuần kèm USD ước tính, thời điểm reset.
- **Luật dữ liệu:** không giao hand ngoài việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude. Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.
- **Cách ly worktree:** `hand-ext run` mặc định chạy hand trong git worktree sạch (chỉ file tracked + thay đổi chưa commit/untracked không bị ignore; `.env` bị ignore không có trong workspace), lưu `changes.patch` rồi áp về cwd gốc; xem mục 5.3.
- **Bật theo dự án:** cài ở scope project trong thư mục dự án, tắt `parallel-subagents` ở scope project (xem mục 3).
- **Việc cần làm lần đầu:** `hand-ext setup`, người dùng tự đăng nhập từng backend (mục 5), rồi `hand-ext doctor`.

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
    ├── lib/hand_ext/ (backends/: codex | claude | dsh | opencode; isolation.py), lib/side_session/, lib/hh_ps/, lib/cc_switch/
    ├── commands/to-paseo.md, commands/to-term.md  # slash command chuyển phiên hai chiều
    ├── hooks/hooks.json
    ├── scripts/session-start-policy.sh, scripts/inject-policy.sh
    ├── skills/ext-hand/, skills/side-session/, skills/paseo/
    └── templates/hand-brief.md, ext-hand-preamble.md, dsh-hand.yml, opencode-hand.jsonc, side-session-prompt.md
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
    "order": ["dsh", "opencode"],
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
      "codex": { "home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "high" },
      "claude": { "config_dir": "~/.claude-hand", "model": "claude-opus-5-5", "effort": "medium", "max_turns": 80 },
      "dsh": { "home": "~/.dsh-hand", "key_file": "~/.dsh-hand/go.key", "browser_dir": "~/.dsh-hand/browser", "model": "deepseek-v4.1-flash", "effort": "max", "base_url": "https://opencode.ai/inference/go/openai/v1", "go_price_per_mtok": { "input": 0.30, "cached_input": 0.006, "output": 1.20 } },
      "opencode": { "config": "<PL>/templates/opencode-hand.jsonc", "model": "opencode-go/deepseek-v4.1-flash", "variant": "max", "go_price_per_mtok": { "input": 0.30, "cached_input": 0.006, "output": 1.20 } },
      "gemini": { "home": "~/.gemini-hand", "model": "gemini-4-carbon" }
    }
  },
  "side_session": {
    "max_parallel": 2,
    "handoff_dir": "docs/work-in-progress/handoffs"
  },
  "ps": {
    "session_meta_globs": ["docs/work-in-progress/*.meta"]
  }
}
```

Tên khoá chuẩn theo `lib/hand_ext/constants.py` (mặc định), `lib/side_session/` và `lib/hh_ps/`; thiếu file thì dùng các giá trị mặc định trên. `ps.session_meta_globs` (mặc định rỗng) là danh sách glob tương đối repo trỏ tới file `<TÊN>.meta` của launcher riêng (dạng `key=value`: `uuid=`, `cap_usd=` là trần token, `started=`, `screen_pid=`, `exempt=` chỉ là miễn trần ngày, trần token vẫn hiện); `hh-ps` dùng để hiện trần token và tỉ lệ. `<PL>` được thay bằng thư mục plugin. `codex`, `claude` và `gemini` chỉ khai báo trong `backends`, không nằm trong `order` mặc định; gọi tường minh bằng `--backend codex|claude|gemini` khi cần. Sổ Go nằm ngoài repo (mặc định `~/.hybrid-hands/go_usage.jsonl`, bản tóm tắt cạnh đó); đổi bằng `go_usage.ledger`, còn biến `HYBRID_HANDS_STATE_DIR` đổi thư mục mặc định (dùng cho test).

`ext_hand.isolation` nhận `worktree` (mặc định khi cwd là git repo) hoặc `none`; cờ `--isolation` ghi đè cho một lượt. `ext_hand.worktree_root` là thư mục chứa worktree tạm, mặc định `~/.hybrid-hands/worktrees` (nếu không khai báo thì đi theo `HYBRID_HANDS_STATE_DIR`); đường dẫn tương đối tính từ git toplevel. Không nên đặt `worktree_root` trong repo trừ khi thư mục đó bị ignore. Cwd không phải git repo mà isolation là mặc định thì lượt chạy rơi về `none` kèm cảnh báo trong report; nếu `worktree` được yêu cầu tường minh (config hoặc cờ) mà không tạo được worktree sạch thì `run` thoát 2, không âm thầm chạy trong repo gốc.

### 4.1 Phiên phụ: Chrome, phiên cha, trần ngày, hand ngoài

`side-session start` nhận thêm:
- `--chrome` / `--no-chrome`: mặc định theo `claude_args` (mặc định `--no-chrome`). `--chrome` thay mọi `--no-chrome` trong argv claude bằng `--chrome` và ghi `chrome` vào state; chỉ dùng với provider `claude`, provider khác in lỗi và thoát 2.
- `--provider dsh|opencode`: chạy hand ngoài trong screen bằng `hand-ext run --backend <p> --brief <state_dir>/<tên>.prompt.md --label side:<tên> --cwd <worktree> [--timeout-min <giờ×60>]`; không truyền `--max-tokens` vì hand-ext tính cả token đọc cache, trần do `watch` canh (không tính cached). Bắt buộc `--worktree` (thiếu thoát 2); prompt sau khi ghép template phải có mục `LUẬT BẮT BUỘC` (thiếu thoát 2). `watch`/`ls` đọc token của lượt `hand-ext` nhãn `side:<tên>` bắt đầu từ `state.started` (vào + ra, không tính cached); khi lượt kết thúc, chép `report.md` thành `<handoff_dir>/<tên>.md` nếu chưa có và đặt `stopped` (ok) hoặc `dead` (lỗi).
- `--budget-exempt` / `--force-budget`: bỏ qua trần ngày ở lần `start` này; `--budget-exempt` ghi `budget_exempt=True` và cũng miễn mã 20 khi `watch`, còn `--force-budget` chỉ bỏ qua một lần.
- Mọi phiên ghi `parent_session` = `CLAUDE_CODE_SESSION_ID` của phiên gọi; môi trường phiên con bỏ `CLAUDE_CODE_CHILD_SESSION`.

`side_session.budget_check_cmd` (mặc định `[]` = tắt) là argv của lệnh kiểm trần ngày, chạy không qua shell, timeout 30 s; phần tử đầu là đường dẫn tương đối thì tính từ repo (ví dụ `["scripts/day-budget.sh", "status"]`). `start`: mã khác 0 (kể cả lỗi không chạy được lệnh) in stdout của lệnh rồi từ chối, thoát 4, trừ khi có `--budget-exempt` hoặc `--force-budget`. `watch`: chạy lại mỗi vòng; mã 20 và state không `budget_exempt` thì dừng phiên với trạng thái `daystop`. `side-session ls` thêm cột `CHROME`.

`side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ provider `claude`, đường dẫn tương đối tính từ repo; `start` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`, ví dụ để phiên phụ ghi số liệu cho lệnh trần ngày.

## 5. Backend của hand ngoài

Lệnh: `hand-ext setup|doctor [--backend B|all] [--cwd D]`, `hand-ext run --brief F|- [--backend B|auto] [--browser] [--label L] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`, `hand-ext status`, `hand-ext usage [--json]`, `hand-ext report`. Mã thoát: 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập. `--browser` chỉ dùng với backend `dsh`: `--backend auto --browser` chỉ xét `dsh`, còn `--backend` khác `dsh` kèm `--browser` thoát 2.

| Backend | Gói | Người dùng tự đăng nhập | Theo dõi hạn mức | Rủi ro tính tiền |
|---|---|---|---|---|
| `codex` | ChatGPT | `CODEX_HOME=~/.codex-hand codex login --device-auth` | `used_percent`, `resets_at` từ sự kiện của `codex exec --json` | đăng nhập API key thì tính tiền; `doctor` chặn, hand gỡ biến `OPENAI_API_KEY` |
| `claude` | Claude tài khoản thứ hai | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` | lỗi hết hạn mức trong stream, `hand-ext status` | dùng nhầm tài khoản chính thì ăn hạn mức brain; hook repo vẫn chạy |
| `dsh` | OpenCode Go qua DeepSeek Harness (`dsh --profile headless`, DeepSeek V4.1 Flash, reasoning `max`); tuỳ chọn `--browser` qua Playwright MCP cô lập | cài `npm install -g @deepseek-ai/dsh@latest`; người dùng tự chép API key Go từ OpenCode Console vào `~/.dsh-hand/go.key` (một dòng) rồi `chmod 600 ~/.dsh-hand/go.key`; cài trình duyệt theo mục 5.1 nếu dùng `--browser` | lỗi `QUOTA`/`RATE_LIMIT` trong sự kiện `turn_end`, `hand-ext status`; USD ước tính trong sổ Go toàn máy (mục 5.2) | như `opencode`: phải TẮT Extra Usage, để credit 0; dsh luôn đọc `<cwd>/.env` nên hand khởi chạy dsh từ `~/.dsh-hand/launch` và trỏ workspace sang repo bằng patch `templates/dsh-hand.yml`; không được tạo `~/.dsh-hand/.env`; dsh bản developer preview, `doctor` chỉ đạt với bản đã đọc mã nguồn (0.2.1-rc.5) |
| `opencode` | OpenCode Go (DeepSeek V4.1 Flash, biến thể max) | `opencode auth login` chọn OpenCode Go | lỗi hết hạn mức, `hand-ext status`; USD ước tính trong sổ Go toàn máy (mục 5.2) | Extra Usage bật hoặc Console còn credit thì tính tiền khi hết hạn mức: phải TẮT Extra Usage, để credit 0; metadata models.dev ghi 0910 nhưng OpenCode báo Go đã phục vụ 1017 dưới cùng id |
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

Mỗi lượt `dsh`/`opencode` ghi một dòng vào sổ toàn máy `~/.hybrid-hands/go_usage.jsonl` (không theo repo, vì hạn mức theo tài khoản): `run_id`, `ended`, `backend`, `model`, `tokens`, `cost_usd`, `cost_source` (`exact`/`estimated`/`unknown`), `cwd_basename` (chỉ tên thư mục, không đường dẫn tuyệt đối). Bản tóm tắt `go_usage_summary.json` cạnh sổ được ghi lại sau mỗi lượt và bởi `hand-ext usage [--json]`; mỗi model có ba cửa sổ trượt 5 giờ / 7 ngày / 30 ngày với `used_usd`, `limit_usd`, `percent`, `estimated`, cộng `updated_at`.

Cách tính chi phí: nếu backend kịp lộ `opencode.allowance` thì cộng số thật (`exact`); nếu không thì ước tính `(input − cached_input) × giá input + cached_input × giá cached + output × giá output`, chia 1 triệu. Bản dsh 0.2.1-rc.5 bỏ metadata cost của pi-ai, còn opencode 1.19.5 không giữ `opencode.allowance` và `step_finish.cost` bằng 0 với Go trong hạn mức, nên hiện tại mọi lượt là `estimated` theo giá peak; thiếu `go_price_per_mtok` thì `cost_usd = null`, `cost_source = unknown`.

Cửa sổ của Go **có thể không trượt**: OpenCode chưa công bố mốc reset, nên số của `hand-ext usage`, `hand-ext status` và statusline chỉ là ước tính để biết đang ở đâu; **OpenCode Console là nguồn chuẩn**. `hand-ext status` in thêm bảng Go khi đã có tóm tắt; khối cuối mỗi `run` in `hạn mức: ~x% 5h, ~y% tuần (ước tính)`.

### 5.3 Cách ly worktree (mặc định)

Vì hook của Claude Code không chạy trong dsh/opencode/codex/gemini, hàng rào chắc nhất là secret không tồn tại trong thư mục hand làm việc. Khi `isolation=worktree` (mặc định nếu cwd là git repo), `hand-ext run`:

1. Tạo worktree detached tại `HEAD` dưới `worktree_root` (mặc định `~/.hybrid-hands/worktrees/<repo>-<run-id>`), ngoài repo.
2. Chép trạng thái làm việc: áp `git diff HEAD --binary` của file tracked rồi chép các file untracked **không bị ignore** (`git ls-files --others --exclude-standard`). File bị ignore như `.env`, `*.demo.env` không bao giờ được chép, nên không có trong workspace. Lớp chặn thứ hai: untracked có basename giống secret (`.env`, `*.env`, `*.pem`, `*.key`, `id_rsa*`, `.netrc`, `.npmrc`, `.pypirc`; trừ `.env.example`/`.env.sample`/`.env.template`/`*.env.example`) bị bỏ qua dù repo quên ignore, và symlink untracked chỉ được chép khi là đường dẫn tương đối, đích resolve nằm trong repo và không giống secret; tên bị bỏ được ghi vào report.
3. Chạy backend với cwd/worktree (dsh nhận worktree qua `HAND_EXT_DSH_WORKSPACE`).
4. Sau run, chụp trạng thái worktree bằng một git index riêng, ghi diff nhị phân vào `<runs_dir>/<run-id>/changes.patch`, rồi áp về cwd gốc bằng `git apply --check` + `git apply`. Xung đột thì không ghi đè thay đổi người dùng: report ghi `xung đột` kèm danh sách file, patch vẫn nằm trong thư mục lượt chạy. Patch rỗng thì bỏ qua áp.
5. Dọn worktree (`git worktree remove --force` + `git worktree prune`) kể cả khi timeout/lỗi; patch vẫn được lưu. `--keep-worktree` giữ worktree để kiểm tra; `--no-apply` chỉ lưu patch, không áp.

Cờ `--isolation none` tắt cách ly cho một lượt (chỉ dùng khi biết repo không có secret/dữ liệu khách hàng). Cwd không phải git repo và isolation là mặc định: chạy trực tiếp `none` kèm cảnh báo trong report. `--isolation worktree` tường minh mà không tạo được worktree sạch (không phải git repo, HEAD chưa có commit, đường dẫn đã tồn tại, lỗi git) thì thoát 2. Worktree được tạo từ `HEAD` nhưng có thay đổi chưa commit, nên hand thấy đúng trạng thái làm việc; hand không thấy file bị ignore hay file untracked nghi bí mật.

## 6. Theo dõi phiên và hand: `hh-ps`

`hh-ps [--since 6h] [--all] [--json] [--watch N] [--count K] [--cwd D] [--main-session UUID]` vẽ cây chỉ đọc: phiên Claude (phiên chính đánh dấu `[chính]` theo `CLAUDE_CODE_SESSION_ID`, phiên phụ và phiên đã kết thúc) → subagent `hybrid-hands:hand` → lượt `hand-ext run` do phiên đó gọi, kèm trạng thái, ngữ cảnh token, trần token/tỉ lệ (nếu có meta), thời gian bắt đầu, lần hoạt động cuối và thời lượng. Mặc định chỉ lấy project của git toplevel cwd (mọi phiên đang sống vẫn hiện); `--since` (m/h/d) lọc phiên/subagent/lượt đã xong; `--all` lấy mọi project; `--watch N` vẽ lại mỗi N giây (tối thiểu 2), dừng bằng Ctrl-C hoặc `--count K`; màu chỉ bật khi stdout là TTY và tắt bằng `NO_COLOR`. `--main-session <UUID>` đè phiên chính lấy từ `CLAUDE_CODE_SESSION_ID`; id không đúng dạng UUID thì argparse báo lỗi.

Nguồn: `~/.claude/sessions/<pid>.json` (hoặc `CLAUDE_CONFIG_DIR`) đối chiếu `os.kill(pid, 0)`, transcript `~/.claude/projects/<slug>/<sessionId>.jsonl` (tìm theo tên file trên mọi slug; `customTitle` cuối cùng thắng), subagent `.../<sessionId>/subagents/agent-*.meta.json|.jsonl` (`finished` khác true và jsonl im quá 30 phút → "im lặng"), và sổ lượt đang chạy `~/.hybrid-hands/runs/<run_id>.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Không đọc file `.key`, không in nội dung tin nhắn/prompt hay socket token, không gửi mạng. `--json` in schema `schema`, `generated_at`, `since_seconds`, `cwd`, `all_projects`, `main_session_id`, `sessions[]` (mỗi phiên có `subagents[]`, `hand_runs[]`), `orphan_runs[]` và `totals`; lượt `running` mà pid đã chết hiện `mất (tiến trình đã chết)`. Phiên phụ có `parent_session` khớp một phiên đang hiện được vẽ lồng dưới phiên cha (kể cả phiên phụ lồng nhau), và `--json` thêm ba trường `parent_session`, `side_name`, `provider` cho mỗi phiên.

## 7. Chuyển phiên giữa terminal và Paseo: `cc-switch`

`cc-switch term [--agent ID|--session SID] [--dry-run] [-- <đối số thêm cho claude>]` lấy agent Paseo provider `claude` của project hiện tại (hoặc chọn theo id/tiền tố/session), chờ `paseo wait` nếu agent đang chạy, từ chối nếu đã có TUI `claude` sống cùng session, rồi `chdir` vào cwd agent và `exec claude --resume <sid> [--model <model>]`. Sau đó đừng gửi tin cho agent từ Paseo cho tới khi chuyển lại.

`cc-switch paseo [--session SID] [--dry-run]` lấy transcript sửa gần nhất có dòng `user` trong project (hoặc session chỉ định), từ chối nếu TUI còn sống (phải `/exit` trước), rồi `paseo agent reload <id>` nếu đã có agent, không thì `paseo import <sid> --provider claude --cwd <cwd> --json`. Xong thì mở Paseo trên điện thoại để tiếp tục. `cc-switch term` ghi sổ bàn giao ở `~/.hybrid-hands/cc-switch/handoff.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`); `cc-switch paseo` không có `--session` dùng phiên trong sổ nếu transcript còn và xoá mục sau khi nạp lại/import thành công. `cc-switch status [--all]` in bảng id/title/status Paseo/session/TUI và nơi đang giữ (`terminal`, `paseo`, `không`).

**Chuyển chính phiên TUI đang mở:** `cc-switch paseo --self [--idle-sec 20] [--exit-timeout 30] [--dry-run]` dùng ngay bên trong phiên Claude Code TUI, không cần `/exit` bằng tay. Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, tìm pid TUI đang mở qua sổ `~/.claude/sessions/<pid>.json` (nhiều pid thì chọn pid là tổ tiên của tiến trình gọi bằng `ps -o ppid=`), rồi tách một tiến trình nền độc lập; log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại pid vẫn là TUI của session, gửi SIGTERM và chờ TUI thoát tối đa `--exit-timeout` giây (không SIGKILL), rồi chạy đúng luồng `cc-switch paseo --session <sid>`. Lệnh cha trả về ngay và in pid TUI, thời gian chờ, đường log cùng cách quay lại (`cc-switch term`); đừng gõ hay nhấn Enter cho tới khi TUI tự đóng. `--dry-run` chỉ in kế hoạch, không tách tiến trình; `--self` không đi cùng `--session` (sai cách dùng, thoát 2).

**Chuyển chính phiên Paseo về terminal:** `cc-switch term --self [--idle-sec 20] [--app Terminal|iTerm] [--dry-run]` dùng bên trong phiên Claude Code do Paseo giữ (agent Paseo provider `claude`). Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, từ chối nếu phiên đã mở trong terminal, tìm agent Paseo theo session (không có thì báo "phiên không do Paseo giữ" và gợi ý `cc-switch term --session`), và chỉ chạy trên macOS. `--dry-run` in kế hoạch gồm session/agent rút gọn, cwd, app, lệnh sẽ chạy trong cửa sổ và đường log. Không dry-run: lệnh tách một tiến trình nền rồi in hướng dẫn đừng gửi tin cho agent từ Paseo cho tới khi chạy `/to-paseo` hoặc `cc-switch paseo`; cửa sổ sẽ mở sau khi lượt hiện tại xong. Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại không còn TUI sống cho session, rồi ghi `cd <cwd> && exec <bin/cc-switch> term --session <sid>` vào `~/.hybrid-hands/cc-switch/term-<sid8>.command` (quyền 700) và chạy `open -a Terminal` (hoặc `iTerm`) với file đó — đúng luồng `cc-switch term` hiện có: ghi sổ bàn giao và `exec claude --resume`. Log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Cách mở bằng `open` không cần quyền Automation của macOS. `--self` không đi cùng `--agent`/`--session` và không nhận đối số sau `--` (sai cách dùng, thoát 2).

**Slash command `/to-paseo` và `/to-term`:** plugin có hai lệnh trong `commands/`; mỗi lệnh chỉ chạy đúng một lệnh `cc-switch paseo --self` hoặc `cc-switch term --self` bằng tool Bash làm hành động cuối, rồi trả lời một câu ngắn. Nếu `cc-switch` không có trong `PATH`, dùng đường dẫn tuyệt đối mà hook SessionStart in ra. Chưa kiểm hai slash command chạy được bên trong agent Paseo (cần máy có Terminal.app).

**Vì sao phải reload:** tiến trình `claude` do Paseo giữ hội thoại trong bộ nhớ. Lượt làm ở terminal ghi tiếp vào cùng transcript; nếu Paseo trả lời mà không reload, nó dựa vào lịch sử cũ và ghi một nhánh rẽ. Lần `--resume` sau đi theo lá mới nhất nên lượt terminal bị mất khỏi ngữ cảnh. `paseo agent reload` khởi lại tiến trình lười, resume từ transcript nên thấy đủ lượt terminal. `cc-switch` chỉ đọc các trường agent đã khai báo và không đọc `.key`; việc ghi trạng thái là do `paseo`.

Mã thoát: 2 sai cách dùng (kể cả `--self` đi cùng `--agent`/`--session` hoặc có đối số sau `--`) và `term --self` trên hệ điều hành không phải macOS, 3 không tìm thấy agent/transcript hoặc pid TUI (kể cả session không do Paseo giữ), 4 TUI còn sống, không xác định được pid, hoặc không mở được cửa sổ terminal (`open` lỗi), 5 lệnh `paseo` lỗi.

## 8. Xem cây trên Paseo

Plugin `hh-tree` trong `paseo-hh-tree/` hiện cây phiên Claude → subagent → lượt hand ngoài trong app Paseo (desktop và điện thoại): panel cạnh từng agent, màn hình đầy đủ mở từ sidebar, và ô cài đặt đường dẫn `hh-ps`; dữ liệu tự làm mới mỗi 5 giây. Xem `paseo-hh-tree/OVERVIEW.md` để biết cách cài, cách đặt đường dẫn `hh-ps` và những dữ liệu plugin chỉ đọc trên máy.

## 9. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
