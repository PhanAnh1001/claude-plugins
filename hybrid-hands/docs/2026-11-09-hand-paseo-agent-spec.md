# Hand/subagent thành agent Paseo — spec lane A

Ngày cập nhật: **09/11/2026**. [Plan triển khai](2026-11-09-hand-paseo-agent-plan.md). G0 chốt thiết kế trên base `cee82cc`, main tham chiếu `fd7d071`, plugin/revive **0.33.1**. Interface dưới đây đã có implementation offline: G0 `a67f050`, G1 `af71045`, G6a `fa87ef5`, G2 `cb756dd`, G6b `3def687`, gateway settlement `53a2738`, compatibility `b5c4243`. Theo bàn giao Sol, mỗi gói implementation đã qua 3 test offline và Sol review; aggregate chạy đúng một lần sau `53a2738`: 12 tests OK (6.740s). Sau đó compatibility `b5c4243` sửa account/scope, chỉ narrow execution 3 tests OK (2.852s); không lặp aggregate/full, aggregate không xác nhận exact final head. Không xác nhận full suite/live/install.

## 1. Quyết định và phạm vi

- **Q1:** lane **A**, ACP gateway bọc runner hiện tại cho đủ `codex`, `dsh`, `claude-v1`, `claude-v2`; provider đề xuất `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`. Chưa đăng ký provider thật.
- **Q2:** mỗi hand có workspace riêng trỏ đúng isolated cwd, cùng **verified project** với cha; create dùng explicit `workspaceId` và `callerAgentId`. Child xuất hiện ở Subagents track/tab cha; không cần sidebar native lồng. Cwd đơn thuần không chứng minh project.
- **Q3:** sau rollout, intent mới vốn giao native Sol-low đi hand Paseo theo policy dispatcher. Existing native tiếp tục đường cũ, không migrate/promote. Không tự mở rộng sang chuyển đổi mọi native Claude.
- **Q4:** done giữ hiện để review; Sol archive **exact child** sau review. Follow-up tự reopen cùng agent/workspace theo revive 0.33.1; không archive parent.
- **Q5:** giữ history Paseo; mỗi prompt là epoch và brief tự chứa mới, **không CLI resume**, không hứa giữ backend thread/context giữa epochs.
- **Q6:** MVP không dọn worktree sau done/archive; mất cwd thì blocked, không recreate ngầm. Không đụng `output/llm/`.
- **Q7:** shell là mặc định; opt-in tại `claude-plugins` sau gate. Daemon/capability thiếu thì auto fallback shell cùng backend **trước dispatch**; `paseo-required` trả lỗi transport riêng. ACK mất sau create/send phải reconcile, không fallback mơ hồ.

B direct Codex bị loại khỏi execution vì giảm guard UI/OS-exit parity; C plugin orchestration bị loại vì không có drop-in giữ contract hand-ext. Khảo sát lịch sử được giữ ở cuối, không tạo lane triển khai.

Stage 1 chỉ **G0/G1/G2/G6a/G6b**, offline fixtures. G3+ deferred trong Stage 1. Stage 2 G3 controller/completion/provider đã implement offline và qua Sol review vòng 2; chưa đăng ký provider thật, G4/G5/live/release chưa hoàn tất. Order lấy policy repo hiệu lực: quyết định repo `6d3e9c7` là codex `gpt-6.1-sol low` → dsh → claude-v1 → claude-v2; defaults có thể khác, không hardcode bảng order trong gateway. Giữ model/account/effort, guard và retry cùng backend một lần rồi backend kế tiếp. Không bật parallel-subagents hay sửa settings/credentials.

## 2. Runtime, dependency và license

Gateway là **Python 3 stdlib**, ACP JSON-RPC qua **NDJSON stdin/stdout**, không SDK/dependency third-party. Node **>=22** chỉ dùng cho bridge public client: operator cung cấp **explicit package root** của official `@getpaseo/cli` **0.15.0**; bridge kiểm metadata/version và resolve client/protocol từ root đó. Không tìm ngầm addon `node_modules`, không tải/cài dependency. Không dùng daemon RPC tự chế hay sửa storage của Paseo.

Code mới theo license repo. Kiểm metadata công khai tại base: không thấy LICENSE/COPYING/NOTICE trong file tracked và manifest plugin/addon không khai license. Vì vậy không vendor/copy code bên ngoài; license distribution là gate deferred của release, không tự gán license. Source/recipe chỉ là bằng chứng thiết kế; license của Paseo không cấp license cho repo này.

## 3. Schema và API chung đã implement offline

Tên dưới đây đối chiếu actual implementation G1/G2/G6, là contract để G3 tích hợp. Record authoritative nằm ngoài isolated writer cwd, không chứa auth/env values; labels chỉ ID an toàn, không chứa prompt. JSON dùng null cho dữ liệu chưa biết. Dataclass công khai bổ sung cuối với default tương thích.

### 3.1 Identity bất biến

`Invocation` frozen, `version=1`:

```text
invocation_id: str (UUID)
scope_id: str                     # parallel.scope_digest(Path(source_root)), độc lập parent
parent_session: str               # sid canonical
parent_paseo_agent_id: str | null
backend: str; account_alias: str; model: str; effort: str
origin: shell | managed | native_intent | legacy_native
source_cwd: str; isolated_cwd: str
fixed_options: dict               # validated timeout/cap/max-turns/sandbox/browser
resource_claims: tuple[str, ...]   # canonical repo/file/dependency write claims
```

Invocation đã pin backend/account; fallback backend tạo invocation mới liên kết logical task, sau khi writer cũ quiescent, không sửa invocation cũ. Follow-up giữ invocation/options, tạo attempt/epoch mới và brief mới; muốn retarget/options khác phải tạo invocation khác qua dispatcher.

`Invocation.scope_id` do dispatcher tính `parallel.scope_digest(Path(source_root))` trong env Sol rồi pin vào invocation/reservation để shell cùng scope. Worker canonical-validates và trusts pinned reservation, không recompute scope từ env daemon; HAND_SCOPE_ENV/CODEX_THREAD_ID của daemon khác Sol được phép. Không dùng scope làm parent. `parallel.canonical_scope` giữ nguyên digest 64 hex, raw scope ID được hash theo `HAND_SCOPE_ENV:<id>`; không truyền path làm raw ID.

`ExecutionKey(invocation_id, attempt_id, epoch)` là frozen dataclass; API nhận key này hoặc tuple ba phần qua `as_key`. `Attempt.key` trả ExecutionKey. `Attempt` có immutable identity `(invocation_id, attempt_id, epoch)` với `epoch >= 1`, `request_key: str` ghi trước network; `run_id: str | null`. Placement fields `target_key`, `project_id`, `workspace_id`, `agent_id`, `thread_id` nullable trước create, sau xác minh chỉ bind một lần; không đổi sang daemon/child khác. `thread_id` là provider execution thread nếu quan sát được, không hứa giữ thread giữa epochs. Agent/workspace history có thể reuse, attempt thì mới.

