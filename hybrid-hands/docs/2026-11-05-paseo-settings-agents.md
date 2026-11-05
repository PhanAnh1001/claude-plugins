# Paseo 0.15.0 — Settings → Agents và Orchestration skills

## Tóm tắt

- **Nguồn và phạm vi:** báo cáo của hand ngoài dsh ngày 05/11/2026, chỉ đọc mã đã build của Paseo 0.15.0; chưa kiểm bằng chạy thật. `<npm-global>` là thư mục npm toàn cục của Node 24 trên máy chạy daemon.
- Paseo 0.15.0, đọc mã đã build tại `<npm-global>/lib/node_modules/@getpaseo/cli/node_modules/@getpaseo`; không chạy `paseo`/`claude`/`dsh`/`opencode`/`screen`, không đọc `~/.paseo`, không mở mạng.
- Trang **Settings → host → Agents** gồm đúng 5 card: `Enable Paseo tools`, `Browser tools`, `System prompt`, `Resume agents after restart`, `Release idle agents`; sau đó là 2 section: `Orchestration skills`, `Agent profiles`.
- Tất cả đều là **cấu hình daemon** trong `~/.paseo/config.json` (không phải cài đặt app phía client): `daemon.mcp.injectIntoAgents`, `daemon.browserTools.enabled`, `daemon.appendSystemPrompt`, `agents.resumeOnStartup` + `agents.resumePrompt`, `agents.idleRuntimeCleanup`, `daemon.agentProfiles`, `agents.skills.selection`.
- Mặc định runtime: Paseo tools **tắt**, Browser tools **tắt**, System prompt **rỗng**, Resume **tắt** (prompt `"Resume working."`), Release idle **bật** (60 phút), Agent profiles **rỗng**, Skills selection **rỗng** nhưng được hiểu là `mode: "all"`.
- Có 6 skill bundled: `paseo`, `paseo-advisor`, `paseo-committee`, `paseo-handoff`, `paseo-help`, `paseo-plugin`; cài vào `~/.agents/skills` và `~/.claude/skills`; `~/.codex/skills` chỉ còn là đường dọn legacy.
- Cơ chế “agent điều khiển agent” là MCP server nội bộ ở `/mcp/agents` (hoặc CLI `paseo`), với `callerAgentId`, label `paseo.parent-agent-id`, `send_agent_prompt` và cơ chế `notifyOnFinish`; skill chỉ là hướng dẫn, không phải code thực thi.
- Điểm khác cốt lõi với brain/hand hiện tại: Paseo chỉ quản lý agent do nó tạo hoặc import; nó **không tự thấy** tiến trình Claude Code trong terminal, `hand-ext`, hay phiên `screen` hiện có. Muốn theo dõi các phiên đó từ Paseo phải dùng terminal agent hooks, import session, hoặc plugin cầu nối.
- Khuyến nghị ngắn: giữ `Release idle = true`; `Resume = false` trong lúc chuyển đổi rồi bật `true` khi brain/hand đã chạy trong Paseo; `Enable Paseo tools = true` chỉ cho agent Paseo đáng tin; `Browser tools = false` trừ khi thật cần; đặt System prompt ngắn; tạo 3 Agent profiles; cài skill qua `mode: "all"`.

## 0. Phạm vi, phiên bản, quy ước bằng chứng

- Phiên bản: `@getpaseo/server` 0.15.0 (`P/server/package.json:3`).
- `P` = `<npm-global>/lib/node_modules/@getpaseo/cli/node_modules/@getpaseo`.
- `W` = `P/server/dist/server/web-ui/_expo/static/js/web/index-c26368bf062ddf91b40b9d95aae94799.js` (bundle web/desktop, một dòng rất dài; số `@...` là offset ký tự trong file, dùng để grep lại).
- Các khẳng định hành vi đều có `file:dòng` hoặc chuỗi grep trong `W`. Phần suy luận từ kiến trúc được đánh dấu **(suy luận)**.
- Báo cáo chỉ đọc mã; không xác nhận cấu hình thực tế của máy vì `~/.paseo` nằm ngoài phạm vi được phép đọc.

## 1. Bản đồ thật của trang Settings → Agents

### 1.1 Thứ tự UI

`W @23618988` (đoạn `HostAgentsPage`) render theo đúng thứ tự:

```text
SettingsSection(title = "Agents")
  ├─ Ce                      → Enable Paseo tools
  ├─ BrowserToolsOptInCard   → Browser tools
  ├─ ke                      → System prompt
  ├─ RestartRecoveryCard     → Resume agents after restart
  └─ IdleRuntimeCleanupCard  → Release idle agents
AgentSkillsSection           → Orchestration skills
AgentProfilesSection         → Agent profiles
```

Đây là bằng chứng trực tiếp cho việc cả 5 card và 2 section nằm cùng trang **Agents**. Trong i18n, hai card `Enable Paseo tools` và `System prompt` dùng khoá `settings.host.orchestration.*`, nhưng không có section “Orchestration” riêng trong `HostAgentsPage`; chúng chỉ là card trong trang Agents (`W @23618988`, `W @5883963`).

Các mục dễ bị nhầm là “cùng nhóm Agents” nhưng thật ra nằm trang khác:

- `Enable terminal agent hooks` nằm ở **Settings → host → Terminals → Terminal agents** (`W @23622148`, đoạn `HostTerminalsPage`).
- `Archive merged PR workspaces` nằm ở **Settings → host → Workspaces** (`W @23620015`, đoạn `HostWorkspacesPage`).

### 1.2 Bảng khoá cấu hình

| Tên trong Settings | Khoá trong `config.json` | Kiểu | Mặc định runtime | Nơi lưu |
|---|---|---|---|---|
| Enable Paseo tools | `daemon.mcp.injectIntoAgents` | boolean | `false` | config daemon |
| Browser tools | `daemon.browserTools.enabled` | boolean | `false` | config daemon |
| System prompt | `daemon.appendSystemPrompt` | string | `""` | config daemon |
| Resume agents after restart | `agents.resumeOnStartup` | boolean | `false` | config daemon |
| Resume prompt (phụ) | `agents.resumePrompt` | string | `"Resume working."` | config daemon |
| Release idle agents | `agents.idleRuntimeCleanup` | boolean | `true` | config daemon |
| Agent profiles | `daemon.agentProfiles` | `AgentProfile[]` | không có / rỗng | config daemon |
| Orchestration skills (selection) | `agents.skills.selection` | `{mode:"all"} \| {mode:"custom",skills:string[]}` | chưa set → coi là `all` | config daemon |

Bằng chứng schema và mặc định:

- Schema tổng: `P/server/dist/server/server/persisted-config.js:194-316`.
- `daemon.browserTools`: `persisted-config.js:217-222`; mặc định `false`: `config.js:332-334`.
- `daemon.agentProfiles`: `persisted-config.js:234`; resolver giữ `undefined` nếu chưa có: `config.js:337-344`.
- `agents.idleRuntimeCleanup`, `resumeOnStartup`, `resumePrompt`, `skills.selection`: `persisted-config.js:294-305`.
- Mặc định `mcp.injectIntoAgents = false`: `config.js:348-349`; `mcp.enabled = true`: `config.js:348`.
- Mặc định `idleRuntimeCleanup = true`: `config.js:435`.
- Mặc định resume: `config.js:560-566`.
- Đường dẫn file: `CONFIG_FILENAME = "config.json"` và `path.join(paseoHome, "config.json")` (`persisted-config.js:317-335`); với daemon thường là `~/.paseo/config.json`.

### 1.3 Vì sao nói “cấu hình daemon”, không phải app client

UI đọc/ghi qua `useDaemonConfig` và gửi patch lên daemon; daemon ghi vào `config.json` qua `DaemonConfigStore.patch` → `persistConfig` → `savePersistedConfigAsync` (`P/server/dist/server/server/daemon-config-store.js:255-297, 459-471`). Client không giữ nguồn sự thật riêng. Các đường dẫn này cũng nằm trong `RELOADABLE_PATHS`, nên sửa `config.json` có thể được daemon áp dụng lại mà không cần khởi động lại (`daemon-config-store.js:78-104`).

## 2. Resume agents after restart

### 2.1 Vị trí và khoá

