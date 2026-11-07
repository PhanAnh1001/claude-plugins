---
name: paseo
description: Dùng Paseo (daemon + CLI + app điện thoại) để theo dõi và điều khiển phiên brain/hand từ xa - cài đặt, khởi và dừng daemon, ghép điện thoại (người dùng tự làm), chạy hand Codex với CODEX_HOME riêng (~/.codex-hand, đăng nhập gói ChatGPT, không API key) qua provider tuỳ biến, theo dõi bằng ls/logs/wait/send, và giới hạn (phiên claude mở ngoài Paseo không tự hiện). Từ khoá kích hoạt - "paseo", "điện thoại", "theo dõi phiên", "điều khiển từ xa", "ghép điện thoại", "pair", "xem hand trên điện thoại", "daemon paseo".
---

## Ngoại lệ Sol native trên Paseo — 0.27.0 (quyết định A)

Theo [policy đầy đủ ở ext-hand](../ext-hand/SKILL.md), ưu tiên tab native chỉ cho Sol trên Paseo khi backend thực theo `ext_hand.order` là codex `gpt-6.1-sol` low và tools chọn được model/effort riêng; giữ `fork_turns=none`, full brief/luật dữ liệu, executor không recursion, tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4), cùng file/phụ thuộc tuần tự. Không áp cho Opus/Claude/dsh hay executor, không đổi code/slots hand-ext, bật parallel-subagents hay sửa config. Thiếu capability trước spawn hoặc backend khác thì fallback `hand-ext run --backend auto`; unknown sau spawn phải xác minh child, không tạo duplicate writer. Native dùng báo cáo/usage native/Paseo, không có ledger hand-ext; thiếu hiện `?`, không bịa quota. Trên điện thoại đã kết nối Paseo, mở Sol rồi bấm tab child; completed giữ tab/history, không archive top-level/parent, không cần pairing/config mới. Hand-ext shell không tự hiện hội thoại; A đã đạt nên B (agent ngang hàng/archive) chưa triển khai.

### Kiểm chứng bridge read-only

Gửi một JSON qua stdin cho `node "${CLAUDE_PLUGIN_ROOT}/lib/side_session/paseo_bridge.mjs" "<thư-mục-gói-@getpaseo/cli-0.15.0>"`. Hai request mẫu dưới đây dùng placeholder, không chứa credential; chỉ dùng với phiên/fixture được phép đọc:

```json
{"command":"subagents","agentId":"<parent-agent-id>","expectedTargetKey":"<targetKey-đã-lưu>"}
```

```json
{"command":"subagent-timeline","agentId":"<parent-agent-id>","subagentId":"<child-id-từ-subagents>","expectedTargetKey":"<targetKey-đã-lưu>"}
```

`agentId` là parent Sol trong Paseo; lấy `subagentId` từ danh sách child của parent đó. Dùng `expectedTargetKey` từ state/metadata endpoint đã lưu để chặn nhầm daemon (`TARGET_CHANGED`); không lấy từ credential. Đối chiếu `parentAgentId` và `subagents[].parentAgentId` với parent, rồi `subagentId` và `rows` của timeline để xác minh history. Hai command chỉ đọc, không tạo/gửi prompt/cancel/archive agent. Probe local Codex CLI 0.166.0 + Paseo CLI 0.15.0 đã xác minh child `completed` đúng parent và timeline 3 dòng assistant; nếu unknown thì giữ child hiện có để xác minh, không spawn lại.

## Usage panel 0.26.0

`hh-ps --once` chạy một lần; `--json` giữ dữ liệu máy đọc, `--watch 5` theo dõi. Mặc định hiện đủ việc chạy/vừa xong theo `--since`, không gấp còn 3 việc và không ẩn cây đã xong (`--full`/`--ended` giữ tương thích). Mỗi dòng session/subagent/hand và phiên phụ mọi provider/backend có model, effort, USD~, quota tài khoản 5h/tuần, ended hoặc `đang chạy`, elapsed. Elapsed đang chạy tăng theo thời gian; ended cố định duration khi xong. Không hiện giờ bắt đầu trong text/panel/statusline; metadata/JSON vẫn giữ started. Thiếu nguồn hoặc legacy unknown hiện `?`, không bịa.