`ExecutionRecord(version=1, revision: int, invocation, attempt, state, ...)` giữ:

```text
state: intent | prepared | admitted | launching | running | settling | awaiting_review | archived | unresolved | failed
writer: {owner_id, kind, observed_at} | null
process: {pid, pgid, start_identity, supervisor_id} | null
receipt: {request_key, create_ack, prompt_ack, provider_receipt} | null
outcome: {status, reason, backend_exit_code: int|null, provenance, quiescent: bool} | null
artifacts: {baseline_path, patch_path, report_path, ledger_ref} # nullable
settle_keys: {outcome_key, patch_key, report_key, ledger_key}   # nullable
reservation: dict | null
pending_outcome: dict | null       # chưa có authority quiescence
quiescence: {confirmed, evidence, observed_at} | null
started_at, finished_at: number | null
```

`provenance` xác định nguồn worker/runner/native reconciliation, không suy từ UI idle. Settle keys dùng `(invocation_id, attempt_id, epoch, artifact-kind)` để retry không apply/report/ledger lặp. Worker outcome bất biến chỉ publish sau supervisor authority quiescence; trước đó lưu pending_outcome. Durable outcome có thể có trước G3 artifact settlement; chỉ `awaiting_review` khi quiescent và các artifact bắt buộc đã durable.

### 3.2 G1 state/admission/supervisor

`execution_state.py` sở hữu `Invocation`, `Attempt`, `ExecutionRecord`, `ExecutionStore(root)`:

```text
create_intent(invocation, attempt) -> ExecutionRecord
get(invocation_id, attempt_id, epoch) -> ExecutionRecord
compare_and_swap(key, expected_revision, updated) -> ExecutionRecord
bind_placement(key, expected_revision, placement) -> ExecutionRecord
list_unsettled(scope_id) -> list[ExecutionRecord]
```

Persist intent trước create/send; CAS dùng file lock + atomic replace hoặc cơ chế atomic CAS tương đương, khóa xuyên read/validate/write. Conflict trả `StateConflict`; không last-writer-wins. Admission và receipt cập nhật cùng cơ chế; lock-file unlink không là recovery.

`execution_admission.py`: `AdmissionController(store, supervisor, policy_checker)` với `admit(invocation, attempt, *, max_parallel) -> Reservation`, `reconcile_legacy(observations)`, `release(reservation, *, outcome, artifacts_settled)`. `Reservation` gồm `reservation_id`, execution key, `scope_id`, `claims`, `store_root`. Claims được canonicalize qua git common-dir để collapse worktrees; hỗ trợ repo:*, file/path và dependency IDs. Policy checker injectable; mỗi prompt phải kiểm fresh policy/guard và fixed options trước start. Stage 1 dùng fake checker, wiring guard thật thuộc G3; không claim parity đã đạt. Full trả `AdmissionFull` (frontend mapping exit 8), conflict claims trả `AdmissionConflict`, denied policy trả `AdmissionDenied`; transport lỗi không mượn exit 7/8.

Pool chung shell + managed + **reconciled legacy native**, cap `1..4`; retry không giữ hai reservation cho một writer. Unknown/unresolved vẫn chiếm slot; frontend chết, TTL hết, PID mất/reuse, idle/mtime không chứng minh quiescence. Cùng file/phụ thuộc tuần tự cả khác worktree. Native ngoài dispatcher chưa được chặn trước spawn: phải báo giới hạn này đến khi rollout đảm bảo routing mới.

`execution_supervisor.py`: `ProcessIdentity(pid, pgid, start_identity)`, `Quiescence(confirmed, evidence, observed_at)`, `ExecutionSupervisor(store, process_ops)`:

```text
register_writer(key, process_identity, owner_id) -> None
cancel(key, reason) -> Quiescence
reconcile(key) -> Quiescence
record_outcome_once(key, outcome) -> ExecutionRecord
```

Supervisor/process ops sở hữu process group và retained Popen identity; runner có control thì start_new_session, spawned/poll/wait/stop/cancel event qua control, không control giữ legacy behavior. Cancel/timeout/EOF phải stop/reap owned group. Default process ops sau restart bảo thủ, không tự nhận authority từ PID lưu. Chưa có containment cho descendant escape session/group; group còn sống sau leader đã reaped vẫn unresolved và không signal numeric PGID có thể bị reuse. Đây là live gate trước rollout, không hứa containment tuyệt đối. Không xác minh dừng được → unresolved giữ slot. Không dùng signal gửi thành công làm bằng chứng quiescent. G1 duy nhất sửa `parallel.py` để compatibility adapter, chưa tích hợp CLI trong Stage 1.

### 3.3 G2 transport

`PaseoTransport(package_root, target, client_factory=None, *, store=None, node='node')` dùng G1 ExecutionStore; mutation thiếu store bị chặn. Target `instance/home` hoặc `endpoint/host` được đối chiếu normalized fingerprint trước kết nối official client, không tự đổi daemon. API trả dict observation/placement, không dataclass CapabilitySnapshot giả:

```text
probe_capabilities(); verify_parent(parent_agent_id)
ensure_workspace(key, verified_project, isolated_cwd)
create_child(key, placement, *, caller_agent_id, provider_id)
send_prompt(key, brief); reconcile(key)
wait_child(key, timeout_s, poll_interval=0.1, *, require_settlement=False)
cancel_child(key); archive_child(key); reopen_child(key)
```

`record.receipt.transport` là state CAS bền: exact target/project/workspace/agent IDs, workspaceKey/agentKey/messageId, pending workspace/create/send/archive/reopen, cancelPending riêng, confirmations và briefDigest. Persist UUID/idempotency keys trước network, không initialPrompt. `messageId = Attempt.request_key` phải UUID theo gateway; public send dùng activeTurnBehavior=steer (API chỉ interrupt|steer), admission chặn concurrent writer. Public create pin provider `hh-hand-*`, model/effort và env không secret chỉ `HYBRID_HANDS_EXECUTION_ROOT`/`HYBRID_HANDS_INVOCATION_ID`. Verify own workspace/project/cwd/caller parent trước send [E1–E3].