- UI: card thứ 4 trong trang Agents.
- Khoá: `agents.resumeOnStartup` (boolean, mặc định `false`), `agents.resumePrompt` (string, mặc định `"Resume working."`).
- Lưu: config daemon (`~/.paseo/config.json`), không phải app client.
- Phụ: mỗi agent record có cờ nội bộ `resumeOnStartup` (`P/server/dist/server/server/agent/agent-storage.js:48, 199-200`), không phải setting người dùng.

### 2.2 Hành vi thật

UI mô tả:

> “Reopen agents that were working when the host stopped and send the resume prompt. Applies after graceful restarts and crashes.”
> “Continue interrupted work automatically.”
> (`W @5884433`, `W @23742263`)

Luồng trong mã:

1. **Chọn ứng viên trước khi sửa trạng thái**: `prepareStartup()` duyệt toàn bộ record, coi là ứng viên nếu setting bật và (`record.resumeOnStartup === true` hoặc `record.lastStatus === "running"`), đồng thời record không archived/internal/owner và workspace không bị archive (`P/server/dist/server/server/agent/restart-recovery/index.js:16-35`; điều kiện workspace: `P/server/dist/server/server/bootstrap.js:712-724`).
2. **Đánh dấu pending và hạ trạng thái**: ghi `resumeOnStartup: pending`, đổi `lastStatus` từ `running`/`initializing` thành `closed` để lần đọc sau không tưởng là đang chạy (`restart-recovery/index.js:21-27`).
3. **Chờ server sẵn sàng**: sau khi WS server được khởi tạo, ngay trước `beginAcceptingConnections()`, gọi `resumePending()` (`bootstrap.js:1390-1400`).
4. **Gửi prompt**: `resume()` đọc lại record, nếu cờ còn true thì **đặt cờ về false trước**, rồi mới kiểm tra setting/điều kiện và gọi `deps.dispatch(agentId, prompt)` (`restart-recovery/index.js:5-13`). Dispatch là `sendPromptToAgent` thông thường, với `unarchive: false` (`bootstrap.js:718-721`), nên prompt được gửi như một user message, không phải một cơ chế “resume” riêng của provider.
5. **Không retry**: lỗi dispatch chỉ được log (`report`), không đưa lại vào hàng đợi; cờ đã false nên crash giữa lúc resume cũng không lặp vô hạn (`restart-recovery/index.js:9, 45-54`).
6. **Lúc shutdown mềm**: `captureRunningAgents()` flush storage, duyệt record `lastStatus === "running"`, set `resumeOnStartup = settings().enabled` (`restart-recovery/index.js:37-43`; gọi tại `bootstrap.js:1484`). Đây là phần “graceful restart”; với crash, ứng viên đến từ `lastStatus` đã persist từ trước.

### 2.3 Điều kiện, giới hạn, rủi ro

- **Chỉ áp dụng cho agent do Paseo quản lý**. Agent terminal/screen bên ngoài không có record trong `agentStorage` nên không được resume. Đây là lý do tính năng này không giúp brain/hand hiện tại nếu chúng vẫn chạy ngoài Paseo.
- **Bỏ qua** agent `archivedAt`, `internal`, có `owner`, hoặc workspace đã archive (`restart-recovery/index.js:4`; `bootstrap.js:718`).
- **Phụ thuộc trạng thái persist**: nếu cửa sổ crash làm mất lần ghi `lastStatus: running` cuối, agent có thể không được chọn. Ngược lại, record “running” cũ có thể được resume dù thực tế đã xong (suy luận từ việc chỉ dựa vào `lastStatus`).
- **Tự chạy lệnh/tốn token**: prompt được gửi như message thật, provider sẽ tiếp tục turn; nếu turn trước đang dở, có thể lặp side effect (commit, gọi API, ghi file). Cơ chế không có idempotency hay kiểm tra “đã hoàn thành chưa”.
- **Prompt rỗng**: schema chỉ là `z.string().optional()` (`persisted-config.js:299`); UI chặn lưu nếu trim rỗng (`O.trim().length>0` trong `W @23742263`), nhưng sửa tay `config.json` có thể đặt `""` và daemon vẫn gửi chuỗi rỗng.
- **Không có toggle per-agent** trên UI; setting là host-wide. Muốn loại một agent phải archive nó hoặc sửa record (không khuyến nghị).
- **“Applies after graceful restarts and crashes”** là mô tả UI; về mã, crash không chạy `captureRunningAgents`, nên chỉ dựa vào `lastStatus` đã ghi trước đó.

### 2.4 Có ích gì cho NGỮ CẢNH và đề xuất

- Với cách làm hiện tại (brain terminal + hand-ext + screen), tính năng này **không tác động** vì các phiên đó không phải Paseo agent.
- Nếu chuyển brain/hand vào Paseo (hoặc tạo hand qua Paseo), bật `true` sẽ giúp hand sống qua restart daemon. Nhưng nên dùng prompt có kiểm tra trạng thái, ví dụ:

```text
Resume working. First inspect the workspace and git status; do not repeat steps that already completed. If the task is already done, report that instead of re-running it.
```

- Đề xuất: **`false` trong giai đoạn chuyển đổi**, **`true` sau khi đã có ít nhất một tuần chạy ổn** và chỉ cho workspace/hand ít side effect. Với brain đang điều phối nhiều hand, resume tự động có thể tạo “bão” agent cùng tỉnh dậy; nên bật sau cùng.

## 3. Release idle agents

### 3.1 Vị trí và khoá

- UI: card thứ 5 trong trang Agents.
- Khoá: `agents.idleRuntimeCleanup` (boolean, mặc định `true`).
- Lưu: config daemon.
- UI mô tả:

> “Free up memory after an hour of inactivity.”
> “Stops the agent's process while keeping its conversation. Send a message to resume. Active work, pending notifications, and provider safety checks prevent cleanup.”
> (`W @5884717`)

### 3.2 Hành vi thật

- Hằng số: `IDLE_PERIOD_MS = 60 * 60000` (60 phút) (`P/server/dist/server/server/agent/idle-runtime-cleanup/index.js:2`).
- Quét mỗi 60 giây: `setInterval(tick, 60000)` (`idle-runtime-cleanup/index.js:110-112`).
- **Gom theo “family”**: từ một runtime gốc, thêm đệ quy các runtime có `parentAgentId` trỏ tới nó (`idle-runtime-cleanup/index.js:12-21`). Nếu một agent cha và các con cùng rảnh mới được gom; một con đang chạy giữ cả family lại (`baselineAllows` kiểm tra `family.every(...)`, dòng 22-24).
- **Điều kiện cơ bản** (`agent/agent-manager.js:1143-1154`):
  - `agent.lifecycle === "idle"`;
  - không phải internal;
  - không có `activeForegroundTurnId`;
  - không có run đang chạy;
  - không có `pendingReplacement`;
  - không có permission đang chờ/đang trả lời;
  - không có lifecycle/foreground/session-event mutation đang dở;
  - không có provider subagent đang `running`.
- **Bảo vệ bổ sung** (`bootstrap.js:1099-1106`):
  - `finishSubscriptions.hasPendingForCaller(agentId)` — còn subscription chờ báo kết thúc;
  - `agentMessages.hasPending(agentId)` — còn message đang chờ gửi.
- **Provider veto**: nếu runtime có `canStopRuntime`, gọi với timeout 10 giây; chỉ khi trả `true` mới đóng (`idle-runtime-cleanup/index.js:25-35`). Claude kiểm tra thêm: không có foreground/autonomous/main turn, không còn message chưa gửi, không permission, không SDK message đang xử lý, và `ClaudeRuntimeSafety.canStopRuntime()` (`P/server/dist/server/server/agent/providers/claude/agent.js:2344-2352`). `ClaudeRuntimeSafety` chỉ cho phép khi binary Claude Code >= 2.1.292 (hoặc có roster) và không còn background task/notification (`P/server/dist/server/server/agent/providers/claude/runtime-safety.js:17-38`).
- **Đóng runtime, giữ hội thoại**: `closeAgentRuntime` gọi `session.close()`, `persistSnapshot`, giữ `persistence.sessionId` (`agent/agent-manager.js:1176-1206`). Lần gửi message sau, `ensureAgentLoaded` mở lại session từ persistence (cơ chế chung của `sendPromptToAgent`).
- **Toggle live**: `connectIdleRuntimeCleanupConfig` theo dõi field và gọi `setEnabled` (`bootstrap.js:1570-1575`); `setEnabled` tăng `generation` để sweep đang chạy không tiếp tục áp dụng (`idle-runtime-cleanup/index.js:115-120`).

