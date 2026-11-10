## Tóm tắt
- **Kết quả: xong một phần; recover legacy và smoke managed bị chặn.** Không có 0.35.6.
- Tái hiện macOS marker scan trả EINVAL sau exit (5/5), gây sticky unknown ở 0.35.4; đã sửa race sau kiểm OS identity. Nhánh chính xác của record lịch sử vẫn UNKNOWN vì thiếu diagnostic.
- Đã release/push main **0.35.5 `baec927`**, code `b0d767b`, merge `09001c1`; remote hai nhánh đã đối chiếu.
- File lib: process_containment — diagnostics/inventory/exit race; execution_worker — evidence/ack/CAS; execution_supervisor — merge/fence; paseo_recovery + post_hoc_reverify mới — recover có proof.
- File test: controller — recovery và refusal; execution — CAS/ack thật; containment — race/diagnostics. README — contract; manifest/CHANGELOG — 0.35.5.
- QA Sol: **18 narrow tests OK; full suite một lần 510 tests OK / 78.084s**; validate mặc định đạt, JSON/link nội bộ đạt; directory LICENSE/ICON vẫn còn như trước.
- Fixture macOS root + setsid child: **certificate confirmed**, root reaped/child gone/inventory đủ; đã cleanup. Không đồng nghĩa gate3 managed đạt.
- Recover exact597c17ca…: dry-run, apply, repeat đều exit1 StateConflict; record/reservation byte-identical, revision20; `c9d729cf…` **chưa nhả** vì thiếu durable OS proof từ 0.35.4.
- managed ls/hh-ps JSON/text: đúng **1 row unknown**, không trùng; chưa phải cancelled. Không approve/archive khi chưa đủ lifecycle.
- Gate5 dsh **BLOCKED exit8**, claude-v2 **BLOCKED exit8** trước dispatch bởi claim toàn repo của reservation cũ; chưa có child/backend managed, mỗi intent hiện một unknown row.
- Gate3 managed trên bản mới **SKIPPED do cùng chặn reservation**; không stop/archive phiên khác, không gọi claude-v1.
- Cả account **~/.claude và ~/.claude-hand** update chính thức thành 0.35.5; plugin list cả hai repo cho cả hai account đều đúng version/readFromFolder checkout chính. Phiên Claude đang mở cần reload/restart theo CLI; không restart daemon.
- Opus cần quyết đường xử lý proof/lifecycle cho record legacy; không thể hợp thức hoá bằng PID absence/idle. Có một lệch phạm vi hand tự báo ở mục Delegation, Sol không đọc/reuse raw output đó.

## Phạm vi, baseline và trạng thái repo

Đã đọc đầy đủ `hpa-pilot3.md`, AGENTS ở main/worktree, skills ext-hand và paseo. Sol không đọc raw transcript/log/env/auth; chỉ source, metadata execution và công cụ runtime chính thức/fixture. Mọi code/test/README do hand làm; Sol review, QA và điều phối release/bàn giao. Không mở side-session/subagent khác, không đổi account/model giữa phiên, không đổi slots/config/order/guard.

- Main `/Users/anhtp/app/claude-plugins`, ban đầu `d8164cb`/0.35.4.
- Worktree `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`, branch `side/hpa-pilot-fix`; fast-forward main trước sửa, giữ toàn bộ `.pilot/`, `.pilot2/`, `.pilot3/`, `output/llm/` và worktrees.
- **B** = `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix/.pilot4` (brief và evidence QA).
- Sol Paseo `6fb4ff02-e101-4187-aead-24863587a861`; CODEX_THREAD_ID `01a1c034-c260-7743-9890-56d1204cb27b`; hand scope `db784ec3-0639-4c09-95f9-9b84add842a2` giữ nguyên.
- Main config ban đầu dirty được phiên khác commit thành `ec05d77` trong lúc làm. Sol không stage/sửa file này; SHA256 trước/sau vẫn `6125a7026b05f84427a0d92a79c59c6eae68e414de3bd85e1d26c12dac81342f`. Không reset/stash thay đổi người khác.
- Main cuối chỉ còn docs WIP untracked có sẵn và bàn giao được giao; worktree chỉ `.pilot*` untracked. Không stage docs WIP, không sửa settings/credential/installed_plugins bằng tay.

