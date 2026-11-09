---
name: paseo
description: Dùng Paseo (daemon + CLI + app điện thoại) để theo dõi và điều khiển phiên brain/hand từ xa - cài đặt, khởi và dừng daemon, ghép điện thoại (người dùng tự làm), chạy hand Codex với CODEX_HOME riêng (~/.codex-hand, đăng nhập gói ChatGPT, không API key) qua provider tuỳ biến, theo dõi bằng ls/logs/wait/send, và giới hạn (phiên claude mở ngoài Paseo không tự hiện). Từ khoá kích hoạt - "paseo", "điện thoại", "theo dõi phiên", "điều khiển từ xa", "ghép điện thoại", "pair", "xem hand trên điện thoại", "daemon paseo".
---

Tóm tắt cập nhật 0.35.0: cấu hình global và repo quyết định lựa chọn phiên/hand theo tài khoản.

`cc-switch paseo` tra `paseo.claude_providers` theo account phiên hiện tại khi `paseo import`; mặc định `{"v1":"claude"}`. Thiếu ánh xạ thì dừng trước khi đóng TUI. Muốn chuyển phiên v2, người dùng tự khai báo provider Claude v2 trong `~/.paseo/config.json` với env `CLAUDE_CONFIG_DIR=~/.claude-hand`, rồi đặt `paseo.claude_providers.v2` bằng tên provider đó trong global hoặc repo. Ánh xạ không tự tạo provider Paseo.


Mở main Sol high: `side-session start --main --name sol-main`; đường Codex cần daemon Paseo. Main Claude: `side-session start --main --provider claude --account v2` (hoặc v1/v…), mặc định qua Paseo; chọn `main_session.transport=screen` nếu cần screen. Cả hai không dùng `--worktree`, không handoff/watchdog, không chiếm slot phiên phụ.


## Chọn hand theo tài khoản

### Hand Paseo opt-in: ưu tiên trước ngoại lệ native

`shell` vẫn là mode mặc định. Chỉ repo được operator bật `ext_hand.mode=auto` hoặc `paseo-required` mới dùng managed hand; không tự sửa config hay bật ở repo khác. Bảng native bên dưới chỉ áp dụng đường cũ. Khi mode opt-in và daemon/provider/capability sẵn sàng, **intent mới vốn giao native Sol low** phải chạy `hand-ext run --backend auto --mode paseo-required --brief /ABS/brief.md --cwd /ABS/REPO`, không spawn native trực tiếp. Native đang tồn tại giữ nguyên, không migrate. Vẫn chạy `hand-ext pick --json` trước; dispatcher giữ order, account/model/effort, quota/day guards và pool chung `ext_hand.max_parallel` (1..4), không ép backend codex vì intent ban đầu là Sol low.

Thiếu daemon/provider/capability **trước dispatch**: `auto` quay đường shell cũ, `paseo-required` báo lỗi, không silent fallback. Parent/project/target không xác minh được thì chặn. Sau create/send hoặc ACK không rõ, reconcile exact invocation/attempt/epoch, giữ reservation; không tạo shell/native writer thứ hai.

Mỗi managed hand có workspace/worktree riêng trong **cùng verified project** với parent, caller gắn parent canonical và tab/track của parent; không hứa sidebar native lồng child. Theo quyết định 09/11/2026 (thay Q4), khi execution đã settled đầy đủ report/hooks thì chuyển `awaiting_review`, tự archive **exact child** và workspace riêng của child; không cần review để archive, không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Lỗi visibility giữ lifecycle/data để retry, không tạo writer trùng. `managed archive` idempotent. Sol vẫn phải đọc diff/report và `review-approve` trước followup. Followup restore workspace rồi mở lại cùng exact child (giữ agent/workspace IDs) với brief tự chứa, epoch/request key và baseline mới; không phải CLI context resume, không tạo child trùng. Thiếu cwd/worktree thì chặn. Giữ history, report, patch, worktree và mọi thư mục/artifact; không cleanup. Archive chỉ đổi khả năng hiển thị ở sidebar Paseo, không đổi các dòng done của hh-ps/panel. Một managed execution là một hand trong pool, không tạo side-session root; token từ parser/ledger chuẩn, ACP chỉ projection, thiếu usage/quota giữ `?`.


