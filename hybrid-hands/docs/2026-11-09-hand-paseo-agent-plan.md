# Hand/subagent thành agent Paseo — plan lane A

[Spec và interface chuẩn](2026-11-09-hand-paseo-agent-spec.md). Base **cee82cc**, đã gồm main **fd7d071**, plugin/revive **0.33.1**. Chỉ lane A ACP gateway cho codex/dsh/claude-v1/claude-v2. B direct Codex giảm guard UI/OS-exit parity; C chưa có drop-in giữ hand-ext, nên cả hai bỏ khỏi execution.

Implementation đã commit: G0 `a67f050`, G1 `af71045`, G6a `fa87ef5`, G2 `cb756dd`, G6b `3def687`, gateway settlement fix `53a2738`, compatibility fix `b5c4243`. Theo bàn giao Sol, G1/G2/G6a/G6b mỗi gói 3 tests offline xanh và Sol review hoàn tất; lượt docs này không chạy lại tests/review hand khác. Gateway bounded wait xuyên settling đã được Sol sửa và narrow 3 tests xanh. Aggregate đúng một lần sau `53a2738`: 12 tests OK (6.740s). Sau đó `b5c4243` sửa account/scope, chỉ narrow execution 3 tests OK (2.852s), không lặp aggregate/full và không claim aggregate trên exact final head; existing parallel 3 + rundir 4 + core token cap 1 + timeout 1 đều OK; không full/live/install.

## 1. Gate và phạm vi hiện tại

- [x] **G0 quyết định:** Q1 A; Q2 own workspace cùng verified project + caller parent track/tab; Q3 new native Sol-low intent đi hand Paseo sau rollout, existing native không migrate; Q4 done giữ hiện, Sol review/archive exact child, follow-up reopen; Q5 history Paseo + epoch/brief mới, không CLI resume; Q6 MVP không cleanup worktree; Q7 shell default, opt-in claude-plugins, thiếu daemon/capability fallback shell trước dispatch.
- [x] **G0 interface:** schema/API/ownership chốt ở spec §3; Python 3 stdlib ACP NDJSON, Node >=22 bridge official @getpaseo/cli 0.15.0 từ explicit operator package root, không addon node_modules/third-party SDK. Repo metadata chưa khai license: không vendor/copy code ngoài, distribution license deferred release.
- [x] **G0 docs:** base/revive cập nhật; không xác nhận live gate, không đổi code/config/manifest/runtime.
- [x] **Stage 1 implementation:** G1/G2/G6a/G6b offline fixtures và review từng gói đã hoàn tất theo bàn giao Sol.
- [x] **Stage 1 offline final verification:** aggregate 12 sau 53a2738 + existing narrow regressions xanh; sau compatibility b5c4243 chỉ narrow execution 3 xanh, aggregate không lặp trên final head. Gateway bounded settlement wait đã kiểm. Không full/live/install. Dependencies: G1 trước consumers; G2 khác file có thể làm song song; G6b theo interface G1; G6a consume G1/G6b. Không writer chung file/phụ thuộc đồng thời.
- [ ] **Deferred G3+** integration, usage/UI/policy, live, release/install; không tự mở scope từ Stage 1.

G0 executor chỉ hai docs, không commit/push/merge. Các gói triển khai cần brief phạm vi ghi riêng; hand làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Sol review theo policy; tổng pool 1..4, không đổi slots/config hay bật parallel-subagents. Order theo repo hiệu lực, không đảo theo config worktree cũ.

## 2. G1 — state, admission, supervisor

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/execution_state.py`, `execution_admission.py`, `execution_supervisor.py`; chỉ G1 sửa `parallel.py`. Test `tests/test_hand_paseo_admission.py`. Đường dẫn từ `hybrid-hands/`; basename liệt kê tiếp thuộc cùng thư mục.

- [x] Implement `Invocation`, `Attempt`, `ExecutionRecord`, `ExecutionStore` và methods spec §3.1–3.2. Immutable invocation version=1, dispatcher tính scope=parallel.scope_digest(source_root) trong env Sol rồi pin invocation/reservation khớp shell; worker canonical-validates/trusts pinned reservation, không recompute env daemon khác HAND_SCOPE_ENV/CODEX_THREAD_ID (raw IDs qua canonical_scope/HAND_SCOPE_ENV), độc lập parent canonical, fixed options/claims; attempt key/epoch>=1/request_key và placement nullable trước create. Durable intent trước network, CAS/file lock + atomic replace; bind IDs một lần. ExecutionKey dataclass/tuple adapter; record có reservation/pending_outcome/quiescence và state launching; immutable outcome chỉ publish sau supervisor authority quiescence.
- [x] `AdmissionController.admit/reconcile_legacy/release`, Reservation và typed errors. Pool shell+managed+reconciled legacy native cap1..4, unknown giữ slot, claims cùng file/phụ thuộc tuần tự, retry không hai slots. Policy checker injected, G3 wiring thật deferred.
- [x] `ExecutionSupervisor.register_writer/cancel/reconcile/record_outcome_once`, process group/start identity, stop/reap/quiescence evidence. Default sau restart conservative; chỉ owned group, chưa containment descendant escape session; leader reaped mà group còn sống unresolved, không signal reused PGID. Không PID/TTL/mtime/idle suy chết, không unlink lock để tạo chỗ; frontend chết vẫn giữ unresolved.

Fixture: mixed pool/scope main path; frontend chết fake writer sống; duplicate epoch/claims CAS conflict. Regression parallel narrow nếu sửa compatibility. Không test lại kernel/framework.

## 3. G2 — public transport và exact placement/reopen

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/paseo_transport.py`, `paseo_bridge.mjs`; test `tests/test_hand_paseo_transport.py`, fixtures `tests/fixtures/hand_paseo/transport/`. Không sửa `lib/side_session/*`.

