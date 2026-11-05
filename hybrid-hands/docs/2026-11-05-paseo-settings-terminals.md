# Paseo 0.15.0 — Settings → Terminals, terminal hooks, terminal profiles và toàn bộ nhóm Settings

## Tóm tắt

- **Nguồn và phạm vi:** báo cáo của hand ngoài dsh ngày 05/11/2026, chỉ đọc mã đã build của Paseo 0.15.0; chưa kiểm bằng chạy thật. `<npm-global>` là thư mục npm toàn cục của Node 24 trên máy chạy daemon.
- **Bổ sung của brain (05/11/2026):** screen của phiên phụ tên `side-<tên>` (screen canh token `side-<tên>-watch`), không phải `side-session`, nên profile `screen -x side-session` ở mục 3.5 không gắn được. Dùng profile `command` = `<plugin>/bin/side-session`, `args` = `["attach"]` (hybrid-hands 0.13.0): lệnh liệt kê phiên phụ đang chạy, gắn bằng `screen -x <pid.tên>` và quay lại menu sau khi detach (Ctrl-a d). Xem skill `paseo`.
- Đã đọc mã đã build của `@getpaseo/*` 0.15.0; không chạy `paseo`/`claude`/`dsh`/`opencode`/`screen`, không đọc `~/.paseo`, không mở mạng.
- Nhóm **Settings → host → Terminals** chỉ có đúng 2 tính năng: **Enable terminal agent hooks** (một switch) và **Terminal profiles** (danh sách profile).
- `Enable terminal agent hooks` là `daemon.enableTerminalAgentHooks`, boolean, mặc định `false`, lưu trong `~/.paseo/config.json`. Bật lên thì Paseo sửa **ba file cấu hình toàn cục**: `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.config/opencode/plugins/paseo-terminal-activity.js`.
- Hook không ghi prompt/nội dung hội thoại; nó chỉ POST `{terminalId, token, state}` vào `http://127.0.0.1:<port>/api/terminal-activity` để báo terminal đang `working` / `idle` / `attention`. Tác dụng thật là chấm trạng thái và thông báo "Terminal needs input" / "Terminal finished", không phải tạo agent hay đọc transcript.
- `Terminal profiles` là `daemon.terminalProfiles`, mảng `{id,name,command,args?,icon?}`, mặc định rỗng trong config và client tự dùng 4 profile built-in (Claude Code, Codex, OpenCode, Pi). Chọn profile nào thì Paseo spawn đúng `command` + `args` bằng PTY, không qua shell.
- **Phiên Claude Code chạy ngoài Paseo (terminal thường, `screen`) KHÔNG hiện được qua terminal hooks**: hook chỉ hoạt động khi tiến trình thừa hưởng `PASEO_TERMINAL_ID` + token do terminal của Paseo sinh ra. Attach `screen` vào một terminal Paseo chỉ cho xem/điều khiển PTY, không làm hook của tiến trình Claude đang chạy nhận được env đó.
- Toàn app có **14 nhóm Settings phía app** và **12 nhóm Settings phía host**; danh sách đầy đủ ở mục 5.
- Khuyến nghị ngắn: để `enableTerminalAgentHooks = false` cho đến khi thực sự chạy agent trong terminal Paseo; thêm một profile `screen -x` để xem/điều khiển phiên `screen` từ desktop/điện thoại; giữ `terminalScrollbackLines = 10000`.

## 0. Phạm vi, phiên bản, quy ước bằng chứng

- Phiên bản: `@getpaseo/server` 0.15.0 (`P/server/package.json:3`).
- `P` = `<npm-global>/lib/node_modules/@getpaseo/cli/node_modules/@getpaseo`.
- `S` = `P/server/dist/server/server` (mã daemon).
- `T` = `P/server/dist/server/terminal` (terminal, agent hooks).
- `C` = `<npm-global>/lib/node_modules/@getpaseo/cli` (CLI `paseo`).
- `PR` = `P/protocol/dist`.
- `W` = `P/server/dist/server/web-ui/_expo/static/js/web/index-c26368bf062ddf91b40b9d95aae94799.js` (bundle web/desktop; số sau `W:` là số dòng, bundle có 18.983 dòng, mỗi module thường nằm trên một dòng).
- Mọi khẳng định hành vi đều có `file:dòng` hoặc chuỗi/testID grep được trong `W`. Phần suy luận từ kiến trúc được ghi **(suy luận)**.
- Chỉ đọc mã; không xác nhận cấu hình thực tế trên máy vì `~/.paseo` nằm ngoài phạm vi được phép đọc. Không có runtime test vì brief cấm chạy các CLI liên quan.

## 1. Bản đồ thật của Settings → host → Terminals

`W:18983` (đoạn `HostTerminalsPage`) render đúng thứ tự:

```text
SettingsSection(title = "Terminal agents")
  └─ card "Enable terminal agent hooks"   [switch]
SettingsSection(title = "Terminal profiles")
  └─ danh sách profile + nút Add
```

Không có tuỳ chọn nào khác trong nhóm Terminals. Bằng chứng:

- `W:18983`: `HostTerminalsPage` trả về `SettingsSection title "Terminal agents"` chứa `He` (card hooks), rồi `Ue` (phần terminal profiles).
- `W:18983`: card hooks có `testID:"host-page-terminal-agent-hooks-card"`, switch `testID:"host-page-terminal-agent-hooks-switch"`, label đúng chuỗi `"Enable terminal agent hooks"`.
- `W:18983`: phần profile có `testID:"terminal-profiles-section"`, `testID:"terminal-profiles-card"`, nút `testID:"terminal-profiles-add-button"`.
- `W:18957`: nav host có `{id:"terminals", labelKey:"settings.hostSections.terminals"}`; i18n `W:16485` dịch thành `"Terminals"`.

Phân biệt quan trọng: **Settings → app → Terminal** (số ít) là một nhóm khác, chỉ có `Terminal scrollback`. Nhóm **Terminals** (số nhiều) nằm dưới host và là nhóm đang được hỏi.

## 2. Enable terminal agent hooks

### 2.1 Tên trong Settings và khoá cấu hình

- Tên UI: **Settings → host → Terminals → Terminal agents → Enable terminal agent hooks**.
- Khoá: `daemon.enableTerminalAgentHooks`.
- Kiểu: boolean.
- Mặc định: `false` (`S/config.js:429`: `persisted.daemon?.enableTerminalAgentHooks ?? false`; bootstrap cũng dùng `?? false` ở `S/bootstrap.js:327`).
- Nơi lưu: **config của daemon**, file `~/.paseo/config.json` (tên file `config.json` ở `S/persisted-config.js:317`; ghép với `paseoHome` ở `:333-334`; schema `:231`). Không phải cài đặt app phía client.
- UI đọc/ghi qua `useDaemonConfig` và `patchConfig({enableTerminalAgentHooks:e})` (`W:18983`). Đổi là có hiệu lực ngay, không có nút Save riêng.
- Đường patch đi qua `set_daemon_config_request` (`S/session.js:2041-2050`), cần quyền `daemon.manage` (`S/authorization/operation-permissions.js:177`).
- Store coi đây là trường reloadable và map sang config runtime (`S/daemon-config-store.js:91-93`, `:118-120`, `:192-194`, `:541-547`).