Giá chỉ từ [`config/model-prices.json`](../../config/model-prices.json), override bằng `HYBRID_HANDS_PRICING_FILE`; mỗi entry có source/price_date, file có verified_at. Mọi USD~ là ước tính offline trên gói subscription, không phải hoá đơn. Cache Claude dùng đúng giá cấu hình 5m/1h; không fallback theo họ/model khác. Nguồn giá công khai được xác minh ngày 2026-11-07 và lưu trong file canonical. Giá DeepSeek peak là ước tính bảo thủ. Không thêm bảng giá backend thứ hai.

Quota tài khoản lấy từ cache/sample sẵn có của đúng gói; thiếu 5h/tuần hiện `?`, tuyệt đối không suy token hay USD thành quota GPT. Phần riêng hand tuần chỉ thêm khi có nguồn và gắn nhãn riêng. Cả hai giao diện cây `hh-tree-pane` và `paseo-hh-tree` không hiện nhóm orphan hand-ext; `hh-ps` text/JSON vẫn giữ orphan.

Metadata mới giữ parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. `CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn đúng cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Sol Codex/Claude/dsh và mọi loại agent/backend. Hand nhận brief trực tiếp là executor: làm trong phạm vi được giao, không gọi hand-ext, không mở side-session hay giao tiếp phiên khác. Luật Sol bắt buộc delegate chỉ áp dụng vai trò Sol; dùng `hand-ext run --backend auto` trừ ngoại lệ native trên Paseo nêu trên.



# Paseo: theo dõi và điều khiển phiên từ điện thoại

## Tóm tắt

- **Là gì:** Paseo là daemon cục bộ + CLI + app (điện thoại, desktop, web) để chạy và điều khiển agent Claude Code, Codex... dùng lại đăng nhập sẵn có của từng CLI; Apache-2.0, bản dùng ở đây **0.15.0** (npm `latest` 04/11/2026) ([repo](https://github.com/getpaseo/paseo), 11/2026; [docs](https://paseo.sh/docs), 11/2026).
- **Đã cài:** `npm install -g @getpaseo/cli@0.15.0`, `paseo --version` in `0.15.0` (kiểm trên máy 04/11/2026).
- **Daemon:** `paseo start` chạy nền, nghe `127.0.0.1:6767`, cấu hình ở `~/.paseo/config.json`; relay (để điện thoại kết nối qua internet) **tắt mặc định**. Không thấy cơ chế tự khởi động khi đăng nhập máy.
- **Hand Codex riêng:** khai provider tuỳ biến `codex-hand` (`extends: "codex"`, `env.CODEX_HOME`) trong config, `paseo reload`, rồi `paseo run --provider codex-hand ...`; hoặc một lần bằng `paseo run --provider codex --env CODEX_HOME=...`.
- **Giới hạn chính:** chỉ agent do Paseo tạo (hoặc `paseo import <session-id>`) mới hiện; phiên `claude` brain đang chạy trong terminal và phiên `screen` **fallback** của side-session **không tự hiện** (đã kiểm: `paseo ls -a -g` rỗng khi có phiên claude đang mở). Side-session Codex đi đường daemon thì agent do Paseo sở hữu nên hiện ngay, không cần screen.
- **Chuyển phiên terminal ↔ Paseo:** dùng `cc-switch term|paseo|status` (README hybrid-hands mục 7); trong phiên TUI đang mở thì `cc-switch paseo --self` (brain chạy ở lượt cuối); reload/import trước khi gửi tin để transcript không rẽ nhánh.
- **Người dùng phải tự làm:** bật relay, quét QR trên điện thoại, cài app; agent không ghép điện thoại hộ, không ghi `~/.paseo/config.json` khi chưa được duyệt.

## 1. Cài đặt và phiên bản

- Cài ghim bản: `npm install -g @getpaseo/cli@0.15.0` ([docs](https://paseo.sh/docs), 11/2026). Kiểm: `paseo --version`.
- npm 11 bỏ qua install script của `node-pty`, `esbuild`, `msgpackr-extract` (cảnh báo `allow-scripts` khi cài, 04/11/2026). Daemon và CLI vẫn chạy; nếu terminal trong app lỗi thì cài lại kèm `--allow-scripts=esbuild,node-pty,msgpackr-extract` (người dùng quyết).
- Paseo dùng `codex`, `claude` có trên `PATH` của daemon; kiểm bằng `paseo provider diagnostic codex` (trên máy: `/Users/anhtp/.local/bin/codex`, `codex-cli 0.150.1`, Status Ready) ([docs Codex](https://paseo.sh/docs/codex), 11/2026).

## 2. Daemon

- **Khởi:** `paseo start` (đọc `~/.paseo/config.json`, tự tạo nếu chưa có), in PID, địa chỉ nghe và đường log. `paseo onboard` = cài đặt lần đầu + khởi daemon + in hướng dẫn ghép (`--port` mặc định 6767, `--relay`/`--no-relay`, `--no-mcp`) (`paseo onboard --help`, 0.15.0).
- **Xem/dừng:** `paseo status` (dòng `localDaemon: running|stopped`), `paseo daemon stop`, `paseo daemon restart` (cần sau khi đổi `daemon.listen`), `paseo reload` (đọc lại config, đủ cho đổi provider) ([connectivity](https://paseo.sh/docs/connectivity), 11/2026; [custom providers](https://paseo.sh/docs/custom-providers), 11/2026).
- **Cổng:** `127.0.0.1:6767`; config mặc định sinh ra có `daemon.relay.enabled: false`, CORS cho `https://app.paseo.sh` (đã kiểm với `--home` tạm 04/11/2026).
- **Thử không đụng config thật:** mọi lệnh nhận `--home <dir>`; dùng thư mục tạm để thử rồi `paseo daemon stop --home <dir>`.
- **Tự khởi động:** docs không nói daemon CLI tự chạy khi đăng nhập; app desktop thì tự khởi daemon kèm theo ([docs](https://paseo.sh/docs), 11/2026). Muốn luôn chạy thì người dùng tự thêm (ví dụ launchd) — chưa làm.

## 3. Ghép điện thoại (người dùng tự làm)

Agent chỉ được nhắc các bước, không chạy hộ (bật relay mở đường vào máy từ internet).

1. Cài app Paseo trên điện thoại (link tải ở [paseo.sh](https://paseo.sh), 11/2026).
2. Trên Mac: `paseo daemon pair` (hoặc `paseo pair --relay` để bật relay không hỏi); xác nhận bật relay — traffic relay mã hoá đầu-cuối ([connectivity](https://paseo.sh/docs/connectivity), 11/2026).
3. Trên điện thoại: quét QR, hoặc "Paste pairing link" dán link CLI in ra.
4. Không muốn relay: cho điện thoại vào cùng Tailscale, đặt `daemon.listen` thành IP Tailscale (`tailscale ip -4`) + `:6767`, `paseo daemon restart`; có thể đặt mật khẩu `paseo daemon set-password` ([connectivity](https://paseo.sh/docs/connectivity), 11/2026).

## 4. Chạy hand Codex với CODEX_HOME riêng

Paseo dùng lại đăng nhập gói của CLI, không cần API key. Tình trạng từ 07/11/2026: `~/.codex` là tài khoản free cũ đã tạm tắt; `~/.paseo/config.json` đã có `agents.providers.codex={enabled:false}`; hand Codex dùng `~/.codex-hand` (gói ChatGPT riêng cho hand, cùng thư mục với backend `codex` của `hand-ext`).

- **Cách đang dùng — provider tuỳ biến** (`~/.paseo/config.json` đã có `agents.providers.codex={enabled:false}` từ 07/11/2026; provider `codex-hand` dùng `~/.codex-hand`, đổi config thì `paseo reload`) ([custom providers](https://paseo.sh/docs/custom-providers), 11/2026):

```json
{
  "agents": {
    "providers": {
      "codex": { "enabled": false },
      "codex-hand": {
        "extends": "codex",
        "label": "Codex hand (gói ChatGPT)",
        "env": { "CODEX_HOME": "/Users/anhtp/.codex-hand" },
        "models": [
          { "id": "gpt-6.1-sol", "label": "GPT-6.1 Sol", "isDefault": true }
        ]
      }
    }
  }
}
```

  Rồi: `paseo provider models codex-hand` (kiểm model), `paseo run --provider codex-hand --title hand-x --no-wait "$(cat brief.md)"`. `codex: {enabled: false}` tắt provider `codex` mặc định (`~/.codex`) toàn cục; vẫn dùng `codex-hand` (kế thừa `codex` qua `extends`) với tài khoản `~/.codex-hand`. Không sửa config thật khi chưa được duyệt.
- **Cấu hình model:** đặt `model` mặc định trong `~/.codex-hand/config.toml` (`hand-ext setup --backend codex` ghi sẵn; CODEX_HOME riêng nên không ảnh hưởng `~/.codex`). Trường `command` của provider thay toàn bộ lệnh khởi nhưng Paseo tự thêm subcommand nên chèn profile `-p` **chưa kiểm**, đừng dùng khi chưa thử.
- **% tuần sống cho phiên Paseo:** thêm provider `claude-tee` (`extends: "claude"`, `command` trỏ tuyệt đối tới `bin/claude-tee`), `paseo reload`, chạy thử rồi mới ghi đè `command` của provider `claude`. Wrapper chỉ chuyển tiếp stream-json và ghi `rate_limit_event` (`seven_day`/`five_hour`) vào `$CLAUDE_CONFIG_DIR/.hh-claude-rate-limit.json`, không lưu hội thoại/`session_id`; `hh-ps`/`hh-tree` dùng mẫu mới hơn cache và không ngoại suy. Gỡ bằng cách bỏ provider/khôi phục `claude` rồi `paseo reload`; đặt `env.HH_CLAUDE_REAL` nếu cần chỉ `claude` thật. Chi tiết ở README hybrid-hands mục 8.1.
- **Hạn mức:** mỗi `paseo run` với hand dùng hạn mức gói ChatGPT của `~/.codex-hand`; Paseo 0.15.0 không có lệnh xem usage/quota, nên đọc trên `hh-ps`/`hh-tree` (USD~ ước tính, % 5h/tuần và giờ reset của tài khoản), luật như skill `ext-hand`.

## 5. Theo dõi và điều khiển

Theo [orchestration](https://paseo.sh/docs/orchestration) (11/2026) và `--help` 0.15.0:

| Việc | Lệnh |
|---|---|
| Liệt kê agent (kể cả lưu trữ, mọi thư mục) | `paseo ls -a -g` |
| Xem nhật ký | `paseo logs <id> --tail 10` (`-f` theo dõi, `--filter tools|text|errors|permissions`) |
| Chờ xong có trần | `paseo wait <id> --timeout 60` |
| Gửi thêm việc | `paseo send <id> "..."` (`--prompt-file`, `--behavior steer|interrupt`, `--no-wait`) |
| Chi tiết / dừng / xoá | `paseo inspect <id>`, `paseo stop <id>`, `paseo archive <id>` |
| Duyệt quyền chờ | `paseo permit ...` |

- Id nhận tiền tố. Không viết vòng chờ không trần; dùng `paseo wait --timeout`.
- Agent trong Paseo gọi agent khác qua tool MCP `create_agent`, `send_agent_prompt` khi bật `daemon.mcp.injectIntoAgents` ([MCP](https://paseo.sh/docs/mcp), 11/2026).

### 5.1 Chuyển chính phiên TUI sang Paseo và ngược lại

**Chuyển phiên TUI đang mở sang Paseo:** khi người dùng nói "switch sang paseo" hoặc "chuyển sang paseo" ngay trong một phiên Claude Code TUI, brain chạy `cc-switch paseo --self` ở **lượt cuối của câu trả lời** (sau khi đã viết xong nội dung cần trả lời, trước khi kết thúc lượt), rồi báo người dùng **đừng gõ hay nhấn Enter** cho tới khi TUI tự đóng. Lệnh trả về ngay và tách tiến trình nền chờ transcript đứng yên, gửi SIGTERM cho TUI rồi nạp phiên sang Paseo theo đúng luồng `cc-switch paseo --session <sid>`; log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log`. Muốn quay lại terminal sau đó thì dùng `cc-switch term`. Dùng cách này thay cho việc `/exit` bằng tay rồi chạy `cc-switch paseo --session`.

**Chuyển chính phiên Paseo về terminal:** khi người dùng nói "về terminal" hoặc "chuyển về terminal" ngay trong một phiên Claude Code do Paseo giữ (agent Paseo provider `claude`), brain chạy `cc-switch term --self` ở **lượt cuối của câu trả lời**, rồi báo người dùng cửa sổ Terminal sẽ mở sau khi lượt này xong và **đừng gửi tin cho agent từ Paseo** cho tới khi chuyển lại. Lệnh trả về ngay và tách tiến trình nền chờ transcript đứng yên, kiểm lại không còn TUI sống, rồi mở cửa sổ `Terminal` (hoặc `--app iTerm`) bằng `open -a` một file `.command` chạy `cd <cwd> && exec <bin/cc-switch> term --session <sid>` — luồng ghi sổ bàn giao và `exec claude --resume` hiện có. Không cần quyền Automation của macOS. Dùng `--dry-run` để xem kế hoạch, `--idle-sec` để đổi thời gian chờ transcript đứng yên.

**Slash command:** `/to-paseo` chạy `cc-switch paseo --self`, `/to-term` chạy `cc-switch term --self`; mỗi lệnh là hành động cuối của lượt, không làm gì khác. Chưa kiểm hai slash command chạy được bên trong agent Paseo.

### 5.2 Phiên Sol do `side-session` tạo trên Paseo

- `side-session start --provider codex` (mặc định) tự thử daemon Paseo trước khi tạo worktree. Nếu daemon sẵn sàng, nó dùng client đi kèm CLI 0.15.0 (`dist/utils/client.js`, `dist/utils/daemon-target.js`) để tạo workspace directory đúng cwd rồi agent provider `codex-hand` với `CODEX_HOME` của hand, model/effort, `sandbox_mode=danger-full-access` và `approval_policy=never` (toàn quyền, không hỏi phê duyệt); không truyền `modeId`. Agent hiện trong app ngay khi tạo, nên điện thoại điều khiển được mà không cần screen.
- Endpoint lấy từ `PASEO_HOME`/`PASEO_HOST` (mặc định home) và được ghim trong state; nếu đổi endpoint giữa chừng, `ls`/`watch` coi là unknown và `stop` không điều khiển nhầm agent. Không kế thừa `PASEO_AGENT_ID`/`PASEO_WORKSPACE_ID` của terminal đang chạy.
- Daemon vắng hoặc CLI không tìm thấy: `side-session start` cảnh báo rồi quay lại screen cũ. `codex_profile` khác rỗng chỉ dùng screen khi daemon vắng; daemon sẵn sàng thì báo chưa hỗ trợ và thoát, không fallback. Daemon đã nhận tạo nhưng lỗi: thoát rõ, không mở screen thứ hai; timeout/protocol/không có agent id giữ trạng thái `unknown`, chặn dùng lại tên và giữ slot tới khi `stop`/reconcile. `side-session attach <tên>` với phiên Paseo chỉ hướng dẫn mở app hoặc `paseo attach <id>`; `stop` interrupt agent rồi dừng watchdog screen, giữ agent/worktree. `.done` vẫn kết thúc phiên; `ls` giữ `done`/`stopped`/`daystop`, không hồi sinh từ trạng thái daemon.
- Native compact của Codex nằm ở key top-level `model_auto_compact_token_limit` trong `config.toml` của `CODEX_HOME` hand (schema `providerOptions` 0.15.0 không nhận key này). Đường screen truyền bằng `-c` trong argv; đường Paseo ghi bằng RPC native `config/value/write` của `codex app-server` tạm (chỉ cấu hình, không tạo thread/turn, không đọc auth), không tự parse/format TOML, không in config hay credential.

## 6. Giới hạn: phiên nào hiện

- **Hiện:** agent tạo bằng `paseo run`, app, MCP; phiên provider nhập vào bằng `paseo import <session-id> --provider claude|codex --cwd <dir>` (`paseo import --help`, 0.15.0); và side-session Codex do bridge tạo (agent `codex-hand`).
- **Không tự hiện:** phiên `claude` brain mở trong terminal, phiên `screen` fallback của side-session, hand chạy qua `hand-ext` ngoài Paseo. Bằng chứng: daemon thử 04/11/2026, `paseo ls -a -g` rỗng trong khi phiên claude brain đang chạy. `import` tạo agent Paseo nối tiếp session đó, không phản chiếu trực tiếp terminal đang mở.
- **Import Codex khi TUI còn chạy:** Codex từ chối với lỗi `thread ... already has an active writer` vì TUI đang giữ quyền ghi; import không phản chiếu hay điều khiển được TUI đó. Chỉ import sau khi TUI đã đóng và cwd/worktree vẫn tồn tại.
- **Import lọc theo workspace cwd:** màn import chỉ thấy phiên có cwd trùng workspace directory đã đăng ký; worktree anh em hoặc thư mục khác không hiện. Vì vậy hand nhiều worktree không gom được bằng import.
- **Giải pháp daemon-owned:** để agent hiện ngay và điều khiển được từ app, tạo agent do Paseo sở hữu (`paseo run`/app/MCP, hoặc `side-session start --provider codex` qua bridge) thay vì import một TUI đang mở.
- Muốn xem brain trên điện thoại thì brain phải chạy trong Paseo (tạo bằng `paseo run --provider claude`) hoặc import khi TUI đã đóng.

## 7. Xem phiên phụ từ Paseo

Paseo không tự thấy screen của side-session, nhưng một terminal profile có thể mở đúng screen đó để xem và gõ.

- **Profile:** thêm trong Settings → host → Terminals → Terminal profiles → Add với Name `Phiên phụ (screen)`, Command là đường dẫn tuyệt đối tới `bin/side-session` của plugin, Arguments `attach` (một dòng, không kèm tên). UI lưu cả mảng profile nên giữ các profile cũ; không sửa `~/.paseo/config.json` bằng tay.

```json
{ "id": "side-attach", "name": "Phiên phụ (screen)", "command": "<đường dẫn tuyệt đối tới plugin>/bin/side-session", "args": ["attach"] }
```

- **Chạy:** mở profile từ menu terminal của Paseo; `attach` không cần `.claude/hybrid-hands.json`, tự tìm `screen` và in menu đánh số. Chọn số để gắn, Ctrl-a d để detach rồi menu hiện lại, `q` để thoát.
- **Chỉ là PTY:** profile này chỉ mở terminal vào screen, không tạo agent Paseo và không có trạng thái agent; terminal agent hooks không thấy tiến trình đã chạy ngoài Paseo.
- **Gõ là điều khiển thật:** phím gõ trong screen đi thẳng vào phiên phụ; thoát bằng Ctrl-a d, đừng dùng Ctrl-c vì Ctrl-c gửi vào phiên và có thể dừng việc đang chạy.