Fresh admitted record chưa có writer/process/outcome/sendConfirmed được dispatch trước khi có quiescence đầu tiên; lượt sau cần authority quiescence. Epoch mới cùng bound IDs chỉ read-only verify workspace/child, không recreate. ACK mất create/send → reconcile ID/receipt, không duplicate hay shell fallback. Cancel khi send còn pending được phép qua cancelPending riêng; cancel ACK chỉ xác nhận request, không process quiescence. Cancel/reopen ACK mất vẫn unresolved tới authoritative proof, không retry mù; public idle không đủ proof và reopen không có refresh receipt API.

`wait_child` bounded read-only đợi outcome và quiescence authority **đúng epoch**, không dùng UI idle làm completed, không mutate receipt/retry/fallback; timeout trả unresolved. Injected client phải tự tuân bounded requests.

Archive đòi `record.artifacts.review.approved is True` và quiescence; `archiveAgent` exact child giữ workspace active, không archive workspace/parent. Reopen exact archived child sau review/quiescence và cwd tồn tại: active workspace recovery `workspace_not_archived` được phép, hoặc action=unarchive có metadata xác minh thì restore/verify trước refresh. Không có unarchiveAgent; refreshAgent có thể interrupt/reload, không polling. Archived workspace vắng public metadata bị blocked trước mutation, không recreate hay hứa recovery đầy đủ. Fake/source evidence chưa chứng minh live API.

### 3.4 G6b worker

`execution_worker.py`: `ExecutionWorker(store, supervisor, runner=None, settlement_hooks=None)` (runner/process ops injectable):

```text
start(invocation, attempt, brief) -> WorkerHandle
cancel(key, reason) -> Quiescence
reconcile(key) -> WorkerObservation
outcome(key) -> WorkerOutcome | null
```

`WorkerHandle` gồm key/owner/process identity; `WorkerObservation` gồm `state`, `quiescence`, `outcome`. `WorkerOutcome` gồm `key`, `status`, `reason`, nullable `backend_exit_code`, `provenance`, nullable `quiescence`, `quiescent`, `artifact_refs`, `final_text`, nullable `usage` (snake keys input/cached_input/output và usage parser hiện có). Default Usage() toàn 0 chưa có observation giữ unknown, không giả đã đo 0. `settlement_hooks` nhận prepared isolation context/artifact refs và idempotency settle keys; không tự mở cwd mới. Start đòi reservation hợp lệ của G1 và fixed invocation; không tự reserve slot thứ hai. Worker là authority ghi outcome một lần qua supervisor/store; retry đọc outcome cũ. Idle Paseo, `.done`, gateway exit không là OS exit backend.

Fixed options chỉ nhận `run_dir`, `sandbox`, `timeout_s`, `max_tokens`, `browser`, `options`; bốn key đầu bắt buộc. `run_dir` là base, thư mục thực là base/hash execution key, lưu `receipt.worker_run_dir`; state root ở ngoài writer/log directory. Worker kiểm backend/account cố định: Codex canonical account là `gpt` (giữ alias `codex`), DSH fixed `dsh`, mismatch bị reject; model/effort tường minh, isolated cwd tồn tại khác source, browser chỉ dsh. Nested options chỉ hỗ trợ existing defaults backend (+ Claude append_system_prompt, DSH browser_dir), reject model/effort/sandbox xung đột và max_turns sai.

Hooks là mapping `kind -> hook(key, idempotency_key, record, outcome) -> refs`; hiện có năm required kinds `finalize`, `report`, `ledger`, `go_ledger`, `usage_state`. Optional `worker.settlement_callback` được completion gắn để kiểm proof và release idempotent sau settlement. Persist settle_keys[kind] `{key, state: in_progress|completed}`; hook crash/ACK ambiguous **không blind repeat**. G3 phải reconcile external sink bằng key rồi đánh dấu completed; đây không là bảo đảm exactly-once ở sink nếu sink chưa hỗ trợ reconcile. Worker giữ state settling và reservation; G3 kiểm mọi REQUIRED hooks durable rồi gọi admission.release một lần sang awaiting_review, không chỉ truyền artifacts_settled=True vì có outcome.

Worker gọi runner nội bộ, không CLI `hand-ext run`, side-session hay native recursion. Có thể adapt hooks của `runner.py`, backend và ledger để lấy process group/exit/parser, giữ scrub/account/sandbox/browser/max-turns/timeout/cap, DSH empty-launch/Go/NDJSON. Stage 1 **không sửa** `run_cmd.py`, `cli.py`, `config.py`, `run_registry.py`, `report.py`, không tự prepare hay quyết định apply policy thay G3. Worker nhận prepared isolation context qua injected runner/hooks; sau authoritative quiescence, worker sở hữu artifact settlement một lần qua hooks và settle keys (finalize/report/ledger), còn G3 sở hữu wiring prepare và policy check/apply. Stage 1 chỉ kiểm hooks bằng fixtures; Stage 2 đã nối runtime report/apply/ledger qua CompletionService (§4), kiểm chứng offline, chưa live. Runner parser/ledger là nguồn usage canonical; ACP projection không tạo ledger thứ hai.

### 3.5 G6a gateway

Python entry `bin/hand-paseo-acp` → `lib/hand_ext/paseo_gateway.py`, `Gateway(store, admission, worker, *, invocation_id=None, max_parallel=1, wait_seconds=30, completion=None)`; NDJSON JSON-RPC handling `initialize`, `session/new`, `session/load`, `session/prompt`, `session/cancel`, `session/close` và EOF. Capability chỉ quảng bá phần có mapping; không tự nhận resume/modes/forks/MCP tùy ý. `session/new/load` bind authoritative record/session ID, xem history không chạy model.

Entry `--state-root`/`--invocation-id` nhận defaults từ `HYBRID_HANDS_EXECUTION_ROOT`/`HYBRID_HANDS_INVOCATION_ID`, yêu cầu binding explicit. Entry hiện gọi `paseo_controller.build_gateway(store, invocation_id)`: chỉ durable controller/completion binding hợp lệ qua `FreshPolicy` mới gắn trusted worker/completion; binding thiếu/sai dùng gateway deny, không worker. `max_parallel` lấy effective policy hiện tại, wait_seconds lấy pinned timeout + 30, không lấy từ ACP params. Đây là G3 wiring đã kiểm offline, chưa chứng minh production/live parity. `session/load` chỉ metadata history, không transcript/CLI context. Prompt thiếu UUID messageId unsupported; Paseo transport gửi UUID request key.