### 2.2 Cài hook: file nào bị sửa, nội dung gì

Cơ chế cài đặt:

- `T/agent-hooks/terminal-agent-hook-setting.js:7-24`: lúc daemon boot, nếu `enableTerminalAgentHooks` đang `true` thì gọi `installRegisteredAgentHooks`; đồng thời đăng ký listener: khi field đổi thành `true` thì cài, khi đổi thành `false` thì gỡ.
- `T/agent-hooks/provider-registry.js:10-29`: cài cho **3 provider**: `claude`, `codex`, `opencode`; mỗi provider lỗi thì chỉ log warning, các provider còn lại vẫn chạy.
- `T/agent-hooks/agent-hook-installer.js:5-17`: có 2 kiểu cài: `config-file` (Claude, Codex) và `plugin-file` (OpenCode).

Ba file bị sửa:

1. **Claude Code**: `~/.claude/settings.json`, hoặc `$CLAUDE_CONFIG_DIR/settings.json` nếu biến môi trường này được đặt.
   - `T/agent-hooks/claude/claude.js:17-24`: `configDir: ".claude"`, `configFile: "settings.json"`, `configDirEnvOverride: "CLAUDE_CONFIG_DIR"`.
   - **Có đụng `~/.claude/settings.json`** — đây là câu trả lời trực tiếp. Không đụng `~/.claude.json`, không đụng `CLAUDE.md`, không đụng `settings.local.json`.

2. **Codex**: `~/.codex/hooks.json`, hoặc `$CODEX_HOME/hooks.json`.
   - `T/agent-hooks/codex/codex.js:18-25`: `configDir: ".codex"`, `configFile: "hooks.json"`, `configDirEnvOverride: "CODEX_HOME"`.
   - Paseo 0.15.0 **không sửa `~/.codex/config.toml`** theo code này.

3. **OpenCode**: `~/.config/opencode/plugins/paseo-terminal-activity.js`, hoặc `$XDG_CONFIG_HOME/opencode/plugins/...`, hoặc `$OPENCODE_CONFIG_DIR/plugins/...`.
   - `T/agent-hooks/opencode/opencode-plugin.js:70-80`: `configDirBase: "xdg-config"`, `configDir: "opencode"`, `configFile: "plugins/paseo-terminal-activity.js"`, `configDirEnvOverride: "OPENCODE_CONFIG_DIR"`.
   - Đây là một file plugin JS sinh sẵn, không phải file JSON config.

Cách ghi file:

- `T/agent-hooks/agent-hook-installer.js:69-84`: đọc file hiện tại, parse, biến đổi, stringify, so sánh; nếu khác mới ghi.
- `S/private-files.js:24-37`: ghi atomic qua file tạm rồi rename; `ensurePrivateDirectory` tạo thư mục và `chmod 700`, `ensurePrivateFile` `chmod 600` (`S/private-files.js:13-22`). Vì vậy bật hook có thể tạo `~/.claude`/`~/.codex` nếu chưa có và đổi mode file cấu hình.
- Nếu file JSON hiện tại parse lỗi, provider đó ném lỗi; `provider-registry` bắt và log, không làm sập daemon, nhưng hook của provider đó không được cài.

Nội dung hook được thêm:

- Claude: `T/agent-hooks/claude/claude-settings.js:16-55`. Với mỗi event, Paseo:
  - gỡ các entry có `command` chứa marker `"hooks claude"` (chỉ các hook do Paseo cài, theo marker),
  - giữ các entry/hook khác của người dùng,
  - thêm một entry `{ matcher: "", hooks: [{ type: "command", command: <lệnh>, timeout: 10 }] }`.
- Codex: `T/agent-hooks/codex/codex-settings.js:16-56`, tương tự nhưng thêm cả `commandWindows` và marker `"hooks codex"`.
- Lệnh hook (POSIX):
  ```sh
  if [ -n "$PASEO_TERMINAL_ID" ]; then "${PASEO_HOOK_CLI:-paseo}" hooks <provider> <event>; fi
  ```
  (`T/agent-hooks/agent-hook-installer.js:43-46`; bản Windows ở `:47-50`).
- Timeout hook là 10 giây (`claude-settings.js:24-30`, `codex-settings.js:29-31`).

Điểm rất quan trọng: **hook được cài toàn cục**, không phải chỉ cho terminal Paseo. Việc chỉ chạy trong terminal Paseo được quyết định ở runtime bằng biến `PASEO_TERMINAL_ID`; ngoài Paseo lệnh hook vẫn được Claude/Codex gọi nhưng thoát ngay vì điều kiện `if` không thoả.

### 2.3 Hook chạy gì, "ghi" gì

Luồng đầy đủ:

1. Claude/Codex/OpenCode gọi hook command khi có event.
2. Lệnh gọi `paseo hooks <provider> <event>`.
3. CLI `paseo` đọc 3 biến môi trường:
   - `PASEO_TERMINAL_ID`
   - `PASEO_ACTIVITY_TOKEN`
   - `PASEO_TERMINAL_ACTIVITY_URL`
   (`C/dist/commands/hooks.js:30-36`).
4. CLI map event sang state `running` / `idle` / `needs-input` (`C/dist/commands/hooks.js:10-28`; registry `T/agent-hooks/provider-registry.js:30-35`).
5. CLI POST JSON `{ terminalId, token, state }` tới URL activity, timeout 500 ms, lỗi thì bỏ qua (`C/dist/commands/hooks.js:67-88`).
6. Server nhận ở `POST /api/terminal-activity` (`S/bootstrap.js:530`):
   - chỉ chấp nhận request từ loopback (`S/bootstrap.js:211-216`),
   - validate schema `terminalId`, `token`, `state` (`:197-201`, `:217-221`),
   - validate token theo từng terminal (`:222-226`; `T/terminal-manager.js:234-239`),
   - map `running → working`, `idle → idle`, `needs-input → attention` (`S/bootstrap.js:202-206`),
   - gọi `terminalManager.setTerminalActivity` (`:227-233`).

**Hook không ghi prompt, không ghi output, không ghi transcript, không tạo file log.** Nó chỉ gửi trạng thái. Với Claude event `Notification`, CLI có đọc stdin tối đa 100 ms để kiểm tra `notification_type === "idle_prompt"`; không lưu nội dung (`C/dist/commands/hooks.js:38-50`; `T/agent-hooks/claude/claude.js:25-45`). Các event khác không đọc stdin.