Phiên chính mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… hoặc Sol 6.1 high. Phiên phụ mặc định Sol 6.1 high, có thể là Opus 5.5 high đúng tài khoản v1/v2/v… . Đổi model/account: mở phiên mới từ bàn giao, không dùng `/model` giữa phiên.

Mặc định `ext_hand.order`: dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus 5.5 low) → claude-v2 (Opus 5.5 low). `claude_accounts` lấy từ mặc định plugin → global `~/.hybrid-hands/config.json` → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình. `claude-main` và `claude` chỉ là alias tương thích lần lượt của `claude-v1` và `claude-v2`.

Luôn chạy `hand-ext pick --json` trước để biết backend/model/effort/account, `native`/`native_reason` và lý do bỏ qua, kể cả trước native v1 để giữ chặn ≥5%/ngày (thiếu nguồn cũng chặn). Ở đường cũ, cùng account và tools chọn đúng model/effort mới native; khác account hoặc thiếu capability dùng `hand-ext run --backend auto`. Không tự áp native cho account khác.

| Phiên phụ | dsh | codex low | claude-v1 low | claude-v2 low | UI v1 low |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex (đường cũ; opt-in xem trên) | hand-ext | hand-ext | hand-ext claude-v1 |
| Opus v1 | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext | Native khi preflight v1 đủ; thiếu thì hand-ext claude-v1 |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext claude-v1 |

Sáng tạo UI mặc định claude-v1 low. Native v1 chỉ khi `hand-ext pick --json` thực trả `claude-v1`, model `claude-opus-5-5`, effort `low`, đúng account và đủ capability. Pick trả dsh/codex chưa chứng minh guard v1 đã qua: dùng `hand-ext run --backend claude-v1` để wrapper enforce guard, không sửa config/order hoặc suy guard pass. Guard chặn thì không spawn native v1; ghi yêu cầu để Opus quyết. Công việc theo order tiếp tục backend pick chọn.
Native Codex đường cũ dùng `fork_turns=none`, brief tự chứa, luật dữ liệu nguyên văn; executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Không bật parallel-subagents, không đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota.

Review thấy lỗi: giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp theo order dsh → codex → claude-v1 → claude-v2. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; không tự đổi effort. Exit 8: đợi slot, không đổi backend/tự làm.


### Setup và lifecycle managed

Operator live đã có quyền dùng `hand-ext provider setup --home /ABS/DAEMON_HOME --package-root /ABS/PASEO_CLI_ROOT --dry-run` trước `--apply`; setup mặc định dry-run, chỉ thêm bốn `hh-hand-*`, giữ provider khác. Sau apply dùng public `paseo daemon reload --home /ABS/DAEMON_HOME`, kiểm `appliedPaths`/`restartRequiredPaths`/`overrideControlledPaths`, rồi `hand-ext provider status --cwd /ABS/REPO` xác nhận catalog runtime. Source 0.15.0 hỗ trợ reload providers, không bắt buộc restart cho thêm provider và không hứa auto-watch; reload có thể áp delta reloadable khác đang chờ. Chưa chạy recipe live trong gói docs.

