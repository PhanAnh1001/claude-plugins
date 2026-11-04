# hybrid-hands

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai, bật theo từng dự án thay cho `parallel-subagents`: brain chạy trên gói Claude, hand chọn loại rẻ nhất làm được việc.
- **Thành phần:**
  - hand Claude: agent `hybrid-hands:hand` (chép từ `parallel-subagents:hand`);
  - hand GPT-6.1 Sol Flex qua Codex: lệnh `hand-gpt` (estimate, trần chi phí, sổ `output/llm/codex_usage.json`), skill `gpt-hand`;
  - phiên phụ: lệnh `side-session` (phiên có ngữ cảnh brain riêng cho gói việc dài), skill `side-session`;
  - hook SessionStart (khuôn brief, luật chọn hand, luật chi phí) và UserPromptSubmit (bản ngắn).
- **Bật theo dự án:** cài ở scope project trong thư mục dự án, tắt `parallel-subagents` ở scope project (scope project ghi đè scope user, xem mục 3).
- **Việc cần làm lần đầu:** `hand-gpt setup`, người dùng tự `CODEX_HOME=~/.codex-hand codex login --with-api-key`, rồi `hand-gpt doctor`.

## 1. Cây thư mục

```text
hybrid-hands/
├── .claude-plugin/marketplace.json     # marketplace hybrid-hands-local
├── README.md
├── tests/                              # test của hand-gpt, side-session
└── plugins/hybrid-hands/
    ├── .claude-plugin/plugin.json
    ├── agents/hand.md                  # hand Claude
    ├── bin/hand-gpt, bin/side-session  # vào PATH của tool Bash khi plugin bật
    ├── lib/hand_gpt/, lib/side_session/
    ├── hooks/hooks.json
    ├── scripts/session-start-policy.sh, scripts/inject-policy.sh
    ├── skills/gpt-hand/, skills/side-session/, skills/paseo/
    └── templates/hand-brief.md, gpt-hand-preamble.md, side-session-prompt.md
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
  "gpt_hand": {
    "model": "gpt-6.1-sol",
    "service_tier": "flex",
    "effort": "medium",
    "max_usd": 1.0,
    "approval_usd": 1.5
  },
  "side_session": {
    "max_parallel": 2,
    "handoff_dir": "docs/work-in-progress/handoffs"
  }
}
```

Tên khoá chuẩn theo `lib/hand_gpt/config.py` và `lib/side_session/`; thiếu file thì dùng các giá trị mặc định trên.

## 5. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