Mỗi prompt UI/API: resolve fixed invocation → CAS epoch/request key → admission fresh → worker.start; duplicate key attach kết quả cũ sau fresh policy check; completed duplicate chỉ policy check không reserve slot. Concurrent epoch bị chặn. Prompt mới có brief tự chứa và epoch mới; không arbitrary retarget cwd/account/model/options từ prompt hay UI metadata. Load không CLI resume. Cancel/close/EOF gọi worker/supervisor; nếu chưa quiescent giữ unresolved, không nhả slot hay báo completed. stdout chỉ protocol, stderr safe diagnostic codes, không forward raw credential/errors. Async input giữ cancel/EOF responsive trong lúc prompt chạy. Success chỉ sau authority outcome, required settlement và release; bounded waiting phải đi xuyên settling tới deadline (đã bổ sung và kiểm bằng final aggregate offline). ACP usage projection từ canonical parser/ledger không thêm ledger. ACP prompt result phản ánh worker outcome; G3 completion hiện kiểm năm required sink proofs và release trước kết quả settled; gateway constructor giữ `completion=None` tương thích caller offline cũ.

### 3.6 Setup provider offline (Stage 2)

Module [paseo_provider.py](../plugins/hybrid-hands/lib/hand_ext/paseo_provider.py) triển khai `setup_provider(home, *, apply=False, package_root=None)` và `status_provider(transport)`; `ProviderError` chỉ mang machine code an toàn. `home` là **Paseo daemon home**, file đích `<home>/config.json`. Official CLI package pin `@getpaseo/cli` **0.15.0**, Node >=22; production validator dùng chính `PersistedConfigSchema.safeParse`, không nhân bản schema. Source đã đối chiếu: `S/server/persisted-config.js:294–305,317,333–335` đặt `agents.providers` và file đích; `S/server/agent/provider-registry.js:484–539` đăng ký custom ACP; `R/provider-config.js:41–96` quy định command argv, label và provider ID.

Setup tạo/cập nhật `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`, mỗi entry `extends: "acp"`, `command: [<plugin>/bin/hand-paseo-acp]`, `enabled: true`; thêm label mặc định khi thiếu, giữ label/env/options và mọi khóa khác. Config/schema/package không hợp lệ hoặc JSON trùng khóa bị từ chối. Dry-run mặc định không ghi, kể cả mkdir/backup. Return gồm `ok`, `applied`, `changed`, `config_path`, `providers`, `changes`, `proposed_updates`, `backup_path`, `reload_required`; `changes` chỉ provider/action, `proposed_updates` chỉ ba giá trị tool sở hữu `command`/`extends`/`enabled` theo provider thay đổi, không echo config/label/env/options có sẵn. Apply backup bytes gốc private 0600 trước atomic write; không tự reload/restart daemon. `reload_required=true` sau ghi: operator cần reload config hoặc restart daemon trước khi dùng catalog để kiểm chứng runtime.

CLI thực dùng tên **`hand-ext provider`**: setup `--home <daemon-home> --package-root <official-cli-root>` với `--dry-run` mặc định hoặc `--apply`; status dùng transport từ config repo qua `--cwd`. Không cần alias `paseo-provider`. Ví dụ lệnh vận hành (apply chưa từng thực thi trên daemon home thật trong gói này):

```sh
hand-ext provider setup --home /absolute/paseo-home --package-root /absolute/official-cli-root --dry-run
hand-ext provider setup --home /absolute/paseo-home --package-root /absolute/official-cli-root --apply
hand-ext provider status --cwd /absolute/claude-plugins
```

`status_provider(transport)` gọi public catalog `transport.probe_capabilities()`; return `providers`, `missing`, `ok`, code `READY` / `PROVIDERS_MISSING` / `CATALOG_UNAVAILABLE`. Config đã ghi không chứng minh provider khả dụng. Setup tests dùng pinned package fixture giả/schema marker và mock validator/subprocess; không vendor upstream, không daemon thật. Narrow provider mới nhất do Sol chạy **3 tests OK (0.025s)**, Sol review vòng 2 đạt; không suy ra smoke backend, live hay release.

## 4. G3 Stage 2 hoàn tất offline; G4+ deferred

G3 controller/completion/provider đã qua Sol review vòng 2. [paseo_controller.py](../plugins/hybrid-hands/lib/hand_ext/paseo_controller.py) cung cấp `FreshPolicy(store)` và `PaseoController.dispatch/approve_review/archive/followup/continue_capacity`. FreshPolicy đọc lại effective repo policy, kiểm immutable backend/account/model/options/sandbox và durable completion binding, gọi preflight backend đã pin cho guard/quota; pool admission giữ cap1..4/exit8. Exhausted order trả exit7; không coi lỗi transport là quota để đổi backend. Dispatch prepare isolated worktree trước network, bind policy/completion rồi admit và tạo đúng child. ACK/crash/cancel chưa rõ giữ unresolved/reservation, reconcile writer cũ, không writer mới.

Config pilot dự kiến ở repo claude-plugins: `ext_hand.mode = "auto"`; shell vẫn default khi không opt-in. `ext_hand.paseo` chỉ `package_root` absolute official CLI root, `target: {kind: "instance", home: <absolute daemon-home>}`, `state_root` optional (default machine_state_dir/executions). Transport còn hỗ trợ explicit endpoint/host theo §3.3. `run --mode` nhận shell/auto/paseo-required. Không sửa config/runtime thật trong gói offline. Auto thiếu daemon/provider/capability chỉ fallback shell **trước dispatch** với backend đã chọn và phần đuôi order; sau mutation/ACK ambiguity không shell fallback. Managed quota/backend fallback chỉ xét sau full settlement/release. DSH capacity patch nhỏ đi backend tiếp theo sau settle; patch lớn tiếp tục cùng invocation/isolated patch qua bounded `continue_capacity`, không fallback sang backend khác.

[CompletionService](../plugins/hybrid-hands/lib/hand_ext/paseo_completion.py) có `bind(key, ctx, *, ledger_path, registry_dir, policy="no_apply", go_ledger=None, go_summary=None, go_monthly_limit=0, codex_ledger=None, quota_path=None, label="")`. Binding immutable trước launch, đòi prepared worktree/cwd đúng identity; policy no_apply/check/apply. `attach(worker)` gắn năm required hooks finalize/report/ledger/go_ledger/usage_state và settlement callback. Sau authoritative quiescence, hooks persist settle key/proof, reconcile external sink theo key; ambiguous in_progress không blind replay apply. `release` chỉ nhả once khi đủ năm completed markers và durable sink proofs, sang awaiting_review. Không owner kép finalize/report/ledger, không lấy có outcome làm settled.

Lifecycle: intent → placement verified → admitted → running → settling → awaiting_review (giữ hiện) → approve_review → archive exact child. Review/archive/followup/capacity chỉ nhận latest exact epoch dưới shared lifecycle lock; chưa quiescent/settled hoặc còn reservation bị chặn. Follow-up cần review/quiescence, brief tự chứa và epoch/request key mới, giữ verified agent/workspace, snapshot baseline mới để không apply patch epoch trước lần hai. Capacity continuation giữ baseline gốc để giữ patch tích lũy. Không CLI/backend context resume (Q5), không auto archive/cleanup worktree.

