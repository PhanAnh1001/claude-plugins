# Changelog

Lịch sử phát hành hybrid-hands, phiên bản mới nhất ở đầu.

## 0.57.0 — 2026-11-12

- Thêm model Claude Fable 5.2 (`claude-fable-5-2`): `hand-ext models set/options` nhận model này cho brain, phiên phụ và hand Claude; giá lấy từ bảng giá chính thức ngày 12/11/2026 (input 8, cache read 0,2, output 40, cache write 5 phút 10, 1 giờ 16 USD/MTok).
- Template phiên chính Claude xưng đúng model/effort được mở (`{model_label} {effort}`) thay cho chữ cố định "Opus 5.5 high"; tên phiên phụ Claude trên Paseo dùng họ model thực (ví dụ `Fable v2 phụ`), model lạ vẫn ghi `Opus`.

## 0.56.0 — 2026-11-12

- Công tắc guard Claude theo ngày: `claude_accounts.<vN>.day_guard` (mặc định `true` ở v1) và `day_guard_off_date` (`"YYYY-MM-DD"` giờ máy). `day_guard: false` tắt hẳn ngưỡng `max_day_pct`; `day_guard_off_date` bằng hôm nay chỉ tắt trong ngày đó, sang ngày sau guard tự bật lại. Giá trị sai kiểu giữ guard bật (fail-closed). Áp cho `hand-ext run`/`pick` (cả alias `claude-main`) và `side-session` (`budget_check_cmd`). Đặt được ở global `~/.hybrid-hands/config.json` hoặc repo.

## 0.55.0 — 2026-11-11

- Hand worktree tự xoá khi xong: settle OK, patch đã lưu ngoài checkout, áp về gốc OK hoặc patch rỗng, HEAD/baseline/snapshot khớp patch → `git worktree remove`; chỉ còn cache tạo lại được (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `node_modules`, `.DS_Store`, `*.pyc/*.pyo`) vẫn xoá. Giữ lại khi lỗi, conflict, `--keep-worktree` hoặc chưa bảo toàn, report ghi đúng lý do ("giữ lại (<lý do>)"/"đã xoá"); áp cho cả đường shell và managed Paseo (dọn sau khi mọi bước settle hoàn tất, metadata `cleanup`).
- Ownership worktree (repo common dir, base commit, mode, backend) ghi bền vào `runs/<id>.json` trước và sau `git worktree add`; bỏ fallback `rmtree`, lỗi giữa chừng không tự xoá checkout.
- Phiên phụ: done + runtime đã dừng + không có thay đổi chưa commit + HEAD trên nhánh → xoá checkout, giữ nhánh; `output/llm` được tar vào `~/.hybrid-hands/wt-output-backup/` trước. `send`/`resume`/followup tạo lại checkout từ nhánh.
- GC lớp `legacy-recoverable` (hand-ext gc, side-session gc, chạy trong auto-gc ≤20s): mọi file sửa/untracked trùng byte với lịch sử git hoặc checkout chính, HEAD thuộc một ref, không process/agent Paseo dùng, yên ≥24h; sao lưu `output/llm` rồi kiểm lại trước khi xoá. Thiếu thông tin thì giữ (fail-closed).

## 0.54.0 — 2026-11-11

- Guard Claude v1 theo ngày nới từ 5% lên 8% (`CLAUDE_MAIN_MAX_DAY_PCT = 8.0`; mặc định `claude_accounts.v1.max_day_pct` dùng chung hằng). Cấu hình global/repo `max_day_pct` vẫn ghi đè được. Policy, skills, templates, README và AGENTS.md đồng bộ "≥8%/ngày"; spec lịch sử giữ số cũ.

## 0.53.1 — 2026-11-11

- `side-session start --main` chạy từ tab Paseo mở tab cấp cao (không parent) trong cùng workspace của tab gọi: caller (`PASEO_AGENT_ID` → `agent.workspaceId`) giờ cũng dùng cho `--main`, chỉ để chọn workspace, không làm parent; `--new-workspace` và terminal (không caller) giữ tạo workspace mới như cũ.
- Account Claude dùng thư mục mặc định `~/.claude` (v1) chạy provider Paseo `claude`, không gửi `CLAUDE_CONFIG_DIR` và không chọn provider `claude-v1` (trước đó báo "Not logged in"); account khác (v2 `~/.claude-hand`) giữ provider `claude-vN` + `CLAUDE_CONFIG_DIR`. Áp cho cả phiên chính và phiên phụ Claude qua Paseo, kể cả dry-run.

## 0.53.0 — 2026-11-11

- Luật test: test hẹp chạy ngay; test có dấu hiệu nặng hoặc CPU toàn máy ≥90% chạy hạ ưu tiên bằng `nice -n 19 taskpolicy -b` trên macOS, thiếu taskpolicy dùng `nice -n 19`. Chỉ đo CPU trước test dự kiến >30s không có dấu hiệu nặng và không phải test hẹp; không tự bật song song, tăng timeout tương ứng. Giữ luật full suite một lần cuối khi brief giao và lệnh >4 phút giao hand riêng vì chi phí cache; chỉ sửa văn bản, không thêm hook/code.

## 0.52.0 — 2026-11-11

- `side-session start` (không `--main`) mặc định mở agent tab trong workspace Paseo của phiên đang chat (`PASEO_AGENT_ID` → `agent.workspaceId`, chỉ khi agent chưa archived và workspace active); cờ `--new-workspace` giữ hành vi cũ, thiếu điều kiện thì fallback tạo workspace mới. State thêm `paseo_workspace_shared`; done/revive/followup chỉ archive/reopen child, không bao giờ archive/restore workspace dùng chung; `tidy` báo `skip (shared)`, đặt tên không warning.
- Agent Claude của side-session dùng provider Paseo `claude-vN` khi daemon có provider đó ở trạng thái ready, vẫn giữ `CLAUDE_CONFIG_DIR`; thiếu thì dùng `claude` + env như cũ.
- Plugin Paseo `paseo-hh-tree` 0.2.0: hook `agent.create.before` cho agent tạo bằng clear/new chat kế thừa provider/model/effort và chỉ `CLAUDE_CONFIG_DIR`/`CODEX_HOME` của agent mới nhất cùng cwd và cùng họ provider; request đã có account env, internal hoặc không có nguồn thì giữ nguyên; lỗi trả nguyên request. Cần reload plugin Paseo; phiên đang mở không đổi.
- `hand-ext` tự dọn worktree lớp `finished` trước run isolation (`ext_hand.worktree_gc.auto=finished|off`, mặc định `finished`), tối đa mỗi giờ một lần, không chờ lock, lỗi chỉ warning. Registry giữ `base_commit`/`worktree` và không bị xoá khi worktree còn. Lớp mới `preserved` (patch đã lưu khớp thay đổi hiện tại) chỉ xoá bằng `hand-ext gc --apply --include-preserved`; output gc có `age_seconds` và bytes mọi mục.
- Run hand-ext có isolation kết thúc lỗi/không OK xoá worktree ngay khi `changes.patch` khớp thay đổi hiện tại (run bắt đầu sạch, `base_commit` hợp lệ, apply không lỗi); patch và meta giữ trong run_dir. Lượt dsh quá tải còn chạy tiếp, `--keep-worktree`, run bắt đầu dirty, patch lệch hoặc lỗi xác minh vẫn giữ worktree.
- Chưa kiểm chứng với daemon thật: agent tab trong workspace dùng chung khi cwd là worktree khác thư mục workspace; nút clear/new chat của app gửi `create_agent_request` (suy từ protocol, chưa thử trên app).

