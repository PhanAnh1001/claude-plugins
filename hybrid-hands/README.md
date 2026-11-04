# hybrid-hands

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai, bật theo từng dự án thay cho `parallel-subagents`: brain chạy trên gói Claude chính; việc code/tài liệu tự chứa mặc định giao hand ngoài chạy trên gói subscription thứ hai để giữ hạn mức gói chính.
- **Thành phần:**
  - hand ngoài: lệnh `hand-ext` (backend `codex`, `claude`, `opencode` theo `order`; sổ token `output/llm/hand_usage.json`, không USD), skill `ext-hand`;
  - hand Claude: agent `hybrid-hands:hand` (gói chính) cho việc cần tool riêng của Claude Code, lệnh trả phí của dự án, hoặc khi `hand-ext` thoát 7;
  - phiên phụ: lệnh `side-session` (phiên có ngữ cảnh brain riêng cho gói việc dài), skill `side-session`; skill `paseo` theo dõi từ điện thoại;
  - hook SessionStart (khuôn brief, luật chọn hand, luật hạn mức) và UserPromptSubmit (bản ngắn).
- **Luật hạn mức:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; sau mỗi lượt báo backend, token, % hạn mức, thời điểm reset.
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
    ├── bin/hand-ext, bin/side-session  # vào PATH của tool Bash khi plugin bật
    ├── lib/hand_ext/ (backends/codex, claude, opencode), lib/side_session/
    ├── hooks/hooks.json
    ├── scripts/session-start-policy.sh, scripts/inject-policy.sh
    ├── skills/ext-hand/, skills/side-session/, skills/paseo/
    └── templates/hand-brief.md, ext-hand-preamble.md, opencode-hand.jsonc, side-session-prompt.md
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
    "order": ["codex", "claude", "opencode"],
    "timeout_min": 60,
    "max_tokens": null,
    "sandbox": "workspace-write",
    "ledger": "output/llm/hand_usage.json",
    "quota_state": "output/llm/hand_quota.json",
    "runs_dir": "output/llm/hand-ext",
    "backends": {
      "codex": { "home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "high" },
      "claude": { "config_dir": "~/.claude-hand", "model": "claude-opus-5-5", "effort": "medium", "max_turns": 80 },
      "opencode": { "config": "<PL>/templates/opencode-hand.jsonc", "model": "opencode-go/deepseek-v4.1-flash", "variant": "max" },
      "gemini": { "home": "~/.gemini-hand", "model": "gemini-4-carbon" }
    }
  },
  "side_session": {
    "max_parallel": 2,
    "handoff_dir": "docs/work-in-progress/handoffs"
  }
}
```

Tên khoá chuẩn theo `lib/hand_ext/constants.py` (mặc định) và `lib/side_session/`; thiếu file thì dùng các giá trị mặc định trên. `<PL>` được thay bằng thư mục plugin. `gemini` chỉ khai báo, không nằm trong `order`.

## 5. Backend của hand ngoài

Lệnh: `hand-ext setup|doctor [--backend B|all] [--cwd D]`, `hand-ext run --brief F|- [--backend B|auto] [--label L] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S]`, `hand-ext status`, `hand-ext report`. Mã thoát: 0 ok, 1 failed, 2 sai cách dùng, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập.

| Backend | Gói | Người dùng tự đăng nhập | Theo dõi hạn mức | Rủi ro tính tiền |
|---|---|---|---|---|
| `codex` | ChatGPT | `CODEX_HOME=~/.codex-hand codex login --device-auth` | `used_percent`, `resets_at` từ sự kiện của `codex exec --json` | đăng nhập API key thì tính tiền; `doctor` chặn, hand gỡ biến `OPENAI_API_KEY` |
| `claude` | Claude tài khoản thứ hai | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` | lỗi hết hạn mức trong stream, `hand-ext status` | dùng nhầm tài khoản chính thì ăn hạn mức brain; hook repo vẫn chạy |
| `opencode` | OpenCode Go (DeepSeek V4.1 Flash, biến thể max) | `opencode auth login` chọn OpenCode Go | lỗi hết hạn mức, `hand-ext status` | Extra Usage bật hoặc Console còn credit thì tính tiền khi hết hạn mức: phải TẮT Extra Usage, để credit 0; Go hiện là bản 0910, chưa phải 1017 |
| `gemini` | dự kiến | chưa có | chưa có | Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI |

## 6. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
