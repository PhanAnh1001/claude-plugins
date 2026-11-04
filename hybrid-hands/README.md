# hybrid-hands

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai, bật theo từng dự án thay cho `parallel-subagents`: brain chạy trên gói Claude chính; việc code/tài liệu tự chứa mặc định giao hand ngoài chạy trên gói subscription thứ hai (mặc định DeepSeek V4.1 Flash qua `dsh`/`opencode`) để giữ hạn mức gói chính.
- **Thành phần:**
  - hand ngoài: lệnh `hand-ext` (mặc định `dsh`, `opencode` — DeepSeek V4.1 Flash trên gói OpenCode Go — theo `order`; `codex`, `claude`, `gemini` chỉ khai báo để gọi tường minh; sổ token `output/llm/hand_usage.json` và sổ USD Go toàn máy `~/.hybrid-hands/go_usage.jsonl`, lệnh `hand-ext usage`), skill `ext-hand`;
  - hand Claude: agent `hybrid-hands:hand` (gói chính) cho việc cần tool riêng của Claude Code, lệnh trả phí của dự án, hoặc khi `hand-ext` thoát 7;
  - phiên phụ: lệnh `side-session` (phiên có ngữ cảnh brain riêng cho gói việc dài), skill `side-session`; lệnh `hh-ps` xem cây phiên Claude → subagent → lượt hand ngoài; skill `paseo` theo dõi từ điện thoại;
  - hook SessionStart (khuôn brief, luật chọn hand, luật hạn mức) và UserPromptSubmit (bản ngắn).
- **Luật hạn mức:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; sau mỗi lượt báo backend, token, % hạn mức (Claude/Codex) hoặc % Go 5h/tuần kèm USD ước tính, thời điểm reset.
- **Bật theo dự án:** cài ở scope project trong thư mục dự án, tắt `parallel-subagents` ở scope project (xem mục 3).
- **Việc cần làm lần đầu:** `hand-ext setup`, người dùng tự đăng nhập từng backend (mục 5), rồi `hand-ext doctor`.

## 1. Cây thư mục

```text
hybrid-hands/
├── .claude-plugin/marketplace.json     # marketplace hybrid-hands-local
├── README.md
├── tests/                              # test của hand-ext, side-session
└── plugins/hybrid-hands/
    ├── .claude-plugin/plugin.json
    ├── agents/hand.md                  # hand Claude
    ├── bin/hand-ext, bin/side-session, bin/hh-ps  # vào PATH của tool Bash khi plugin bật
    ├── lib/hand_ext/ (backends/: codex | claude | dsh | opencode), lib/side_session/, lib/hh_ps/
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

## 5. Backend của hand ngoài

Lệnh: `hand-ext setup|doctor [--backend B|all] [--cwd D]`, `hand-ext run --brief F|- [--backend B|auto] [--browser] [--label L] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S]`, `hand-ext status`, `hand-ext usage [--json]`, `hand-ext report`. Mã thoát: 0 ok, 1 failed, 2 sai cách dùng, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập. `--browser` chỉ dùng với backend `dsh`: `--backend auto --browser` chỉ xét `dsh`, còn `--backend` khác `dsh` kèm `--browser` thoát 2.

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

## 6. Theo dõi phiên và hand: `hh-ps`

`hh-ps [--since 6h] [--all] [--json] [--watch N] [--count K] [--cwd D]` vẽ cây chỉ đọc: phiên Claude (phiên chính đánh dấu `[chính]` theo `CLAUDE_CODE_SESSION_ID`, phiên phụ và phiên đã kết thúc) → subagent `hybrid-hands:hand` → lượt `hand-ext run` do phiên đó gọi, kèm trạng thái, ngữ cảnh token, trần token/tỉ lệ (nếu có meta), thời gian bắt đầu, lần hoạt động cuối và thời lượng. Mặc định chỉ lấy project của git toplevel cwd (mọi phiên đang sống vẫn hiện); `--since` (m/h/d) lọc phiên/subagent/lượt đã xong; `--all` lấy mọi project; `--watch N` vẽ lại mỗi N giây (tối thiểu 2), dừng bằng Ctrl-C hoặc `--count K`; màu chỉ bật khi stdout là TTY và tắt bằng `NO_COLOR`.

Nguồn: `~/.claude/sessions/<pid>.json` (hoặc `CLAUDE_CONFIG_DIR`) đối chiếu `os.kill(pid, 0)`, transcript `~/.claude/projects/<slug>/<sessionId>.jsonl` (tìm theo tên file trên mọi slug; `customTitle` cuối cùng thắng), subagent `.../<sessionId>/subagents/agent-*.meta.json|.jsonl` (`finished` khác true và jsonl im quá 30 phút → "im lặng"), và sổ lượt đang chạy `~/.hybrid-hands/runs/<run_id>.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Không đọc file `.key`, không in nội dung tin nhắn/prompt hay socket token, không gửi mạng. `--json` in schema `schema`, `generated_at`, `since_seconds`, `cwd`, `all_projects`, `main_session_id`, `sessions[]` (mỗi phiên có `subagents[]`, `hand_runs[]`), `orphan_runs[]` và `totals`; lượt `running` mà pid đã chết hiện `mất (tiến trình đã chết)`.

## 7. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