### 3.3 Điều kiện, giới hạn, rủi ro

- **Chỉ giải phóng process/RAM**, không xoá conversation, không xoá workspace, không xoá file. Đóng session có thể làm lần prompt sau chậm hơn (cold start, provider phải resume session) và tốn token để nạp lại ngữ cảnh.
- **Không phải “tắt agent” theo nghĩa UI**: agent vẫn trong danh sách, trạng thái closed; gửi message sẽ đánh thức.
- **Có thể không bao giờ xảy ra với Claude cũ**: nếu `runtimeSafety.supported` false, `canStopRuntime()` trả false, runtime bị giữ mãi. Đây là điểm cần kiểm tra nếu người dùng thấy RAM không giảm.
- **Family grouping** có thể giữ cha lâu hơn dự kiến nếu một con đang chạy; ngược lại, nếu tất cả cùng rảnh, cả family bị đóng.
- **Race**: trước khi đóng có revalidate family và `runLifecycleMutation`; prompt đến đúng lúc được xử lý bằng cách chặn admission (`collectingRuntimes`), nên thiết kế cố gắng tránh mất prompt (`agent-manager.js:1126-1139`). Tuy vậy, đây vẫn là thao tác đóng process; nếu provider có side effect ngoài tầm kiểm soát thì rủi ro vẫn có.
- **Không tiết kiệm token trực tiếp**; chỉ giảm RAM/CPU. Việc resume sau đó có thể tốn token hơn nếu phải nạp lại history.

### 3.4 Có ích gì cho NGỮ CẢNH và đề xuất

- Rất phù hợp với kiểu chạy nhiều hand/agent ngồi chờ: giữ conversation để brain quay lại hỏi, nhưng không giữ process.
- Đề xuất: **`true`** (mặc định). Nếu hand thường xuyên được gọi lại trong vòng vài phút và cold start đắt, có thể cân nhắc `false`, nhưng mặc định 60 phút là hợp lý.
- Nếu dùng Claude Code bản cũ, nâng provider lên >= 2.1.292 để cơ chế provider veto hoạt động đúng; nếu không, tính năng có thể im lặng không làm gì.

## 4. Enable Paseo tools

### 4.1 Vị trí và khoá

- UI: card đầu tiên trong trang Agents.
- Khoá: `daemon.mcp.injectIntoAgents` (boolean, mặc định `false`).
- Lưu: config daemon.
- UI mô tả: “Agents will be able to manage worktrees, agents and schedules” (`W @5883963`).
- Đây là **công tắc tổng** để inject bộ tool Paseo vào agent; không phải cài đặt MCP server phía client.

### 4.2 Hành vi thật

- Runtime coi `mcp.enabled` (mặc định `true`) và `mcp.injectIntoAgents` (mặc định `false`) là hai điều kiện (`config.js:348-349`; `bootstrap.js:1176-1181`).
- Khi bật, agent manager thêm MCP server tên `paseo`, type `http`, URL `${mcpBaseUrl}/mcp/agents?callerAgentId=<agentId>`, kèm header `Authorization: Bearer <token>` nếu daemon có token (`P/server/dist/server/server/agent/runtime-mcp-config.js:23-40`). Token không được in ra báo cáo.
- Với provider có native tool support (OMP, OpenCode bridge), catalog được truyền trực tiếp thay vì MCP (`agent/agent-manager.js:4009-4021`; `agent/providers/omp/agent.js:272`; `agent/providers/opencode-agent.js:982`).
- Catalog tool:
  - 41 tool đăng ký trong `paseo-tools.js` (không tính browser và plugin; `grep -c 'registerTool("'` = 41);
  - 18 tool browser nếu `browserTools.enabled` và broker có mặt (`agent/tools/paseo-tools.js:973-981`);
  - tool do plugin đóng góp (`registerPluginTools`, dòng 2466).
- Policy theo provider: `paseoTools.enabled` mặc định coi là bật trừ khi `false`; `disabledTools` loại từng tên (`P/server/dist/server/server/agent/paseo-tool-policy.js:1-15`). `speak` luôn được phép (`paseo-tool-policy.js:3-5`).
- Toggle live: `onFieldChange("mcp.injectIntoAgents")` cập nhật `setMcpBaseUrl`, `setPaseoToolsEnabled`, `setAgentProviderToolsEnabled` (`bootstrap.js:1327-1337`).

### 4.3 Tool làm được gì

| Nhóm | Tool tiêu biểu | Tác động |
|---|---|---|
| Host / workspace | `list_hosts`, `create_workspace`, `list_workspaces`, `archive_workspace`, `rename_workspace` | Tạo/archive workspace, thao tác worktree |
| Agent | `create_agent`, `send_agent_prompt`, `get_agent_status`, `get_agent_activity`, `list_agents`, `cancel_agent`, `archive_agent`, `kill_agent`, `update_agent` | Tạo và điều khiển agent khác, đọc timeline |
| Terminal | `list_terminals`, `create_terminal`, `kill_terminal`, `capture_terminal`, `send_terminal_keys` | Mở terminal, gõ phím, đọc output |
| Schedule / heartbeat | `create_schedule`, `create_heartbeat`, `delete_heartbeat`, `list_schedules`, `pause_schedule`, `resume_schedule`, `update_schedule`, `run_schedule_once`, `schedule_logs` | Tạo công việc chạy định kỳ, có thể tự chạy mãi |
| Provider / profile | `list_providers`, `list_models`, `list_profiles`, `inspect_provider` | Chọn provider/model/profile cho agent con |
| Permission | `list_pending_permissions`, `respond_to_permission` | Đọc và **phê duyệt/từ chối** permission của agent khác |
| Browser | 18 tool `browser_*` (nếu bật) | Điều khiển tab Paseo, kể cả tab đã đăng nhập |

Danh sách đầy đủ có thể grep `registerTool("` trong `agent/tools/paseo-tools.js`; các tool browser nằm trong `browser-tools/tools.js`.

### 4.4 Điều kiện, giới hạn, rủi ro

- **Không áp dụng cho agent ngoài Paseo**: một Claude Code chạy trong terminal không nhận MCP server này. Nếu muốn brain terminal dùng, phải cấu hình MCP riêng hoặc gọi CLI `paseo`.
- **Áp dụng lúc mở session**: `prepareSessionConfig` mới là nơi chèn MCP server (`agent/agent-manager.js:3943-3957`); agent đang chạy giữ cấu hình đã mở cho đến khi session được mở lại (suy luận từ việc không thấy cơ chế re-inject vào session đang sống). Toggle có hiệu lực rõ nhất với agent mới/được reload.
- **Quyền rất rộng, không phải sandbox**: tool handler chạy trong process daemon, dùng quyền của daemon, không phải quyền shell của agent (suy luận từ kiến trúc: handler nhận `agentManager`, `terminalManager`, `scheduleService` trực tiếp). Vì vậy permission mode của provider không nhất thiết giới hạn các tool này.
- **`respond_to_permission` là rủi ro cao nhất**: một agent có thể approve permission request của agent khác (`paseo-tools.js:2442-2465`). Nếu agent bị prompt injection, nó có thể tự mở đường cho hành động nguy hiểm.
- **Schedule/heartbeat** có thể tạo vòng lặp tự chạy ngoài phiên; **terminal keys** có thể gõ lệnh vào terminal khác; **archive/kill** có thể dừng công việc đang chạy.
- **Tốn token**: mỗi tool schema được đưa vào context; mỗi lần gọi là một lượt model. Agent tự tạo agent con có thể nhân chi phí.
- **Bề mặt mạng**: MCP endpoint `/mcp/agents` nằm trên daemon; nếu daemon lộ ra LAN/relay, cần bảo vệ token/password. Hiện daemon chỉ nghe `127.0.0.1:6767` theo NGỮ CẢNH, nhưng nếu bật relay/Tailscale thì phạm vi thay đổi.
- **Không có allowlist theo agent**: policy là theo provider (`agents.providers[provider].paseoTools` trong `config.json`; UI/mutable là `providers[provider].paseoTools`), không theo từng agent. Muốn giới hạn phải dùng `disabledTools` hoặc tách provider.