## 0.51.1 — 2026-11-10

- Supervisor tự chứng minh lại containment incomplete đã cũ (`stale_uncertainty_reproved`): chỉ khi root đã reap, root/owner/mọi pid từng theo dõi đã mất hoặc bị tái dùng, quét toàn bộ tiến trình cùng uid không còn marker và không env sống nào đọc lỗi; còn nghi ngờ thì vẫn chặn.
- `hand-ext managed recover` (nhánh operator_reconcile) nhận ca outcome đã có/epoch ≥ 2 (`settled_sticky`): dry-run mặc định, `--apply` cần `--reason`, giữ nguyên outcome, ghi provenance, release qua đường chính thức, idempotent. Agent Paseo `error` không còn turn và 0 permission chờ được coi là terminal; bridge `agent-terminal` trả thêm `activeTurn`/`pendingPermissionCount` đã sanitize; sink go_ledger ngoài dsh nhận not_applicable khi recover.
- Full suite chạy được trên Python hệ thống: `test_account_sync` bỏ pytest (shim stdlib), test policy hermetic và trỏ đúng nguồn render.

## 0.51.0 — 2026-11-10

- Thêm `side_session.worktree_sparse_exclude` (mặc định `[]`, list pattern kiểu gitignore, validate lúc nạp config) và `side-session start --no-sparse`. Khi khác rỗng, worktree tạo bằng `git worktree add --no-checkout` → `sparse-checkout set --no-cone --stdin` (`/*`, `!<pattern>`) → `checkout`, dùng chung cho screen và Paseo; lỗi giữa chừng giữ worktree và không launch agent.
- Sửa baseline isolation của hand-ext từ worktree sparse: `_snapshot_tree` seed index tạm từ index thật của worktree nên tracked path skip-worktree không còn bị ghi nhầm là deletion trong `dirty_files`/patch. S0 chạy lại PASS.
- Chưa kiểm chứng `side-session start --worktree` end-to-end thật, lỗi giữa chừng bước sparse trên git thật (chỉ mock) và mức ≤15 MB trên repo thật; chưa ghi config sparse cho repo thật.

## 0.50.0 — 2026-11-10

- Thêm `side-session gc`: dry-run phân lớp A–E, apply có khoá và kiểm tra lại, giữ nhánh mặc định, nhật ký khôi phục; auto GC lớp A khi start mặc định `merged`, có thể tắt bằng `off`.
- Thêm `hand-ext gc` cho worktree đã kết thúc có ownership/completion metadata hợp lệ; giữ dirty/unknown. Disk guard chung cảnh báo dưới 20 GiB, chặn dưới 5 GiB (exit 9), override tường minh `--ignore-disk-guard`.
- Sparse P4 bị chặn bởi S0 FAIL ở baseline `isolation.prepare`; `worktree_sparse_exclude`/`--no-sparse` chưa được phát hành. Release chỉ gồm P1–P3/P5; không khẳng định GC apply thật, cài đặt hay merge đã hoàn tất.

## 0.49.0 — 2026-11-10

- Thêm `hand-ext accounts status/sync`: mặc định chỉ đọc/dry-run, nguồn Claude v1; apply cần manifest và approval cụ thể. Tạo import CLAUDE.md và symlink từng asset được duyệt khi thiếu; conflict không overwrite.
- Settings chỉ reconcile `statusLine`/`hooks` có ownership hash approved + verified, backup và atomic write; permissions/env/model/effort/credential/state giữ riêng từng tài khoản.
- Plugin qua CLI chính thức với scope tường minh và marketplace được duyệt; không autoenable hoặc upgrade. Theo verification công khai ngày 10/11/2026, Codex overlay và hook cụ thể còn blocked; MCP apply blocked vì chưa server nào được duyệt và chưa xác minh transport payload an toàn. Không khẳng định `mcp add-json` đã chạy được hoặc đã apply home thật.

## 0.48.3 — 2026-11-10

- Gateway `hand-paseo-acp` chấp nhận `session/new`/`session/load` có `mcpServers` là list (kể cả có phần tử) và bỏ qua hoàn toàn (không lưu, không log, không kết nối, không truyền xuống backend); không phải list vẫn bị từ chối `MCP servers unsupported`. Nguyên nhân managed create lỗi `AGENT_NOT_FOUND`/`errorCode=unknown`: Paseo daemon `mcp.injectIntoAgents=true` chèn MCP server của nó, gateway cũ chỉ nhận `[]` nên từ chối.

## 0.48.2 — 2026-11-10

- `hand-ext managed recover` nhận execution create-failed (`pending=create`) có `receipt.naming` (retry đặt tên chưa xong, `done=false`, `attempts ≤ 3`, warning `NAME_UNRESOLVED` hoặc rỗng) và metadata ghi trước create `title`/`settled`/`lifecycle` (kiểm kiểu, đúng khóa) khi proof `creation-failure` khớp chính xác; rồi ghi `failed_child_creation` và release reservation. Bằng chứng gửi (`sendConfirmed`, `messageId`, `briefDigest`, `createConfirmed`, gateway, writer, process) vẫn chặn.
- Bridge `creation-failure` trả thêm `failedStage` và `errorCode` đã lọc (chỉ mã `[A-Za-z0-9_.:-]{1,64}`, khác thì `OTHER`, không có thì `null`, không bao giờ trả message); lưu trong proof và hiện ở `create_failure` của execution trong JSON recover/ls.

## 0.48.1 — 2026-11-10

- `hand-ext managed recover` thêm nhánh `operator_reconcile` cho execution `unresolved` kẹt vì containment incomplete dính vĩnh viễn: dry-run in `eligible`/`blocked`/`evidence`; `--apply --reason` chỉ settle khi root đã reap, owner/root/mọi pid đã theo dõi đã mất hoặc bị tái dùng, nhóm tiến trình vắng, quét toàn bộ tiến trình cùng uid không thấy marker và không có env đọc lỗi, agent Paseo `closed`. Outcome ghi `provenance=operator_reconcile`, release reservation qua CompletionService/AdmissionController chính thức; idempotent; supervisor tự động vẫn fail-closed.
- Bridge `agent-terminal` nhận agent archived bị mất label theo `agentId`+`workspaceId` (trả `parentLabel=absent`); label `paseo.parent-agent-id` có mà sai vẫn chặn `PLACEMENT_MISMATCH`.

## 0.48.0 — 2026-11-10