Mapping event:

| Provider | Event | State gửi |
|---|---|---|
| Claude | `UserPromptSubmit` | `running` |
| Claude | `Stop`, `StopFailure`, `SessionEnd` | `idle` |
| Claude | `Notification` | `needs-input` chỉ khi `notification_type === "idle_prompt"`, còn lại bỏ qua |
| Codex | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `running` |
| Codex | `PermissionRequest` | `needs-input` |
| Codex | `Stop` | `idle` |
| OpenCode | `session.status.busy`, `session.status.retry` | `running` |
| OpenCode | `session.status.idle` | `idle` |
| OpenCode | `permission.asked` | `needs-input` |
| OpenCode | `permission.replied` | `running` |

Nguồn: `T/agent-hooks/claude/claude.js:2-31`, `T/agent-hooks/codex/codex.js:2-28`, `T/agent-hooks/opencode/opencode.js:2-22`; plugin OpenCode map thêm event v2 `session.execution.started/succeeded/failed/interrupted` (`T/agent-hooks/opencode/opencode-plugin.js:4-18`).

Env được lấy từ đâu:

- `T/terminal-manager.js:186-202`: mỗi terminal Paseo sinh một `terminalId` và token ngẫu nhiên 32 byte (`createActivityToken`, `:7-9`), đưa vào env `PASEO_TERMINAL_ID`, `PASEO_ACTIVITY_TOKEN`, `PASEO_TERMINAL_ACTIVITY_URL`.
- `T/terminal.js:531-539`: env này được truyền vào PTY khi spawn.
- URL activity chỉ được tạo khi daemon listen kiểu TCP (`S/bootstrap.js:190-196`). Với unix socket, không có `PASEO_TERMINAL_ACTIVITY_URL`; hook sẽ no-op. Máy hiện tại dùng `127.0.0.1:6767` nên có URL.
- `PASEO_HOOK_CLI` được set cho terminal Paseo trỏ tới CLI `paseo` (`T/terminal.js:262-287`), nên trong terminal Paseo không phụ thuộc PATH.

Tác dụng người dùng thấy:

- Terminal activity tracker nhận state; khi state đổi, WebSocket broadcast `terminal attention` (`S/websocket-server.js:455-473`).
- Tiêu đề thông báo: `"Terminal needs input"` hoặc `"Terminal finished"` (`S/websocket-server.js:52-54`).
- Terminal có chấm trạng thái/rollup; `attention` được coi là cần input (`S/bootstrap.js:202-206`, `S/websocket-server.js:41-50`).
- Không có timeline hội thoại, không có prompt, không có khả năng gửi message kiểu agent; muốn tương tác thì phải gõ vào terminal.

### 2.4 Điều kiện, giới hạn, rủi ro

**Điều kiện để có tác dụng:**

- Tiến trình agent phải chạy trong một terminal do Paseo tạo (hoặc tiến trình con thừa hưởng env của terminal đó).
- Daemon Paseo phải đang chạy và URL activity phải còn đúng.
- Token phải còn hiệu lực; token nằm trong bộ nhớ terminal manager, không được ghi ra đĩa.
- Với OpenCode, plugin phải được OpenCode nạp; với Codex, Codex phải đọc `hooks.json`.

**Giới hạn:**

- Một terminal chỉ có một state. Nếu chạy nhiều agent trong cùng terminal, event của agent này ghi đè agent kia; không có trạng thái theo từng agent.
- Hook chỉ biết `terminalId`, không biết session id của Claude/Codex. Vì vậy Paseo không thể gắn status này với một agent/timeline cụ thể.
- Không theo dõi được tiến trình ngoài Paseo (xem mục 4).
- Không có hook event cho "prompt trả lời xong" theo kiểu agent; chỉ có các event CLI cung cấp.

**Rủi ro:**

- **Sửa cấu hình toàn cục**: bật một lần là mọi phiên Claude Code trên máy (kể cả ngoài Paseo) sẽ chạy thêm lệnh hook; ngoài Paseo lệnh no-op nhưng vẫn spawn process.
- **Stale hooks**: nếu bật rồi gỡ Paseo/daemon mà không tắt switch, hook vẫn nằm trong `~/.claude/settings.json`/`~/.codex/hooks.json`/plugin OpenCode. Lần sau chạy Claude/Codex, hook gọi `paseo` và có thể lỗi nếu binary không còn.
- **Tắt bằng config không dọn**: `T/agent-hooks/terminal-agent-hook-setting.js:2-6` nói rõ lúc boot chỉ cài khi bật, còn khi tắt thì "leave the configs untouched"; việc gỡ chỉ xảy ra khi field đổi true → false qua listener. Nếu sửa `config.json` thành `false` lúc daemon đang tắt, hook cũ vẫn còn.
- **Ghi đè/định dạng lại file**: Paseo parse rồi stringify lại toàn bộ `settings.json`/`hooks.json` với JSON 2 space; các key khác được giữ, nhưng comment/định dạng gốc không được giữ (JSON thuần không có comment; nếu file có JSONC thì parse lỗi và không cài). Nó cũng `chmod 600` file và `chmod 700` thư mục.
- **Marker hơi rộng**: khi gỡ, Paseo xoá mọi hook có `command` chứa `"hooks claude"` / `"hooks codex"`. Nếu người dùng tự viết hook có chuỗi đó, hook của họ cũng bị xoá.
- **Nhiều daemon Paseo**: hai daemon khác home cùng bật sẽ cùng sửa một bộ file global; tắt ở daemon này sẽ gỡ hook của daemon kia. Không có namespace theo home.
- **Hook timeout 10 giây**: nếu `paseo` bị treo, Claude/Codex có thể bị chặn tới 10 giây mỗi event. Bình thường CLI POST timeout 500 ms nên rất nhanh.
- **Bảo mật token**: token chỉ chống process ngoài terminal không biết token; mọi process trong terminal đều đọc được env và có thể POST state giả. Endpoint chỉ loopback nên không mở ra mạng.
- **Không tốn token model**: hook không gọi LLM/API; chỉ spawn process + HTTP local. "Tốn token" không phải rủi ro ở đây, nhưng có overhead process/HTTP.
- **Codex/OpenCode phụ thuộc phiên bản**: Paseo ghi `~/.codex/hooks.json` và plugin OpenCode theo đường dẫn trên; việc CLI tương ứng có đọc đúng file hay không cần kiểm tra với bản đang dùng (câu hỏi mở).

### 2.5 Có ích gì cho workflow hiện tại và đề xuất

Với workflow đang mô tả:

- Brain Claude Code chạy terminal thường **ngoài** Paseo → không thấy.
- `hand-ext` chạy ngoài → không thấy.
- Side session `screen` mở ngoài → không thấy.
- `hh-ps` là công cụ ngoài, không liên quan hook.

Vì vậy bật `enableTerminalAgentHooks = true` **không mang lại visibility cho các phiên hiện có**. Nó chỉ có ích khi bắt đầu mở terminal mới trong Paseo và chạy Claude/Codex/OpenCode ở đó.

Đề xuất:

- Giữ `daemon.enableTerminalAgentHooks = false` ở trạng thái hiện tại.
- Chỉ bật `true` khi đã quyết định chuyển ít nhất một phiên sang terminal Paseo; khi bật nên backup `~/.claude/settings.json`, `~/.codex/hooks.json` và kiểm tra `~/.config/opencode/plugins/`.
- Nếu chỉ muốn thử: bật, mở terminal Paseo, chạy `claude`, xem chấm trạng thái/thông báo; sau đó tắt switch để Paseo gỡ hook (đừng chỉ sửa config lúc daemon dừng).
- Nếu không dùng Paseo terminal cho agent, để `false` để tránh sửa file global và tránh stale hook.

## 3. Terminal profiles

### 3.1 Tên trong Settings và khoá cấu hình

- Tên UI: **Settings → host → Terminals → Terminal profiles**.
- Khoá: `daemon.terminalProfiles`.
- Kiểu: mảng object `{ id: string, name: string, command: string, args?: string[], icon?: string }`; schema cho phép key lạ (`passthrough`) (`PR/terminal-profile.js:3-12`).
- Mặc định: **không có key trong config** (undefined). Client resolve undefined thành 4 profile built-in (`PR/terminal-profiles.js:16-27`, `:270-275`).
- Nơi lưu: **config của daemon**, `~/.paseo/config.json` (`S/persisted-config.js:233`; `S/config.js:342`). Không phải app settings phía client.
- UI đọc `config.terminalProfiles` và ghi cả mảng qua `patchConfig({ terminalProfiles: e })` (`W:18983`). Chỉ hiện khi host connected; nếu mất kết nối, section hiện "Connect to this host to manage terminal profiles".
- Thao tác: Add / Edit / Remove / Move up / Move down; mỗi lần lưu là patch cả mảng.

Giá trị mặc định (khi config undefined):

| id | name | command | args |
|---|---|---|---|
| `claude` | Claude Code | `claude` | `["{{{prompt}}}"]` |
| `codex` | Codex | `codex` | `["{{{prompt}}}"]` |
| `opencode` | OpenCode | `opencode` | `["--prompt={{{prompt}}}"]` |
| `pi` | Pi | `pi` | `["{{{prompt}}}"]` |

Nguồn: `PR/terminal-profiles.js:16-27`.

### 3.2 Khai báo trong UI

Modal `TerminalProfileEditModal` (`W:18983`) có đúng 3 field:

- **Name** (bắt buộc)
- **Command** (bắt buộc)
- **Arguments** (không bắt buộc), hint: `"Space-separated arguments passed to the command"`, placeholder `--dangerously-skip-permissions`.

Cách xử lý:

- `args` trong UI là một chuỗi; khi lưu, UI tách theo khoảng trắng: `e.trim().split(/\s+/).filter(Boolean)` (`W:18983`, hàm `Be` trong đoạn profile editor).
- `id` mới được sinh dạng `profile_<timestamp>_<random>`; id cũ giữ nguyên khi edit.
- `icon` không có field trong modal; icon được đoán từ tên command (`getTerminalProfileIcon`, `PR/terminal-profiles.js:91-96`). Config JSON có thể tự đặt `icon`.
- Vì UI join `args` bằng dấu cách khi mở edit rồi split lại khi lưu, **một argument chứa dấu cách sẽ bị tách thành nhiều argument** nếu đi qua UI. Muốn một arg có space, phải viết wrapper script hoặc sửa JSON trực tiếp; UI không giữ ranh giới.
- Cũng vì split theo whitespace, không thể biểu diễn argument rỗng hoặc argument chứa tab/xuống dòng qua UI.

### 3.3 Chạy lệnh gì, ở đâu

Luồng launch:

1. **New workspace → chọn terminal profile**: `W:18860` (`runCreateTerminalWorkspace`).
   - Nếu profile có `{{{prompt}}}` trong command/args (`profileTakesPrompt`), prompt người dùng được thay vào sentinel và truyền làm argv.
   - Nếu profile không có sentinel, Paseo tạo workspace với prompt rỗng, launch command trần; không gửi prompt vào terminal (vì ô nhập đang hiển thị command preview, không phải prompt).
   - Nếu không chọn profile, Paseo tạo shell terminal bình thường và gõ prompt/command vào shell kèm `\r`.
2. **Workspace terminal menu**: menu liệt kê các profile (`W:18321`, `terminal-profile:<id>`), chọn profile thì gọi `resolveTerminalProfileLaunch(profile, "")` và tạo terminal với `command` + `args` đã bỏ sentinel.
3. **Pinned targets / launch target**: cùng helper `resolveTerminalProfileLaunch`; comment trong `PR/terminal-profiles.js:67-75` nói mọi launcher phải đi qua đây để không forward sentinel.

Substitution:

- `PROMPT_SENTINEL = "{{{prompt}}}"` (`PR/terminal-profiles.js:10`).
- `profileTakesPrompt` kiểm tra command hoặc bất kỳ arg nào chứa sentinel (`:31-34`).
- `substitutePrompt` thay mọi sentinel bằng prompt; nếu prompt rỗng thì bỏ các arg "prompt-only" (`{{{prompt}}}` hoặc `--flag={{{prompt}}}`) (`:49-62`).
- `resolveTerminalProfileLaunch` trả `{name, command, args}` (`:73-75`).

Phía server:

- Client gửi `create_terminal_request` với `cwd`, `command`, `args` (`PR/messages.js:2549-2568`).
- `terminalManager.createTerminal` nhận `command`/`args`, tạo terminal id và activity token (`T/terminal-manager.js:186-229`).
- `terminal.js` resolve executable và spawn bằng `pty.spawn` (`T/terminal.js:493-547`). Trên POSIX, `node-pty` spawn trực tiếp qua `execve`, **không qua shell** (`T/terminal.js:463-470`).
- Command được resolve theo PATH của env terminal; nếu command chứa `/` thì resolve theo `cwd` của workspace (`T/terminal.js:471-491`).
- Nếu command không tồn tại/không executable, `assertTerminalCommandCanStart` ném lỗi trước khi spawn (`T/terminal.js:471-492`), create terminal thất bại thay vì mở terminal chết ngay.
- Terminal chạy với `cwd` = workspace hiện tại, env của daemon + env terminal + `PASEO_*`; không có cơ chế set env riêng cho từng profile.

