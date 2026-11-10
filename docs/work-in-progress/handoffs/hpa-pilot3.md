## Tóm tắt
- Kết quả: **xong một phần, dừng ở gate 3 cuối** theo giới hạn Opus; không có 0.35.5.
- Đã release/push main **0.35.4 `d8164cb`**, code containment `d9b8136`; trước đó 0.35.1–0.35.3 đều đã push.
- File đổi: gateway/prompt — discovery không thực thi, kiểm canonical envelope; recovery/bridge/controller/transport/CLI — recovery có proof và fence.
- File đổi: worker/runner/process helper — tracker cây con + marker; README — giới hạn macOS; manifest/CHANGELOG — release; tests/fixture — regression (chi tiết dưới).
- Test cuối: **508 tests OK, 83.954 s**; narrow 27 tests OK; Node check, validate default, probe unbound và fixture macOS thật đều đạt.
- Recover key `68bcf6da…:96b77fc4…:1` đạt: failed, reservation `95f1251c…` đã nhả đúng một lần, hh-ps đúng một row failed.
- Gate 1 PASS (0.35.3); gate 2 metadata/hh-ps PASS, tab Subagents UI UNKNOWN; gate 4 PASS cả epoch 2 trên 0.35.3 trước release cuối.
- Gate 3: 0.35.3 FAIL nhả sai khi sleep còn sống; đã dọn đúng process đó. 0.35.4 dọn process đạt nhưng certificate UNKNOWN, reservation giữ, settlement chưa đạt.
- Gate 5 dsh/claude-v2 SKIPPED do gate 3 chưa đạt; không chạy claude-v1. Fallback chỉ kiểm offline PASS.
- Còn lại: Opus điều tra `597c17ca…` đang unresolved, giữ reservation `c9d729cf…`; không retry writer/recover bằng tay. README ghi rõ containment macOS không tuyệt đối.
- Plugin list hai repo đều 0.35.4 từ checkout chính; account ~/.claude duy nhất. Không restart/reload daemon; cấu hình dirty giữ nguyên hash.

## Phạm vi, phối hợp và nguồn

Sol lead tech/QA; hand code/test qua hand-ext, Sol review toàn bộ diff, chạy QA và điều phối release. Đã đọc đủ hpa-pilot.md, hpa-pilot2.md, AGENTS và skill ext-hand/paseo. Không đọc/hiện .env, token/credential; không giao hand dữ liệu thật. Không sửa config hay auth, không dùng API trả phí, không xóa output/worktree.

Main `/Users/anhtp/app/claude-plugins`; worktree `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`, branch `side/hpa-pilot-fix`. HEAD ban đầu d6f922f; đã merge main trước các vòng. Bằng chứng/brief QA giữ tại `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix/.pilot3` (gọi tắt B). Tất cả output/llm và isolated worktree được giữ.

Paseo CLI/server/client installed 0.15.0 dưới `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`. Chỉ đọc source public, không sửa package. Sol Paseo `e5a9105a-3d9d-44d5-a4cd-b21b28c09a23`, canonical parent `c9b83692-3250-4f92-9a64-af9f82d778ed`.

Người dùng cho phép hỏi brain Claude v2 điều phối. Đã hỏi đúng agent `711ef386-2673-4c8b-8b1a-f24f1e56805e` bằng Paseo send, không mở side-session. L1 message `8693c128` duyệt envelope/recovery/marker và 0.35.3; message `85e0a38f` duyệt containment MVP, mở worker/helper/tests, gate 4 trước release và **0.35.4 vòng cuối**. Brief câu hỏi ở B/brain-question.md và B/brain-stop-question.md. Không xin thêm vòng.

## Release và kiểm chứng

| Version | Code branch | Main release | Full suite Sol (một lần mỗi bản ổn định) |
|---|---|---|---|
| 0.35.1 | 4e8afdf (gồm baseline pilot2 d6f922f) | 008aeb7 | 502 OK / 79.363 s |
| 0.35.2 | 7c336f6 | c5b5185 | 503 OK / 79.556 s |
| 0.35.3 | ecc3b4e | b07ab9a | 506 OK / 79.950 s |
| 0.35.4 | d9b8136 | d8164cb (merge 2e25d1e) | 508 OK / 83.954 s |