- Tách config mode parallel-subagents vào `parallel_subagents.{enabled,backend,account}`: `--account vN` ghi account riêng của mode và backend `claude-vN`; `--backend codex` giữ account. Danh sách tài khoản và policy dùng account của mode, thiếu thì suy từ backend, không đọc `main_session.claude_account`.
- `hand-ext models` xem/set/options không đọc hay cảnh báo về parallel-subagents; giữ nguyên khóa brain cũ, không tự migrate hoặc xoá. Cập nhật README, luật repo và slash command theo hợp đồng tách config.

## 0.47.0 — 2026-11-10

- `/hybrid-hands:models set` chuyển thành wizard tích tầng → provider → account → model → effort + chế độ Hand, tối đa năm lần AskUserQuestion nối tiếp; chỉ ba ô Brain chính/Phiên phụ/Hand, giữ lựa chọn để sửa nhiều tầng trong cùng lần, ghi atomic bằng đúng một lệnh.
- Dùng danh sách providers/accounts/models/efforts thay presets; tự dùng account/model duy nhất. Hủy, thiếu câu trả lời hoặc Other ngoài danh sách thì không ghi; lựa chọn là xác nhận, không hỏi lại.

- Tầng Hand có một tab; hỏi Native subagent hoặc Terminal hand chung màn hình Effort, đánh dấu chế độ đang dùng từ `hand_modes`/`hand_backends[].mode`. DeepSeek luôn terminal và không hỏi chế độ.
- Thêm `--hand-mode native|terminal` cho provider của các `--hand` cùng lệnh, ghi `ext_hand.native.<claude|codex>` thành `auto|off`; `dsh` + `native` lỗi exit 2. `unset hand` gỡ cả `ext_hand.native.*`.

## 0.46.0 — 2026-11-10

- `/hybrid-hands:models set` sửa nhiều tầng trên cùng màn hình bốn tab Brain chính, Phiên phụ, Hand Claude, Hand GPT/DeepSeek; dùng đúng một AskUserQuestion và gộp lựa chọn thành một lệnh ghi atomic. Tất cả “Giữ nguyên” thì không ghi; Other cho Hand nhận nhiều mục cách dấu phẩy.
- `models options --json` thêm bốn nhóm `presets` với label, description và args; mục đầu giữ nguyên cấu hình hiện tại. `--brain`/`--side` nhận thêm `MODEL:EFFORT[@vN]` suy provider từ capability; alias Codex `max` → `xhigh` dùng cho cả cờ phẳng và `--brain`/`--side`/`--hand`.

## 0.45.0 — 2026-11-10

- `/hybrid-hands:models set` dùng một màn hình AskUserQuestion với bốn câu Tầng, Model, Effort, Account rồi chạy đúng một lệnh ghi; lựa chọn là xác nhận, không thêm dry-run hay hỏi lại.
- Thêm cờ phẳng `models set --tier brain|side|hand --model MODEL --effort EFFORT [--account vN]`, loại trừ với nhóm cờ set cũ; suy provider từ capability model, Codex chuẩn hoá `max` thành `xhigh`. Account chỉ áp cho Claude, provider khác bỏ qua kèm cảnh báo; Hand Claude chọn backend `claude-vN` theo account bắt buộc.

## 0.44.0 — 2026-11-10

- `/hybrid-hands:models` không đối số chỉ xem; `set` không cờ dùng AskUserQuestion chọn tầng, model, effort và tài khoản Claude khi cần rồi ghi theo lựa chọn. Các đối số khác tiếp tục chuyển nguyên cho CLI; lỗi thì dừng, không tự sửa config hay chạy lại.
- Thêm `hand-ext models options --json` cung cấp tiers, providers, profiles, accounts và hand_backends cho luồng chọn; bản text in danh sách gọn. Ghi thành công nhắc mở phiên mới để áp dụng.

## 0.43.0 — 2026-11-10

- Thêm `hand-ext models` và `/hybrid-hands:models`: xem model/effort/account cùng nguồn của brain, phiên phụ và hand; `set` và `unset brain|side|hand` theo repo, hỗ trợ `--json`, `--cwd`, `--dry-run`.
- Validate model bằng nguồn giá canonical và capability provider, kiểm effort/account; ghi atomic cùng file repo đã resolve như `parallel-subagents`, giữ khóa khác và không tạo config riêng worktree. Chỉ ghi khi người dùng chốt thay đổi cụ thể; mở phiên mới để áp dụng.
- Giữ mặc định brain Codex Sol high; brain/side chỉ Claude hoặc Codex, account chỉ Claude. Không đổi model/account phiên đang chạy.

## 0.42.0 — 2026-11-10

- hh-store giai đoạn 2: làm mới trực tiếp. Dữ liệu đổi thì `state_dir()/revision` đổi sau p50 0,39 s, max 2,33 s (đo thật 10/11/2026, n=9, có hh-ps chạy mỗi 5 s). Pane và Paseo chỉ chạy hh-ps khi revision đổi.
- Thêm `bin/hh-indexer`: daemon singleton (flock `indexer.lock`), theo dõi bằng kqueue VNODE, debounce 300 ms, quét file active mỗi 30 s, quét full rollout Codex mỗi 300 s; không có kqueue thì poll stat 2 s. Tự thoát sau 600 s không có reader chạm `last_read`. `revision` chỉ tăng khi có thay đổi thật, kể cả khi hh-ps tự ingest giữa hai chu kỳ.
- Thêm `bin/hh-store touch [--path P] [--hook-stdin]` và `hh-store status [--json]`. Hook SessionStart/Stop/SubagentStop/SessionEnd gọi `scripts/hh-store-touch-hook.sh`, chạy `hh-store touch --hook-stdin` nền và trả về ngay (~7 ms; touch ~90 ms chạy nền). hh-ps chạy từ terminal (tty) tự khởi indexer. Tắt bằng `HYBRID_HANDS_INDEXER=off` (hoặc `HYBRID_HANDS_STORE=off`).
- Pane `hh-tree-pane`: `watchPaths` trên file revision và poll stat 1 s, debounce 300 ms, single-flight, touch mỗi 60 s khi pane hiện; chu kỳ cũ giữ làm lưới an toàn. Cần mở phiên Claude mới để pane nạp `watchPaths`.
- Paseo `paseo-hh-tree`: RPC `hh-tree.revision` hỏi mỗi 2 s, lỗi thì thử lại sau 60 s, lưới an toàn 120 s.
- Sửa indexer: cờ CLI map vào `Config` theo tên (trước đây quét full Codex mỗi chu kỳ 30 s); indexer ingest không decode `payload_json`; quét full bỏ qua rollout biến mất giữa chừng thay vì dừng cả lượt. CPU nền indexer 0,37% lúc nhàn, 0,50% khi có hh-ps mỗi 5 s (trước khi sửa 2,2–2,7%). hh-ps p50 ~0,9 s khi indexer chạy, dao động giống khi tắt indexer.

## 0.41.0 — 2026-11-10