### 4.5 Có ích gì cho NGỮ CẢNH và đề xuất

- Đây là điều kiện tiên quyết để brain (nếu chạy trong Paseo) tạo hand, gửi prompt, đọc trạng thái, và nhận thông báo hoàn thành.
- Với brain terminal hiện tại: **bật hay tắt đều không ảnh hưởng**; muốn dùng phải chuyển brain vào Paseo hoặc cấu hình MCP/CLI riêng.
- Đề xuất:
  - `true` nếu brain/hand được chạy như Paseo agent và người dùng tin các agent đó.
  - Bắt đầu với `disabledTools` loại các tool nguy hiểm chưa cần: `respond_to_permission`, `kill_agent`, `archive_workspace`, `create_schedule`, `send_terminal_keys`.
  - Không bật cho agent xử lý nội dung không tin cậy (web, email, issue từ ngoài) vì prompt injection có thể điều khiển tool.
  - Nếu chỉ cần hand nhận việc và báo cáo, có thể chỉ để `create_agent`, `send_agent_prompt`, `list_agents`, `get_agent_status`, `get_agent_activity` — nhưng UI không expose `disabledTools` (suy luận từ bundle không có nhãn này); phải sửa `config.json`.

## 5. Browser tools

### 5.1 Vị trí và khoá

- UI: card thứ 2 trong trang Agents.
- Khoá: `daemon.browserTools.enabled` (boolean, mặc định `false`).
- Lưu: config daemon.
- Cảnh báo UI:

> “Allow agents to access and control Paseo browser tabs, including logged-in browser state. Only enable this for agents you trust.”
> (`W @23742014`)

### 5.2 Hành vi thật

- `DaemonConfigBrowserToolsPolicy.isEnabled()` chỉ trả true khi `browserTools.enabled === true` (`P/server/dist/server/server/browser-tools/policy.js:1-15`).
- Khi bật và có broker, catalog đăng ký 18 tool (`agent/tools/paseo-tools.js:973-981`; `grep -c 'registerTool("browser_'` = 18):
  `browser_list_tabs`, `browser_new_tab`, `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_fill`, `browser_keypress`, `browser_wait`, `browser_screenshot`, `browser_upload`, `browser_evaluate`, `browser_logs`, `browser_scroll`, `browser_resize`, `browser_select`, `browser_drag`, `browser_close_tab`.
- Tool gửi request qua `BrowserToolsBroker` tới một **browser automation host** đã đăng ký; host là client Paseo có capability `browser_host` (`P/server/dist/server/server/session.js:1487-1505`), thường là app desktop đang mở tab Paseo. Broker chọn host theo `browserId`/command, timeout mặc định 15 giây (`P/server/dist/server/server/browser-tools/broker.js:6, 74-120`).
- `browser_new_tab`/`browser_list_tabs` cần workspace context; thiếu workspace sẽ trả lỗi hướng dẫn (`browser-tools/tools.js:7-9, 51-62`).
- URL chỉ chấp nhận `http/https`; URL không scheme được coi là `http` (`browser-tools/tools.js:4-26`).
- `browser_evaluate` chạy JavaScript trong tab; `browser_upload` đặt file từ workspace vào input file; `browser_screenshot` chụp PNG; `browser_logs` đọc console/network; `browser_snapshot` trả ref cho các tool tương tác (`browser-tools/tools.js:80-120, 288-330, 415-470`).

### 5.3 Điều kiện, giới hạn, rủi ro

- **Cần host browser**: nếu không có app Paseo desktop/browser host kết nối, tool trả lỗi `browser_no_host`, không treo.
- **Tab Paseo, không phải Chrome profile bất kỳ**: tool nói “Paseo browser tabs”; không điều khiển trực tiếp cửa sổ Chrome thông thường trừ khi tab đó nằm trong Paseo.
- **Dùng chung trạng thái đăng nhập**: cảnh báo UI nói rõ “logged-in browser state”; agent có thể đọc/ghi dữ liệu phiên đăng nhập, đăng bài, mua hàng, đổi cài đặt.
- **Prompt injection**: nội dung trang web có thể chứa chỉ dẫn độc hại; agent đọc snapshot rồi làm theo. Đây là rủi ro thực tế cao hơn so với tool file.
- **`browser_evaluate` + `browser_upload`** là bề mặt nguy hiểm nhất: chạy JS tùy ý trong origin đang đăng nhập, và đọc file workspace để upload.
- **Toàn daemon**: bật là mọi agent có Paseo tools đều thấy browser tools (trừ provider policy); không có công tắc per-agent.
- **Không thay thế kiểm thử web thật**: snapshot/ref có thể lệch với DOM thay đổi; timeout 15 giây; wait tối đa 30 giây (`browser-tools/tools.js:17-20`).

### 5.4 Có ích gì cho NGỮ CẢNH và đề xuất

- Nếu công việc có thao tác web (đăng nội dung, kiểm tra dashboard, điền form), browser tools hữu ích cho hand chạy trong Paseo.
- Với brain/hand hiện tại, browser tools **không** giúp điều khiển terminal/screen; chỉ mở thêm khả năng web cho agent Paseo.
- Đề xuất: **`false`** mặc định. Chỉ bật cho workspace/agent tin cậy, trong phiên làm web cụ thể; tắt lại sau khi xong. Nếu bắt buộc dùng, tránh `browser_evaluate`/`browser_upload` trừ khi thật cần, và không dùng trên tab đang đăng nhập tài khoản nhạy cảm.

## 6. System prompt

### 6.1 Vị trí và khoá

- UI: card thứ 3 trong trang Agents, nút Edit mở sheet “Append system prompt”.
- Khoá: `daemon.appendSystemPrompt` (string, mặc định `""`).
- Lưu: config daemon.
- UI mô tả: “Adds a system prompt to all agents” (`W @5883963`).

### 6.2 Hành vi thật

- Khi mở session, `prepareSessionConfig` lấy `this.appendSystemPrompt.trim()`, nếu khác rỗng thì gán vào `config.daemonAppendSystemPrompt` (`P/server/dist/server/server/agent/agent-manager.js:3943-3968`).
- Provider ghép system prompt của agent với phần daemon theo thứ tự: `config.systemPrompt` trước, `daemonAppendSystemPrompt` sau, nối bằng `\n\n` (`P/server/dist/server/server/agent/system-prompt.js:1-7`).
- Các provider dùng chung hàm này: Claude (`agent/providers/claude/agent.js:2896`), Codex (`codex-app-server-agent.js:2853, 3062, 3188, 4183`), OpenCode (`opencode-agent.js:2637, 2914`), Pi (`pi/agent.js:2118, 2173`), OMP (`omp/agent.js:259, 1863`), plugin provider (`plugin-provider.js:1479`).
- Toggle live: `onFieldChange("appendSystemPrompt")` gọi `setAppendSystemPrompt` (`bootstrap.js:1334-1336`), nhưng giá trị chỉ được đọc khi `prepareSessionConfig` chạy; agent đang mở giữ prompt cũ đến lần mở session sau (suy luận từ luồng code).

### 6.3 Điều kiện, giới hạn, rủi ro

- **Toàn cục**: áp dụng cho mọi agent, mọi provider, không có ngoại lệ per-agent.
- **Không thay thế brief**: đây là system/developer instruction, không phải task; nội dung dài làm tốn token mỗi lượt và có thể lấn át hướng dẫn của skill.
- **Thứ tự**: prompt riêng của agent đứng trước, prompt daemon đứng sau; provider có thể tiếp tục ghép thêm developer instructions (Codex).
- **Áp dụng lúc mở session**: sửa setting không làm thay đổi ngay agent đang chạy; cần reload/mở lại.
- **Lưu plaintext** trong `config.json`; không đặt secret trong đây.
- **Có thể xung đột**: nếu System prompt nói “luôn trả lời ngắn” nhưng skill `paseo-handoff` yêu cầu briefing dài, agent phải cân; nên viết quy tắc chung, không mâu thuẫn.

### 6.4 Có ích gì cho NGỮ CẢNH và đề xuất

- Rất hữu ích để áp quy ước chung cho mọi hand Paseo: báo cáo 4 mục, không commit, ghi file:line, không bịa.
- Đề xuất: đặt một prompt ngắn 3–6 dòng, ví dụ:

```text
You are a hand in a brain/hand workflow. Work only within the brief. Report in Vietnamese with: result, files changed (path:line), verification commands and real results, open issues. Never commit, push, or read secrets. Prefer file:line evidence over prose.
```

- Không đặt nội dung brief cụ thể vào đây; brief nên nằm trong prompt của từng agent.

## 7. Agent profiles

### 7.1 Vị trí và khoá

- UI: section cuối trang Agents, có Add/Edit/Remove/Move up/Move down (`W @19950166`, đoạn `AgentProfilesSection`).
- Khoá: `daemon.agentProfiles` (mảng `AgentProfile`), mặc định không có → danh sách rỗng.
- Lưu: config daemon. Đây là điểm dễ nhầm: tên “Agent profiles” nhưng nằm trong namespace `daemon`, không phải `agents`.
- UI mô tả: “No profiles yet. Add one to start agents from a saved provider and model.” (`W @5885857`).

### 7.2 Schema và trường

`AgentProfileSchema` (`P/protocol/dist/agent-profile.js:9-27`):

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `id` | string | ID do client sinh |
| `name` | string | Tên hiển thị |
| `icon` | string? | Key trong icon registry của client, không phải glyph |
| `color` | string? | Tên màu identity, dùng chung host badge |
| `provider` | string | Provider ID |
| `model` | string? | Model ID |
| `modeId` | string? | Mode (plan, full-access, ...) |
| `thinkingOptionId` | string? | Mức thinking |
| `featureValues` | record<string, unknown>? | Feature values theo provider |
| `notes` | string? | Free text cho agent khác đọc khi chọn profile |

Schema cho phép `passthrough` nên field lạ được giữ. **Không có `systemPrompt`** trong profile; comment trong schema nói rõ lý do: `systemPrompt` là creation-only, profile mang theo sẽ chỉ áp lúc tạo mới và im lặng không làm gì khi áp lên agent đang chạy (`agent-profile.js:5-8`).

### 7.3 Hành vi thật

- UI đọc/ghi toàn bộ mảng qua config patch `{ agentProfiles: [...] }`; daemon lưu vào `daemon.agentProfiles` (`P/server/dist/server/server/daemon-config-store.js:94, 121, 204, 548-549`).
- Tool `list_profiles` trả `daemonConfigStore.get().agentProfiles ?? []` (`P/server/dist/server/server/agent/tools/paseo-tools.js:2292-2311`).
- **`create_agent` không có tham số `profile`**. Skill `paseo` hướng dẫn: gọi `list_profiles`, đọc `notes`, rồi copy `provider`, `model`, `modeId`, `thinkingOptionId`, `featureValues` vào `create_agent` (`P/server/dist/server/skills/paseo/SKILL.md:95-108`). Đây là thiết kế có chủ ý: profile chỉ là launch config, không phải tham chiếu runtime.
- UI dùng profile để bắt đầu agent mới (empty state nói “start agents from a saved provider and model”); profile không tự động áp lên agent đang chạy.
- `notes` được hiển thị cho orchestrator: UI hint “Helps agents choose this profile when starting another agent” (`W @5885857`).

### 7.4 Điều kiện, giới hạn, rủi ro

- **Chỉ là launch bundle**: không mang system prompt, không mang brief, không mang quyền, không tự chọn profile khi tạo agent.
- **Có thể lỗi thời**: model ID/mode ID có thể không còn sau khi nâng provider; profile không được validate lại cho đến khi dùng. `list_profiles` chỉ trả dữ liệu, không kiểm tra provider tồn tại.
- **Không có secret**: schema không có field bí mật; không nên nhét token vào `notes` vì `notes` được trả cho mọi agent gọi `list_profiles`.
- **Per-host**: profile thuộc daemon, không đồng bộ sang host khác. Agent cross-host phải dùng profile của host đích hoặc tự chọn provider/model.
- **Không giới hạn số lượng** trong schema; UI có reorder. Nhiều profile làm `list_profiles` dài và tăng token.
- **Icon/color** chỉ là UI; không ảnh hưởng chọn model.

### 7.5 Có ích gì cho NGỮ CẢNH và đề xuất

- Rất phù hợp để chuẩn hoá brain/hand/reviewer nếu chuyển sang Paseo:
  - `Brain` — Claude/Opus, mode plan hoặc full-access tuỳ quy ước, notes: “điều phối, viết brief, không tự sửa code”.
  - `Hand` — provider/model rẻ hơn (OpenCode/DeepSeek hoặc model tương ứng), notes: “thực thi brief, báo cáo 4 mục, không commit”.
  - `Reviewer` — Codex/GPT, notes: “review độc lập, chỉ đọc, không sửa”.
- Đề xuất: tạo 3 profile, giữ `notes` ngắn và mô tả đúng loại việc; không đặt system prompt/brief trong profile. Dùng `list_profiles` trong skill handoff/advisor/committee thay vì đoán model.
- Vì profile không có `systemPrompt`, muốn áp quy ước chung vẫn phải dùng `System prompt` toàn cục hoặc brief từng lần.

## 8. Orchestration skills

### 8.1 Danh sách và nội dung

Bundle có đúng 6 skill, mỗi skill là một thư mục chứa `SKILL.md`; không có file thực thi:

| Skill | Số dòng | Nội dung chính | Khi dùng |
|---|---:|---|---|
| `paseo` | 152 | Reference vận hành Paseo: host, project, workspace, script, agent, profile, schedule/heartbeat, CLI | Agent cần biết gọi tool/CLI nào |
| `paseo-handoff` | 65 | Chuyển task sang agent mới với brief tự chứa; template Task/Context/Files/State/Tried/Decisions/Acceptance/Constraints | Brain giao việc cho hand |
| `paseo-advisor` | 65 | Một agent cố vấn, không sửa file; chọn profile khác provider; chuyển tiếp skill | Cần ý kiến thứ hai |
| `paseo-committee` | 46 | Hai agent từ profile khác provider, chạy song song, không sửa file, giải quyết bất đồng | Bí ý tưởng, cần root-cause/plan |
| `paseo-help` | 92 | Trả lời về sản phẩm Paseo: docs, topology, diagnostic, log, escalate | Debug Paseo |
| `paseo-plugin` | 766 | Viết/quản lý plugin Paseo: screen, panel, command, timeline, theme, RPC | Phát triển plugin (hh-tree) |

Bằng chứng: `P/server/dist/server/skills/<tên>/SKILL.md`; số dòng lấy từ `wc -l`.

Chi tiết đáng chú ý:

- **`paseo`**: chia section rõ: Connected hosts (dòng 8–27), Projects (29–41), Workspaces (43–55), Workspace scripts (57–73), Agents (75–94), Agent profiles & provider discovery (95–116), Schedules/heartbeats (118–126), Waiting (128–132), CLI semantics (134–150). Điểm quan trọng: agent-scoped `create_agent` mặc định tạo subagent; `send_agent_prompt` mặc định `steer` cho agent-scoped, `interrupt` cho top-level; `notifyOnFinish` mặc định true cho agent-scoped (dòng 75–93).
- **`paseo-handoff`**: yêu cầu đọc `paseo`, gọi `list_profiles`, chọn profile theo `notes`; brief phải tự chứa vì agent nhận “zero context”; template 8 phần (dòng 25–51); launch bằng `create_agent`, không poll (dòng 55–65). Đây là bản gần nhất với brief brain→hand hiện tại.
- **`paseo-advisor`**: một agent, briefing tự chứa, luôn kết thúc bằng câu cấm sửa file (dòng 26–39); nếu user gọi skill lồng nhau (`/unslop`, `$diagnose`), advisor phải tự load skill đó (dòng 41–57); có thể giữ advisor cho nhiều quyết định (dòng 63–65).
- **`paseo-committee`**: hai agent khác provider family, cùng prompt, chạy song song; cấm sửa file; không poll, có thể chờ 15–30 phút; truyền lập luận qua lại đến khi hội tụ (dòng 28–46).
- **`paseo-help`**: fetch `https://paseo.sh/llms.txt` trước, chọn trang docs; xác định topology (desktop-managed/standalone/Docker) trước khi chẩn đoán; lệnh đọc `paseo daemon status --json`, `paseo provider diagnostic`; log path; escalation GitHub/Discord (dòng 12–92). Skill này cần mạng; nếu offline thì chỉ dùng phần topology/log trong skill.
- **`paseo-plugin`**: không phải orchestration thuần; dạy viết plugin (screen, workspace panel, command center, slash command, timeline, theme, RPC), và các bước publish/typecheck. Hữu ích cho hh-tree nhưng rất dài (766 dòng), chỉ nên invoke khi thật sự sửa plugin.