Managed task dùng `hand-ext managed ls|review-approve|archive|followup`; `ls` chỉ cần `--cwd`, ba lệnh sau cần `--cwd` và `--key INVOCATION_UUID:ATTEMPT_UUID:EPOCH`, riêng followup bắt buộc `--brief /ABS/fresh-brief.md`. Settled đầy đủ report/hooks thì `awaiting_review` tự archive exact child và workspace riêng; archive idempotent, không đợi review. Sol review rồi approve trước followup latest epoch cùng child/workspace với brief mới. Không dùng direct `paseo send/archive` để bỏ lifecycle gate. [Recipe và giới hạn live](../../../../README.md#vận-hành-managed-hand-paseo).

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

Metadata mới giữ parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. `CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn đúng cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Sol Codex/Claude/dsh và mọi loại agent/backend. Hand nhận brief trực tiếp là executor: làm trong phạm vi được giao, không gọi hand-ext, không mở side-session hay giao tiếp phiên khác. Luật Sol bắt buộc delegate chỉ áp dụng vai trò Sol; dùng `hand-ext run --backend auto` theo routing opt-in/ngoại lệ native đường cũ nêu trên.



# Paseo: theo dõi và điều khiển phiên từ điện thoại

## Tóm tắt

- **Là gì:** Paseo là daemon cục bộ + CLI + app (điện thoại, desktop, web) để chạy và điều khiển agent Claude Code, Codex... dùng lại đăng nhập sẵn có của từng CLI; Apache-2.0, bản dùng ở đây **0.15.0** (npm `latest` 04/11/2026) ([repo](https://github.com/getpaseo/paseo), 11/2026; [docs](https://paseo.sh/docs), 11/2026).
- **Đã cài:** `npm install -g @getpaseo/cli@0.15.0`, `paseo --version` in `0.15.0` (kiểm trên máy 04/11/2026).
- **Daemon:** `paseo start` chạy nền, nghe `127.0.0.1:6767`, cấu hình ở `~/.paseo/config.json`; relay (để điện thoại kết nối qua internet) **tắt mặc định**. Không thấy cơ chế tự khởi động khi đăng nhập máy.
- **Hand Codex riêng:** khai provider tuỳ biến `codex-hand` (`extends: "codex"`, `env.CODEX_HOME`) trong config; operator kiểm catalog sau bước nạp cấu hình được xác minh, rồi `paseo run --provider codex-hand ...`; hoặc một lần bằng `paseo run --provider codex --env CODEX_HOME=...`.
- **Giới hạn chính:** chỉ agent do Paseo tạo (hoặc `paseo import <session-id>`) mới hiện; phiên `claude` brain đang chạy trong terminal và phiên Claude chọn `screen` của side-session **không tự hiện** (đã kiểm: `paseo ls -a -g` rỗng khi có phiên claude đang mở). Side-session Codex đi đường daemon thì agent do Paseo sở hữu nên hiện ngay, không cần screen.
- **Chuyển phiên terminal ↔ Paseo:** dùng `cc-switch term|paseo|status` (README hybrid-hands mục 7); trong phiên TUI đang mở thì `cc-switch paseo --self` (brain chạy ở lượt cuối); reload/import trước khi gửi tin để transcript không rẽ nhánh.
- **Người dùng phải tự làm:** bật relay, quét QR trên điện thoại, cài app; agent không ghép điện thoại hộ, không ghi `~/.paseo/config.json` khi chưa được duyệt.

## 1. Cài đặt và phiên bản

- Cài ghim bản: `npm install -g @getpaseo/cli@0.15.0` ([docs](https://paseo.sh/docs), 11/2026). Kiểm: `paseo --version`.
- npm 11 bỏ qua install script của `node-pty`, `esbuild`, `msgpackr-extract` (cảnh báo `allow-scripts` khi cài, 04/11/2026). Daemon và CLI vẫn chạy; nếu terminal trong app lỗi thì cài lại kèm `--allow-scripts=esbuild,node-pty,msgpackr-extract` (người dùng quyết).
- Paseo dùng `codex`, `claude` có trên `PATH` của daemon; kiểm bằng `paseo provider diagnostic codex` (trên máy: `/Users/anhtp/.local/bin/codex`, `codex-cli 0.150.1`, Status Ready) ([docs Codex](https://paseo.sh/docs/codex), 11/2026).

## 2. Daemon

- **Khởi:** `paseo start` (đọc `~/.paseo/config.json`, tự tạo nếu chưa có), in PID, địa chỉ nghe và đường log. `paseo onboard` = cài đặt lần đầu + khởi daemon + in hướng dẫn ghép (`--port` mặc định 6767, `--relay`/`--no-relay`, `--no-mcp`) (`paseo onboard --help`, 0.15.0).
- **Xem/dừng:** `paseo status` (dòng `localDaemon: running|stopped`), `paseo daemon stop`, `paseo daemon restart` (cần sau khi đổi `daemon.listen`), `paseo daemon reload --home <home>` (public reload config; kiểm kết quả và catalog, không hứa auto-watch) ([connectivity](https://paseo.sh/docs/connectivity), 11/2026; [custom providers](https://paseo.sh/docs/custom-providers), 11/2026).
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

- **Cách đang dùng — provider tuỳ biến** (`~/.paseo/config.json` đã có `agents.providers.codex={enabled:false}` từ 07/11/2026; provider `codex-hand` dùng `~/.codex-hand`, đổi config cần operator xác minh cách nạp và catalog) ([custom providers](https://paseo.sh/docs/custom-providers), 11/2026):

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
- Daemon vắng hoặc CLI không tìm thấy: `side-session start` báo lỗi và dừng, không tự lùi về screen. `codex_profile` khác rỗng chưa được hỗ trợ qua Paseo và báo lỗi. Daemon đã nhận tạo nhưng lỗi: thoát rõ, không mở screen thứ hai; timeout/protocol/không có agent id giữ trạng thái `unknown`, chặn dùng lại tên và giữ slot tới khi `stop`/reconcile. `side-session attach <tên>` với phiên Paseo chỉ hướng dẫn mở app hoặc `paseo attach <id>`; `stop` interrupt agent rồi dừng watchdog screen, giữ agent/worktree. `.done` vẫn kết thúc phiên; `ls` giữ `done`/`stopped`/`daystop`, không hồi sinh từ trạng thái daemon.
- Native compact của Codex nằm ở key top-level `model_auto_compact_token_limit` trong `config.toml` của `CODEX_HOME` hand (schema `providerOptions` 0.15.0 không nhận key này). Đường screen truyền bằng `-c` trong argv; đường Paseo ghi bằng RPC native `config/value/write` của `codex app-server` tạm (chỉ cấu hình, không tạo thread/turn, không đọc auth), không tự parse/format TOML, không in config hay credential.

## 6. Giới hạn: phiên nào hiện

- **Hiện:** agent tạo bằng `paseo run`, app, MCP; phiên provider nhập vào bằng `paseo import <session-id> --provider claude|codex --cwd <dir>` (`paseo import --help`, 0.15.0); và side-session Codex do bridge tạo (agent `codex-hand`).
- **Không tự hiện:** phiên `claude` brain mở trong terminal, phiên Claude chọn `screen` của side-session, hand chạy qua `hand-ext` ngoài Paseo. Bằng chứng: daemon thử 04/11/2026, `paseo ls -a -g` rỗng trong khi phiên claude brain đang chạy. `import` tạo agent Paseo nối tiếp session đó, không phản chiếu trực tiếp terminal đang mở.
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

## Archive và giao lại side-session (09/11/2026)

Thay Q4, side-session qua Paseo ở mọi provider ghi report/handoff rồi `.done`: archive exact child, sau đó archive workspace theo ownership/membership sau; không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Cảnh báo archive workspace không chặn trạng thái `done`; `ls`/`watch` retry có giới hạn. Giữ handoff, state, history, worktree, patch và report, không cleanup. Archive chỉ ẩn ở sidebar Paseo; các dòng done của hh-ps/panel giữ nguyên.

Giao lại bằng `side-session send --name NAME --prompt-file /ABS/FILE` cho mọi provider Paseo. Trình tự: restore workspace → unarchive cùng exact agent qua public send → gửi prompt, đặt state `running`, đổi tên `.done` cũ sang tên duy nhất để giữ lịch sử và khởi động lại watchdog. Không create agent trùng; thiếu cwd/worktree thì chặn. Khi ACK chưa rõ, trạng thái pending chặn gửi lại để tránh prompt trùng; lỗi xác định xảy ra trước khi gửi có thể retry. `start --resume` giữ tương thích hiện có. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts.