- Thêm kho chỉ mục `lib/hh_store/` (SQLite WAL `~/.hybrid-hands/state/hh-store.sqlite3`, quyền 0600; tự dựng lại khi hỏng hoặc đổi version). Kho ingest tăng dần rollout Codex và transcript/subagent Claude theo cursor và generation; rotate/truncate thì sinh generation mới, ghi đè tại chỗ thì phát hiện bằng fingerprint. Kho lỗi, khoá bận hoặc `HYBRID_HANDS_STORE=off` thì quay về đường đọc file cũ.
- `codex.py`, `native_source.py`, `machine_usage.py`, `transcript_source.py` đọc từ kho. Rollout không đổi stat thì không ghi kho, không đọc lại. Tổng GPT tuần được cache theo thread, khoá gồm stamp file, cửa sổ, giá và options. Các lần đọc transcript Claude cho mốc tuần, live split và hiệu chỉnh dùng chung một lần parse. `claude auth status` được cache theo account trong một chu kỳ poll (chỉ lưu digest). Gộp các lần resolve đường dẫn lặp lại.
- Ba writer (`run_registry`, `execution_state`, `side_session/state`) tăng `revision` của kho; lỗi kho không làm hỏng writer.
- Hệ số Claude USD~/1% tuần tách theo account: file cũ thuộc v2, v1 hiện `?` cho tới khi có mẫu.
- Đo thật `hh-ps --since 3h --json --ended --full`: kho tắt ~9 s → kho bật p50 0,70 s (n=5). JSON giống hệt giữa kho bật và tắt, và giống bản trước tối ưu, ngoài `duration_seconds`/`generated_at`.

## 0.40.0 — 2026-11-10

- Thêm nhãn tài khoản thống nhất `{provider} {slot} {plan} {name}` qua helper `lib/account_label.py`: ưu tiên `plan`/`name` cấu hình, thiếu plan dùng plan phát hiện sẵn nếu có, thiếu name thì Claude lấy local-part của `oauthAccount.emailAddress` trong `<config_dir>/.claude.json` (không in email đầy đủ), GPT hiện `?`; phần thiếu hiện `?`.
- Cấu hình mới: `ext_hand.claude_accounts.vN.plan|name`, section `ext_hand.gpt_accounts` (mặc định `v1` home `~/.codex-hand`, chỉ phục vụ nhãn) và `ext_hand.account_label_format`; format sai placeholder thì cảnh báo không in giá trị và dùng mặc định.
- `parallel-subagents` status dùng nhãn ở dòng brain/backend, JSON thêm `brain_account_label`, `backend_account_label`; `pick --json` thêm `account_label`; hh-ps JSON usage thêm `account_label` và cột tài khoản dùng nhãn khi biết slot. Field cũ giữ nguyên.
- Thêm `parallel-subagents accounts [--json]` liệt kê đánh số tài khoản Claude rồi GPT theo nhãn, `*` ở backend đang chọn; `on` không cờ trên TTY hỏi chọn (Enter giữ hiện tại, sai exit 2 không ghi), slash command hỏi bằng AskUserQuestion. Plan GPT tự lấy từ `rate_limits.plan_type` của rollout mới nhất trong `~/.codex-hand/sessions` khi chưa cấu hình; `HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE=1` (chỉ cho test) tắt mọi lần đọc file tài khoản.

## 0.39.0 — 2026-11-10

- Thêm `parallel-subagents --account vN`: validate theo `ext_hand.claude_accounts` hiệu lực, ghi atomic cùng lúc `parallel_subagents.backend = "claude-vN"` và `main_session.claude_account = "vN"`; account lạ hoặc `--backend` khác `claude-vN` thì exit 2, không ghi. Slash command nhận cờ mới.
- Status text/JSON thêm `brain_account`, `brain_account_source`, `account_mismatch` và cảnh báo khi backend subagent khác tài khoản brain; policy mode bật nêu tài khoản brain, hướng dẫn `hand-ext run --backend claude-vN` và mở brain mới bằng `side-session start --main --provider claude --account vN` khi khác account. Mode tắt giữ nguyên output.

## 0.38.0 — 2026-11-10

- Thêm `parallel_subagents.backend` mặc định `claude-v1`, đặt từ global/repo hoặc `parallel-subagents --backend NAME`; status hiện backend/model/effort và nguồn.
- `pick --backend NAME` preflight đúng backend, giữ guard/native và không fallback; policy mode bật hướng dẫn giao theo backend đã giải, mode tắt giữ nguyên output. Slash command nhận cờ mới.
- Sửa `run --mode auto` từ phiên ngoài Paseo (thiếu `PASEO_AGENT_ID`): preflight báo `PaseoUnavailable('PARENT_REQUIRED')` nên lùi về shell cùng backend thay vì exit 1; `paseo-required` vẫn báo lỗi.

## 0.37.3 — 2026-11-10

- `hh-ps` nhanh hơn: nạp config và bảng giá một lần mỗi tiến trình (memo theo file stamp, trả bản sao), lọc literal trước regex khi đọc rollout. Đo thật `hh-ps --since 3h --json --ended --full`: ~13,5 s → ~8,5 s (n=3), output không đổi.
- Pane `hh-tree-pane` và panel `paseo-hh-tree` làm mới thích nghi: max(30 s, 3 × thời gian chạy trước), trần 120 s, lỗi giãn gấp đôi; pane ẩn thì bỏ lượt tự động; server Paseo single-flight + cache theo cùng chu kỳ; client poll 30 s.

## 0.37.2 — 2026-11-10

- Đổi tên lệnh chính thành `hand-ext parallel-subagents [on|off]`, giữ `parallel` làm alias cũ cùng flags và hành vi.
- Thêm slash command `/hybrid-hands:parallel-subagents [on|off]` cho Claude Code; không đối số chỉ xem, chỉ đổi mode khi người dùng chốt và mở phiên mới để hook nạp luật.

## 0.37.1 — 2026-11-10

- Thêm `hand-ext parallel [on|off]`, `--cwd`, `--json`: trạng thái kèm nguồn/file, ghi bool atomic đúng config repo/fallback worktree, giữ key và thứ tự, từ chối file lỗi.
- Hướng dẫn đổi mode qua lệnh sau khi người dùng chốt từng repo và mở phiên mới để hook nạp luật; plugin parallel-subagents cũ luôn tắt.

## 0.37.0 — 2026-11-10

- Thêm mode `parallel_subagents.enabled` mặc định tắt, chỉ bool thật và chỉ repo được bật; global true/sai kiểu bị bỏ qua kèm warning, giữ provenance và fallback worktree.
- Hai hook dùng chung renderer policy: mode bật thay luật delegate/review bằng brain → native hand theo max_parallel thực và giữ guard v1; mode tắt giữ output 0.36.1, kể cả rút đoạn trùng AGENTS.md. Config lỗi fallback policy thường, không hiện giá trị lỗi.
- Hướng dẫn migrate: tắt plugin parallel-subagents cũ, chỉ bật key repo khi người dùng chốt và mở phiên mới; không tự thay cấu hình/runtime.

## 0.36.1 — 2026-11-09