`wait_child(key, timeout_s, poll_interval=.1, *, require_settlement=False)` giữ compatibility caller Stage 1; controller luôn True, đòi outcome/quiescence và reservation đã release ở awaiting_review/archived. Transport CAS chỉ merge receipt.transport khi nhánh transport không đổi, giữ receipt worker/completion độc lập; concurrent transport conflict vẫn reconcile, không blind retry mutation.

Kiểm chứng Sol báo: controller **3 tests OK (4.067s)**, completion **3 tests OK (0.652s)**, provider **3 tests OK (0.025s)**; review vòng 2 đạt. Aggregate Stage 2 do Sol chạy đúng **một lần**: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_*.py'` → **198 tests OK (27.234s), exit 0**. Code ổn định trước aggregate, sau đó chỉ đổi docs; không chạy thêm test. Node `--check` bridge pass; default plugin validation pass; directory LICENSE_MISSING/ICON_MISSING vẫn là release gate. Không full suite/live/install.

G4 dùng mapping explicit `(target_key, agent_id, epoch)` ↔ invocation/attempt/run/provider thread/parent canonical, một execution một dòng. Managed thuộc hand pool 4, không thêm side-session root hay ăn giới hạn 6 phiên phụ. Native legacy giữ fixed sessions và không giả run/meta/report/ledger. Runner parser/ledger là nguồn managed usage; ACP/Paseo là projection, không cộng rollout + ledger + projection. GPT machine tuần vẫn delta timestamp reset window từ fixed sessions + archived_sessions, dedup thread/event; giá duy nhất [model-prices.json](../plugins/hybrid-hands/config/model-prices.json), thiếu nguồn/giá/quota giữ `?`, không suy quota từ USD. DSH context used/size không billable.

Giữ layout/colors/counts/hidden/selection, giờ kết thúc local/elapsed, không giờ bắt đầu; hh-ps text/JSON giữ orphan, hai UI cây bỏ orphan. Statusline là plugin riêng, không sửa trong scope. G5 policy/release hướng dẫn opt-in qua official setup, không tự sửa settings/credential/install ledger. Live gate/release chưa chạy; Stage 1 không quảng bá supported runtime cho bốn backend chỉ vì có fixture xanh.

## 5. Kiểm chứng và gate còn lại

Kết quả đoạn kế tiếp là lịch sử Stage 1; kết quả Stage 2 hiện tại ở §4: aggregate `test_hand_*.py` 198 OK, không phải full suite repo. G3 offline hoàn tất, G4/G5/live/release chưa hoàn tất.

Theo bàn giao Sol: G1/G2/G6a/G6b mỗi gói 3 tests offline xanh và review xong, aggregate 12 tests OK (6.740s) đúng một lần sau `53a2738`; sau đó compatibility `b5c4243` chỉ narrow execution 3 tests OK (2.852s), không lặp aggregate/full và không claim aggregate trên exact final head; existing parallel 3 + rundir 4 + core token cap 1 + timeout 1 tests đều OK. Node bridge syntax và git diff --check OK. Default validation pass; directory profile còn lỗi LICENSE_MISSING và warning ICON_MISSING; không mở rộng scope sửa chúng. Lượt cập nhật G0 chỉ đọc consumers để mô tả interface, không review hand khác, chỉ sửa hai docs, kiểm link nội bộ và diff; không test cho prose. Stage 1 dùng synthetic fixtures, fake daemon/runner/process ops; mỗi gói một main path và tối đa hai failure/boundary quan trọng. Sol đã chạy từ root `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py'` **một lần** cùng existing regression narrow cho phần thật sự sửa; **không full suite hiện tại**. Không live API/model, không cài dependency/plugin, không tạo resource daemon.

Live gate deferred: cần brief disposable resources/account/trần thời gian/chi phí, kiểm exact placement/parent track, admission UI, stop/reap, ACK recovery, done-review-archive-reopen và smoke từng backend/account trước rollout supported. Public API evidence đã dùng cho transport offline; reopen/stop thực tế vẫn cần live gate trên package root được cấp. License distribution và release/install/version/path thực tế deferred. Không đánh dấu các gate này đã pass.

## 6. Nguồn khảo sát lịch sử (không phải execution plan)

### 1.2 Quy ước bằng chứng

`Đã đọc source` mô tả implementation cài đặt; `đã probe` chỉ nói hàm/fixture đã chạy; `đề xuất` là contract mới chưa tồn tại. Không suy end-to-end từ unit probe. Mọi bằng chứng được đọc ngày **09/11/2026**.

- `P` = `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`.
- `S` = `P/node_modules/@getpaseo/server/dist/server`.
- `C` = `P/node_modules/@getpaseo/client/dist`.
- `R` = `P/node_modules/@getpaseo/protocol/dist`.
- `D` = `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@deepseek-ai/dsh`.
- `H` = `hybrid-hands/plugins/hybrid-hands` tính từ root repo.

Package metadata xác nhận CLI/server/client Paseo **0.15.0**, DSH **0.2.1-rc.5**. Repo nghiên cứu ở `a76826aa1e3ef0ae2ed10aa9b42d066c70c9a070`. Tài liệu public có thể đi trước bản cài; khi khác nhau ưu tiên source 0.15.0.

