# Hand/subagent thành agent Paseo — plan lane A

[Spec và interface chuẩn](2026-11-09-hand-paseo-agent-spec.md). Base **cee82cc**, đã gồm main **fd7d071**, plugin/revive **0.33.1**. Chỉ lane A ACP gateway cho codex/dsh/claude-v1/claude-v2. B direct Codex giảm guard UI/OS-exit parity; C chưa có drop-in giữ hand-ext, nên cả hai bỏ khỏi execution.

## 1. Gate và phạm vi hiện tại

- [x] **G0 quyết định:** Q1 A; Q2 own workspace cùng verified project + caller parent track/tab; Q3 new native Sol-low intent đi hand Paseo sau rollout, existing native không migrate; Q4 done giữ hiện, Sol review/archive exact child, follow-up reopen; Q5 history Paseo + epoch/brief mới, không CLI resume; Q6 MVP không cleanup worktree; Q7 shell default, opt-in claude-plugins, thiếu daemon/capability fallback shell trước dispatch.
- [x] **G0 interface:** schema/API/ownership chốt ở spec §3; Python 3 stdlib ACP NDJSON, Node >=22 bridge official @getpaseo/cli 0.15.0 từ explicit operator package root, không addon node_modules/third-party SDK. Repo metadata chưa khai license: không vendor/copy code ngoài, distribution license deferred release.
- [x] **G0 docs:** base/revive cập nhật; không xác nhận live gate, không đổi code/config/manifest/runtime.
- [ ] **Stage 1:** G1/G2/G6a/G6b offline fixtures và review. G1 trước consumers; G2 khác file có thể làm song song; G6b theo interface G1; G6a consume G1/G6b. Không writer chung file/phụ thuộc đồng thời.
- [ ] **Deferred G3+** integration, usage/UI/policy, live, release/install; không tự mở scope từ Stage 1.

G0 executor chỉ hai docs, không commit/push/merge. Các gói triển khai cần brief phạm vi ghi riêng; hand làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Sol review theo policy; tổng pool 1..4, không đổi slots/config hay bật parallel-subagents. Order theo repo hiệu lực, không đảo theo config worktree cũ.

## 2. G1 — state, admission, supervisor

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/execution_state.py`, `execution_admission.py`, `execution_supervisor.py`; chỉ G1 sửa `parallel.py`. Test `tests/test_hand_paseo_admission.py`. Đường dẫn từ `hybrid-hands/`; basename liệt kê tiếp thuộc cùng thư mục.

- [ ] Implement `Invocation`, `Attempt`, `ExecutionRecord`, `ExecutionStore` và methods spec §3.1–3.2. Immutable invocation version=1, scope độc lập parent canonical, fixed options/claims; attempt key/epoch>=1/request_key và placement nullable trước create. Durable intent trước network, CAS/file lock + atomic replace; bind IDs một lần.
- [ ] `AdmissionController.admit/reconcile_legacy/release`, Reservation và typed errors. Pool shell+managed+reconciled legacy native cap1..4, unknown giữ slot, claims cùng file/phụ thuộc tuần tự, retry không hai slots. Policy checker injected, G3 wiring thật deferred.
- [ ] `ExecutionSupervisor.register_writer/cancel/reconcile/record_outcome_once`, process group/start identity, stop/reap/quiescence evidence. Không PID/TTL/mtime/idle suy chết, không unlink lock để tạo chỗ; frontend chết vẫn giữ unresolved.

Fixture: mixed pool/scope main path; frontend chết fake writer sống; duplicate epoch/claims CAS conflict. Regression parallel narrow nếu sửa compatibility. Không test lại kernel/framework.

## 3. G2 — public transport và exact placement/reopen

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/paseo_transport.py`, `paseo_bridge.mjs`; test `tests/test_hand_paseo_transport.py`, fixtures `tests/fixtures/hand_paseo/transport/`. Không sửa `lib/side_session/*`.

- [ ] Implement `PaseoTransport` methods spec §3.3, injected fake client, official package root/version check. Read-only source/API evidence trước mutation; pinned target và provider capability catalog. Không raw RPC/storage/config edits.
- [ ] Own workspace tại isolated cwd đã chuẩn bị, cùng verified project; exact workspaceId/callerAgentId. Persist create IDs/idempotencyKey trước request; **không initialPrompt**. Verify exact target/project/cwd/parent/provider/IDs trước send; messageId persist trước send. API activeTurnBehavior chỉ interrupt|steer, không invent reject/enqueue; admission/precheck chặn concurrent turn.
- [ ] ACK create/send mất: reconcile exact IDs/key/receipt, không duplicate/fallback shell. Archive chỉ Sol sau review. Reopen API gate: không có unarchiveAgent; inspect action=unarchive + cwd tồn tại + durable quiescence trước exact refreshAgent; source có thể interrupt/reload, không refresh polling/parent. Verify cùng agent/workspace sau revive 0.33.1, không hứa backend thread giữ nguyên. API thiếu an toàn → blocked.

Fixture: own placement/caller/archive-reopen cùng IDs; ACK mất không duplicate/send/fallback; wrong target/parent hoặc missing cwd chặn mutation. Source/fixture không chứng minh live API thành công.

## 4. G6b — worker và settlement hooks