- Đặt tên agent và workspace phiên phụ theo `<tên> · <loại> phụ` (Sol, Opus theo account, dsh); managed hand theo `<tên cha> › hand <backend> · <label>`, cha main xác minh dùng `chính`, unknown dùng `?`. Tối đa 60 ký tự, cắt label giữ tiền tố cha/backend; không đưa path/brief/secret vào tên, giữ title main/shared.
- Naming khi create/send/followup dùng API public Paseo 0.15.0 `updateAgent(..., {name: title})` và `setWorkspaceTitle(...)`; lỗi chỉ cảnh báo, không chặn lifecycle, retry hữu hạn qua `ls`/`watch`, idempotent; không thêm rename vào required capabilities preflight.
- Thêm `side-session tidy --names [--name NAME] [--apply]` và `hand-ext managed names --cwd /ABS [--apply]`: dry-run mặc định không ghi, apply chỉ plugin-owned, chặn main/shared/foreign/unknown members; không archive. Giữ contract tidy archive, review gate và lifecycle hiện có.

## 0.36.0 — 2026-11-09

- Claude main: thêm `main_session.claude_auto_compact_window` mặc định `272000` cho mọi account; nhận số nguyên `100000..1000000`, `null`/`"auto"` bỏ override, giá trị khác báo lỗi kèm nguồn; công khai helper chuẩn hóa và provenance qua `hand-ext config --json`. `side-session start --main --provider claude` qua Paseo/screen truyền `CLAUDE_CODE_AUTO_COMPACT_WINDOW` khi có window; `ls` dùng window đã áp dụng, lưu lúc launch kèm `(tự nén)`. Main cũ chưa lưu window giữ hiển thị cũ; mở main MỚI để nhận env/window mới, không sửa settings hay restart/dừng main đang chạy. Phiên phụ/hand giữ nguyên; hand Claude lọc biến compact kế thừa.

- `side-session` qua mọi provider Paseo: report/`.done` archive đúng agent và workspace do plugin tạo (LOCAL riêng hoặc worktree) khi mọi agent cùng `workspaceId` đã archived hoặc được xác nhận là phiên plugin đã đóng rồi archive. Không archive `main_session`, workspace ngoài plugin hay workspace còn thành viên hoạt động; xét thành viên theo `workspaceId`, không theo cwd vì nhiều workspace LOCAL có thể dùng chung checkout. Lỗi archive workspace vẫn giữ done và retry có giới hạn; giữ thư mục, lịch sử, report và artifacts.
- `side-session send --name NAME --prompt-file FILE` khôi phục cùng workspace rồi đúng agent, lưu marker cũ vào lịch sử và chạy lại, không tạo bản trùng. Lỗi chắc chắn trước send cho phép retry; send chưa rõ kết quả giữ pending.
- `side-session tidy [--name NAME] [--apply]` mặc định dry-run, dọn trạng thái archive workspace do plugin tạo đã rỗng hoặc chỉ còn agent plugin đã archived, lặp an toàn; bảo vệ main, workspace ngoài plugin, workspace dùng chung còn thành viên cần giữ và mọi thư mục.
- Managed `awaiting_review` sau đủ report/hooks tự archive đúng child và workspace trước review; follow-up vẫn cần review approval, khôi phục cả hai với cùng ID và epoch mới. Archive tường minh lặp an toàn, không dọn worktree; lifecycle hh-ps/panel giữ nguyên.

## 0.35.6 — 2026-11-09

- `managed recover --legacy-attest --reason` bổ sung ngoại lệ người vận hành xác nhận cho record trước 0.35.5 thiếu inventory/reap proof: dry-run mặc định, apply kiểm exact binding/revision/reservation, owner/root/group đã vắng hoặc PID reuse được chứng minh và marker scan mới sạch. Record mang evidence inventory/reap hiện đại phải dùng `post_hoc_reverify`.
- Quiescence legacy giữ `confirmed=false`, ghi `attested=true` và method `operator_legacy_attest`; settlement qua năm hook chuẩn và admission release đúng một lần. Record cũ không lưu phiên bản nên operator xác nhận nguồn gốc; rủi ro còn lại là process vừa bỏ marker vừa thoát cây theo dõi.
- AdmissionConflict/AdmissionFull trước reservation/dispatch ghi terminal `not_admitted`, exit 8 có loại chặn và holding key an toàn; recover intent cũ qua cùng cờ xác nhận, hh-ps hiển thị lỗi kết thúc thay vì unknown. Không ghi/in env, argv hay exception text tùy ý.

## 0.35.5 — 2026-11-09

- Giữ diagnostics containment an toàn (stage/method/loại lỗi/PID/OS start), inventory identity, bằng chứng reap và owner acknowledgment; giữ lỗi fatal đầu tiên và retry CAS có giới hạn.
- Kiểm lại OS birth khi marker scan gặp exit race (kể cả EINVAL trên macOS), giữ fail closed với identity/scan chưa chắc; exec đổi tên tiến trình không bị nhầm là PID reuse.
- `managed recover` bổ sung `post_hoc_reverify` cho cancelled-unresolved có đủ proof, dry-run mặc định, `--apply` qua supervisor/completion hooks/release chuẩn, khóa và revision fence. Legacy thiếu inventory/OS start/root-reaped vẫn từ chối và giữ reservation.

## 0.35.4 — 2026-11-09

- Managed worker theo dõi cây con khi root sống và trước cancel, giữ PID + OS start time + comm cùng lịch sử chuỗi cha; kiểm lại identity trước từng signal. Cancel dừng root group và descendant đã setsid/reparent, TERM/KILL với thời hạn; marker invocation exact được quét cùng user qua KERN_PROCARGS2 trên macOS, không ghi/in giá trị môi trường.
- Chỉ xác nhận quiescence khi root đã reap, group vắng và không còn tracked/marker process sống; evidence `root_group+tracked_tree+env_marker`. Scan lỗi, mất authority hoặc process còn sống giữ unknown/reservation; gateway/ancestors được bảo vệ, không signal PID phục hồi khi thiếu Popen ownership.
- Giới hạn macOS: process vừa bỏ marker vừa double-fork giữa hai snapshot có thể thoát; đây là best-effort, không phải containment tuyệt đối. Kiểm offline: 508 tests pass; syscall và setsid fixture thật trên macOS pass. Kết quả gate live được ghi riêng trong bàn giao pilot.

## 0.35.3 — 2026-11-09

- Dispatcher pin plaintext/digest trước network cho dispatch/follow-up/capacity; gateway kiểm exact một envelope Paseo canonical với messageId/source parent/body khớp pin, trim đúng ECMAScript. Worker nhận plaintext pin; raw prompt chỉ nhận khi digest khớp, prompt ACP lạ không tự tạo epoch managed.
- Prompt fence ghi durable rejection marker chỉ trước claim/worker, controller terminal failed và nhả reservation exact. `managed recover` hỗ trợ legacy claim đã lỗi trước worker_owner/process với inspect public exact error/closed và invariant persist-before-spawn; dry-run mặc định, apply/repeat fenced, uncertainty giữ reservation.
- Kiểm offline: 506 tests pass; envelope sai ID/source/body, nhiều message, thiếu digest và marker mâu thuẫn bị từ chối; unbound discovery vẫn không thực thi/ghi state/đọc auth. Live gates được ghi riêng trong bàn giao pilot.

## 0.35.2 — 2026-11-09