### 8.2 Cài vào đâu

`resolveSkillTargets(home = os.homedir())` (`P/server/dist/server/server/orchestration-skills/internal/paths.js:12-19`):

| Đích | Đường dẫn | Cách ghi |
|---|---|---|
| Claude Code | `~/.claude/skills/<skill>` | `syncDirectoryFiles` |
| Codex | `~/.agents/skills/<skill>` | `syncDirectoryFiles`; Codex đọc `.agents/skills` |
| Các agent khác đọc chuẩn `.agents/skills` (nếu hỗ trợ) | `~/.agents/skills/<skill>` | `syncDirectoryFiles` |
| Codex legacy | `~/.codex/skills/<skill>` | Chỉ dọn copy cũ; không tạo mới |

Bằng chứng:

- Nguồn bundle: `resolveBundledSkillsDir()` trỏ tới `dist/server/skills` (`paths.js:4-11`).
- `agentsDir = ~/.agents/skills`, `claudeDir = ~/.claude/skills`, `codexDir = ~/.codex/skills` (`paths.js:15-18`).
- Sync ghi `agentsDir` và `claudeDir`; nếu `codexDir` là copy legacy tách biệt thì `retireManagedSkill` dọn nó (`P/server/dist/server/server/orchestration-skills/internal/sync.js:202-213`).
- Comment nói rõ Codex cũng discover `.agents/skills`, nên bản copy riêng ở `.codex/skills` là leftover (`sync.js:157-162`).
- `removeSkill` xoá cả ba đường dẫn bằng `fs.rm(..., { recursive: true, force: true })` (`sync.js:145-151`).

Lưu ý: `~` là home của **process daemon**, không phải home của client. Nếu daemon chạy trong Docker/remote SSH, skill được cài trong container/máy remote; app desktop/điện thoại chỉ điều khiển từ xa.

### 8.3 Vòng đời: status, install, update, uninstall, selection

- Selection mặc định `{ mode: "all" }` (`P/server/dist/server/server/orchestration-skills/internal/selection-store.js:1`), nhưng chỉ có hiệu lực khi thực sự chạy install/reconcile.
- Trạng thái: `not-installed` nếu không có skill Paseo nào trên đĩa; `up-to-date` nếu không có op; `drift` nếu có op (`operations.js:105-134`).
- **Install/Update**: UI “Install”/“Update” gọi `updateSkills` (qua `reconcile`), hàm này lọc bỏ `delete` và chỉ áp dụng `add`/`update` (`operations.js:161-180`). Riêng `installSkills` có thể nhận một plan đã có `delete` nếu caller truyền vào, nhưng UI không đi đường đó.
- **Uninstall**: xoá mọi tên managed (gồm cả legacy `paseo-chat`, `paseo-epic`, `paseo-orchestrate`, `paseo-orchestrator`) khỏi cả ba thư mục (`operations.js:7-12, 181-188`).
- **Save selection**: áp dụng đúng plan, gồm cả `delete`; nếu plan có xoá mà chưa được xác nhận, trả `confirmationRequired` và không làm gì (`P/server/dist/server/server/orchestration-skills/internal/controller.js:30-45`). UI hiện cảnh báo “Anything you added inside those skill folders is deleted too.”
- **Auto-update lúc khởi động**: `bootstrap` gọi `orchestrationSkills.autoUpdate()` (`bootstrap.js:383-385`); hàm này chỉ sửa `drift`, không xoá, và **không cài mới** nếu state là `not-installed` (`operations.js:173-180`). Vì vậy daemon mới không tự cài skill; người dùng phải bấm Install.
- **Transaction/rollback**: trước khi save, `beginSkillsTransaction` backup các thư mục skill, kể cả file người dùng thêm; lỗi thì rollback, recovery xử lý transaction dở dang (`P/server/dist/server/server/orchestration-skills/internal/transaction.js:341-385`). Tuy nhiên, khi xoá thành công thì `removeSkill` xoá cả thư mục, không chỉ file manifest.
- **Ghi đè file trùng tên**: `syncDirectoryFiles` ghi mọi file bundle vào đích, nên file người dùng sửa cùng tên sẽ bị ghi đè khi update (`sync.js:108-145`). File người dùng thêm với tên khác được giữ khi update, nhưng bị xoá khi uninstall/deselect.

UI strings xác nhận:

- “Teach your agents to orchestrate through the CLI”
- “Removes all Paseo orchestration skills from ~/.agents, ~/.claude, ~/.codex on this host.”
- “Keep every bundled skill installed, including ones added later.”
- “Anything you added inside those skill folders is deleted too.”
(`W @5881500-5884500`)

### 8.4 Cơ chế agent điều khiển agent khác

Đây là phần cốt lõi: **skill không tự chạy**. Nó chỉ dạy agent gọi tool/CLI; quyền thực thi đến từ MCP server hoặc CLI.

#### Đường MCP (khi `Enable Paseo tools = true`)

1. Daemon chèn MCP server `paseo` vào agent, URL `/mcp/agents?callerAgentId=<id>` (`runtime-mcp-config.js:2,23-40`).
2. Agent gọi các tool như `create_agent`, `send_agent_prompt`, `list_agents`, `get_agent_status`, `get_agent_activity`, `update_agent`, `cancel_agent`, `archive_agent`.
3. `create_agent` tạo agent mới trong daemon; nếu gọi từ agent khác, `resolveCreateAgentIntent` gắn label `paseo.parent-agent-id = caller.id` (`P/server/dist/server/server/agent/create-agent/intent.js:1-16`; hằng số `P/protocol/dist/agent-labels.js:2`).
4. Agent con xuất hiện trong “subagents track” của UI; detach là thao tác người dùng, không phải tool (`paseo/SKILL.md:81-85`).
5. `send_agent_prompt` đưa message vào hàng đợi; agent-scoped nhận receipt ngay, delivery sau **2 giây yên tĩnh** (`P/server/dist/server/server/agent/agent-messages/delivery.js:108`; `paseo-tools.js:1421-1505`).
6. `notifyOnFinish` đăng ký finish subscription; khi con xong/lỗi/cần permission, daemon gửi notification kèm last response cho cha (`paseo-tools.js:1431-1470`; `agent/finish-subscriptions`). Vì vậy skill nói “đừng poll, hãy chờ notification” (`paseo/SKILL.md:128-132`).
7. `activeTurnBehavior`: agent-scoped mặc định `steer`; top-level mặc định `interrupt` (`paseo-tools.js:1431`). `agent-prompt.js` xử lý steer, fallback replace, reload session stale, out-of-band command (`/goal pause`) (`P/server/dist/server/server/agent/agent-prompt.js:4-62`).
8. Cross-host: các tool host-aware nhận `serverId`; `list_hosts` liệt kê host đích (`paseo-tools.js:395-420`; `paseo/SKILL.md:10-27`).

#### Đường CLI (khi agent không có MCP tools)

Skill `paseo` đưa ví dụ CLI tương đương (`paseo/SKILL.md:134-150`):

```bash
paseo run --provider codex/gpt-5.4 --mode full-access --workspace <workspace-id> "<prompt>"
paseo send <agent-id> "<follow-up>"
paseo ls
paseo schedule create --cron "*/15 * * * *" "ping main build"
```

CLI và MCP dùng cùng daemon API/ownership semantics. Với agent terminal hiện tại, đây là đường khả thi nhất: cài skill vào `~/.claude/skills`, để brain gọi `paseo` CLI; nhưng brain sẽ **không** nhận `notifyOnFinish` vì nó không phải Paseo agent cha.

#### Ví dụ luồng handoff

1. Brain đọc `paseo-handoff`, gọi `list_profiles`.
2. Chọn profile theo `notes`, materialize thành `provider/model` + `settings`.
3. Nếu cần worktree, gọi `create_workspace` trước.
4. Gọi `create_agent` với title `[Handoff] <task>`, brief tự chứa, `workspaceId` nếu cần.
5. Nhận `agentId`; con nằm trong subagent track; brain kết thúc turn và chờ notification.
6. Con xong → finish subscription gửi last response; brain tổng hợp báo cáo.