Ví dụ cấu hình JSON (khi sửa trực tiếp `~/.paseo/config.json`):

```json
{
  "daemon": {
    "terminalProfiles": [
      { "id": "claude", "name": "Claude Code", "command": "claude", "args": ["{{{prompt}}}"] },
      { "id": "screen-side", "name": "Screen: side-session", "command": "/usr/bin/screen", "args": ["-x", "side-session"] }
    ]
  }
}
```

Lưu ý: nếu chỉ muốn thêm một profile, phải giữ cả các profile cũ trong mảng; UI luôn patch cả mảng. Nếu để mảng rỗng, menu không còn profile nào (vẫn có "New terminal" shell).

### 3.4 Điều kiện, giới hạn, rủi ro

**Điều kiện:**

- Host phải connected; profile là cấu hình của daemon/host, không phải của từng workspace hay từng client.
- Command phải tồn tại trên host chạy daemon, theo PATH của daemon hoặc đường dẫn tuyệt đối.
- Với profile có prompt sentinel, prompt chỉ được truyền nếu launch từ New Workspace; launch từ menu terminal dùng prompt rỗng (bỏ arg prompt-only).

**Giới hạn:**

- Không có `env`, `cwd`, `shell`, `timeout` riêng cho profile; chỉ `id/name/command/args/icon`.
- Không chạy qua shell: không có `|`, `>`, `&&`, `$VAR`, `~`, glob. Muốn dùng shell phải đặt command là `/bin/zsh` (hoặc `bash`) và args `["-lc", "..."]`; nhưng UI split space sẽ phá chuỗi này, nên thực tế cần wrapper script.
- UI args split theo whitespace, không hỗ trợ quote; argument có space bị tách.
- Profile command chạy dưới user của daemon, không phải user của client.
- Không có validation command trước khi lưu; chỉ fail khi chọn launch.
- Existing profiles pointing at `claude`/`codex`/`opencode`/`pi` không có sentinel sẽ được "adopt" sentinel ở read-time nếu không có positional arg (`PR/terminal-profiles.js:215-275`). Đây là tương thích ngầm, có thể làm thay đổi cách launch profile cũ.

**Rủi ro:**

- **Thực thi lệnh tuỳ ý trên host**: profile là bề mặt chạy lệnh. Ai có quyền `daemon.manage` (qua UI/API) có thể thêm profile và chọn launch; nếu thiết bị đã pair được cấp quyền này, điện thoại cũng làm được. Cần kiểm tra quyền của thiết bị pair.
- **Lưu nhầm vào config global**: profile áp dụng cho mọi workspace trên host, không chỉ workspace hiện tại.
- **Tên/profile giả mạo**: người dùng có thể đặt tên "Claude Code" nhưng command là lệnh khác; UI không kiểm tra. Đây là tính năng (custom command) nhưng cũng là risk nếu config bị sửa.
- **Không có sandbox**: command chạy với quyền daemon; không có giới hạn tool/permission như agent Paseo.
- **Args split**: profile cấu hình đúng trong JSON nhưng mở UI edit rồi Save có thể làm hỏng argument có space.

### 3.5 Có ích gì cho workflow hiện tại và đề xuất

Hữu ích:

- Chuẩn hoá cách mở terminal cho các CLI hay dùng (Claude, Codex, OpenCode, Pi) mà không phải gõ lệnh.
- Có thể thêm profile để **attach `screen`** đang chạy ngoài Paseo: mở terminal Paseo chạy `/usr/bin/screen -x side-session`, từ desktop/điện thoại xem và điều khiển phiên `screen`. Đây là cách thực dụng để "thấy" phiên ngoài, nhưng chỉ là terminal PTY, không phải agent status.
- Có thể thêm profile cho các script nội bộ (hand-ext, hh-ps) nếu chúng là executable; nhưng không nên đưa command phức tạp có pipe/space vào UI.

Đề xuất:

- Giữ 4 profile mặc định; có thể xoá `Pi` nếu không dùng để menu gọn.
- Thêm một profile:
  ```json
  {
    "id": "screen-side",
    "name": "Screen: side-session",
    "command": "/usr/bin/screen",
    "args": ["-x", "side-session"]
  }
  ```
  Dùng `-x` thay vì `-r` nếu phiên đang được attach ở nơi khác (multi-display); `-r` sẽ từ chối nếu đã có người attach. Cả hai đều chỉ hoạt động nếu tên screen session đúng là `side-session`.
- Không đặt `enableTerminalAgentHooks = true` chỉ vì thêm profile screen: tiến trình Claude trong screen đã chạy trước đó, không thừa hưởng `PASEO_TERMINAL_ID`, nên hook vẫn không báo trạng thái.
- Nếu muốn status/notification thật cho một phiên, phải **khởi động lại phiên đó bên trong terminal Paseo** (hoặc mở terminal Paseo rồi chạy `claude`/`codex` tại đó), rồi bật hooks.

## 4. Phiên Claude Code chạy ngoài Paseo có hiện được không?

### 4.1 Qua terminal hooks: Không

Lý do trực tiếp:

- Hook command chỉ chạy khi `PASEO_TERMINAL_ID` có giá trị (`T/agent-hooks/agent-hook-installer.js:43-46`).
- `PASEO_TERMINAL_ID`, `PASEO_ACTIVITY_TOKEN`, `PASEO_TERMINAL_ACTIVITY_URL` chỉ được terminal manager của Paseo sinh ra khi tạo terminal (`T/terminal-manager.js:186-202`) và truyền vào PTY (`T/terminal.js:531-539`).
- Endpoint activity chỉ nhận request loopback và phải đúng token của terminal id (`S/bootstrap.js:211-226`); token nằm trong bộ nhớ terminal manager, không có cách "đăng ký" một tiến trình ngoài.
- Paseo không quét tiến trình để tìm Claude/Codex. `getTerminals` chỉ duyệt `terminalsByCwd` trong bộ nhớ (`T/terminal-manager.js:167-185`); không có code đọc `ps`, `/proc`, `screen -ls` hay tương tự.

Vì vậy, phiên Claude Code trong Terminal.app/iTerm (không mở qua Paseo), dù có cài hook toàn cục, sẽ chạy lệnh hook nhưng điều kiện `if` fail và không gửi gì. Paseo không thấy terminal, không thấy agent, không thấy status.

### 4.2 Với `screen`: Không, trừ khi screen được start từ terminal Paseo