- Recover exact failed child creation vẫn hoạt động khi parent/workspace đã archived: proof public và agent absence bắt buộc, không nới kiểm cha của create/send. Chỉ suy inFlight từ public snapshot khi daemon đúng 0.15.0 đã đối chiếu source; daemon khác/thiếu version từ chối, không fallback.
- ACP bound new/load công bố model và effort từ Invocation cùng policy mode hiện tại, tránh Paseo gọi setter không được hỗ trợ; không thêm setter hay đổi quyền thực thi.
- Kiểm offline: 503 tests pass, regression qua ACPAgentSession public của Paseo 0.15.0, binary discovery/partial binding probe pass. Live lifecycle vẫn được ghi riêng trong bàn giao pilot.

## 0.35.1 — 2026-11-09

- Sinh workspace ID đúng schema Paseo 0.15.0 (`wks_` + 16 ký tự hex); kiểm official schema workspace/create/send trước kết nối, chỉ trả issue path/code và bằng chứng notSent, giữ reservation khi network/ACK chưa rõ.
- Thêm `managed recover` dry-run mặc định: recovery workspace ID không hợp lệ hoặc exact child creation được daemon xác nhận failed/known outcome và inspect không tồn tại; `--apply` mới terminal failed và nhả đúng reservation, lặp an toàn. Ưu tiên lifecycle API public, receipt local chỉ khi thiếu capability; không sửa immutable IDs hay suy từ UI idle.
- ACP unbound chỉ phục vụ initialize/session/new với catalog metadata tĩnh `default` chung (Paseo probe không truyền provider identity); mọi prompt/side effect bị từ chối cố định trước state/worker/auth, binding một phần hoặc rỗng vẫn fail. Bound execution giữ policy/model của invocation.
- Kiểm offline: 502 tests pass, probe binary unbound không spawn/ghi state/đọc auth; G7 live đang được kiểm riêng, chưa quảng bá backend supported end-to-end.

## 0.35.0 — 2026-11-09

- A — Cấu hình mặc định plugin → global → repo → CLI; dict merge sâu, list/scalar thay nguyên; global hỏng báo lỗi kèm đường dẫn. `hand-ext config --json` hiện cấu hình hiệu lực và nguồn từng key; account/backend đặt được ở global.
- B — `main_session` và các key provider/model/effort/account của `side_session`; Claude chính/phụ mặc định qua Paseo, có thể chọn screen tường minh, không tự fallback khi Paseo lỗi. Truyền `CLAUDE_CONFIG_DIR` theo account; template Sol chính có đường dẫn bin/skill, khuôn brief và model/effort thực tế.
- C — `ext_hand.native.{claude,codex}=auto|off`; `pick --json` thêm `native`/`native_reason`, caller vẫn kiểm capability.
- E — `paseo.claude_providers` ánh xạ account cho `cc-switch` khi import; thiếu ánh xạ dừng trước khi đóng TUI. Provider v2 do người dùng khai báo trong Paseo.
- Đã kiểm offline; chưa kiểm live phiên Claude v2 qua Paseo, chưa chuyển phiên v2 thật.

## 0.34.0 — 2026-11-09

- Hand chạy thành agent Paseo (lane A, opt-in): `ext_hand.mode` = `shell` (mặc định) / `auto` / `paseo-required`, cùng `ext_hand.paseo.{package_root,target,state_root}`. Mỗi hand một workspace riêng cùng project, gắn cha qua `PASEO_AGENT_ID`, giữ worktree/patch/report/ledger/guard, pool 4 và exit 7/8. `auto` thiếu daemon/provider/capability thì về shell trước dispatch; sau dispatch không tạo writer trùng.
- Gateway ACP `bin/hand-paseo-acp` cho 4 provider `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`; `hand-ext provider setup --dry-run|--apply` (backup trước khi ghi, giữ khoá khác) và `provider status`. Nạp provider bằng `paseo daemon reload`, không cần restart.
- Lệnh `hand-ext managed ls|review-approve|archive|followup`: Sol duyệt rồi archive đúng hand, follow-up mở epoch mới cùng agent/workspace (không resume context CLI).
- hh-ps hiện mỗi managed execution/epoch đúng một dòng dưới cha canonical, khử trùng với registry meta và rollout native, không cộng token hai lần.
- Skill ext-hand/paseo và template Sol: khi mode bật và provider sẵn sàng, việc mới trước đây giao native Sol low chuyển sang `hand-ext run --mode paseo-required`; native đang chạy giữ nguyên.
- Đã kiểm offline (487 test). Live trên daemon thật (placement, stop/reap, recovery ACK, smoke từng backend) chưa kiểm chứng.

## 0.33.1 — 2026-11-09

- `ls` bỏ qua riêng phiên có agent đã xoá hoặc workspace lệch, vẫn reconcile các phiên hợp lệ khác.
- Phiên phụ Codex/Paseo vẫn archive workspace riêng khi done. Khi người dùng unarchive agent, `ls`/watch mở lại workspace nếu recovery có `action:"unarchive"`; `action:"restore"` không mutation.
- Guard `paseo_revived` giữ status `done`, ngăn `.done` cũ tự finish lại phiên vừa mở; lỗi giữ nguyên state để vòng sau retry.
- `ls` đọc archive state theo lô một lần, chỉ reconcile agent đổi archive state; snapshot lỗi/thiếu thì giữ state và warning một dòng. Watch giữ flow một phiên; rearchive chỉ tác động workspace riêng sau private check.

## 0.33.0 — 2026-11-09

- Thêm sổ tài khoản Claude `v1`/`v2`/`v…`, alias backend cũ và `hand-ext pick`; auto chọn theo order dsh → Codex low → Claude v1 low → Claude v2 low, giữ chặn ngày theo tài khoản.
- Phiên chính/phụ Claude chọn `--account` qua cùng loader tài khoản của hand-ext, nhận cả override backend canonical và legacy; không thêm nguồn cấu hình người dùng.
- Giữ model dsh `deepseek-v4.1-flash`, mặc định effort `off`; template ánh xạ `off: null` để tắt thinking, giữ low/high/max và nguồn giá canonical. User-Agent lấy version plugin 0.33.0.
- Đồng bộ policy Opus → Sol → hand theo tài khoản và order; rút hook mỗi prompt, giảm policy trùng và đưa phần tĩnh của brief lên đầu để dùng cache tiền tố.

## 0.32.2 — 2026-11-09

- Kiểm freshness quota theo thời điểm hoàn tất đọc nguồn, giữ timestamp quan sát gốc; không loại nhầm mẫu Paseo được tạo trong lúc lệnh đang chạy. Cho phép poll sớm một lần khi cache thành công đã hết hạn.
- Giữ baseline hiệu chỉnh cùng account/reset khi mốc reset chỉ jitter tối đa 2 giây; không nối các cửa sổ tuần khác nhau.

## 0.32.1 — 2026-11-09

- Sửa nguồn token/USD Claude ngoài khi chạy plugin từ bản cài đặt: cho phép tìm mã helper statusline qua cài đặt tài khoản chính nếu tài khoản ngoài chưa cài statusline, vẫn chỉ quét transcript `~/.claude-hand`. Giữ ưu tiên helper hiện có và override tường minh; helper thiếu/hỏng trả unknown.

