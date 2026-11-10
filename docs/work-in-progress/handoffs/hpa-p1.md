## Tóm tắt

- Kết quả: G0 + G1 + G2 + G6a + G6b xong offline trên `side/hpa-p1`, đã review và commit theo gói.
- Commits: G0 `a67f050`; G1 `af71045`; G6a `fa87ef5`; G2 `cb756dd`; G6b `3def687`; settlement `53a2738`; account/scope compatibility `b5c4243`.
- Đồng bộ spec/plan theo implementation và test thực: `54480e7` (HEAD); worktree sạch, không push/merge/main.
- Spec/plan chốt lane A, Q1–Q7 và interface G3/G4/G5; code mới state/admission/supervisor/transport/bridge/gateway/worker + ACP entry; chỉ sửa code cũ `parallel.py`, `runner.py`.
- Có bốn test module mới, mỗi module ba nhóm, cùng fake Node client/package fixture; Sol review diff từng gói và giao sửa các lỗi phát hiện.
- Aggregate chạy đúng một lần: 12/12 OK; regression parallel 3 + rundir 4 + core cap 1 + timeout 1 đều OK. Sau compatibility cuối, worker narrow 3/3 OK; không lặp aggregate/full.
- Default plugin validation pass; directory submission có lỗi LICENSE_MISSING và warning ICON_MISSING. Bridge syntax, diff và link nội bộ xanh.
- G3 integration/production guards, G4/G5, live pilot/provider registration, release/install chưa làm theo scope. Standalone ACP entry cố ý deny prompt tới khi G3 nối policy/worker tin cậy.
- Cần Opus lưu ý license distribution chưa có khai báo repo, recovery workspace archived bị giới hạn public API, descendant escape session/group chưa containment; xem chi tiết bên dưới.

## Nhánh và phạm vi

Worktree `/Users/anhtp/app/claude-plugins-wt/hpa-p1`, nhánh `side/hpa-p1`, base `cee82cc` gồm main `fd7d071` và revive 0.33.1. Không push, merge hay commit main. Không bump version/CHANGELOG hoặc update runtime/install/provider. Không sửa side_session, hh_ps, run_cmd, cli, config, run_registry, report, skills/templates/README/OVERVIEW, settings/credentials. Không tạo/mutate agent/workspace/project Paseo thật, không gọi daemon để pilot. Không tải dependency/API key. Giữ nguyên `output/llm/`.

## File mới/sửa và lý do

Đường dẫn bảng dưới từ `hybrid-hands/`:

| File | Thay đổi và lý do |
| --- | --- |
| `docs/2026-11-09-hand-paseo-agent-spec.md` | Chốt lane A/Q1–Q7 và schema/API thực tế, ghi rõ offline/production gates. |
| `docs/2026-11-09-hand-paseo-agent-plan.md` | Bỏ B/C khỏi execution, tick G0 và các gói offline, giữ G3+ deferred. |
| `plugins/hybrid-hands/lib/hand_ext/execution_state.py` | Invocation bất biến, ExecutionKey/Attempt, store CAS/file lock/atomic fsync, bind placement một lần. |
| `plugins/hybrid-hands/lib/hand_ext/execution_admission.py` | Pool chung, claims, durable reservation và legacy observation; unknown không nhả slot. |
| `plugins/hybrid-hands/lib/hand_ext/execution_supervisor.py` | Writer/process identity, quiescence authority, pending outcome và immutable terminal outcome. |
| `plugins/hybrid-hands/lib/hand_ext/parallel.py` | Compatibility shell slots chia pool với managed reservation, giữ existing shell semantics. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_transport.py` | Shared-store transport intent/receipts, bounded wait và exact child lifecycle. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs` | Official public client từ explicit pinned CLI package root, không raw RPC hay addon dependencies. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_gateway.py` | ACP JSON-RPC NDJSON, durable prompt/epoch claim, fresh policy, concurrent cancel/EOF và outcome projection. |
| `plugins/hybrid-hands/bin/hand-paseo-acp` | Executable Python entry, explicit binding env/flags, mặc định fail closed. |
| `plugins/hybrid-hands/lib/hand_ext/execution_worker.py` | Internal async runner, owner claim trước launch, process-group authority, artifact settlement hooks không replay mù. |
| `plugins/hybrid-hands/lib/hand_ext/runner.py` | Optional control hooks cho process group/cancel/poll/wait/cleanup; managed report đi settlement, legacy caller giữ hành vi cũ. Không cần sửa backend/parser/ledger. |
| `tests/test_hand_paseo_admission.py` | Ba nhóm mixed pool/scope, frontend death, duplicate/CAS/claims. |
| `tests/test_hand_paseo_transport.py` | Ba nhóm placement/archive/reopen/follow-up, ACK loss/wait, mismatch/missing cwd. |
| `tests/test_hand_paseo_gateway.py` | Ba nhóm handshake/outcome/delayed settlement, saturated cancel/EOF, history/duplicate/full/follow-up. |
| `tests/test_hand_paseo_execution.py` | Ba nhóm real runner trên fake backend, admission/options/caps, crash/cancel/ACK/settlement once. |
| `tests/fixtures/hand_paseo/transport/package/package.json` | Metadata package giả CLI 0.15.0, không cài dependency. |
| `tests/fixtures/hand_paseo/transport/run.mjs` | Fake public client chạy qua exported bridge handler, lưu fake receipts/calls để mô phỏng ACK mất. |

## Interface đã chốt cho G3

- `ExecutionStore(root)`: `create_intent`, `get(key)` hoặc `get(invocation_id, attempt_id, epoch)`, `compare_and_swap`, `bind_placement`, `list_unsettled`. `ExecutionKey` dataclass hoặc tuple ba phần. Record ngoài isolated cwd, không labels chứa prompt/env/auth. `Invocation` version 1 frozen; resource claims dùng `repo:*`, `file:path`, `dependency:id`; whole repo dùng `repo:*`.
- Scope được dispatcher tính bằng `parallel.scope_digest(source_root)` trong env Sol, pin vào invocation/reservation; scope độc lập parent canonical. Worker phải dùng scope đã pin, không recompute từ env daemon. `record.reservation` là admission evidence, không chỉ status/mtime/PID. Legacy native ngoài dispatcher chưa được enforce trước spawn.
- `AdmissionController(store, supervisor, policy_checker)`: `admit(..., max_parallel=1..4)`, `reconcile_legacy`, `release(reservation, outcome=..., artifacts_settled=True)`. G3 cung cấp checker thật cho fresh pick/account/guard/quota/capacity. Missing checker không allow. Full mapping exit 8; exhausted backend order/exit 7 thuộc G3, không dùng transport error làm quota fallback.
- `ExecutionSupervisor`: `register_writer`, `cancel`, `reconcile`, `record_outcome_once`. Chưa quiescent chỉ `pending_outcome`/unresolved; terminal `outcome` bất biến sau authority. Process ops sau restart bảo thủ, không signal numeric PID/PGID chỉ vì metadata có sẵn.
- `PaseoTransport(package_root, target, client_factory=None, *, store=None, node='node')`: probe/verify_parent/ensure_workspace/create_child/send_prompt/reconcile/wait_child/cancel_child/archive_child/reopen_child. Node >=22, explicit official CLI 0.15.0 root. Target `instance/home` hoặc `endpoint/host` pin fingerprint; project phải được verify qua parent workspace public metadata.
- Persist workspace/agent UUID và idempotency keys trước create, không initialPrompt. `messageId = Attempt.request_key` UUID. `receipt.transport` giữ pending/confirmations và `cancelPending` riêng. ACK mất reconcile bằng exact IDs/timeline receipt, không resend/create/fallback shell. `wait_child(key, timeout_s, poll_interval=.1)` chỉ đọc authoritative outcome+quiescence đúng epoch; public idle không completion.
- `createAgent` pin provider `hh-hand-*`, model/effort và env metadata không secret `HYBRID_HANDS_EXECUTION_ROOT`, `HYBRID_HANDS_INVOCATION_ID`. Gateway entry nhận các env này hoặc `--state-root`, `--invocation-id`. Không truyền credential hoặc raw prompt trong labels/env.
- Initial admitted record chưa có writer/process/outcome có fresh dispatch fence, không cần quiescence từ writer chưa tồn tại. Archive phải có `artifacts.review.approved=True` và authority quiescence; archiveAgent exact child, giữ workspace active. Reopen epoch cũ sau review/quiescence, settle/release; rồi admit epoch mới với same bound IDs và fresh request key. Existing IDs verify read-only, không recreate.
- `ExecutionWorker(store, supervisor, runner=None, settlement_hooks=None)`: `start`, `cancel`, `reconcile`, `outcome`; không reserve slot thứ hai/CLI recursion. Fixed options: `run_dir` BASE, `sandbox`, `timeout_s`, `max_tokens` bắt buộc; `browser`, backend `options` optional. Actual logs base/hash execution key tại `receipt.worker_run_dir`, không overwrite epoch trước. Codex account canonical `gpt` (giữ compatibility alias `codex`); model/effort/account/options pin.
- `WorkerOutcome`: key/status/reason/nullable backend_exit_code/provenance/quiescence/quiescent/nullable usage/artifact_refs/final_text. Usage canonical `{input,cached_input,output}`, mặc định toàn 0 chưa observation giữ unknown. ACP map projection, không tạo ledger thứ hai.
- Settlement hooks mapping `kind -> (key, idempotency_key, record, outcome) -> refs`. Persist `in_progress/completed` trước/sau side effect. Hook crash/ACK ambiguous không tự replay; G3 reconcile external sink theo key rồi đánh dấu completed. G3 giữ prepared isolation context/check-apply policy, inject finalize/report/ledger hooks; worker là một owner gọi hooks. Chỉ sau tất cả REQUIRED artifacts durable mới gọi `admission.release` sang awaiting_review. Không suy settled từ có outcome hoặc truyền bool True tùy ý.
- `Gateway(..., invocation_id=..., max_parallel=1, wait_seconds=30)` cần G3 inject trusted worker/checker/limits/deadline theo task. Mọi prompt fresh policy; completed duplicate policy-only, không cần slot. Bounded wait xuyên settling, success chỉ sau outcome/quiescence/settlement/release; timeout unresolved giữ reservation. Load chỉ history metadata, không chạy CLI/context resume. Reader vẫn nhận cancel/EOF khi prompt pending; cancellation có lane riêng không bị saturation prompt chặn.

## Interface cho G4/G5 và quyết định sản phẩm

G4 mapping target/agent/epoch ↔ invocation/attempt/run/thread/parent canonical; một execution một dòng thuộc hand pool 4, không thành side-session root hay dùng giới hạn 6 phiên phụ. Runner parser/ledger là nguồn usage managed; ACP/Paseo chỉ projection, không cộng trùng rollout/ledger/projection. Pricing vẫn chỉ canonical model-prices.json; token/giá/quota thiếu giữ `?`, không suy quota từ USD.

G5 giữ shell default, opt-in pilot repo claude-plugins; thiếu daemon/capability trước dispatch mới shell fallback cùng backend. Sau dispatch/ACK mất phải reconcile writer cũ. Q3 chỉ task native Sol-low mới sau rollout, legacy giữ nguyên. Q4 giữ done hiện để Sol review rồi archive exact child; follow-up epoch/brief mới giữ history Paseo, không hứa backend CLI context/thread resume. MVP không auto-clean worktree. Runtime policy/template/docs vận hành là giai đoạn sau.

## Review, delegation và ngoại lệ

Mỗi native delegation đều preflight `hand-ext pick --json`: backend codex, model gpt-6.1-sol, effort low, account gpt; brief fork_turns=none tự chứa và luật dữ liệu nguyên văn. G1/G2 khác file song song; gateway/worker khác file theo interface G1 ổn định. Tổng native + hand-ext không quá bốn; không hand review hand khác. Native usage/token/USD~/quota: `?`, không tạo ledger hand-ext giả.

Sol đã review diff và semantics từng gói: sửa scope pool/claim overlap/pending outcome G1; request shapes, fresh admitted dispatch, message ID, follow-up reuse/ACK/cancel G2; policy-only cached outcome và saturated cancellation G6a; account/options/log epoch/process identity/settlement ambiguity G6b. Những lượt native sửa sau review giữ cùng backend đúng một lần; review lần hai lỗi mới chuyển DSH.

- G6a delayed-settlement: DSH run `20261109-150928-136191-hpa-p1-gateway-settlement-dsh` thoát **4 capped**, 8.1s, cap 20k thấp hơn context đã đọc; patch rỗng. Sol tự sửa gateway và test theo ngoại lệ hand-ext lỗi. Report: `/Users/anhtp/app/claude-plugins-wt/hpa-p1/output/llm/hand-ext/20261109-150928-136191-hpa-p1-gateway-settlement-dsh/report.md`. Không xóa/di chuyển artifacts.
- G6b post-review compatibility: canonical account `gpt` sửa bằng native cùng backend; review lần hai phát hiện env Sol/daemon scope được giao DSH run `20261109-151545-671404-hpa-p1-worker-scope-dsh`. DSH thoát **4 capped**, 18.2s, cap 100k; patch rỗng sau đọc ngữ cảnh. Sol tự sửa scope authority + test theo cùng ngoại lệ hand-ext lỗi; giữ account fix, commit `b5c4243`. Report: `/Users/anhtp/app/claude-plugins-wt/hpa-p1/output/llm/hand-ext/20261109-151545-671404-hpa-p1-worker-scope-dsh/report.md`. Không xóa/di chuyển artifacts.

## Kiểm chứng thật

Từ worktree root:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py'
```