## Chẩn đoán record và race macOS

Exact key **`597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1`**, child `6690365c-6cc5-4778-a502-622a3705827a`. Reservation **`c9d729cfa7d0287e1b2ef8d8abc0fa6946719c72a36e88eb97ac61a35efd8d93`**.

B/baseline-record.json: unresolved/revision20, pending cancelled/exit-15/client_cancel, outcome null, hooks rỗng, quiescence containment unknown. Root37676/PGID37676 chỉ có opaque `start_identity` token nội bộ, **không phải OS birth**; supervisor37655, worker_owner07b53278…. Không có durable OS inventory, root-reaped hay owner-done. Reservation giữ claim `repo:/Users/anhtp/app/claude-plugins/.git:*`.

B/scan-baseline.json: same-user scan278 processes,0 errors, exact marker chỉ gateway37655/start1794225413:805677. Scan hiện tại không chứng minh lịch sử root đã reap hay danh sách identity đầy đủ. Bằng chứng pilot3 cũng chỉ là tập PID đã quan sát ngoài worker, không thể thay thế toàn bộ inventory worker + reap proof.

B/own-zombie-race.json: tạo 5 `/bin/sleep 0.02` với marker synthetic, chờ0.04 nhưng chưa wait; `KERN_PROCARGS2` trả errno22(EINVAL) cả5, trong khi snapshot mới không còn identity. Bản0.35.4 bọc lỗi thành RuntimeError và đặt authoritative=False vĩnh viễn. Mỗi fixture được wait(timeout2) trong finally. **Đây là lỗi phân loại có thể tái hiện**, chưa đủ dữ liệu để khẳng định là nhánh duy nhất/đúng nhánh của597c17ca lịch sử.

Bản mới kiểm lại PID + OSstart + uid bằng direct identity query. Chỉ khi identity đã mất hoặc PID reuse được chứng minh mới coi lỗi scan là vô hại; tiếp tục scan các process khác. EINVAL đã được ghi category/resolution an toàn. EPERM hoặc identity/snapshot chưa chắc vẫn fail closed; không thêm suy đoán theo giờ chạy. Exec thay comm nhưng giữ OS birth không bị nhầm PID reuse. Diagnostic bounded giữ first_fatal riêng để không bị harmless races che mất; không lưu env/argv/error text.

B/own-exit-race-new-pre-review.json:3/3 fixture trên mã mới giữ authority/complete. B/mac-owned-fixture.json: root61437/child61438 setsid thật, certificate confirmed bằng root_group+tracked_tree+env_marker, root reaped, child gone, inventory_complete=true/first_fatal=null. finally xác nhận cleanup root/child; không còn tiến trình fixture đó. Đây là helper live fixture, không phải Paseo stop gate3.

## Thiết kế và review

`managed recover` giữ dry-run mặc định. Nhánh mới chỉ nhận cancelled-unresolved có process/worker_owner, latest exact epoch, bound invocation/attempt/request/placement/cwd/reservation khớp durable receipt. Bắt buộc inventory đầy đủ PID+OSstart+uid, retained Popen reap proof và owner self-ack đúng key/owner sau runner return hoặc OS identity owner đã chết/reused. Root và mọi identity tracked phải mất/reused; fresh same-user marker scan sạch, chỉ loại owner/ancestor theo exact identity. Legacy thiếu proof từ chối, không retrofit current PID.

Apply dùng proof-backed read-only ProcessOps, supervisor, năm completion hooks và admission release chuẩn. Không launch lại backend, không suy usage, không unlink reservation tay. Inventory/first-fatal/incomplete/reap/ack được giữ qua merge; CAS contention có retry hữu hạn ở worker thường, strict reverify không nâng revision để ghi lại proof cũ.

Sol review phát hiện và giao sửa:
1. Evidence CAS đơn lẻ có thể race cancel rồi đẩy worker vào exception; sửa bounded retry/giữ uncertainty, tránh đảo thứ tự worker.lock/process_ops.lock. Test runner thật kiểm root birth/inventory/ack/outcome và không launch lần2.
2. Harmless diagnostics có thể chiếm64slot, che fatal; giữ first_fatal riêng và category EINVAL.
3. Supervisor refresh revision sau OS proof, có thể release dù concurrent CAS trong scan. B/revision-fence-prereview.json chứng minh lỗi với fixture giả (release đã xảy ra). Bản cuối có START/END revision check và một strict CAS đúng revision lấy trước proof; StateConflict strict được propagate.

