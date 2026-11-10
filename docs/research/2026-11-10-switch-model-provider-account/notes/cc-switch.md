# cc-switch — cơ chế switch model, effort, provider, account và bảo mật

## Tóm tắt

- **Mục đích:** ghi lại cách `farion1231/cc-switch` (app Tauri) đổi model/effort/provider/account cho Claude Code, Codex và các CLI khác, cách nó đồng bộ MCP/skills/plugin, và rủi ro bảo mật.
- **Kết luận chính:**
  1. Switch provider = **ghi đè cấu hình toàn cục** của CLI (`~/.claude/settings.json`, `~/.claude.json`, `~/.codex/config.toml` + `auth.json`), merge theo "ownership floor", chỉ một thư mục override cho mỗi app; không đọc `CLAUDE_CONFIG_DIR`/`CODEX_HOME`.
  2. Effort: Codex ghi `model_reasoning_effort` (mặc định `high`) vào `config.toml`; Claude qua proxy có `claudeReasoningEffort` (auto/off/passthrough) và 2 bộ "rectifier" thinking (bỏ chữ ký lỗi, ép budget ≤ 32000) rồi retry.
  3. Nhiều account Claude OAuth: mỗi account là `<data>/claude-accounts/<id>/config` làm `CLAUDE_CONFIG_DIR`; **symlink** `skills/ commands/ agents/ plugins/ rules/ projects/…` về `~/.claude`, mirror `settings.json` (bỏ khoá nhạy cảm) và chỉ `mcpServers` của `.claude.json`, `CLAUDE.md` = một dòng `@<default>`.
  4. Bảo mật: 2 High (đổi token vào default slot toàn cục; deeplink `ccswitch://` nhập endpoint/env/usageScript chỉ cảnh báo, không chặn), 3 Medium (API key plaintext SQLite + sync không mã hoá; proxy không auth, listen_address cấu hình được; CSP `connect-src` rộng + `bash -c` cài CLI), Low tích cực (updater ký, không telemetry).
- **Mốc dữ liệu:** clone HEAD `76e19b47cfb8e379f8944d3fe2ad6d4c369d438a` (11/2026). Mọi link trỏ `https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/<path>#L<n>`. Điểm ghi "(quét trước, chưa kiểm lại)" lấy từ brief, chưa spot-check lần này.
- **Người đọc phải làm:** không dùng cc-switch song song với hybrid-hands trên cùng `~/.claude`/`~/.codex-hand` khi chưa xem mục 2 và 4 (suy luận).

## 1. Switch model, effort, provider