Chạy đúng **một lần**, **12 tests OK, 6.740s** sau gateway settlement fix `53a2738`. Sau đó có compatibility account/scope worker `b5c4243`; chỉ chạy lại `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_execution.py'`, **3 tests OK, 2.852s**, không lặp aggregate/full. Aggregate không được chạy lại trên exact final head; phần code thay sau aggregate chỉ là worker/account/scope, đã kiểm bằng narrow tương ứng. Các gói trước đó đều narrow 3/3 xanh.

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_parallel.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_rundir.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_core.py' -k 'CoreTest.test_capped_by_tokens'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_core.py' -k 'CoreTest.test_timeout'
```

Kết quả tương ứng **3, 4, 1, 1 tests OK**. Không full suite. `node --check .../paseo_bridge.mjs`, `git diff --check` pass; bảy link nội bộ spec/plan hợp lệ. `claude plugin validate hybrid-hands/plugins/hybrid-hands`: **default Validation passed**, directory submission có **LICENSE_MISSING problem** và **ICON_MISSING warning**; không sửa license/icon ngoài scope. Không claim directory-profile pass.

## Rủi ro, gate còn lại và việc Opus cần giữ

1. G3 phải nối fresh production policy/pick/day guard/quota/capacity/order, isolation.prepare/check/apply/finalize/report/ledger và required settlement reconciliation/release. Entry hiện deny prompt; không bật pilot bằng entry hiện tại. Offline fake checker/hooks không chứng minh production guard parity.
2. Worker chỉ sở hữu group/session tạo bởi runner; descendant tự escape session/group chưa containment. Sau restart không còn Popen authority thì unresolved; leader đã reaped mà group còn sống không signal PGID có thể reuse. Cần giải pháp containment/recovery được duyệt trước live supported rollout, không quảng bá đã có bảo đảm tuyệt đối.
3. Archived workspace không có public project/cwd metadata bị blocked trước mutation, không restore/recreate mù. Luồng hiện archive child, giữ workspace active để reopen. Lost cancel/reopen ACK không có proof từ public idle/refresh receipt thì unresolved, cần controller/supervisor reconcile; không fallback writer mới.
4. Hook side effect ACK mất giữ in_progress, không tự retry. G3 cần idempotent sink hoặc read-only reconciliation theo key; chưa có exactly-once sink integration thực.
5. License repo chưa khai báo; gateway Python stdlib, bridge dùng official externally provided CLI pin, không vendor/copy upstream code hay kéo dependency. Opus cần chốt license distribution trước release. Directory icon là gate publication riêng.
6. G7/live/backend smoke, provider registration/setup, release/version/install/runtime path verification chưa được giao; không làm. Không có câu hỏi Q1–Q7 cần hỏi lại người dùng. Không có quyền tự mở rộng scope.

## Trạng thái cuối

HEAD `54480e7` trên `side/hpa-p1`; tám commit sau base, worktree sạch. Sol đã review các diff cuối và kiểm không có file ngoài phạm vi trong diff base→HEAD. Hai hand-ext run đều đã kết thúc mã 4; không còn tiến trình nền do Sol tạo đang chạy. Native hands completed giữ history, không archive parent hay tạo side-session khác. Bàn giao này ở repo chính theo hợp đồng side-session, không commit vào main. Tạo `hpa-p1.done` sau khi ghi bàn giao hoàn tất.
