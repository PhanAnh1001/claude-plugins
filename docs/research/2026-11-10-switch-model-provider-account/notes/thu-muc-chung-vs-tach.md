# Thư mục chung (A) và tách thư mục theo tài khoản (B): đồng bộ plugin, skill, config

## Tóm tắt

- **Mục đích:** so sánh hai cách dùng nhiều tài khoản Claude Code/Codex trên một máy: (A) dùng chung `~/.claude` (hoặc `~/.codex`) và đổi tài khoản bằng cách thay credential/settings trong thư mục đó (kiểu cc-switch chế độ official); (B) mỗi tài khoản một thư mục qua `CLAUDE_CONFIG_DIR`/`CODEX_HOME` (cách hybrid-hands đang dùng: v1=`~/.claude`, v2=`~/.claude-hand`, codex=`~/.codex-hand`). Trọng tâm là khó khăn đồng bộ plugin, skill, config, MCP, agents/commands, CLAUDE.md, hooks/statusLine.
- **Kết luận chính (suy luận):** giữ B vì chỉ B cho phép chạy song song nhiều tài khoản và tách quota/usage. Cách đồng bộ khuyến nghị là **khai báo manifest trung tâm rồi reconcile từng thư mục bằng CLI chính thức** (`claude plugin install` lặp theo mỗi `CLAUDE_CONFIG_DIR`). Chỉ symlink nội dung không có trạng thái (skills/agents/commands, CLAUDE.md). Không bao giờ chia sẻ credential, `projects/` (transcript), state đăng nhập.
- **Số chính:** 3 thư mục cần quản lý cấu hình (`~/.claude`, `~/.claude-hand`, `~/.codex-hand`); hiện repo chỉ có một bước cài plugin (scope project, README:165), không có bước cài cho `~/.claude-hand`.
- **Kiểm chứng:** dữ kiện docs chính thức do brain xác minh (11/2026); cấu trúc máy là quan sát tên mục do brain cung cấp ngày 10/11/2026, không đọc nội dung thư mục tài khoản.
- **Người đọc phải làm:** giữ tách credential/state, xem overlay ở [report](../report.md); chỉ triển khai reconcile sau khi người dùng chốt thay đổi L2.

## 1. Hai mô hình

### 1.1 A — thư mục chung, đổi credential tại chỗ

Một thư mục provider duy nhất; công cụ switch ghi đè credential/settings (và với Claude trên macOS là mục Keychain) khi đổi tài khoản. Cấu hình, plugin, skill dùng chung tự nhiên vì chỉ có một bản. Nhược: chỉ một tài khoản hoạt động tại một thời điểm; mỗi lần đổi là một lần ghi vào file sống → rủi ro mất login nếu ghi dở; usage/transcript trộn tài khoản. (suy luận từ chế độ official trong [note cc-switch](cc-switch.md), có link code gốc 11/2026)

### 1.2 B — mỗi tài khoản một thư mục

Đặt `CLAUDE_CONFIG_DIR`/`CODEX_HOME` theo tiến trình. Song song được, cô lập login và usage. Nhược: mọi thứ "user scope" bị nhân bản theo thư mục → lệch plugin/skill/MCP/hooks giữa các tài khoản.

## 2. Cái gì thuộc thư mục cấu hình

### 2.1 Claude Code (`CLAUDE_CONFIG_DIR`)