Nhánh và main đã push origin. Chỉ stage file plugin của bản vá, không stage .claude/hybrid-hands.json hay docs WIP có sẵn. SHA256 config protected vẫn `6125a7026b05f84427a0d92a79c59c6eae68e414de3bd85e1d26c12dac81342f`.

Lệnh QA: `python3 -m unittest discover -s hybrid-hands/tests -p '<file>' -v`; full dùng `python3 -m unittest discover -s hybrid-hands/tests -v`. B/*-0354.txt có output thực:

| Test hẹp 0.35.4 | Số | Thời gian |
|---|---:|---:|
| test_hand_process_containment.py | 2 | 1.594 s |
| test_hand_paseo_execution.py | 3 | 4.873 s |
| test_hand_paseo_integration.py | 1 | 1.466 s |
| test_hand_paseo_gateway.py | 6 | 1.494 s |
| test_hand_paseo_controller.py | 7 | 4.157 s |
| test_hand_paseo_cli.py | 3 | 1.706 s |
| test_hand_paseo_transport.py | 5 | 3.515 s |

`node --check hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs` exit0. `claude plugin validate hybrid-hands/plugins/hybrid-hands` default exit0 ở worktree và sau bump main. Validator vẫn báo vấn đề directory LICENSE_MISSING và cảnh báo ICON_MISSING có từ trước; **không claim profile directory đạt**. B/validate-0354.txt, release-validate-0354.txt.

Mỗi release dùng official `CLAUDE_CONFIG_DIR=/Users/anhtp/.claude claude plugin update hybrid-hands@hybrid-hands-local --scope user --json`; lần cuối updated 0.35.3 → 0.35.4. `plugin list --json` tại main và `/Users/anhtp/app/live-tiktok-games` đều version/folderVersion0.35.4, readFromFolder `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`. Không cài cho account khác. CLI báo phiên Claude đang mở cần restart để áp plugin; Sol không reload phiên hay daemon. Provider command đã trỏ checkout main nên invocation mới dùng code mới.

## File đã đổi và lý do

Đường dẫn tính từ repo; lib dưới `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/`:

- `paseo_gateway.py`: unbound discovery không store/auth/backend; bound metadata model/effort; kiểm prompt pin, durable rejection marker.
- `paseo_prompt.py` (mới): canonical envelope projection exact một message, source/messageId/body khớp dispatcher pin, ECMAScript trim chính xác; không normalize tùy ý.
- `paseo_controller.py`: pin plaintext/digest durable trước network ở dispatch/followup/capacity, giữ fenced completion/admission.
- `paseo_recovery.py`: create-failure proof public ưu tiên, exact IDs/agent absence, archived parent không chặn proof đọc; legacy prompt rejection recovery chỉ khi chứng minh chưa spawn.
- `paseo_bridge.mjs`: public creation lifecycle/inspect/version proof và bound ACP transport metadata; error output tối thiểu.
- `paseo_transport.py`: marker rejection chuyển failed/release thay vì chờ timeout; giữ fail closed với network/ACK unknown.
- `cli.py`: entry managed recover, dry-run mặc định, --apply mới mutation.
- `execution_worker.py`: retained Popen ownership + tracked/marker descendant verify trước certificate/release; snapshot trước poll/reap/cancel.
- `process_containment.py` (mới): OS start microseconds trên macOS, same-user KERN_PROCARGS2 marker parser chỉ trong memory, protected ancestors, ancestry history, PID reuse revalidation từng signal.
- `runner.py`: truyền invocation marker vào child env, snapshot khoảng50ms khi managed poll; shell path giữ POLL_SECONDS cũ.
- `hybrid-hands/tests/test_hand_paseo_gateway.py`: discovery/partial binding, official ACP overrides, envelope/fence regression.
- `hybrid-hands/tests/test_hand_paseo_controller.py`: recovery exact proof/dry-run/apply/repeat/uncertainty và marker settlement.
- `hybrid-hands/tests/test_hand_paseo_transport.py`: lifecycle proof/version/schema/pre-network regression.
- `hybrid-hands/tests/fixtures/hand_paseo/transport/run.mjs`: fixture public lifecycle giả.
- `hybrid-hands/tests/test_hand_paseo_execution.py`: giữ fixtures không quét env thật của host, regression worker/admission/settlement.
- `hybrid-hands/tests/test_hand_process_containment.py` (mới): reused PID, ancestry sau reparent, marker exact/argv exclusion/no secret leak, real owned setsid child + conservative lost ownership.
- `hybrid-hands/README.md`: contract containment best-effort và giới hạn macOS.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`: version0.35.4.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: 0.35.1–0.35.4, schema validation/recover/discovery/envelope/containment và giới hạn thật.

## Delegation và review

Mọi lượt đều pick --json trước, backend codex/gpt-6.1-sol/low theo order repo; run --backend auto --mode shell --cwd worktree --keep-worktree. Không spawn native riêng, không đổi config/order/model/effort. Scope Sol giữ nguyên. Hand chỉ nhận brief tự chứa + luật dữ liệu nguyên văn; không đọc runtime/log thật, không live daemon/API. Sol đọc toàn bộ diff, chỉ một lượt sửa cùng backend sau review mỗi vòng.

Reports dưới worktree `output/llm/hand-ext/<id>/report.md`:

| Lượt | ID | Kết quả |
|---|---|---|
| E/F | 20261109-175107-743371-hpa-pilot3-ef-codex | exit0 |
| E/F review | 20261109-175708-593711-hpa-pilot3-ef-review-codex | exit0, sửa empty binding |
| live fix 0.35.2 | 20261109-180153-115245-hpa-pilot3-livefix-codex | exit0 |
| review0.35.2 | 20261109-180502-515792-hpa-pilot3-livefix-review-codex | exit0, version proof pin |
| envelope0.35.3 | 20261109-181859-552738-hpa-pilot3-envelope-codex | exit0 |
| review0.35.3 | 20261109-182757-510855-hpa-pilot3-envelope-review-codex | exit0 |
| containment0.35.4 | 20261109-184213-228996-hpa-pilot3-containment-codex | **exit4 capped**, patch6file đã áp; input1535914/cache1480576/output15608,446.5s; report chưa hoàn chỉnh |
| review0.35.4 | 20261109-185117-322815-hpa-pilot3-containment-review-codex | exit0; input297000/cache262784/output2982,96.1s; sửa ancestry, hoàn tất narrow tests/report |

Lượt0.35.4 cuối dùng max-tokens2500000 sau capped1.5m; cùng backend, không tự làm code. Hand báo pytest thiếu module, đã dùng unittest đạt; không coi pytest đã chạy thành công. Sol test lại narrow/full như trên. Không có fallback tự code dựa vào ngoại lệ.

## Probe offline và các invariant

`python3 B/offline_probe.py` chạy binary worktree với NO_BROWSER=true, bỏ hai biến binding. initialize và session/new có result; session/prompt/cancel/close/set_model trả cùng JSON-RPC -32003 `discovery only; execution binding required`. Direct executable protocol khớp lần chạy audit; audit chặn subprocess/fork/write/auth/store và ghi **zero blocked events**, không store/admission/auth constructed. Binding chỉ root hoặc chỉ invocation exit2, stdout protocol rỗng; test bao gồm empty/CLIpartial. Evidence offline-probe-0354.out và offline-probe.json, các vòng trước có file riêng.

Catalog unbound là singleton `default` cho model/mode. Probe initialize của Paseo0.15.0 không truyền provider identity và bốn provider command giống nhau nên không thể biết backend ở discovery; bound new/load công bố model/effort chính xác từ Invocation. Đây là giới hạn cần Opus biết, không claim discovery đã liệt kê mọi model backend.

0.35.2 sửa metadata bound sau khi official ACPAgentSession.applyConfiguredOverrides tự gọi setter không được gateway hỗ trợ. Regression dùng public class từ installed package và fixture metadata; không thêm setter side effect.

0.35.3 envelope proof: plaintext9654bytes SHA4e1a326d710372d0ddd3f14e5d33076a871bc2a23bc77dc9e8ca2b33247c79e0; official buildAgentPrompt(trim)+formatAgentMessage tạo9940bytes SHA3b8651017be6026e747a43a86e676670f5a1f6d6b64a70bd0386081d6cd45dcc khớp exact gateway digest. B/official-normalized-envelope-proof.json. Plaintext+digest dispatcher authoritative, worker nhận pin; projection canonical chỉ chấp nhận một message đúng IDs/body. Wrong IDs,2messages,body lệch1byte,missing digest từ chối; rawplaintext chỉ nếu digest khớp.

Persist-before-spawn: ExecutionWorker.start CAS worker_owner durable trước thread.start; _run sau đó mới gọi runner.Popen. `_Control.spawned` đăng ký process **sau** Popen, vì thế vắng process riêng lẻ không đủ. Recovery legacy bắt buộc vắng cả worker_owner và process cùng outcome/writer/artifacts dưới revision/lock fence; ownership không bị xóa trong epoch. B/worker-spawn-invariant.md. Rejection marker chỉ được tạo khi chưa worker/claim hợp lệ, controller settle exact failed/release.

Public CreationSnapshot không expose inFlight. Chỉ daemon version exactly0.15.0 được suy inFlight=null theo source CreationService catch; version khác/thiếu/API lỗi từ chối, không fallback receipt khi API có mà lỗi. creationLifecycle=true thực tế nên live dùng public API. Receipt local chỉ fallback thiếu capability; không echo raw diagnostics/env.

## Recover live hai key lỗi

CLI main: `hand-ext managed recover --cwd /Users/anhtp/app/claude-plugins --key K`, rồi cùng lệnh thêm --apply, rồi repeat --apply.

1. Original `68bcf6da-5503-4ff5-b366-1c040c97303c:96b77fc4-c729-4a40-b519-98d2602a4752:1`: dry-run0.35.1 bị parent archived → từ chối, record/pool giữ nguyên. Sau0.35.2 public exact failed creation/known outcome + successful fetchAgent=null: dry-run byte-identical, applyfailed/release reservation `95f1251ce5b2d5b1c9fe2d4a4535909cef88ef6959dd82969c83cabf83d8cec0`, repeat byte-identical. Childc46fa523… không tồn tại. managedls/hhps một failed row, exit1, ended18:09:39, tokens/USD unknown; không trùng root. B/recover-*-0352.txt, proof-readonly-0352.json, recover-tree.*, final-projection-safe.json.
2. Dispatch0.35.2 `3310956d-f843-4b42-9786-2c1613d827e9:dff1aae1-29c3-4d6d-b2e8-62bec979fc6c:1`, child8d903704-33ae-4d7f-bbe4-46c3cb62d61a: create/sendConfirmed, gatewayclaim nhưng chưa worker/process/outcome, public child error. Canonical envelope mismatch đã chứng minh. 0.35.3 recover dry-run no mutation; applyfailed reason gateway_prompt_fence_rejected/release; repeat stable. B/gateway-recover-*.txt. Không archive child failed trước review; lifecycle chỉ approve awaiting_review, không bypass.

## Gate 1 — PASS trên main0.35.3

`hand-ext pick --json`, rồi `hand-ext run --backend auto --mode paseo-required --brief B/dispatch-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply --label hpa-pilot3-dispatch-0353 --timeout-min 4 --max-tokens 1500000` (outer310s).

Key `7ca02bde-0330-45c0-b840-2e439d881a90:0cfee56e-03ed-465e-aecf-731ae2c272c1:1`; child63b9e1b3-96ca-467e-b1a5-0aa30f0dd46f; workspacewks_0efc3824e6923199; projectprj_7a322b4848a466f5. Exit0 codexok, awaiting_review, reservationnull, đủ5settlementhooks. Patch duy nhất thêm scratch một dòng pilot ok, source không apply. B/dispatch-0353.out, task1-0353-safe.json.

## Gate 2 — metadata/hh-ps PASS; UI tab UNKNOWN

Public verify-child/inspect đúng hh-hand-codex, gpt-6.1-sol/low/default, parent Sol, project/cwd/workspace riêng đúng. hh-ps --once text+JSON đúng một hand row, không rollout root trùng. Tokens input42794/cached24576/output193, USD~0.040824 (offline estimate), ended18:33:07, elapsed12.667864s. GPT own week unknown; account14% chỉ sample tài khoản lúc ấy, không suy riêng của hand. B/task1-placement-0353.json, task1-projection-0353.json, task1-tree-0353.*. Không mở UI để nhìn tab Subagents nên **không claim phần UI đạt**.

## Gate 4 — PASS main0.35.3, đã làm trước0.35.4 theo Brain

Đọc report+changes.patch epoch1: đúng một newfile scratch pilot ok. `managed review-approve --cwd MAIN --key K1` exit0, `managed archive ...K1` exit0; inspect exact child Archivedtrue/closed, parent Sol không archived/workspace còn. Sau đó `managed followup --cwd MAIN --key K1 --brief B/followup-brief.md` exit0 với brief tự chứa mới.

Epoch2 key `7ca02bde-0330-45c0-b840-2e439d881a90:67815c83-ca2e-4574-a515-9853c61097e7:2`, cùng agent/workspace. Requestkey mới; baseline epoch1ef22391c4649fec932646a90debd978951eb7c93 → epoch2 6f41c521c82390ad5a17893498e87b65968fcf00. Report/artifact path mới; epoch1 giữ nguyên. Patch epoch2 chỉ đổi pilot ok → pilot ok 2, không thêm lại epoch1; source scratch vẫn không tồn tại. Đã đọc report/patch epoch2, approve và archive exact epoch2 exit0. Cả2record archived, history/worktree giữ. B/gate4-result.json, task1-epoch{1,2}-artifacts.json, task1-epoch2-{report,patch}-review.txt, followup-0353.out. Không claim đã lặp lại followup trên0.35.4.

## Gate 3 — lỗi0.35.3 và kết quả0.35.4 cuối

0.35.3 task2 key `475fb663-46f8-4870-b68f-fd7a23285c82:fdd11c43-23ee-40f8-97fe-5bf5c9b1f1dc:1`, childf73ba8c8-8a86-47ea-8896-7b181da48f2c. Task sleep120s, auto/no-apply/timeout4min. Root20830; descendants tách nhóm có sleep21486 PGID21486, OSstartMonNov9 18:34:33 2026. `paseo stop child --home /Users/anhtp/.paseo --json` exit0, stoppedCount1; CLIcancelled/awaiting_review/quiescenceconfirmedtrue và **reservation đã nhả sai trong khi sleep21486 còn sống**. Sol xác minh lại pid+start+comm rồi TERM đúng sleep của task, gone sau cleanup. **Hiện thực tế đã quiescent**, không sửa record/pool bằng tay. B/stop-process-before.json, stop-process-after.json, stop-manual-cleanup.json, stop-command.json. Không dùng UIidle hay thời gian im lặng làm proof.

0.35.4 source containment được L1 duyệt và release như trên. Sol probe real macOS syscalls trên hai child giả: exact env true/other invocationfalse/argvmarkerignored/startmicrosecondavailable; real synthetic root+setsidchild cancel confirmed/rootreaped/childgone với evidence root_group+tracked_tree+env_marker. B/mac-syscall-own-fixture.json, mac-real-containment-fixture.json. Đã dừng và reap tất cả fixture tự tạo.

Lặp live bằng `python3 B/live_stop_0354.py` (driver có hạn300s), thực thi CLI main `run --backend auto --mode paseo-required --brief B/stop-0354-brief.md --cwd MAIN --no-apply --label hpa-pilot3-stop-0354 --timeout-min 4 --max-tokens 1500000`. Brief chỉ scratch và Python Popen(['/bin/sleep','120'],start_new_session=True), child wait130s hữu hạn. Pick codex/low đúng. Chỉ gọi stop khi đã nhìn thấy descendant setsid.

Key **`597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1`**, child **6690365c-6cc5-4778-a502-622a3705827a**, workspace `wks_95567480628a52bc`; xem inspect/evidence cwd riêng `claude-plugins-20261109-185651-243156-hpa-pilot3-stop-0354-codex`.

Trước stop: root37676, npm37729, node38083, code-mode-host38386, Python38389 và **sleep38390 PPID38389/PGID38390**. Stop public exit0/stoppedCount1. CLI kết thúc exit1 với `managed execution unresolved; reconcile exact execution, no shell fallback` (không cần kill wrapper); pending backend_exit_code=-15. Sau stop `ps -p 37676,37729,38083,38386,38389,38390 -o pid=,ppid=,pgid=,lstart=,comm=` exit1/stdoutempty; rootgroup37676 không tồn tại. Sameuser exactmarker scan Sol sau stop0errors/289processes: chỉ còn gateway supervisor37655, không backend/descendant mang marker. Không log/lưu/in env khác.

**Nhưng record vẫn `unresolved`, quiescence.confirmed=false/evidence containment unknown, pending_outcome.status=cancelled, outcome=null, settle_keys rỗng, reservation giữ.** Không coi idle trong inspect là bằng chứng settlement. Reservation **`c9d729cfa7d0287e1b2ef8d8abc0fa6946719c72a36e88eb97ac61a35efd8d93`**, process binding root37676/supervisor37655, worker_owner07b532781a1849e38876a26dec311e00. hhps đúng một row unknown, exit/ended/USD/token unknown theo contract; không rowtrùng.

Kết luận: phần cleanup descendant live PASS; phần certificate/quiescence/settlement **UNKNOWN/chưa đạt**, fail closed đúng hướng hơn0.35.3. Không đủ bằng chứng nguyên nhân nội bộ: code giữ sticky lost-authority khi scan/signal lỗi; record chỉ có evidence tổng quát nên không biết nhánh nào đã mất authority. Phép quét sau stop thành công không đảo được bằng chứng tại thời điểm worker cancel. Không giả định nguyên nhân từ UI/sleep và không tự nhả reservation. Không thêm0.35.5 theo giới hạn Brain. B/stop-0354-{before,command,ps-after,marker-after,after}.json, stop-0354.out/exit.txt.

## Gate 5, fallback và bàn giao điều tra

Gate5 optional dsh/claude-v2 **SKIPPED** do gate3 cuối chưa đạt và reservation còn giữ; không claim guard/live backend đó pass. Không chạy claude-v1. Không tạo writer/attempt thứ hai để bypassunknown.

Fallback đọc code và test sẵn có `test_modes_default_and_only_predispatch_same_backend_fallback` trong controller suite PASS; chỉ auto thiếu capability trước dispatch mới shell cùng backend, ambiguity sau create/send giữ reservation. Không tắt provider/daemon để thử. Public `client.refreshProvidersSnapshot(options)` tồn tại trong0.15.0; không cần gọi vì lỗi catalog hết sau fixes, không có cached probe error cần refresh. Không restart/reload daemon.

Opus cần xem: vì sao worker containment authority trở thành stickyunknown trong live597c17ca dù Sol quan sát rootgroup/descendants đã vắng sau đó; có thể cần safe diagnostic method/stage metadata (không env), nhưng phiên này chưa sửa/không đủ proof gốc để kết luận. Giữ exactreservation, không managedrecover record này bằng điều kiện gateway-no-worker vì worker_owner/process đã có. Child chưa review/archive khi unresolved. Gateway daemon-owned37655 giữ để bảo toàn trạng thái điều tra; backend task/fixtures và wrapper QA đã kết thúc trước .done. Các child failed3310956d và cancelled475fb663 giữ history, không archive bypasslifecycle. Main/parent/tiktok không bị stop/archive.

README/CHANGELOG ghi giới hạn: process bỏ marker đồng thời double-fork giữa snapshots vẫn có thể thoát; macOS không absolutecontainment. TabUI và smoke2backend chưa kiểm, không quảng bá G7 hoàn tất. Handoff này ghi kết quả một phần đúng hợp đồng; không mở vòng release tiếp.