- [x] Implement `PaseoTransport(package_root,target,client_factory=None,*,store=None,node="node")` methods spec §3.3, injected fake client, official package root/version check. Read-only source/API evidence trước mutation; pinned target và provider capability catalog. Không raw RPC/storage/config edits.
- [x] Own workspace tại isolated cwd đã chuẩn bị, cùng verified project; exact workspaceId/callerAgentId. Persist create IDs/idempotencyKey trước request; **không initialPrompt**. Verify exact target/project/cwd/parent/provider/IDs trước send; messageId=Attempt.request_key UUID persist trước send; receipt.transport CAS giữ pending/cancelPending/confirmations. Public create env nonsecret execution root/invocation ID cùng pinned model/effort/provider. Fresh admitted no-writer dispatch trước q được phép; epoch sau same bound IDs read-only verify, không recreate. wait_child(key,timeout_s,poll_interval=.1) bounded read-only current-epoch outcome/q, không UI idle. API activeTurnBehavior chỉ interrupt|steer, không invent reject/enqueue; admission/precheck chặn concurrent turn.
- [x] ACK create/send mất: reconcile exact IDs/key/receipt, không duplicate/fallback shell. Archive đòi artifacts.review.approved và q; archiveAgent exact child giữ workspace active. Cancel được phép khi send pending; lost cancel/reopen ACK unresolved không retry mù. Reopen API gate: không có unarchiveAgent; active workspace hoặc verified action=unarchive + cwd tồn tại + durable quiescence trước exact refreshAgent; archived workspace thiếu public metadata blocked, không recreate; source có thể interrupt/reload, không refresh polling/parent. Verify cùng agent/workspace sau revive 0.33.1, không hứa backend thread giữ nguyên. API thiếu an toàn → blocked.

Fixture: own placement/caller/archive-reopen cùng IDs; ACK mất không duplicate/send/fallback; wrong target/parent hoặc missing cwd chặn mutation. Source/fixture không chứng minh live API thành công.