Đây chính là mô hình brain/hand, nhưng thay vì `hand-ext`/`screen`/`report.md`, Paseo quản lý process, identity, trạng thái và notification.

### 8.5 Khác gì với brain/hand/phiên phụ hiện tại

| Khía cạnh | Cách đang làm | Paseo orchestration |
|---|---|---|
| Process | `hand-ext` spawn dsh/opencode; side-session chạy `screen` | Daemon quản lý agent session, provider process do daemon mở |
| Identity | PID/screen name/tên file report | `agentId`, `workspaceId`, label `paseo.parent-agent-id` |
| Cây phiên | `hh-ps` đọc process/screen để in cây | `list_agents` + subagent track trong UI |
| Giao việc | Brief file/stdin, `hand-ext` | `create_agent` + `send_agent_prompt`, queue 2 giây |
| Theo dõi | `hh-ps`, terminal, report.md | UI desktop/phone, timeline, status, activity |
| Hoàn thành | Hand ghi report, brain poll/đọc file | Finish subscription đẩy last response cho cha |
| Restart | `screen` giữ process; không có resume cấp daemon | `Resume agents after restart` (host-wide) |
| Idle | Process vẫn sống | `Release idle agents` đóng process, giữ conversation |
| Danh tính/khám phá | Không có registry | `list_agents`, `get_agent_status`, `get_agent_activity` |
| Bảo mật | Cùng user OS, không có tuyến kiểm soát trung tâm | MCP token + policy, nhưng tool rất rộng |
| Giới hạn | Không cần Paseo | Không thấy tiến trình terminal có sẵn; import chỉ là provider session |

Điểm quan trọng cho NGỮ CẢNH:

- **Paseo không tự “nhìn thấy” brain terminal, hand-ext, hay screen hiện tại**. Nó chỉ quản lý agent do nó tạo/import. Không có code path nào attach vào stdin/stdout của một process terminal đang chạy (suy luận từ kiến trúc: `AgentManager` chỉ thao tác trên `this.agents`; import tạo record từ provider session handle, `P/server/dist/server/server/agent/import-sessions.js:87-150`).
- **Finish notification chỉ đến Paseo caller agent**. Brain terminal không phải caller agent, nên dù gọi CLI `paseo run`, nó không nhận notification trừ khi tự poll `paseo ls`/status.
- **`screen` và Paseo resume khác nhau**: `screen` giữ process qua terminal disconnect; Paseo resume mở lại session sau daemon restart, nhưng cần setting + record. Cái này không thay thế `screen` cho process không phải agent Paseo.
- **`hh-ps` có thể vẫn cần** cho các phiên ngoài; nếu muốn hợp nhất, phải chuyển brain/hand vào Paseo hoặc viết plugin đọc process (hh-tree) — plugin đang tắt vì `pluginsEnabled: false`.

### 8.6 Rủi ro và đề xuất cho skills

- **Rủi ro filesystem**: uninstall/deselect xoá cả thư mục skill, gồm file người dùng thêm; UI có cảnh báo nhưng thao tác là thật. Không đặt file cá nhân trong `~/.claude/skills/<paseo-skill>` hoặc `~/.agents/skills/<paseo-skill>`.
- **Rủi ro ghi đè**: update ghi đè file trùng tên trong skill folder; đừng sửa trực tiếp file bundle, hãy copy ra ngoài.
- **Rủi ro supply chain**: skill là text hướng dẫn agent tạo agent/gọi tool; nếu bundle bị thay đổi, agent có thể bị dụ làm việc ngoài ý. Chỉ cài từ package chính thức.
- **Rủi ro token**: `paseo` (152 dòng) và `paseo-plugin` (766 dòng) khá dài khi invoke; frontmatter description được nạp sớm, body chỉ nạp khi gọi (suy luận theo chuẩn progressive disclosure của Claude Code/Codex).
- **Rủi ro mạng**: `paseo-help` fetch docs; trong môi trường offline sẽ fail. Không ảnh hưởng skill khác.
- **Đề xuất**:
  - Cài `mode: "all"` nếu muốn nhận skill mới; hoặc `custom` gồm 5 skill (`paseo`, `paseo-handoff`, `paseo-advisor`, `paseo-committee`, `paseo-help`) và thêm `paseo-plugin` khi sửa hh-tree.
  - Với brain terminal: cài vào `~/.claude/skills` là hữu ích, nhưng phải có `paseo` CLI trong PATH hoặc MCP server riêng. Nếu không, skill sẽ hướng dẫn gọi tool mà không có tool.
  - Với hand Paseo: cài `~/.agents/skills` + `~/.claude/skills`; bật `Enable Paseo tools`; kiểm tra `list_profiles` trước khi dùng handoff.

### 8.7 Cầu nối cho các phiên terminal hiện có (ngoài nhóm Agents)

Ba tính năng dưới đây không nằm trong trang Agents nhưng là các đường thực tế để đưa phiên terminal/screen hiện tại vào tầm nhìn của Paseo:

- **Terminal agent hooks** — `Settings → host → Terminals → Terminal agents`; khoá `daemon.enableTerminalAgentHooks` (mặc định `false`; `persisted-config.js:231`, `config.js:429`). UI nói: “Get notifications and status from terminal agents. This installs hooks in your agent config files.” (`W @23644188`). Installer ghi hook vào `~/.claude/settings.json` cho Claude (events `UserPromptSubmit`, `Stop`, `StopFailure`, `SessionEnd`, `Notification`), và config tương tự cho Codex/OpenCode (`P/server/dist/server/terminal/agent-hooks/claude/claude.js:1-30`; `provider-registry.js:13-40`; `agent-hook-installer.js:36-40`). Hook chỉ chạy khi có `PASEO_TERMINAL_ID`, tức terminal do Paseo mở; **không biến terminal bên ngoài thành agent điều khiển được**. Đây là cách nhẹ nhất để có status/notification cho brain terminal nếu brain được chạy trong terminal của Paseo.
- **Import session** — Paseo có thể import một provider session theo `providerHandleId` + `cwd` để tạo agent record (`P/server/dist/server/server/agent/import-sessions.js:87-150`). Đây là import lịch sử/khôi phục record, không phải attach vào stdin/stdout của process đang chạy; nên import sau khi phiên terminal kết thúc (suy luận từ kiến trúc).
- **Plugin hh-tree** — cần `pluginsEnabled: true` (mặc định `false`, `P/server/dist/server/server/config.js:431`). Plugin chạy code trong daemon/client nên phải audit trước; đây là đường duy nhất có thể tự vẽ cây phiên ngoài nếu plugin đọc process/screen.
- **Điện thoại** — daemon đang nghe `127.0.0.1:6767`; điện thoại không vào được nếu không bật relay/Tailscale/SSH. Đây là vấn đề kết nối, không phải setting Agents.

## 9. Agent attention policy và prompt dispatch (phần phụ trợ)

### 9.1 Attention policy

`agent-attention-policy.js` quyết định notification đi đâu:

- `PRESENCE_THRESHOLD_MS = 180000` (3 phút) (`P/server/dist/server/server/agent-attention-policy.js:1`).
- Một client được coi là “present” nếu `lastActivityAt` trong vòng 3 phút (`agent-attention-policy.js:14-19`).
- Nếu có client present, `appVisible` và đang focus đúng agent/terminal → **không gửi in-app, không push** (`agent-attention-policy.js:20-22`).
- Nếu có present nhưng không focus → chọn client present gần nhất để gửi in-app, **không push** (`agent-attention-policy.js:23-30`).
- Nếu không có present → push nếu `pushEligible` (`agent-attention-policy.js:31`).
- `isPushEligibleAttentionReason(reason)` trả `reason !== "error"` (`agent-attention-policy.js:33-35`), nghĩa là **lỗi không push**, chỉ in-app (nếu có client present). Terminal attention luôn `pushEligible: true` (`P/server/dist/server/server/websocket-server.js:2224-2237`); agent attention dùng hàm trên (`websocket-server.js:2154-2168`).

Hệ quả cho monitoring từ điện thoại: nếu desktop Paseo đang mở và focus đúng agent, điện thoại sẽ không rung; nếu có bất kỳ client nào active trong 3 phút, push bị chặn và chỉ in-app. Muốn test push, đóng/không focus app desktop hoặc chờ quá 3 phút.