B/revision-fence-final.json là probe riêng của Sol với concurrent CAS trong **snapshot lần2** của `apply` (sau initial read-only proof): từ chối, reservation còn, revision chỉ+1 do CAS ngoài, state/outcome/quiescence/hooks không đổi. Test committed cũng kiểm race ở initial proof cho dry-run/apply; **không claim test của hand tự chèn snapshot lần2**, dù report hand mô tả vậy. Probe Sol đã kiểm đúng ca đó.

## File đổi

Các lib dưới `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/`:

| File | Lý do |
|---|---|
| process_containment.py | Direct OS birth query, exit/PID reuse/exec handling, safe diagnostics, inventory và merge giữ uncertainty. |
| execution_worker.py | Persist containment/owner acknowledgment, bounded CAS, tránh mất outcome vì contention thông thường. |
| execution_supervisor.py | Quiescence.details default tương thích; merge inventory; ordinary retries và strict revision CAS cho reverify. |
| paseo_recovery.py | Route cancelled record sang post-hoc proof, giữ các nhánh recovery cũ. |
| post_hoc_reverify.py (mới) | Proof only, dry-run/apply, exact bindings, owner/root/inventory/marker, standard hooks/release. |
| hybrid-hands/tests/test_hand_paseo_controller.py | Recovery main/refusal/idempotency và race synthetic. |
| hybrid-hands/tests/test_hand_paseo_execution.py | Worker evidence thật, CAS contention, root/inventory/ack, single launch. |
| hybrid-hands/tests/test_hand_process_containment.py | Race exit/reuse/exec, secret sentinel, EINVAL và diagnostic saturation. |
| hybrid-hands/README.md | Điều kiện recover và giới hạn legacy/fail closed. |
| .claude-plugin/plugin.json + CHANGELOG.md | Version0.35.5 và release notes; chỉ Sol bump trên main sau merge. |

## Delegation, token và lệch phạm vi

Mỗi lượt chạy `hand-ext pick --json --cwd WORKTREE` trước. Effective worktree mode=shell, main mode=auto; order thực tế repo là codex,dsh,claude-v1,claude-v2; max_parallel4. Không đổi cấu hình. Hai lượt đầu dùng `--backend auto`, sau review còn lỗi chuyển backend kế tiếp dsh theo policy; mỗi backend chỉ một lượt correction. Không gọi claude-v1/v2 cho code.

Lệnh mẫu code: `hand-ext run --backend auto --brief B/implementation-brief.md --cwd WORKTREE --keep-worktree --label hpa-pilot4-implementation --timeout-min 12 --max-tokens 3000000`; review tương tự timeout9/cap2000000. Dsh correction dùng `--backend dsh`, timeout6, cap1500000 rồi2500000. Đây là code worktree riêng, **không phải retry original managed writer hoặc gate5 managed**. Mọi brief có luật dữ liệu nguyên văn, role executor, scope và acceptance tối đa3nhóm, cấm raw runtime/host env.

Reports tại `WORKTREE/output/llm/hand-ext/<ID>/report.md`; giữ artifact/worktree:

| ID | Backend | Exit | Input / cached / output | USD~ offline | Duration |
|---|---|---:|---|---:|---:|
| 20261109-191018-440414-hpa-pilot4-implementation-codex | gpt-6.1-sol/low |0|1382799 /1328640 /18416|0.425342|535.1s|
| 20261109-192158-477541-hpa-pilot4-review-codex | gpt-6.1-sol/low |0|627657 /591744 /8293|0.213930|237.5s|
| 20261109-192813-621820-hpa-pilot4-fence-dsh | deepseek-v4.1-flash/off |**4 capped**|1518539 /1458304 /14564|0.044297|143.1s|
| 20261109-193241-416080-hpa-pilot4-fence-review-dsh | deepseek-v4.1-flash/off |0|1004260 /941056 /9635|0.036170|123.0s|