Đã xác minh từ [claude-directory](https://code.claude.com/docs/en/claude-directory), [settings](https://code.claude.com/docs/en/settings), [env-vars](https://code.claude.com/docs/en/env-vars), [MCP](https://code.claude.com/docs/en/mcp), [memory](https://code.claude.com/docs/en/memory) (11/2026): `CLAUDE_CONFIG_DIR` đổi nơi lưu settings, lịch sử phiên và plugins; mọi đường dẫn `~/.claude` chuyển dưới nó; `.claude.json` (tài khoản, MCP user/local scope, state theo project) cũng theo nó.

| Nhóm | Nội dung trong thư mục cấu hình | Ghi chú |
|---|---|---|
| Settings | `settings.json`: permissions, hooks, env, model, statusLine | Script có thể ở ngoài |
| Chỉ dẫn | `CLAUDE.md`, `rules/`, `agents/`, `commands/`, `skills/` | Tài sản dùng chung có chọn lọc |
| Plugin | `plugins/`: installed_plugins.json, marketplaces, data | Sổ cài đặt phải giữ riêng |
| Phím tắt | `keybindings.json` | Cấu hình người dùng |
| Transcript | `projects/<project>/<session>.jsonl` | Plaintext, giữ 30 ngày |
| State | `.claude.json` | Khi không đặt biến: `~/.claude.json` |
| Credential | macOS Keychain; fallback `.credentials.json` mode 0600 | Keychain từ chối mới fallback; file và entry Keychain theo config dir |

Credential theo [authentication](https://code.claude.com/docs/en/authentication) (11/2026). Không đọc credential để kiểm chứng.

Ưu tiên: managed > CLI `--settings` > `.claude/settings.local.json` > `.claude/settings.json` > user; list như `permissions.allow` được gộp ([settings](https://code.claude.com/docs/en/settings), 11/2026). Project `.claude/`, `.mcp.json` không thuộc user config dir.

Managed macOS ở `/Library/Application Support/ClaudeCode/managed-settings.json`, thêm `managed-settings.d/`, `managed-mcp.json`, áp mọi user máy. `enabledPlugins`, `extraKnownMarketplaces`, hooks khai được ở managed; `strictKnownMarketplaces`, `managedMcpServers` chỉ managed. **Chưa xác minh managed tự tải plugin lúc khởi động** ([managed-settings](https://code.claude.com/docs/en/managed-settings), [settings-reference](https://code.claude.com/docs/en/settings-reference), 11/2026).

Cờ theo phiên: `--settings` ghi đè từng key; `--plugin-dir` lặp được, nhận thư mục hoặc `.zip`; `--mcp-config`, `--strict-mcp-config`, `--append-system-prompt`, `--model`, `--effort low|medium|high|xhigh|max|ultracode` (không lưu). `--add-dir` chỉ cấp quyền file; CLAUDE.md ở đó cần `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`, còn `.claude/skills` có nạp ([cli-reference](https://code.claude.com/docs/en/cli-reference), 11/2026).

Effort: `CLAUDE_CODE_EFFORT_LEVEL` > `/effort` > `--effort` > settings `effortLevel`/`modelSettings` > mặc định. `/model`, `/effort`: Enter lưu, `s` chỉ phiên; `MAX_THINKING_TOKENS` chỉ là env ([model-config](https://code.claude.com/docs/en/model-config), [env-vars](https://code.claude.com/docs/en/env-vars), 11/2026). Có `claude plugin install <plugin>@<marketplace>`; scope install chưa xác minh ([cli-reference](https://code.claude.com/docs/en/cli-reference), 11/2026).

### 2.2 Codex (`CODEX_HOME`)

`CODEX_HOME`, profiles, `model_reasoning_effort`, nơi lưu auth **đã xác minh từ docs ở mục 2.1 chính thức**; [config-reference](https://developers.openai.com/codex/config-reference) chưa đọc. Nguồn nội bộ chỉ xác nhận home riêng, sessions/archived_sessions: `AGENTS.md`, `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/codex.py` (không có nguồn internet, nguồn nội bộ). Có `allow_managed_hooks_only` trong requirements.toml ([config.md](https://github.com/openai/codex/blob/main/docs/config.md), 11/2026).

### 2.3 Cấu trúc thực tế trên máy

Quan sát cục bộ, không có nguồn internet: brain chỉ liệt kê **tên mục top-level** ngày 10/11/2026; hand không đọc nội dung tài khoản.

| Thư mục | Có / thiếu đáng chú ý |
|---|---|
| `~/.claude` | Có CLAUDE.md, agents/, hooks/, skills/ (paseo* thật + synced/), settings.json và nhiều .bak, statusline-command.sh, projects/ |
| `~/.claude/plugins` | installed_plugins.json và nhiều .bak, known_marketplaces.json, marketplaces/, cache/, data/, store/, synced/ |
| `~/.claude-hand` (v2) | Thiếu CLAUDE.md, agents/, hooks/; skills/ có paseo*@ symlink sang v1 + synced/; sổ installed_plugins.json và known_marketplaces.json riêng; có settings.json.bak-20261110-sync |
| `~/.codex-hand` so với `~/.codex` | Thiếu AGENTS.md, agents/, rules/, hooks.json; skills/ chỉ .system/; plugins/, sessions/, archived_sessions/ riêng |

Suy luận: chỉ dẫn toàn cục CLAUDE.md của v1 không tự áp cho v2; tên backup cho thấy đã có lần đồng bộ settings ngày 10/11, không chứng minh nội dung hiện khớp.

## 3. Hybrid-hands hiện xử lý thế nào

Không có nguồn internet, nguồn nội bộ:

### 3.1 Claude

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/claude.py:26,32`: tài khoản v2 dùng `CLAUDE_CONFIG_DIR=~/.claude-hand`; docstring dòng 3 ghi Keychain khoá theo thư mục.
- `claude.py:76-77`: chặn `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_BASE_URL`, Bedrock/Vertex → buộc dùng login subscription.
- `claude.py:228-232`: v1 **gỡ** `CLAUDE_CONFIG_DIR` thay vì đặt `~/.claude`, vì đặt biến làm Claude Code tìm `~/.claude/.claude.json` và báo "Not logged in". Hệ quả: v1 và v2 không đối xứng (v1 có `~/.claude.json` ngoài thư mục).
- `lib/hand_ext/config.py:175-195`: `claude_accounts` merge mặc định → global → repo.
- `lib/cc_switch/providers.py:19,34`: cc-switch cần provider có env `CLAUDE_CONFIG_DIR`, mặc định `~/.claude` → cc-switch của plugin theo mô hình B.

### 3.2 Codex

`lib/hand_ext/backends/codex.py:24,65,143,183`: luôn đặt `CODEX_HOME` riêng (`~/.codex-hand`), không bao giờ dùng `~/.codex`; dòng 167: Sol và hand dùng chung một `CODEX_HOME`.

### 3.3 Cài plugin

README:163-166 chỉ có `claude plugin marketplace add` + `claude plugin install ... --scope project` chạy với cấu hình mặc định. Không tìm thấy bước cài plugin/skills cho `~/.claude-hand` trong `lib/`, `scripts/`, README. AGENTS.md bắt buộc cập nhật plugin "cho mọi repo qua công cụ chính thức" nhưng không nói tới mọi thư mục cấu hình → khoảng trống. (suy luận: scope project ghi vào `.claude/settings.json` của repo nên `enabledPlugins` dùng chung, nhưng cache/`known_marketplaces` user scope vẫn theo từng thư mục — scope cài đặt vẫn chưa xác minh.)

## 4. Phương án đồng bộ cho B

Tất cả đánh giá là suy luận.

### 4.1 Nhóm chia sẻ tĩnh

| Phương án | Ưu | Nhược / rủi ro |
|---|---|---|
| Symlink `skills/`, `agents/`, `commands/`, `CLAUDE.md` | Đơn giản, luôn khớp | Ghi từ một tài khoản ảnh hưởng tất cả; công cụ có thể thay symlink bằng file thật |
| Symlink cả `plugins/` | Một bản cài | `installed_plugins.json` có đường dẫn tuyệt đối/phiên bản; hai tiến trình ghi đồng thời → hỏng sổ; xung đột phiên bản khi một bên update |
| Chỉ symlink `plugins/marketplaces` | Giảm tải clone | Vẫn lệch sổ cài đặt; ít lợi |
| Managed settings dùng chung | Một nguồn cho hooks/env/plugin bắt buộc | Cần quyền admin, áp mọi tài khoản và mọi repo, khó gỡ |

### 4.2 Nhóm chèn theo phiên (launcher hybrid-hands)

Cờ `--settings`, `--plugin-dir`, `--mcp-config` do `hand-ext`/`side-session` chèn: không ghi gì vào thư mục cấu hình, đúng luật không sửa settings. Nhược: chỉ áp phiên khởi chạy qua plugin; phiên người dùng mở tay vẫn lệch; merge settings theo từng key đã xác minh ở mục 2.1.

### 4.3 Nhóm reconcile

- **Manifest trung tâm** trong `~/.hybrid-hands/config.json` (danh sách marketplace, plugin@version, skills, MCP user) + lệnh reconcile lặp `CLAUDE_CONFIG_DIR=<dir> claude plugin marketplace add/install/update` cho từng account. Dùng CLI chính thức nên không phá định dạng sổ; idempotent.
- **Lệnh reconcile một chiều** cho phần không có CLI (statusLine, hooks, keybindings): dry-run mặc định, chỉ ghi khoá do plugin sở hữu (ownership floor, học cc-switch `live/floor.rs`, xem [note](cc-switch.md)), backup lần ghi đầu. Lưu ý: luật repo hiện cấm sửa thủ công settings/sổ cài đặt → cần người dùng chốt trước.
- **Codex:** skills ở một thư mục chung symlink vào mỗi `CODEX_HOME`; profiles trong `config.toml` thay cho nhiều thư mục khi chỉ khác model (không thay được tách login). Chưa xác minh từ nguồn chính thức.

### 4.4 Không bao giờ chia sẻ

Credential (Keychain, `.credentials.json`, `auth.json`), `projects/` và `sessions/` (transcript), `.claude.json` (state đăng nhập, onboarding, MCP user kèm có thể có secret), statsig/telemetry, cache rate-limit theo tài khoản.

## 5. So sánh A và B

| Tiêu chí | A — thư mục chung | B — tách thư mục |
|---|---|---|
| Cô lập | Không; transcript/usage trộn | Có |
| Chạy song song nhiều tài khoản | Không | Có |
| Rủi ro mất login | Cao (ghi đè credential mỗi lần đổi) | Thấp (không ghi credential) |
| Đồng bộ plugin/skill/config | Tự nhiên | Phải reconcile/symlink |
| Quota/usage theo account | Khó tách | Tách tự nhiên (hybrid-hands dựa vào đây) |
| Độ phức tạp | Thấp ở cấu hình, cao ở thao tác switch | Cao ở đồng bộ, thấp ở vận hành |

## 6. Khuyến nghị (suy luận)

Giữ B + overlay tài sản tĩnh. Không symlink plugins/ hay installed_plugins.json; không chia sẻ transcript/state. Đề xuất `hand-ext accounts sync` dry-run mặc định, CLI chính thức cho plugin, reconcile settings có ownership floor + backup; chỉ triển khai sau khi người dùng chốt L2. Chi tiết và ngoại lệ ở [report](../report.md).