### 1.1 Provider (ghi cấu hình live)
- Thư mục Claude = override hoặc `~/.claude` ([src-tauri/src/config.rs:91-97](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/config.rs#L91-L97)), MCP `~/.claude.json` ([config.rs:100](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/config.rs#L100)) (11/2026).
- Codex `config.toml` + `auth.json` ([src-tauri/src/codex_config.rs:270-280](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/codex_config.rs#L270-L280)) — quét trước, chưa kiểm lại.
- Merge theo ownership floor: khoá `env ANTHROPIC_*`, `CLAUDE_CODE_OAUTH_TOKEN`, `apiKeyHelper`, `model`, `fallbackModel`, `modelOverrides` thuộc cc-switch; `hooks/statusLine/plugins` giữ ([src-tauri/src/live/floor.rs:40-75](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/live/floor.rs#L40-L75)); backup lần ghi đầu ([live/engine.rs:161-181](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/live/engine.rs#L161-L181)) — quét trước, chưa kiểm lại.
- Suy luận: model Claude đổi bằng cách ghi `model`/env vào settings toàn cục, nên áp cho mọi phiên mới, không theo phiên.

### 1.2 Effort / thinking
- Codex: provider sinh `config.toml` với `model_reasoning_effort = "{reasoning_effort}"`, mặc định `"high"` ([src-tauri/src/provider.rs:926-948](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/provider.rs#L926-L948)); thêm `codex_stack_subagent_reasoning_effort` ([settings.rs:575](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/settings.rs#L575)) (11/2026).
- Claude qua proxy sang OpenAI Chat/Responses: `claudeReasoningEffort` mặc định auto, `off`/`passthrough` ([provider.rs:585-592](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/provider.rs#L585-L592)) (11/2026).
- Proxy `thinking_rectifier.rs`: lỗi chữ ký thì xoá block thinking/redacted_thinking/signature rồi retry ([proxy/thinking_rectifier.rs:1-4](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/proxy/thinking_rectifier.rs#L1-L4)); `thinking_budget_rectifier.rs`: lỗi `budget_tokens` thì chỉnh budget, trần `MAX_THINKING_BUDGET = 32000` ([proxy/thinking_budget_rectifier.rs:1-10](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/proxy/thinking_budget_rectifier.rs#L1-L10)) (11/2026).
- `model_mapper.rs` thay tên model trong request theo cấu hình provider (haiku/sonnet/… ) ([proxy/model_mapper.rs:1-12](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/proxy/model_mapper.rs#L1-L12)) (11/2026).
- Các CLI khác cũng có effort riêng: Copilot `reasoning_effort` ([copilot_config.rs:138](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/copilot_config.rs#L138)), Hermes ([hermes_config.rs:16](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/hermes_config.rs#L16)) (11/2026).
- Proxy 127.0.0.1:15721 còn circuit breaker/failover/codex_quota_protection (`src-tauri/src/proxy/`) — quét trước, chưa đọc chi tiết.

## 2. Account và đồng bộ MCP/skills/plugin

### 2.1 Nhiều account Claude
- Thư mục `<app_config_dir>/claude-accounts/<local_id>/` ([services/claude_account/layout.rs:1](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L1), [:19-34](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L19-L34)); Keychain `Claude Code-credentials-<sha256(CLAUDE_CONFIG_DIR)[0:8]>` ([layout.rs:10-11](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L10-L11)); `CLAUDE_CONFIG_DIR` của account được ghi vào `settings.json` ([layout.rs:100](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L100)) (11/2026).
- Bảng account `claude_accounts.json` chỉ local, không sync ([claude_account/mod.rs:11](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/mod.rs#L11)) (11/2026).
- Hai chế độ: mở terminal per-session vs chọn thẻ official chuyển token vào default slot `~/.claude` có journal ([claude_account/snapshot/store.rs:3](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/snapshot/store.rs#L3); snapshot/mod.rs:1-24 quét trước) (11/2026).

### 2.2 Account nhận skills/plugins/MCP thế nào
- `shared.rs` ([services/claude_account/shared.rs:1-12](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/shared.rs#L1-L12)) (11/2026):
  - `skills/ commands/ agents/ output-styles/ plugins/ rules/ workflows/` và `projects/ file-history/ todos/ plans/`: **symlink** về thư mục mặc định; chỉ thay thư mục rỗng, không copy/xoá.
  - `settings.json`: mirror, bỏ khoá nhạy cảm và `CLAUDE_CONFIG_DIR`, merge ba bên theo `.mirror-state.json`.
  - `.claude.json`: chỉ mirror `mcpServers`.
  - `CLAUDE.md`: một dòng `@<default CLAUDE.md>`.

### 2.3 Đồng bộ giữa các app (Claude/Codex/Gemini…)
- MCP: một kho chung, chiếu các mục bật vào `~/.claude.json` ([src-tauri/src/mcp/claude.rs:40](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/mcp/claude.rs#L40)); mỗi app một file trong `src-tauri/src/mcp/` (11/2026).
- Skills: SSOT rồi symlink, lỗi thì copy ([services/skill.rs:55](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/skill.rs#L55)); thư mục đích Claude = override hoặc mặc định ([skill.rs:672-678](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/skill.rs#L672-L678)) (11/2026).
- Prompts/plugin (`commands/{prompt,plugin}.rs`, `claude_plugin.rs`): không thấy tham chiếu `claude-accounts` (grep), nên account nhận qua symlink ở 2.2 (suy luận).

## 3. Bảo mật

### 3.1 High
- **H1 default-slot swap:** chọn thẻ official ghi token account vào slot mặc định toàn cục; mọi phiên Claude dùng `~/.claude` đổi account (snapshot/store.rs:3, mục 2.1).
- **H2 deeplink `ccswitch://`:** nhận `usageScript`, `usageApiKey`, `usageBaseUrl`, endpoint, env ([deeplink/parser.rs:186-190](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/deeplink/parser.rs#L186-L190)); `deeplinkRisk.ts` ghi rõ "chỉ dùng cho UI, không tham gia quyết định chặn" ([src/utils/deeplinkRisk.ts:1-6](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src/utils/deeplinkRisk.ts#L1-L6)) (11/2026). `usage_script.rs:81-129` chạy script — quét trước, chưa kiểm lại.

### 3.2 Medium
- API key nằm trong `settings_config TEXT` SQLite plaintext ([database/schema.rs:60-63](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/database/schema.rs#L60-L63)); sync WebDAV/S3 không mã hoá (`services/webdav_sync.rs`, `s3_sync.rs`) — quét trước.
- Proxy bind `listen_address:listen_port` cấu hình được ([proxy/server.rs:110-122](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/proxy/server.rs#L110-L122)), không auth (token giả `PROXY_MANAGED`), có `browser_guard.rs` (11/2026).
- CSP `img-src … https: http:` và `connect-src` rộng ([src-tauri/tauri.conf.json:31](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/tauri.conf.json#L31)); `bash -c` cài CLI (commands/misc.rs:416-439, quét trước) (11/2026).

### 3.3 Low / tích cực
- Capabilities hẹp, updater minisign, notarize, không telemetry; MIT; ~15 commit/ngày — quét trước, chưa kiểm lại. semgrep/cargo-audit chưa chạy.

## Chưa kiểm
- Không build/chạy app. Chưa đọc `circuit_breaker`, `failover_switch`, `codex_quota_protection`, `commands/plugin.rs`.