Dsh capped patch đã áp nhưng không hoàn chỉnh; Sol không chấp nhận, giao lại cùng backend đúng một lần. Final hand restore public code đơn giản, bỏ machinery sai và hoàn thành narrow. Sol không tự sửa product code/test dựa trên ngoại lệ exit4. USD~ tính qua helper hiện có từ canonical model-prices.json, không phải hóa đơn. B/hand-usage.json. Codex wrapper sample tài khoản15% (reset16/11); không quy15% đó cho riêng hand. Go thật wrapper:0%5h/1%tuần/15%tháng; không dùng sổ token/USD suy quota.

**Lệch phạm vi hand tự báo:** report lượt dsh cuối nói đã chạy `pgrep -fl unittest`, làm hiện command line vài phiên Sol khác. Việc đó vượt brief chỉ code/fixture; Sol không đọc log/raw output đó, không dùng dữ liệu đó, không can thiệp những process đó. Hand tự nói không có secret/customer data; Sol không có xác minh độc lập nội dung raw. Các diff được Sol review không chứa dữ liệu process đó. Ghi nhận để Opus biết, không coi lần hand này hoàn toàn tuân scope đọc. Không đọc thêm raw transcript để điều tra.

## QA, release và cài đặt

Sol chạy narrow bằng `python3 -m unittest discover -s hybrid-hands/tests -p FILE -v` ở worktree, output B/final-FILE.txt:

| File | Kết quả |
|---|---|
| test_hand_process_containment.py |3 OK /1.518s|
| test_hand_paseo_execution.py |3 OK /4.831s|
| test_hand_paseo_controller.py |8 OK /3.463s|
| test_hand_paseo_cli.py |3 OK /1.342s|
| test_hand_paseo_integration.py |1 OK /1.120s|

Full đúng một lần cho release ổn định: `python3 -m unittest discover -s hybrid-hands/tests -v` → **510 tests OK /78.084s**, B/full-suite-0355.txt. Không chạy full lần2. `git diff --check` sạch. `claude plugin validate hybrid-hands/plugins/hybrid-hands` exit0 ở worktree và main sau bump (B/validate-0355.txt, release-validate-0355.txt). Directory vẫn LICENSE_MISSING/ICON_MISSING baseline, **không claim profile directory pass**. Manifest JSON hợp lệ;7 local links README tồn tại, không link thiếu (B/final-validation.json).

Release dùng `git -C`:
- Stage đúng9 file code/test/README, commit `b0d767b`, push origin side/hpa-pilot-fix.
- Merge main `09001c1`; bump manifest/changelog trên main, commit **`baec927253d679025d1c19c44a4d20166a686c0f`**, push origin main.
- `git ls-remote origin refs/heads/main refs/heads/side/hpa-pilot-fix` xác nhận main baec927… và side b0d767b70cd55f8d6734008e37969b76610009df. Không stage config hay docs WIP.

Bổ sung Brain message8f61f499 cho phép update accountv2 đã cài0.35.4. Đã chạy tuần tự cho **cả hai** account:
`CLAUDE_CONFIG_DIR=/Users/anhtp/.claude claude plugin update hybrid-hands@hybrid-hands-local --scope user --json`, rồi cùng lệnh với `/Users/anhtp/.claude-hand`. Cả hai exit0/updated0.35.4→0.35.5. Sau đó official `plugin list --json` ở main và live-tiktok-games cho từng account: cả4 lượt exit0, version/folderVersion0.35.5, readFromFolder `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`; cache path đúng account/version. B/installation-0355-verified.json. Không cài/bật cho account/repo khác. CLI yêu cầu restart để áp cho phiên Claude đang mở; không reload/restart daemon/phiên nào. Gateway cũ vẫn là process code0.35.4, không hotpatch.

## Recover main 0.35.5 — BLOCKED, giữ reservation

Đã chạy CLI **main** theo thứ tự:
`hand-ext managed recover --cwd /Users/anhtp/app/claude-plugins --key 597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1`, rồi `--apply`, rồi `--apply` lần2. Cả3 **exit1**, stdout `{ok:false,code:StateConflict}`, stderr rỗng. CLI hiện chỉ trả code tổng quát; không claim nó in chi tiết lý do. Source guard + metadata chứng minh thiếu complete retained containment evidence. Không dùng nhánh never-worker để bypass process/worker_owner đã có.