- Nếu screen server được start **bên trong** một terminal Paseo, tiến trình con Claude thừa hưởng `PASEO_TERMINAL_ID` + token; khi đó hook có thể báo status cho terminal Paseo đó, kể cả sau khi detach (miễn terminal Paseo còn và token còn).
- Nếu screen server đã start **ngoài** Paseo rồi mới `screen -r`/`screen -x` từ terminal Paseo, tiến trình Claude đã có env từ lúc start, **không** nhận thêm `PASEO_TERMINAL_ID`. Attach chỉ nối PTY, không thay đổi env của process đang chạy.
- Vì vậy case của người dùng (side-session trong `screen`, start ngoài) sẽ **không** hiện qua hooks.

### 4.3 Các cách khác (không phải hooks)

1. **Attach `screen` qua terminal Paseo** (khả thi nhất để xem/điều khiển):
   - Thêm profile `/usr/bin/screen -x side-session`, hoặc mở terminal Paseo và gõ lệnh.
   - Paseo coi đây là một terminal bình thường; thấy output, gõ được từ desktop/điện thoại.
   - Không có status agent, không có hook, không có timeline; chỉ là PTY.
   - Có thể vướng resize/redraw của screen trên mobile; cần thử.

2. **Import session**:
   - UI có **Import session** ở New Workspace và workspace menu (`W` chuỗi `importSession.title`, `new-workspace-import-session`; mô tả `"Open a Claude Code, Codex or other session you started in a terminal"`).
   - Với Claude, Paseo đọc transcript trong `~/.claude/projects` (`S/agent/providers/claude/agent.js:1242-1250`) rồi resume session đó thành agent Paseo (`S/agent/provider-session-import.js:15`, `S/agent/import-sessions.js:136-147`).
   - Đây **không phải attach tiến trình đang chạy**; nó đọc lịch sử và mở một agent Paseo dùng cùng provider session id. Nếu phiên gốc vẫn đang chạy, có thể có hai tiến trình cùng resume một session; **(suy luận)** nên dừng phiên gốc trước khi import, hoặc chỉ import khi chắc chắn không ghi đè.
   - Import session có thể giúp xem lại/tiếp tục hội thoại, nhưng không mirror live session đang chạy.

3. **Khởi động lại agent trong terminal Paseo**:
   - Mở terminal Paseo mới, chạy `claude`/`codex` tại đó; bật hooks nếu muốn status.
   - Đây là cách duy nhất để có cả terminal visibility lẫn hook status.

4. **Plugin tự viết**:
   - `hh-tree`/plugin Paseo có thể tự đọc dữ liệu bên ngoài và hiển thị, nhưng đó là code plugin, không phải tính năng terminal hooks. Theo ngữ cảnh, plugin này đang tắt vì `pluginsEnabled=false`; nó không nằm trong nhóm Terminals.
   - Không có built-in bridge nào khác trong 0.15.0 mà mình thấy.

5. **CLI `paseo`**:
   - `paseo run` tạo agent Paseo mới; không attach vào process Claude đang chạy.
   - `paseo hooks` chỉ ghi activity khi có env của terminal Paseo; không phải API đăng ký tiến trình ngoài.

**Kết luận mục 4:** Không có cách chính thức nào để Paseo "thấy" một tiến trình Claude Code đang chạy ngoài Paseo như một agent live. Tối đa là attach PTY qua `screen` trong terminal Paseo (xem/điều khiển), hoặc import transcript thành agent mới (không live).

## 5. Danh sách đầy đủ các nhóm Settings còn lại

Nguồn bản đồ nav: `W:18957` (mảng `Ve` cho app, `Ae` cho host); nhãn lấy từ i18n `W:16485`.

### 5.1 Nhóm phía app (App)

App có 14 nhóm: General, Appearance, Sidebar, Chat, Terminal, Browser, Editor, Files, Shortcuts, Integrations, Notifications, Permissions, Diagnostics, About.

#### General

- **Language** — System / Arabic / English / Spanish / French / Japanese / Korean / Brazilian Portuguese / Russian / Simplified Chinese. Không có tiếng Việt trong danh sách (`W:16485`).
- **Send shortcut** — Enter hoặc ⌘/Ctrl+Enter (`settings.general.sendShortcut.options`).
- **Default send** — Interrupt / Steer / Queue, kèm mô tả hành vi khi agent đang chạy (`settings.general.defaultSend.options`; `W:16485`).
- **Open location → Clicking a file in the Explorer sidebar** — Main panel / On the side.
- **Open location → Clicking a change in the Explorer sidebar or a chat** — Main panel / On the side.
- **Open location → Clicking a file in an agent chat** — Main panel / On the side.
- **Open location → Clicking a file in a diff** — Main panel / On the side.
- **Open location → Clicking a subagent in an agent chat** — Main panel / On the side.
- **Open location → Clicking a pull request in the Explorer sidebar** — Main panel / On the side / Explorer sidebar.
- **Open location → Clicking a script's service URL** — Ask / In Paseo / External browser.
- (Open location chỉ có trên desktop; component `OpenLocationSection` `W:18957`.)

#### Appearance

- **Theme** — Light / Dark / Zinc / Midnight / Claude / Ghostty / Pure black / System, cộng theme do plugin đóng góp (`settings.appearance.theme.options`).
- **Interface font** — font family cho toàn app; rỗng = system default.
- **Interface size** — cỡ chữ điều hướng/control/label.
- **Content size** — cỡ chữ chat/Markdown.
- **Code font** — font cho code/diff/terminal output; rỗng = system default.
- **Code size** — cỡ chữ code/diff/terminal output.
- **Content width** — max width của chat/Markdown trên màn hình rộng; có Reset.
- **Highlight theme** — theme màu syntax độc lập với theme app, kèm live preview.
- (Nguồn: `settings.appearance.*` trong `W:16485`; component `AppearanceSection` `W:18958`.)

#### Sidebar

- **Header** — bật/tắt và sắp xếp các mục đầu sidebar: New workspace, History, Search, Schedules, và các plugin group.
- **Footer** — bật/tắt và sắp xếp các mục cuối sidebar: Usage, và các plugin group; "Add project" và icon row luôn hiện.
- (Nguồn: `settings.appearance.sidebar.header/footer`; built-in ids `["new-workspace","history","search","schedules"]` và `["usage"]` trong `W` module sidebar nav.)

#### Chat

- **Always expand reasoning** — mặc định mở rộng block suy nghĩ/chain-of-thought.
- **Chat display** — Full / Collapse tool calls / Collapse turns.
- **Chat outline** — hiện outline để nhảy giữa các prompt (ẩn trên native).
- (Nguồn: `settings.general.autoExpandReasoning`, `chatDisplay`, `settings.appearance.chatOutline`; component `ChatSection` `W:18962`. Tiêu đề section dùng lại chuỗi "Detail level".)

#### Terminal

- **Terminal scrollback** — số dòng giữ trong buffer terminal phía client; mặc định `10000`, min `0`, max `1.000.000` (`W:7252122`, `settings.general.terminalScrollback`; component `TerminalSection` `W:18962`).