## 4. G6b — worker và settlement hooks

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/execution_worker.py`; được adapt hooks `runner.py`, backend/parser/ledger khi cần, tránh writer chung. Test `tests/test_hand_paseo_execution.py`. **Không sửa run_cmd.py/cli.py/config.py/run_registry.py/report.py** trong Stage 1.

- [x] `ExecutionWorker(store, supervisor, runner=None, settlement_hooks=None)`, `start(invocation, attempt, brief)`, `cancel`, `reconcile`, `outcome`, WorkerHandle/Observation/Outcome đúng spec §3.4. Inject runner/process ops cho test; đòi reservation hợp lệ, không reserve lần hai, worker authority outcome once sau q; trước q lưu pending_outcome. WorkerOutcome có final_text/nullable usage snake input/cached_input/output/artifact_refs, default Usage0 chưa observation giữ unknown. Fixed_options chỉ run_dir(base),sandbox,timeout_s,max_tokens,browser,options; receipt.worker_run_dir là subdir hash execution key. Validate backend/account/default backend opts (Codex canonical account gpt, alias codex; dsh fixed dsh; mismatch reject), reject conflicting model/effort/sandbox.
- [x] Process groups/supervisor cancel/EOF/crash; nullable backend_exit_code và provenance, unresolved giữ slot nếu chưa quiescent. Không lấy .done/wait/idle làm exit0.
- [x] Prepared isolation context do G3 cung cấp sau; worker sở hữu finalize/report/ledger hooks và settle keys một lần **sau authoritative quiescence**, G3 sở hữu prepare/apply policy. Hook kind -> (key,idempotency_key,record,outcome)->refs lưu in_progress/completed; crash ambiguous không blind repeat, G3 reconcile sink bằng key. Worker giữ settling/reservation; G3 phải kiểm mọi REQUIRED hooks durable rồi admission.release once sang awaiting_review. Stage 1 fake hooks, không tự implement integration hoặc apply source. Giữ account/scrub/options/DSH empty-launch Go NDJSON của runner; không CLI recursion.
- [x] Canonical parser/ledger usage; ACP chỉ projection, không additive ledger, thiếu giá/token/quota giữ unknown.

Fixture: start/outcome/settlement once bằng injected hooks; cancel/EOF writer chưa dừng giữ slot; duplicate/reconcile không outcome hay ledger lặp. Không test lại framework.

## 5. G6a — ACP protocol

**Owner:** mới `plugins/hybrid-hands/bin/hand-paseo-acp`, `lib/hand_ext/paseo_gateway.py` dưới plugin; test `tests/test_hand_paseo_gateway.py`. Gateway constructor keyword invocation_id, max_parallel=1, wait_seconds=30; G3 supply trusted policy limits/deadline phù hợp task. Entry --state-root/--invocation-id hoặc env execution root/invocation ID deny mọi prompt tới khi trusted G3 checker/worker wiring; không tự có production day_guard/quota/capacity. Python 3 stdlib, stdout NDJSON JSON-RPC sạch, diagnostics safe stderr.

- [x] `Gateway(store, admission, worker)` initialize/session/new/load/prompt/cancel/close + EOF theo spec §3.5. Capability chỉ phần implement; load chỉ metadata history không chạy model/CLI resume; UUID messageId bắt buộc (transport gửi request key).
- [x] Resolve fixed authoritative invocation; mỗi prompt UI/API qua fresh policy/admission, epoch/brief tự chứa mới, CAS/idempotency. Duplicate attach fresh policy, completed duplicate policy-only không slot; concurrent chặn; không arbitrary retarget cwd/account/backend/model/options qua prompt/UI.
- [x] Async input responsive cancel/EOF; success chỉ settled/released authority, bounded settling wait tới deadline đã được bổ sung và kiểm offline. Cancel/close/EOF dùng worker/supervisor quiescence, chưa rõ unresolved không release; ACP result theo worker outcome, không claim patch/report đã xong khi G3 chưa wire hooks. Context occupancy tách billable usage.

Fixture: handshake+prompt/outcome main path; cancel/EOF fake writer sống; history/duplicate/concurrent không start CLI lặp.

## 6. Kiểm chứng Stage 1

G0 cập nhật interface theo actual consumers, kiểm diff và link nội bộ, không tests cho prose. Kết quả từng gói nêu trên lấy từ bàn giao Sol, không phải aggregate hay kiểm chứng live. Các gói chạy test hẹp đúng phần đổi, tối đa main path + hai biên quan trọng. Sol đã chạy aggregate đúng **một lần** sau `53a2738` từ repo root (12 tests OK, 6.740s). Compatibility `b5c4243` đến sau và chỉ chạy narrow execution 3 tests OK (2.852s); không lặp aggregate/full, không xác nhận aggregate trên exact final head:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py'
```

Existing parallel 3 + rundir 4 + core token cap 1 + timeout 1 tests đều OK. Node bridge syntax/git diff --check OK; default validation pass; directory profile còn lỗi LICENSE_MISSING và warning ICON_MISSING (không mở rộng scope sửa). Kết quả do Sol cung cấp; không full suite hiện tại, không claim test/cài đặt/live đã chạy từ kế hoạch. Không daemon thật/model API/transcript thật, không tải dependency hay tạo key. Sol review source/diff và semantics ownership/identity/quiescence/settlement, không chỉ đếm test xanh.

## 7. Deferred G3+ và release gates

- [ ] **G3:** controller/completion và run_cmd/cli/config/run_registry/report integration; preflight/order/guard/quota/capacity/exit7/8, isolation.prepare, injected finalize/report hooks và apply policy sau quiescence, required artifact settle durable/reconcile sink trước release, không blind replay in_progress hooks. Không owner kép worker finalization. Shell default, opt-in claude-plugins; native-intent mới route sau rollout, legacy giữ nguyên. ACK ambiguity không shell fallback.
- [ ] **G4:** hh-ps mapping/one execution one row, canonical parser/ledger projection dedup, legacy native fixed sources; giữ counts/colors/hidden/layout/no start time/orphan contract; không sửa statusline ngoài scope riêng.
- [ ] **G5:** policy/templates/docs vận hành; Q2–Q7 nhất quán, official setup provider, không settings/credential edits hay manager cộng đồng. UI chỉ khi cần và brief riêng.
- [ ] **G7 live:** quyền disposable resources/account/trần thời gian/chi phí riêng; test own workspace/project/parent track, admission cả UI, exact stop/reap/ACK recovery, done giữ hiện → review/archive → follow-up reopen epoch mới; smoke từng backend/account trước quảng bá supported. Stage 1 chưa pass bất kỳ live gate nào.
- [ ] **Release:** license distribution, version/changelog theo main thực, plugin validate, test hẹp đã review; brain điều phối commit/push/merge theo brief. Update plugin qua official tooling ở các repo đang dùng, kiểm version/path thực nạp và báo reload nếu không hot load. Không tự bật repo mới, không sửa sổ cài đặt/settings. Không release/bump/install từ gói docs này.

## 8. Luật dữ liệu nguyên văn vào mọi brief hand

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

G0 done là hai docs thống nhất/interface đủ để giao gói, đã kiểm links/diff; không đồng nghĩa code, daemon capability, live gate hay release hoàn tất.