B/recover-0355-summary.json và recover-{dry-run,apply,repeat-apply}-0355.txt: cả record lẫn pool reservation byte-identical ở cả3 lệnh, revision20, unresolved, confirmedfalse, outcome null, hooks rỗng. Hash record `ac86d5a902ae88ecfb85eade707d9fb51fd4595503352f7f122137ef6eac3061`, reservation `e1511c76c3a51757ea0a16c08e3b0084c636069390bfffa79ec538b929342b81`.

`hand-ext managed ls --cwd MAIN` exit0 và `hh-ps --once --json`/`hh-ps --once` exit0: đúng1 row key/child cũ, **unknown**, exit/ended/USD/token chưa biết; text có dòng `? codex ... hpa-pilot3-stop… unknown`, không row trùng. B/final-managed-ls.json, final-tree.json/txt, final-projection-safe.json. Không đạt tiêu chí1row cancelled vì recover không đủ proof. Không approve/archive exact child do chưa awaiting_review/terminal evidence; không tác động gateway37655 hay parent.

## Gate5 — dsh và claude-v2 bị chặn trước dispatch

Đã thử trước release ở main0.35.4 (brief cho phép độc lập trước nếu slot đủ). Mỗi backend có `pick --json` ngay trước; label và one-line scratch riêng, `--no-apply`. Lệnh:
`hand-ext run --backend dsh --mode paseo-required --brief B/smoke-dsh-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply --label hpa-pilot4-smoke-dsh --timeout-min 4 --max-tokens 300000`; tương tự `--backend claude-v2`, brief/label tương ứng.

Cả2 exit8, stdout/stderr rỗng: AdmissionConflict hiện không in lý do. Intents đã được tạo nhưng **không reservation/process/worker/agent/placement/send**. Claims giống old reservation và claims_overlap=true, nên bị chặn trước dispatch, không phải live backend pass. B/smoke-predispatch-blocked.json. Sau release reservation cũ byte-identical, nên không retry tạo thêm intent để bypass/đợi vô hạn.

| Backend | Key | Pinned policy | Kết quả thực |
|---|---|---|---|
| dsh |9d939fbb-61ba-46b7-bcc0-93af0dd5477b:9c960316-9a77-477e-b6fb-b7f127bd72ca:1|deepseek-v4.1-flash/off/accountdsh|BLOCKED exit8, stateintent; actual placement/model/account execution UNKNOWN|
| claude-v2 |b6a7f87a-a8e7-444a-b984-79a3dc2f9587:9a9858bf-886c-4a88-906b-e21a22055e74:1|claude-opus-5-5/low/accountclaude-v2|BLOCKED exit8, stateintent; actual placement/model/account execution UNKNOWN|

hh-ps JSON/text có mỗi intent đúng1unknown row, không backend usage giả. Không child để review-approve/archive. Không có patch/scratch được áp source. **Dsh shell code hand đã chạy thành công ở phần sửa fence; điều đó không chứng minh gate5 managed dsh pass.** Không chạy claude-v1. Guard/quota không bị đổi, không tự chọn account khác.

## Gate3 optional, cleanup và phần còn lại

Gate3 managed mới SKIPPED do reservation old giữ claim toàn repo; không tạo invocation stop nữa rồi bỏ lại một intent vô ích. Chưa có `paseo stop` child0.35.5, nên **chưa xác nhận managed certificate/release trên live daemon**. Chỉ helper fixture thật và recovery+hooks fixture giả đã đạt như trên.

Mọi wrapper hand/QA do Sol tạo đã thoát; mọi root/child fixture tự tạo được wait/cleanup. Không tiến trình nền QA còn chạy; không dừng/archive agent khác, phiên tiktok hay brain. Gateway cũ37655 daemon-owned giữ để bảo toàn điều tra; không gọi stop ngoài đường chính thức/exact identity. Không xóa output/worktree/artifacts/history.

**Điểm chặn cần Opus:** source0.35.4 không lưu OS inventory/reap/owner-done nên không thể tạo proof lịch sử từ PID absence hoặc UI idle. Hiện không có xác nhận chủ động hợp lệ từ owner cũ cho contract reverify. Cần nguồn proof/lifecycle được duyệt riêng cho legacy; Sol không nhả reservation tay và không đề xuất đánh dấu confirmed bằng suy đoán. Sau khi chặn này được giải quyết đúng quyền, mới có thể rerun gate5 hai backend và gate3 managed. Không claim G7 hoàn tất.