#### Browser (desktop)

- **Cookies and site data** — nút **Clear browser data**, có confirm; xoá cookie/site data dùng chung giữa các browser tab Paseo (`settings.general.browserData.*`; component `BrowserDataSection`).

#### Editor (web)

- **Vim keybindings** — bật keybinding Vim cho source file trên web/desktop (`settings.editor.vimKeybindings`; component `EditorSection`).

#### Files

- **File panel selector** — với mỗi loại file/selector do plugin đăng ký: chọn panel sẽ mở, hoặc **Ask every time**; có nút **Ask again** để reset (`settings.files.askEveryTime`, `askAgain`, `askAgainFor`; component `FilesSection`). Danh sách row là động, không cố định.

#### Shortcuts (desktop)

- **General** — nhóm phím tắt chung.
- **Projects & Workspaces** — nhóm phím tắt project/workspace.
- **Tabs & Panes** — nhóm phím tắt tab/pane.
- **Layout** — nhóm phím tắt layout.
- **Agent Input** — nhóm phím tắt nhập liệu cho agent.
- Với mỗi action: **Bind / Rebind / Clear / Reset to default**; có **Reset all**; có search và capture chord.
- (Nguồn: `settings.shortcuts.sections.*`, `settings.shortcuts.actions.*`; component `KeyboardShortcutsSection`.)

#### Integrations (desktop)

- **Command line** — nút **Install** để cài CLI `paseo` (trạng thái Installed), kèm link **CLI docs** (`settings.integrations.commandLine`, `actions.install`; component `IntegrationsSection`).

#### Notifications (desktop)

- **Notification permission** — trạng thái + Request/Refresh quyền thông báo OS.
- **Play sound** — phát âm thanh khi có desktop notification.
- **Test notification** — gửi thử; cần quyền trước; có trạng thái sending/sent/failed.
- (Nguồn: `settings.notifications.*`; component `DesktopNotificationsSection`.)

#### Permissions (desktop)

- **Microphone** — trạng thái + Request/Refresh quyền micro (dùng cho dictation/voice).
- **Refresh desktop permissions** — làm mới trạng thái quyền.
- (Nguồn: `settings.permissions.*`; component `DesktopPermissionsSection`.)

#### Diagnostics

- **App diagnostic** — Run/Copy; thu thập connection, daemon, provider, desktop, log details.
- **Test audio** — Play test; báo playing/playback failed.
- (Nguồn: `settings.diagnostics.app.*`, `settings.diagnostics.testAudio`; component `Oe` trong settings page `W:18957`.)

#### About

- **App version** — phiên bản app.
- **Release channel** — Stable / Beta.
- **App updates** — Check / Update / Install; trạng thái ready-to-install, installing.
- **This device** — thông tin thiết bị hiện tại.
- **Connected hosts** — danh sách host, trạng thái Offline/version differs.
- (Nguồn: `settings.about.*`; component `Ee`/`AboutSection`.)

### 5.2 Nhóm phía host (Host)

Host có 12 nhóm: Overview, Projects, Connections, Pair device, Agents, Metadata, Voice, Workspaces, Providers, Usage, Terminals, Plugins.

#### Overview

- **Name** — tên hiển thị của host.
- **Color** — Default / Violet / Sky / Emerald / Orange / Pink / Indigo / Teal / Red / Amber / Blue.
- **Sidebar badge** — Name / Icon only / Hidden.
- **Built-in daemon management** (localhost) — bật/tắt quản lý daemon tích hợp.
- **Keep running after quit** (localhost) — giữ daemon chạy sau khi thoát app.
- **Daemon status / Stop / Logs / CLI status** (localhost) — trạng thái, dừng, xem log, chạy `paseo daemon status`.
- **Rename host** — đổi label host.
- **Restart daemon** — restart; có tuỳ chọn **Restart and close terminals** (đóng mọi terminal, dừng chương trình trong đó).
- **Update daemon** — cập nhật daemon lên bản mới rồi restart.
- **Remove host** — danger zone; xoá host/connection đã lưu (localhost còn tắt built-in daemon management).
- (Nguồn: `settings.host.appearance`, `desktop.daemon.*`, `settings.host.daemon.*`; `HostSettingsPage` `W:18983`.)

#### Projects

- **Project list / Add project** — danh sách project trên host.
- **Name** — tên project.
- **Icon** — Choose image / Use automatic / Image or website URL.
- **Worktree setup** — lệnh chạy khi tạo worktree.
- **Worktree teardown** — lệnh chạy khi xoá worktree.
- **Scripts** — danh sách script: Name, Command, Run as a service, port; thêm/sửa/xoá.
- **Metadata generation** — prompt riêng cho branch names, commit messages, pull requests.
- (Nguồn: `settings.project.*`; project config nằm trong `paseo.json` của project, không phải daemon config.)

#### Connections

- **Connection list** — các connection đã lưu (Relay / Local / Remote SSH / TCP), badge và latency.
- **Remove connection** — xoá connection khỏi thiết bị.
- (Nguồn: `settings.host.connections.*`; component `HostConnectionsPage`.)

#### Pair device

- **Pair a device** — mở QR/link để ghép điện thoại với host (`settings.host.pairDevices.*`; component `HostPairDevicePage`).

#### Agents

- **Enable Paseo tools** — inject MCP tools của Paseo vào agent (`daemon.mcp.injectIntoAgents`, mặc định false).
- **Browser tools** — cho agent điều khiển browser tab Paseo, gồm cả trạng thái đăng nhập; cảnh báo chỉ bật cho agent tin cậy (`daemon.browserTools.enabled`, mặc định false).
- **System prompt** — append system prompt cho mọi agent (`daemon.appendSystemPrompt`, mặc định rỗng).
- **Resume agents after restart** — tự mở lại agent đang làm dở sau restart/crash (`agents.resumeOnStartup`, mặc định false).
- **Resume prompt** — prompt gửi khi resume (mặc định `"Resume working."`).
- **Release idle agents** — dừng process agent sau 1 giờ không hoạt động, giữ hội thoại (`agents.idleRuntimeCleanup`, mặc định true).
- **Orchestration skills** — Install/Update/Uninstall/Choose skills; cài skill vào `~/.agents/skills` và `~/.claude/skills`; `~/.codex/skills` chỉ còn là đường legacy được dọn (`S/orchestration-skills/internal/paths.js:16-18`, `.../sync.js:160-166`).
- **Agent profiles** — danh sách profile provider/model/mode/thinking/features/notes; thêm/sửa/xoá/sắp xếp.
- (Nguồn: `settings.host.agents.*`, `settings.host.orchestration.*`, `settings.host.skills.*`, `settings.host.agentProfiles.*`; `HostAgentsPage` `W:18983`.)