**Owner:** mới `plugins/hybrid-hands/lib/hand_ext/execution_worker.py`; được adapt hooks `runner.py`, backend/parser/ledger khi cần, tránh writer chung. Test `tests/test_hand_paseo_execution.py`. **Không sửa run_cmd.py/cli.py/config.py/run_registry.py/report.py** trong Stage 1.

- [ ] `ExecutionWorker(store, supervisor, runner, settlement_hooks=None)`, `start(invocation, attempt, brief)`, `cancel`, `reconcile`, `outcome`, WorkerHandle/Observation/Outcome đúng spec §3.4. Inject runner/process ops cho test; đòi reservation hợp lệ, không reserve lần hai, worker authority outcome once.
- [ ] Process groups/supervisor cancel/EOF/crash; nullable backend_exit_code và provenance, unresolved giữ slot nếu chưa quiescent. Không lấy .done/wait/idle làm exit0.
- [ ] Prepared isolation context do G3 cung cấp sau; worker sở hữu finalize/report/ledger hooks và settle keys một lần **sau authoritative quiescence**, G3 sở hữu prepare/apply policy. Stage 1 fake hooks, không tự implement integration hoặc apply source. Giữ account/scrub/options/DSH empty-launch Go NDJSON của runner; không CLI recursion.
- [ ] Canonical parser/ledger usage; ACP chỉ projection, không additive ledger, thiếu giá/token/quota giữ unknown.

Fixture: start/outcome/settlement once bằng injected hooks; cancel/EOF writer chưa dừng giữ slot; duplicate/reconcile không outcome hay ledger lặp. Không test lại framework.

## 5. G6a — ACP protocol

**Owner:** mới `plugins/hybrid-hands/bin/hand-paseo-acp`, `lib/hand_ext/paseo_gateway.py` dưới plugin; test `tests/test_hand_paseo_gateway.py`. Python 3 stdlib, stdout NDJSON JSON-RPC sạch, diagnostics safe stderr.

- [ ] `Gateway(store, admission, worker)` initialize/session/new/load/prompt/cancel/close + EOF theo spec §3.5. Capability chỉ phần implement; load history không chạy model/CLI resume.
- [ ] Resolve fixed authoritative invocation; mỗi prompt UI/API qua fresh policy/admission, epoch/brief tự chứa mới, CAS/idempotency. Duplicate attach, concurrent chặn; không arbitrary retarget cwd/account/backend/model/options qua prompt/UI.
- [ ] Cancel/close/EOF dùng worker/supervisor quiescence, chưa rõ unresolved không release; ACP result theo worker outcome, không claim patch/report đã xong khi G3 chưa wire hooks. Context occupancy tách billable usage.

Fixture: handshake+prompt/outcome main path; cancel/EOF fake writer sống; history/duplicate/concurrent không start CLI lặp.

## 6. Kiểm chứng Stage 1

G0 kiểm diff và link nội bộ, không tests cho prose. Các gói chạy test hẹp đúng phần đổi, tối đa main path + hai biên quan trọng. Cuối Stage 1 Sol chạy đúng **một lần** từ `hybrid-hands/`:

```sh
python3 -m unittest discover -s tests -p 'test_hand_paseo_*.py'
```

Thêm existing regression narrow phù hợp runner/parser/ledger/parallel thực đổi; không full suite hiện tại, không claim test/cài đặt/live đã chạy từ kế hoạch. Không daemon thật/model API/transcript thật, không tải dependency hay tạo key. Sol review source/diff và semantics ownership/identity/quiescence/settlement, không chỉ đếm test xanh.

## 7. Deferred G3+ và release gates

- [ ] **G3:** controller/completion và run_cmd/cli/config/run_registry/report integration; preflight/order/guard/quota/capacity/exit7/8, isolation.prepare, injected finalize/report hooks và apply policy sau quiescence, artifact settle once. Không owner kép worker finalization. Shell default, opt-in claude-plugins; native-intent mới route sau rollout, legacy giữ nguyên. ACK ambiguity không shell fallback.
- [ ] **G4:** hh-ps mapping/one execution one row, canonical parser/ledger projection dedup, legacy native fixed sources; giữ counts/colors/hidden/layout/no start time/orphan contract; không sửa statusline ngoài scope riêng.
- [ ] **G5:** policy/templates/docs vận hành; Q2–Q7 nhất quán, official setup provider, không settings/credential edits hay manager cộng đồng. UI chỉ khi cần và brief riêng.
- [ ] **G7 live:** quyền disposable resources/account/trần thời gian/chi phí riêng; test own workspace/project/parent track, admission cả UI, exact stop/reap/ACK recovery, done giữ hiện → review/archive → follow-up reopen epoch mới; smoke từng backend/account trước quảng bá supported. Stage 1 chưa pass bất kỳ live gate nào.
- [ ] **Release:** license distribution, version/changelog theo main thực, plugin validate, test hẹp đã review; brain điều phối commit/push/merge theo brief. Update plugin qua official tooling ở các repo đang dùng, kiểm version/path thực nạp và báo reload nếu không hot load. Không tự bật repo mới, không sửa sổ cài đặt/settings. Không release/bump/install từ gói docs này.

## 8. Luật dữ liệu nguyên văn vào mọi brief hand

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

G0 done là hai docs thống nhất/interface đủ để giao gói, đã kiểm links/diff; không đồng nghĩa code, daemon capability, live gate hay release hoàn tất.