| Mã | File:dòng hoặc URL công khai — nội dung đã đối chiếu |
|---|---|
| E1 | `C/daemon-client.d.ts:194–212`: create nhận provider/cwd/env/workspace/caller, agentId, idempotencyKey, autoArchive. `R/messages.js:1440–1473`: env chỉ là string map; agentId tạo mới là UUID. |
| E2 | `S/server/agent/create-agent/intent.js:2–28`: cha từ caller, label cha do daemon stamp; explicit workspace trước caller. `S/server/session.js:3310–3346`: public create thay config.cwd bằng intent.cwd. |
| E3 | `S/server/agent/create-agent/create.js:136–173`: resolver MCP dùng resolvedCwd. `P/dist/commands/agent/run.js:368–408,447–459,506–526`: CLI chọn/tạo workspace và truyền caller. `P/dist/utils/caller-agent.js:1–15`: xác minh PASEO_AGENT_ID trên daemon đích. |
| E4 | `R/agent-labels.js:2–17`: label `paseo.parent-agent-id`. `S/server/agent/agent-storage.js:36–59,303–307`: persisted record giữ labels/workspace/cwd/launchEnv và đường JSON theo agent ID. `S/server/agent/agent-manager.js:3999–4007`: inject PASEO_AGENT_ID của chính child. |
| E5 | `S/skills/paseo/SKILL.md:75–93`; `S/skills/paseo-handoff/SKILL.md:53–63`: child giữ parent dù khác workspace, tab/track, send và archive. [Orchestration](https://paseo.sh/docs/orchestration), [workflows](https://paseo.sh/docs/orchestration-workflows), truy cập 09/11/2026. |
| E6 | [OVERVIEW](../paseo-hh-tree/OVERVIEW.md), dòng 5–16,28–30; `P/node_modules/@getpaseo/plugin/dist/client/contracts.d.ts:146–156`: chỉ sidebar header/footer contributions, không hook sửa dòng native. Bundle `S/web-ui/_expo/static/js/web/index-c26368bf062ddf91b40b9d95aae94799.js:18571,18592,18823`: lọc child theo parent label rồi render SubagentsTrack trong ComposerTrackBar; `:16663` là helper parent label. Không dùng sự hiện diện label làm bằng chứng sidebar lồng. |
| E7 | `S/server/agent/provider-registry.js:484–569`: provider custom `extends:acp` cần command; provider kế thừa claude/codex có runtime/env riêng. `S/server/agent/providers/generic-acp-agent.js:4–24`: generic ACP client. [Custom providers](https://paseo.sh/docs/custom-providers), truy cập 09/11/2026. |
| E8 | `S/server/agent/providers/claude/agent.js:1228–1233,1852–1853,2872–2918`: per-launch env, thinkingOptionId → effort, env overlay. `S/server/agent/agent-storage.js:51`: lưu launchEnv. `S/server/agent/provider-launch-config.js:127–143` và `S/server/paseo-env.js:14–30`: merge env daemon, không tự scrub danh sách API key của hand-ext. |
| E9 | `S/server/agent/providers/codex-app-server-agent.js:387,5834–5866`: CODEX_HOME và app-server. Registry E7 chứng minh alias kế thừa codex khả thi; cấu hình `codex-hand` đang dùng được brief cung cấp, phiên này không mở config tài khoản để xác minh. |
| E10 | `D/node_modules/@deepseek-ai/dsh-acp/README.md:55–80`: initialize/new/resume/close/cancel/config, không session/load hay replay. `D/node_modules/@deepseek-ai/dsh-acp-app/cordis.patch.yml:15–20`: profile shipped trỏ deepseek-official/deepseek-v4-flash, khác route hand-ext. |
| E11 | `D/node_modules/@deepseek-ai/dsh-acp/lib/index.js:625–635`: usage_update chỉ context used/size. `S/server/agent/providers/acp-agent.js:1138–1174,2301–2325`: hỗ trợ resume khi không load; context update khác response.usage. |
| E12 | `P/node_modules/@getpaseo/plugin/dist/server/lifecycle.d.ts:93–150`: turn.before là notification, không request gate. `S/server/plugins/lifecycle/index.js:56–80`: các request gate hiện có. [Plugin hooks](https://paseo.sh/docs/plugins/hooks), truy cập 09/11/2026. |
| E13 | `C/daemon-client.d.ts:984–1001`: list/timeline provider subagents, cancelAgent nhận agent ID; không API promote child. `S/server/agent/providers/codex-app-server-agent.js:2518–2538,3834–3870`: session sở hữu app-server và turn/interrupt. [Agent lifecycle](https://github.com/getpaseo/paseo/blob/main/docs/agent-lifecycle.md), truy cập 09/11/2026; không coi main upstream là contract của bản cài. |
| E14 | `P/dist/commands/agent/send.js:143–165`, `wait.js:110`, `stop.js:43–62`, `archive.js:44–63`: send/wait/cancel/archive. `C/daemon-client.js:4378–4399`: wait trả status/final/error, không OS exit backend. |
| E15 | `S/server/session/workspace-recovery/workspace-recovery-service.js:28–74`: còn directory → unarchive; thiếu local directory → unavailable; chỉ owned worktree có đường recreate. `C/daemon-client.d.ts:969–971`: inspect/restore/resume. |
| E16 | `H/lib/side_session/paseo_bridge.mjs:26–93,267–313,334–355`: mẫu target/exact ID, workspace riêng, giữ ID khi follow-up read lỗi, archive workspace có kiểm private. Chỉ tham chiếu snapshot, không sửa vì sol-ws-hoi đang làm. |
| E17 | `H/lib/hand_ext/run_cmd.py:70–114,231–301,493–535`: preflight/day guard, attempt/run/meta/report/ledger/finalize và slot/exit 7/8. `H/lib/hand_ext/parallel.py:29–69`: scope lock kernel, nhả khi controller thoát. |
| E18 | `H/lib/hand_ext/constants.py:94–105,163–172`: defaults order, cap và exit mappings. `git show 6d3e9c7 -- .claude/hybrid-hands.json`: override repo mới codex trước. |
| E19 | `H/lib/hand_ext/isolation.py:133–166,305–343,372–380`: baseline có dirty changes, worktree, patch/check/apply. `H/lib/hand_ext/runner.py:36–40,63–75,93–108,148–184`: scrub, cap/time, pid, parser/report/OS exit. |
| E20 | `H/lib/hand_ext/backends/claude.py:75–94,143–152`; `backends/codex.py:123–143`; `backends/dsh.py:3–20,60–93`: account env, CLI options, DSH launch tránh .env, route Go và NDJSON token. |
| E21 | `H/lib/hh_ps/tree.py:300–341`; `native_source.py:138–158,204–241`; `run_registry.py:68–104`: identity/parent/token nguồn hiện tại, native aliases và attach riêng. |

Bổ sung vòng 2 (đọc 09/11/2026):

| Mã | Bằng chứng |
|---|---|
| E22 | `P/dist/commands/plugin/index.js:143–150`: install là alias add, hỗ trợ registry/directory/Git/npm. `R/plugin-registry.js:10–26,72–83`: artifact pin và registry mặc định. `S/server/plugins/managed-source/registry.js:8–60`: đọc detail JSON, header install chỉ khi cài. `S/server/plugins/builtin/index.js:4–18`: danh sách builtin. Nguồn public và pin từng plugin ở mục 3.5. |
| E23 | Snapshot nhánh sol-ws-hoi **`2eae0b877a226705cd0209cb012861a4fd6d9100`**: `H/lib/side_session/paseo_bridge.mjs:241–273` revive chỉ unarchive workspace còn directory khi agent đã active; `:278–287` rearchive exact private workspace; `H/lib/side_session/actions.py:392–410` finish gọi cleanup/archive khi `.done`, `:414–454` revive bỏ qua marker cũ. Đọc bằng `git show <hash>:<path>`, không sửa file nhánh đó. `C/daemon-client.d.ts:973` có refreshAgent; `S/server/session.js:3501–3525` refresh có unarchive/reload và có thể interrupt agent đang chạy. Phải precheck exact child archived/quiescent; không refresh parent hay dùng refresh làm polling. |
| E24 | `S/skills/paseo-advisor/SKILL.md:14–39,59–65`, `S/skills/paseo-committee/SKILL.md:13–44`, `S/skills/paseo-plugin/SKILL.md:1–24`: mẫu advisor/committee và authoring, không phải quota/patch runner. [License Paseo](https://github.com/getpaseo/paseo/blob/main/LICENSE), Apache-2.0 cho code của Paseo; third-party giữ license riêng. Truy cập 09/11/2026. |

Các source trong repo có thể mở từ [hand-ext](../plugins/hybrid-hands/lib/hand_ext), [hh-ps](../plugins/hybrid-hands/lib/hh_ps), [bridge mẫu](../plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs). Bàn giao nghiên cứu cwd trước đó: `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/sol-ws-chung.md`; chỉ dùng làm ngữ cảnh, các kết luận chính đã đọc lại source.

### Khảo sát registry, plugin và skill có sẵn

**Nguồn và phạm vi (09/11/2026):** đã xem [directory chính thức](https://paseo.sh/plugins), [nhóm orchestration](https://paseo.sh/plugins/category/orchestration?window=all), [plugin reference](https://paseo.sh/docs/plugins/reference), và repository [getpaseo/plugins tại snapshot c64d118](https://github.com/getpaseo/plugins/tree/c64d1181b85d1dcdce552d50496ad1a88d749f9e). Registry mặc định CLI là `https://plugins.paseo.sh`; `install` alias `add` đọc `/plugins/<owner>/<slug>.json`, không phải chạy tìm kiếm rồi install [E22]. [Protocol registry tại pin](https://github.com/getpaseo/plugins/blob/c64d1181b85d1dcdce552d50496ad1a88d749f9e/PROTOCOL.md) mô tả detail JSON và artifact npm integrity/Git commit cố định. Registry chính thức chứa cả plugin cộng đồng, không có nghĩa code do Paseo viết hoặc đồng giấy phép.

GET trực tiếp `plugins.paseo.sh/index.json` bằng HTTP client trả **403**; đã thay bằng directory public + 10 record ở repo registry pin trên + source repo từng plugin. Không dùng install header, không gọi install/reload, không chạy code tải về. Đây là khảo sát có chọn lọc các dispatcher/workflow và plugin hiển thị/lifecycle liên quan, **không kết luận đã audit toàn bộ registry**. Git source pin dưới đây là artifact commit với Git; hai npm package dùng version/integrity từ registry và commit nguồn được record khai báo, chưa tải/đối chiếu byte npm hay runtime compatibility 0.15.0.

**Mẫu chính thức đóng gói trong Paseo 0.15.0:**

| Thành phần | Tạo child và có thể tái dùng gì | Giới hạn / giấy phép |
|---|---|---|
| `paseo` + `paseo-handoff` | `create_agent`/CLI, explicit workspace giữ parent; handoff skill chọn workspace/worktree, brief tự chứa. Tái dùng làm policy mẫu cho B, client/caller/placement vẫn adapter riêng [E3,E5]. | Handoff là chuyển việc cho người dùng tiếp tục, không tự là hand-ext waiter/patch/slot. Code upstream Apache-2.0, phải giữ NOTICE/license khi copy; package third-party có license riêng [E24]. |
| `paseo-advisor`, `paseo-committee` | Chọn profile, create child read-only, wait/synthesize; committee hai góc nhìn [E24]. | Học create/wait/archive; không áp cơ chế hand tự review hay tự chọn profile thay pick; không có quota/patch contract. Cùng license upstream. |
| `paseo-plugin` và orchestration workflows | Skill authoring plugin; [workflows public](https://paseo.sh/docs/orchestration-workflows) có ví dụ worktree-per-task, follow-up, stop và track/tab. | Là recipe/docs, không phải plugin gateway thực thi đã có. Đọc như nguồn nghiên cứu, không invoke workflow. |
| Builtin provider/usage/worktree-include | Danh sách source chỉ gồm các provider, usage-source, worktree-include [E22]. | Không thấy builtin generic hand dispatcher trong danh sách này. Usage account không thay ledger/token per-run. Không đổi provider config để thử. |

**Plugin cộng đồng đối chiếu source:** mỗi hàng dẫn source và license tại commit đã đọc; ngày truy cập chung **09/11/2026**. Không có kết luận “tái dùng được” đồng nghĩa đã test hoặc đã có quyền cài.

| Plugin / pin khảo sát | Làm gì, tạo agent con thế nào | Tái dùng/fork cho hand-ext và giấy phép |
|---|---|---|
| **[gpambrozio/firstmate](https://paseo.sh/plugins/gpambrozio/firstmate)**, npm 0.4.0, source 5989657 | First-mate manager + board; charter dùng MCP create_workspace(worktree) rồi create_agent explicit workspace/model/effort/notify. [Source](https://github.com/gpambrozio/paseo-plugins/blob/5989657e7a37bbbd1a582257d6acf397289750be/firstmate/templates/data/charter.md#L269-L289) | Gần nhất mẫu mỗi worker workspace; có thể học placement/board. Charter không cap concurrency và không tự serialize cùng file, trái pool repo; guard phần lớn là prompt, phải thay routing/review/quota. [MIT](https://github.com/gpambrozio/paseo-plugins/blob/5989657e7a37bbbd1a582257d6acf397289750be/firstmate/LICENSE). |
| **[lerenn/playbooks](https://paseo.sh/plugins/lerenn/playbooks)**, Git 1480de9 (v0.23.1) | YAML DAG, roles, loop, human gates, timeout; runtime tạo workspace.agents.create với parent=manager, rồi send; step cùng run workspace. [Source](https://github.com/lerenn/paseo-playbooks/blob/1480de9c8f1af83d3fd8e23b07066f4dc0d53ca1/server/runtime.ts#L550-L575) | Có thể fork attempt/state/timeout, nhưng phải đổi placement mỗi hand và gắn guards/pool/patch; thừa DAG cho MVP. [Package khai MIT](https://github.com/lerenn/paseo-playbooks/blob/1480de9c8f1af83d3fd8e23b07066f4dc0d53ca1/package.json#L36); không thấy LICENSE riêng tại pin, cần làm rõ notice trước vendor. |
| **[duongvm57/slp](https://paseo.sh/plugins/duongvm57/slp)**, Git 43452ab (v0.9.1) | Supervisor/Lead/Peer desk, assignment/review/evidence; host adapter chuyển parent→callerAgentId, placement tạo agent trong workspace đã kiểm. [Host](https://github.com/duongvm57/paseo-slp-plugin/blob/43452ab06793c7ad6318bb01d9a74652f81727f1/plugin/server/desk-task-execution-host.ts#L26-L27), [placement](https://github.com/duongvm57/paseo-slp-plugin/blob/43452ab06793c7ad6318bb01d9a74652f81727f1/plugin/server/desk-placement.ts#L281-L304) | Học exact placement/recovery; whole plugin sở hữu role pool và cấu hình provider/MCP khác repo, cần viết tích hợp lớn. [MIT](https://github.com/duongvm57/paseo-slp-plugin/blob/43452ab06793c7ad6318bb01d9a74652f81727f1/LICENSE); không kích hoạt/setup. |
| **[gyuha/agent-team](https://paseo.sh/plugins/gyuha/agent-team)**, Git 50e8449 | Tạo orchestrator bằng workspace.agents.create; worker được chỉ dẫn dùng Paseo CLI/MCP, chung workspace, lưu team roles ([README](https://github.com/gyuha/paseo-agent-team/blob/50e84497b220ef44e1986f3328483629aa9fbadf/README.md#L98)). [Source](https://github.com/gyuha/paseo-agent-team/blob/50e84497b220ef44e1986f3328483629aa9fbadf/server/team.ts#L345) | Chỉ tham khảo flow; phải đổi workspace/caller/pool/guard và không thêm manager cạnh Sol. [Tree/package tại pin](https://github.com/gyuha/paseo-agent-team/tree/50e84497b220ef44e1986f3328483629aa9fbadf) không thấy LICENSE hoặc package license: **chưa rõ giấy phép, không chọn copy/fork code**. |
| **[ssime-git/agent-teams](https://paseo.sh/plugins/ssime-git/agent-teams)**, Git 6f9006d (v0.1.2) | Plan/Build/Test/Review persistent; SDK agents.create có idempotency role/cycle, chung workflow workspace, object này không đặt parent. [Source](https://github.com/ssime-git/paseo-agent-teams/blob/6f9006d273ec35235c4bb51e96cb469e0a3422fb/server/runtime.ts#L65-L112) | Học idempotency/role state; chưa chứng minh child của Sol, phải thêm caller và worktree từng hand, giữ Sol tự review. [MIT](https://github.com/ssime-git/paseo-agent-teams/blob/6f9006d273ec35235c4bb51e96cb469e0a3422fb/LICENSE). |
| **[omercnet/agent-crew](https://paseo.sh/plugins/omercnet/agent-crew)**, npm 4.1.2, source 4c6987e | Explorer tree cho managed agents đã có, controls follow-up/redirect/archive, loại archived; không chuyển shell/native thành agent thật. [Source](https://github.com/omercnet/paseo-plugins/blob/4c6987e4c51314032866c723d97d30d571c72344/agent-crew/OVERVIEW.md#L1-L16) | Học UI/identity nếu cần, không là executor/admission; Q2 đã đủ nên không cần thêm panel tương tự Cây phiên. [MIT](https://github.com/omercnet/paseo-plugins/blob/4c6987e4c51314032866c723d97d30d571c72344/agent-crew/LICENSE). |
| **[sm1ee/session-janitor](https://paseo.sh/plugins/sm1ee/session-janitor)**, Git e901fef (v0.1.6) | Archive finished subagents và retention cleanup, kiểm family/children/target; không tạo child. [Source](https://github.com/sm1ee/paseo-session-janitor/blob/e901fef9b00af045ca5a0c4fa74c4d75951d1d30/server/service.ts#L144-L171) | Học guard exact target; **không bật auto-archive** vì Q4 Sol archive sau review, không theo idle/retention của plugin. [MIT](https://github.com/sm1ee/paseo-session-janitor/blob/e901fef9b00af045ca5a0c4fa74c4d75951d1d30/LICENSE). |
| **[epistex-dev/parent-wake](https://paseo.sh/plugins/epistex-dev/parent-wake)**, Git 7a4d46a (v0.3.0) | Hook permission/turn finished rồi parent.send system message; không tạo worker. [Source](https://github.com/epistex-dev/paseo-subagent-notifications/blob/7a4d46a92be4bcae93a69ad384caf33c185e66e2/index.server.ts#L18-L65) | Học notification/dedup nếu thực sự thiếu, không thay .done/report/guard. Không bật gửi thông báo trong nghiên cứu này. [MIT](https://github.com/epistex-dev/paseo-subagent-notifications/blob/7a4d46a92be4bcae93a69ad384caf33c185e66e2/LICENSE). |
| **[lanioque/agent-tree](https://paseo.sh/plugins/lanioque/agent-tree)**, Git 85aee7c | Đọc Claude native subagents/workflow/background metadata và transcript để vẽ tree; không promote thành daemon child. [RPC source](https://github.com/Lanioque/paseo-agent-tree/blob/85aee7c4690daeacea4e6eb40cf7ddf8077c34fc/index.server.ts#L1-L12), [reader](https://github.com/Lanioque/paseo-agent-tree/blob/85aee7c4690daeacea4e6eb40cf7ddf8077c34fc/server/transcript.ts) | Học view, không đạt stop/archive riêng; không tái dùng đọc nội dung thật cho hand nghiên cứu. [MIT](https://github.com/Lanioque/paseo-agent-tree/blob/85aee7c4690daeacea4e6eb40cf7ddf8077c34fc/LICENSE). |
| **[sbhas2k/workflow-progress](https://paseo.sh/plugins/sbhas2k/workflow-progress)**, Git f433cbe | Cards tiến độ Claude Workflows từ journal/transcript, native subagents nằm trong cùng Claude session; không create agent độc lập. [Source](https://github.com/sbhas2k/paseo-plugins/blob/f433cbe0acd49262a46f186a524d2d527219685a/workflow-progress/index.server.ts#L10-L45) | Không thay executor Codex/hand-ext; chỉ mẫu presentation và vẫn cần metadata-only adaptation. [MIT](https://github.com/sbhas2k/paseo-plugins/blob/f433cbe0acd49262a46f186a524d2d527219685a/workflow-progress/LICENSE). |


Bảng khảo sát chỉ giữ attribution và nguồn/pin đã đọc trước đây; không cho phép cài/copy/chạy plugin bên ngoài hoặc mở lane B/C. Các probe P1/P2/P3 lịch sử là fixture resolver/env/context, không phải live gate; G0 lần này không chạy lại hay xác nhận thêm chúng.