## 0.32.0 — 2026-11-09

- Thêm hiệu chỉnh Claude ngoài (`~/.claude-hand`): ưu tiên live `rate_limit_event`/cache trực tiếp còn mới, dự phòng usage report Paseo khớp metadata auth Claude chính thức (kể cả Pi đăng nhập); chỉ lưu identity đã hash, không lưu email thô/credential, không cần đổi settings cho nguồn trực tiếp. USD~ chỉ từ token transcript Claude hand và giá canonical, tách input/output/cache đọc/cache ghi 5m/1h.
- USD~/1% tuần dùng chênh lệch USD và quota của hai quan sát hợp lệ cùng tài khoản/reset; quota số nguyên cần delta ≥2 điểm phần trăm, nguồn có phần lẻ thực cần delta dương; chưa đủ ngưỡng/mẫu, stale hoặc model thiếu giá thì `?`, không dựng baseline lịch sử. Lấy mẫu khoảng 120 giây, cache Paseo tối đa 5 phút. Panel/sidebar thêm quota 5h/tuần Claude ngoài, rate và các nhóm token tổng hợp transcript; USD~ lượt cũ thiếu cache split/session correlation vẫn unknown.
- Theo lựa chọn người dùng, dùng chung rate này để ước tính phần Claude riêng giữa các tài khoản khi rate sẵn sàng; đây là ước tính subscription, không phải hoá đơn hay đồng hồ riêng chính xác của từng tài khoản. Giữ độ chính xác nguồn, hiển thị % một chữ số lẻ không tăng độ chính xác của API.

## 0.31.6

- Sửa workspace phiên phụ vẫn hiện sau khi gom chung project: xác minh workspace ID đã lưu và không có agent dùng chung trước mutation; archive agent rồi workspace riêng, yêu cầu archivedAt hợp lệ. Lỗi cleanup retry, ls/watch đối soát done cũ; không archive project hoặc workspace phiên chính.

## 0.31.5

- Panel/Cây phiên chỉ hiện root đang chạy theo live/status; root đã kết thúc hoặc unknown ẩn cả cây, phiên phụ thiếu parent không thành root. Tổng usage toàn máy vẫn giữ nguyên.
- Tên phiên/hand ưu tiên description ngắn nếu snapshot cung cấp, rồi ai_title và tên/label có nghĩa; thiếu thì `?`, không lấy ID làm tên. Giữ giới hạn 6 phiên phụ, pool 4 và tóm tắt/màu trạng thái.

## 0.31.4

- Panel agent và màn hình Cây phiên mở tối đa 6 phiên phụ mỗi cây chính, ưu tiên đang chạy rồi mới nhất; phần dư giữ tóm tắt running/done/failed/unknown và màu trạng thái hiện có. Pool subagent/hand vẫn tối đa 4.

## 0.31.3

- Panel agent và màn hình Cây phiên dùng chung thứ tự forest: parent tường minh chứa phiên phụ dù input child đến trước; phiên phụ thiếu parent đứng sau mọi root, không đoán parent từ cwd.
- Tên subagent ưu tiên description ngắn thay type/id; native đọc description/title/agent_path/nickname từ metadata, không đọc prompt để đặt tên. Giữ mô tả gốc, pool 4, usage/status/counts.
- SDK Paseo 0.15.0 không có hook chỉnh hierarchy/order/label của danh sách sidebar native; nút sidebar chỉ mở Cây phiên. Không sửa bundle native hoặc archive/đổi tên agent runtime; brain cần cập nhật plugin và reload.

## 0.31.2

- hh-ps khám phá phiên Codex gốc chưa có side-session state từ metadata rollout cục bộ theo repo và thời gian quan sát; gắn native children theo parent thread, giữ alias pinned và không suy diễn status/model/usage. Không gọi RPC/API hay tạo state runtime.
- Rollout fork giữ identity/parent từ session_meta đầu, không để metadata cha kế thừa ghi đè; bỏ qua activity/model/token kế thừa trước mốc child và giữ quota riêng unknown khi chưa tách được sample kế thừa.

## 0.31.1

- Phiên chính Sol chỉ được archive bởi người dùng; gom phiên phụ theo project và dọn project legacy.
- Bổ sung luật sau sửa plugin: validate/test hẹp/review, tăng version và cập nhật qua công cụ chính thức cho mọi repo đang dùng; kiểm version/path nạp thực tế và báo reload khi cần.

## 0.31.0

- Thêm `side-session start --main` mở brain Sol Codex trên Paseo tại repo chính, prompt tùy chọn, effort mặc định high; không fallback screen, handoff/watchdog hay slot phiên phụ. State giữ role tương thích và stop archive lịch sử; bổ sung template và hướng dẫn phiên chính.

## 0.30.0

- GPT machine USD~ dùng token delta có timestamp quan sát được trong cửa sổ reset quota tuần hiện tại ở `~/.codex-hand/sessions` và `archived_sessions`, khử trùng thread/event, không cộng ledger trùng. Metadata-only thread không làm tổng observed thành unknown; không có event trong cửa sổ, event thiếu baseline/timestamp/giá hợp lệ hoặc file không đọc được thì `?`. Tổng chỉ phản ánh nguồn cục bộ đo được, không bảo đảm đủ mọi hoạt động tài khoản; USD~ là ước tính offline subscription, không phải hoá đơn.
- Phần riêng session pinned rollout/native child đo biến động quota tuần từ ít nhất hai sample `rate_limits` hợp lệ, không giảm trong cùng reset hiện tại. `Usage.week_pct_source` mặc định rỗng; nguồn known `codex_rate_limits_delta`, `week_pct_estimated=false`, nhãn `GPT riêng (đo) N% tuần`. Khoảng đo có thể gồm phiên đồng thời, không quy riêng độc quyền; thiếu nguồn/qua reset hiện `?`, không suy quota từ token/USD.
- GPT account có duration tường minh phân loại 5h bằng `window_minutes=300`, không đổi nhãn primary tuần `10080`; source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần. Phép đo GPT phần riêng mới bắt buộc duration tuần tường minh `window_minutes=10080`. Claude 5h kiểm freshness/reset numeric hoặc ISO của cache/live sẵn có; thiếu/hết hạn hiện `?`. Statusline dùng chung helper nguồn usage và bump phiên bản riêng.
- Giữ nguồn giá canonical duy nhất, không fallback model lạ; giữ colors/layout/counts/pool và unknown legacy.

## 0.29.0

- hh-ps đọc metadata native Codex child từ rollout cục bộ trong đường dẫn cố định ~/.codex-hand/sessions (không dùng override CODEX_HOME để giữ cô lập tài khoản), không gọi daemon RPC/API; đối chiếu parent thread qua pinned Sol rollout về sid canonical và xuất trong Session.subagents với provider codex, agent_type native-codex.
- JSON giữ status/provider/parent canonical của native cùng exit_code nullable cho subagent và hand; field mới có default cuối dataclass để giữ tương thích. Không suy completed từ mtime hoặc im lặng.
- Native chung pool tối đa 4 và số đếm X✓ Y✗ trong panel: completed → ✓; failed/errored/cancelled hoặc exit_code khác 0 → ✗, unknown → ?. Lỗi có precedence.
- Token chỉ từ nguồn native, USD~ theo giá canonical; thiếu nguồn hiện ?, không bịa quota hay tạo run/meta/report/token ledger hand-ext.