### 9.2 Prompt dispatch

- `send_agent_prompt` agent-scoped mặc định `notifyOnFinish = true`, `activeTurnBehavior = "steer"`; top-level mặc định `notifyOnFinish = false`, `activeTurnBehavior = "interrupt"` (`P/server/dist/server/server/agent/tools/paseo-tools.js:1431`).
- Steer: cố gắng đưa message vào turn đang chạy; nếu không được thì replace turn (`agent/agent-prompt.js:4-19`).
- Interrupt: `startOrReplaceRun` với `replaceRunning: true`, replace run đang chạy (`agent-prompt.js:20-26`; `sendPreparedPromptToAgent` luôn `replaceRunning: true`, dòng 209-215).
- Message agent-to-agent vào hàng đợi, gộp theo recipient, chờ 2 giây yên tĩnh rồi dispatch (`agent/agent-messages/delivery.js:108`).
- Agent archived: nếu `unarchive: false` thì silently no-op; tool gửi mặc định unarchive (`agent-prompt.js:164-166, 180-190`).
- Provider session stale: tự reload từ persistence rồi retry một lần (`agent-prompt.js:50-62`; `startAgentRunInner` 86-93).
- Out-of-band command (`/goal pause`) được intercept trước khi cancel turn (`agent-prompt.js:43-49`).
- `waitForAgentRunStartWithTimeout` 60 giây (`agent-prompt.js:136-149`).

Phần này giải thích tại sao “gửi prompt” có thể steer, interrupt, queue, hoặc không làm gì (archived), và tại sao notification có thể không đến điện thoại.

## 10. Phụ lục: ánh xạ nhanh UI ↔ config ↔ file

| UI | Config | File xử lý chính |
|---|---|---|
| Enable Paseo tools | `daemon.mcp.injectIntoAgents` | `bootstrap.js:1327-1337`, `runtime-mcp-config.js:23-40` |
| Browser tools | `daemon.browserTools.enabled` | `browser-tools/policy.js`, `browser-tools/tools.js`, `browser-tools/broker.js` |
| System prompt | `daemon.appendSystemPrompt` | `agent-manager.js:3943-3968`, `system-prompt.js` |
| Resume | `agents.resumeOnStartup`, `agents.resumePrompt` | `agent/restart-recovery/index.js`, `bootstrap.js:712-724` |
| Release idle | `agents.idleRuntimeCleanup` | `agent/idle-runtime-cleanup/index.js`, `agent-manager.js:1103-1154` |
| Agent profiles | `daemon.agentProfiles` | `protocol/agent-profile.js`, `paseo-tools.js:2292-2311` |
| Skills selection | `agents.skills.selection` | `orchestration-skills/**`, `session.js:1599-1630` |
| Skills files | — | `~/.agents/skills`, `~/.claude/skills`; legacy `~/.codex/skills` |

## 11. Bảng tổng hợp đề xuất

| Tính năng | Đề xuất | Giá trị / cách làm | Lý do |
|---|---|---|---|
| Resume agents after restart | Bật sau, không bật ngay | `agents.resumeOnStartup: true`; prompt kiểm tra trạng thái | Tránh lặp side effect khi hand đang dở; chỉ có lợi khi agent do Paseo quản lý |
| Release idle agents | Bật | `agents.idleRuntimeCleanup: true` (mặc định) | Giảm RAM; giữ conversation; 60 phút là hợp lý |
| Enable Paseo tools | Bật cho agent Paseo tin cậy | `daemon.mcp.injectIntoAgents: true`; cân nhắc `disabledTools` | Cần để brain Paseo điều khiển hand; không ảnh hưởng brain terminal |
| Browser tools | Tắt mặc định | `daemon.browserTools.enabled: false` | Rủi ro tab đăng nhập, prompt injection, JS eval |
| System prompt | Đặt ngắn | 3–6 dòng quy ước báo cáo/không commit | Áp dụng mọi agent; tránh brief dài |
| Agent profiles | Tạo 3 profile | Brain / Hand / Reviewer, notes rõ | Chuẩn hoá chọn provider/model; hỗ trợ handoff |
| Orchestration skills | Cài `all` hoặc 5 skill | `agents.skills.selection: {mode:"all"}` | Có sẵn hướng dẫn; `paseo-plugin` chỉ khi sửa plugin |
| Terminal agent hooks | Bật nếu cần theo dõi brain terminal | Settings → Terminals → Terminal agents | Nhận status/notification từ Claude Code terminal; không phải Agents |
| Plugins (hh-tree) | Audit rồi bật | `pluginsEnabled: true` | Plugin chạy code trên daemon; cần tin cậy |
| Phone connectivity | Cấu hình riêng | Relay/Tailscale/SSH; không chỉ setting Agents | Daemon đang nghe `127.0.0.1:6767`; điện thoại không vào được nếu không mở đường |

### 11.1 Gợi ý cấu hình (chỉ để tham khảo, không tự sửa)

```json
{
  "daemon": {
    "mcp": { "enabled": true, "injectIntoAgents": true },
    "browserTools": { "enabled": false },
    "appendSystemPrompt": "You are a hand in a brain/hand workflow. Work only within the brief. Report result, files changed (path:line), verification commands and real results, and open issues. Never commit, push, or read secrets.",
    "agentProfiles": [
      {
        "id": "brain",
        "name": "Brain",
        "provider": "claude",
        "model": "<model-id>",
        "modeId": "plan",
        "notes": "Orchestrates work, writes briefs, does not edit code."
      },
      {
        "id": "hand",
        "name": "Hand",
        "provider": "opencode",
        "model": "<model-id>",
        "modeId": "full-access",
        "notes": "Executes a self-contained brief and reports back with evidence."
      },
      {
        "id": "reviewer",
        "name": "Reviewer",
        "provider": "codex",
        "model": "<model-id>",
        "modeId": "read-only",
        "notes": "Independent review only; never edits files."
      }
    ]
  },
  "agents": {
    "resumeOnStartup": false,
    "resumePrompt": "Resume working. First inspect the workspace and git status; do not repeat steps that already completed.",
    "idleRuntimeCleanup": true,
    "skills": { "selection": { "mode": "all" } }
  }
}
```

Các `<model-id>` và `modeId` phải lấy từ `paseo provider`/`list_models` của host; không đoán. Ví dụ `plan`/`full-access`/`read-only` chỉ là minh hoạ, có thể khác theo provider.

## 12. Câu hỏi còn mở

1. Người dùng muốn Paseo **sở hữu** brain/hand mới, hay chỉ **quan sát** các phiên terminal/screen hiện có? Hai hướng dùng tính năng khác nhau hoàn toàn.
2. Có sẵn sàng chuyển brain khỏi terminal sang Paseo agent không? Nếu không, `Resume`/`Release idle`/`Enable Paseo tools` gần như không tác động brain hiện tại.
3. Provider/model nào đang có trên host? Cần `list_providers`/`list_models` để điền Agent profiles chính xác.
4. Phiên bản Claude Code trên máy có >= 2.1.292 không? Nếu không, `Release idle` có thể không bao giờ đóng runtime Claude.
5. `pluginsEnabled` có được bật không, và hh-tree đã được audit chưa? Plugin chạy code trên daemon/client, rủi ro cao hơn skill.
6. Có cần điện thoại truy cập trực tiếp không? Daemon đang `127.0.0.1:6767`; cần relay/Tailscale/SSH và cân nhắc bảo mật.
7. Có muốn dùng `Enable terminal agent hooks` (Settings → Terminals) để lấy status từ brain terminal không? Nó sửa `~/.claude/settings.json` (và config Codex/OpenCode), không chỉ là setting Paseo.
8. Có cần `paseo-plugin` skill thường trực không, hay chỉ khi sửa hh-tree? Cài tất cả thì tiện nhưng tăng bề mặt skill dài.
9. Có chấp nhận `Resume` tự chạy lại turn dở không? Nếu hand có side effect (commit, gọi API, gửi tin), nên mặc định tắt hoặc dùng prompt kiểm tra.
10. Có muốn import các phiên Claude Code đã kết thúc vào Paseo để xem timeline không? Import dựa trên provider session handle, không phải attach process đang chạy; cần kiểm tra provider hỗ trợ.