#### Metadata

- **Model selection** — Automatic hoặc Manual.
- **Model** — model dùng cho workspace titles, branch names, commit messages, PR drafts; chỉ dùng model này, không fallback.
- (Nguồn: `settings.metadataGeneration.*`.)

#### Voice

- **Dictation** — bật/tắt nhập bằng giọng nói vào message box.
- **Voice mode** — bật/tắt hội thoại hands-free; nghe/đọc trả lời.
- **Provider** — Local hoặc OpenAI.
- **Model** — model STT/TTS tương ứng.
- **Language** — ngôn ngữ hoặc auto-detect.
- **API key** — lưu trên host, không hiện lại.
- **Base URL** — cho server OpenAI-compatible; rỗng = OpenAI.
- **Local models** — download/delete model local, xem dung lượng/ngôn ngữ.
- (Nguồn: `settings.voice.*`, `voice.*`; component `HostVoicePage`.)

#### Workspaces

- **Archive merged PR workspaces** — tự archive workspace sạch sau khi PR được merge (`daemon.autoArchiveAfterMerge`, mặc định false).
- (Nguồn: `HostWorkspacesPage` `W:18983`; chuỗi `"Archive merged PR workspaces"`.)

#### Providers

- **Add provider** — thêm provider.
- **Enable/Disable provider** — bật/tắt từng provider.
- **Models** — xem model discovered; **Add model** custom; **Remove model**.
- **Diagnostic** — chạy diagnostic provider, copy kết quả.
- **Remove provider** — xoá entry khỏi `config.json`.
- (Nguồn: `settings.providers.*`; component `ProvidersSection`.)

#### Usage

- **Check usage** — bật/tắt theo dõi usage theo host.
- **Show in sidebar** — hiện usage trong sidebar.
- **Display as** — Used hoặc Remaining.
- **Refresh / host filter** — refresh dữ liệu; lọc host khi có nhiều host.
- (Nguồn: `providerUsage.*`, `UsageOptions`; component `HostUsageSection`.)

#### Terminals

- **Enable terminal agent hooks** — chi tiết mục 2.
- **Terminal profiles** — chi tiết mục 3.
- (Không còn tuỳ chọn nào khác.)

#### Plugins

- **Enable plugins** — công tắc global (`pluginsEnabled`, mặc định false).
- **Install plugin** — nhập source (owner/slug, directory, Git URL, npm package) và Install.
- **Per-plugin actions** — Reload / Enable / Disable / Remove.
- **Logs** — xem log của plugin.
- **Status** — running / disabled / failed.
- **Trust warning** — plugin chạy code tin cậy, không sandbox; chỉ cài code tin cậy.
- (Nguồn: `settings.plugins.*`; component `HostPluginsPage`.)

## 6. Bảng tổng hợp đề xuất

| Cấu hình | Đề xuất | Lý do |
|---|---|---|
| `daemon.enableTerminalAgentHooks` | `false` hiện tại; `true` chỉ khi chuyển phiên vào terminal Paseo | Không thấy brain/hand/screen ngoài; bật là sửa global config |
| `daemon.terminalProfiles` | Giữ 4 default; thêm `screen-side` (`/usr/bin/screen -x side-session`) | Xem/điều khiển screen từ desktop/điện thoại; không có hook status |
| `settings.terminalScrollbackLines` | `10000` (hoặc `20000` nếu cần log dài) | Cân bằng bộ nhớ client; max 1.000.000 |
| `notifications.playSound` | `true` nếu dùng terminal hooks | Có âm thanh khi "Terminal needs input/finished" |
| `pluginsEnabled` | giữ `false` nếu chưa dùng hh-tree | Plugin là code tin cậy, không sandbox; không liên quan hooks |

## 7. Câu hỏi còn mở

1. **Codex**: Paseo 0.15.0 ghi `~/.codex/hooks.json`; bản Codex người dùng đang chạy có đọc file này và firing đúng các event `PreToolUse`/`PostToolUse`/`PermissionRequest`/`Stop` không?
2. **OpenCode**: plugin `~/.config/opencode/plugins/paseo-terminal-activity.js` có được cả OpenCode v1 và v2 nạp đúng không? Code comment nói cả hai generation tìm cùng file, nhưng cần xác nhận với bản cài thực tế.
3. **Claude Code**: các event `StopFailure`, `SessionEnd`, và `Notification` với `notification_type=idle_prompt` có được phiên bản Claude Code đang dùng phát ra đúng không? Nếu `Notification` không có `idle_prompt`, trạng thái "needs input" sẽ không xuất hiện.
4. **Screen qua Paseo**: `screen -x` trong terminal Paseo có ổn định về resize/redraw trên desktop và điện thoại không? Cần thử thực tế; không chạy `screen` trong lượt này.
5. **Import session khi phiên gốc đang chạy**: Paseo resume cùng provider session id; có xung đột ghi transcript với tiến trình Claude đang chạy ngoài không? **(suy luận)** nên dừng phiên gốc trước khi import.
6. **Nhiều daemon/nhiều home**: nếu có nhiều Paseo daemon trên cùng máy, cơ chế hook global có thể xung đột (bật/tắt qua lại). Cần chính sách một daemon quản lý hook.
7. **Quyền thiết bị pair**: thiết bị điện thoại đã pair có được cấp `daemon.manage` để sửa `terminalProfiles`/bật hooks không? Nếu có, bề mặt "thêm profile rồi chạy lệnh" mở rộng sang điện thoại.
8. **Đường dẫn CLI trong terminal cũ**: `PASEO_HOOK_CLI` được set lúc tạo terminal; sau khi nâng cấp CLI, terminal Paseo mở từ trước có thể trỏ path cũ. Cần mở terminal mới sau khi update.
9. **Stale hooks sau khi gỡ Paseo**: nếu bật hooks rồi xoá CLI/Paseo mà không tắt switch, `~/.claude/settings.json`/`~/.codex/hooks.json` vẫn còn lệnh gọi `paseo`. Cần kiểm tra và dọn thủ công.
10. **Tiếng Việt**: app chưa có locale `vi` trong danh sách Language; nếu cần UI tiếng Việt thì phải dùng tiếng Anh/hệ thống.

## 8. Ghi chú về giới hạn của báo cáo

- Không đọc `~/.paseo`, `~/.claude`, `~/.codex*`, không đọc `.env`/key/credential; mọi giá trị mặc định lấy từ code.
- Không chạy `paseo`, `claude`, `dsh`, `opencode`, `screen`; không có kết quả runtime thực tế.
- Các kết luận về việc Codex/OpenCode có thực sự nạp file hook hay không là điểm cần kiểm chứng runtime; phần code chỉ chứng minh Paseo ghi file và kỳ vọng provider đọc file đó.