Panel agent/sidebar Paseo: running/busy dùng theme accent nếu accent là xanh dương, nếu không dùng màu xanh dương dự phòng bảo đảm tương phản ở giao diện sáng/tối; done dùng statusSuccess (xanh lá); failed/exit khác 0/timeout/killed dùng statusDanger (đỏ); idle/silent dùng statusWarning (vàng); lost/unknown dùng foregroundMuted (xám). Số đếm ✓ xanh lá, ✗ đỏ. Dòng đã kết thúc hiện giờ local HH:MM, thêm dd/mm nếu khác ngày; running không hiện giờ kết thúc. Không hiện giờ bắt đầu. Mỗi dòng hiện USD~ riêng, provider Claude/GPT và usage.week_pct riêng trong tuần; thiếu hiện ?. Không thay phần riêng bằng phần trăm tài khoản hoặc suy quota GPT.

Khối riêng ở đầu panel/sidebar hiện tổng USD~ toàn máy trong tuần của Claude/GPT và phần trăm tài khoản 5h/tuần, thay quota ở dòng root. JSON tree.machine_usage:[{plan,window:"tuần",usd,source}] cung cấp tổng toàn máy, không cộng các dòng cây đang hiển thị. Claude dùng phép tổng hợp tuần cục bộ hiện có. GPT đọc rollout trong đường dẫn cố định ~/.codex-hand/sessions và ~/.codex-hand/archived_sessions, khử trùng theo thread, chỉ cộng token delta được chứa trong cửa sổ tuần hiện tại; thiếu cửa sổ/giá/nguồn giữ unknown. Không cộng trùng ledger và rollout. Riêng gắn native child vào cây vẫn chỉ đọc sessions.

Giữ tối đa 4 phiên phụ, pool chung 4 agent, lựa chọn phiên gần nhất, số đếm phần ẩn và loại nhóm orphan. Addon này chỉ áp dụng panel/sidebar Paseo; hh-tree-pane giữ bố cục, chỉ nhận sửa tương thích native status/exit/unknown ban đầu.

## 0.28.0

- User-Agent của hand-ext dsh lấy phiên bản từ manifest plugin, tránh lệch phiên bản khi release.
- Sửa cc-switch --self báo nhầm PID TUI đã được reap còn sống khi tiến trình kết thúc giữa liveness probe và ps; kiểm tra lại PID khi ps không còn state.
- Panel agent/sidebar Paseo gọn: icon, tên, model·effort, elapsed, USD~; quota tài khoản mỗi account plan chỉ ở root, bỏ header/footer và nhãn lặp.
- Mỗi cây hiện tối đa 4 phiên phụ, chỉ phiên hoạt động gần nhất mở tối đa 4 subagent/hand có cha; phần cũ gộp done/error/running/unknown, không mất số đếm phiên ẩn. Running ưu tiên, tie giữ thứ tự duyệt cây/agent đầu vào; lỗi có precedence trên trạng thái running cũ.
- Native Codex child còn phụ thuộc nguồn JSON hh-ps; không tự suy dữ liệu hoặc quota. Không đổi hh-ps, hh-tree-pane hay statusline.

## 0.27.0

- Quyết định A: ưu tiên tab native cho Sol trên Paseo khi backend thực theo order là codex `gpt-6.1-sol` low và tools hỗ trợ model/effort riêng; `fork_turns=none`, full brief/luật dữ liệu, executor không recursion. Tổng native + hand-ext không vượt `ext_hand.max_parallel` (1..4), cùng file tuần tự; không đổi code/slots hand-ext, config hay policy Opus/Claude/dsh.
- Đã kiểm chứng local: Codex CLI 0.166.0 + Paseo CLI 0.15.0, child completed đúng parent và timeline 3 dòng assistant. Tab/history native được giữ; không archive top-level/parent. B chưa triển khai vì A đạt.
- Bridge read-only `subagents`/`subagent-timeline` và Python wrappers xác minh child thuộc đúng parent và đọc history; kiểm endpoint bằng `expectedTargetKey`, không tạo hay archive agent.
- Phân biệt báo cáo/usage native/Paseo với run/meta/report/token ledger hand-ext; thiếu hiện `?`, không bịa quota. Thiếu capability trước spawn dùng auto như cũ; unknown sau spawn không tạo duplicate writer.

## 0.26.0

- Usage panel cho session/subagent/hand/side provider: model, effort, USD~ offline, quota tài khoản 5h/tuần, ended hoặc đang chạy và elapsed; thiếu nguồn hiện `?`, không suy token thành quota GPT. Phần riêng hand tuần có nhãn riêng khi có nguồn.
- Giá canonical [`config/model-prices.json`](config/model-prices.json), override `HYBRID_HANDS_PRICING_FILE`, lưu date/source xác minh ngày 2026-11-07; cache Claude theo cấu hình, model lạ không fallback. USD~ subscription là ước tính, không phải hoá đơn.
- `hh-ps --once`; mặc định đủ việc chạy/vừa xong theo since, không gấp 3 hay ẩn cây đã xong. Text/JSON giữ orphan hand-ext; cả hai giao diện cây bỏ nhóm này.
- Gắn cha từ `CODEX_THREAD_ID`/`PASEO_AGENT_ID` về sid canonical; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời. Áp dụng mọi loại agent/backend, gồm Sol Codex/Claude/dsh.
- Sổ usage statusline version 4 có fingerprint; USD~ Claude là ước tính, không phải chi phí chính xác hay hoá đơn.
- UI bỏ giờ bắt đầu; JSON/meta giữ started và metadata parent canonical, ended, status, exit_code, tokens, effort, duration. Legacy unknown không bịa giá trị.

## 0.25.3

- Giữ phiên có dòng `user` khi chọn phiên gần nhất để chuyển terminal/Paseo.

- Mặc định 4 Sol; mỗi Sol tối đa 4 hand nền độc lập, cùng file tuần tự, đợi đủ rồi Sol review. Scope uuid riêng qua screen/Paseo; exit 8 chờ slot, exit 7 doctor trước dự phòng. Giới hạn cấu hình số nguyên 1..4.

- Doctor Codex không chặn khi model, effort hoặc sandbox trong config thiếu/lệch: CLI override mỗi lượt, dùng chung home với Sol và không ghi config. Cài đặt, đăng nhập gói và service_tier legacy vẫn bắt buộc.
- Prompt Sol bắt buộc giao code/test/tài liệu L0/L1 qua auto theo ext_hand.order; chỉ tự viết khi hand-ext lỗi (ghi lý do/mã thoát) hoặc cần secret. Exit 7 phải doctor trước dự phòng, chỉ dùng ví dụ codex medium khi xác nhận dsh hết quota.
