## Tóm tắt

- **Kết quả: xong phạm vi pilot5. Release 0.35.6 đã merge/push main `055336a`; không cần 0.35.7.**
- Legacy `597c17ca…`: recover PASS, cancelled/attested, confirmed=false, đủ 5 hook, reservation `c9d729cf…` đã nhả; dry-run không ghi, repeat apply byte-identical.
- Hai intent cũ dsh/claude-v2: recover PASS thành terminal `not_admitted`, repeat ổn định; hh-ps mỗi key đúng 1 row ✗, không unknown.
- Gate5 managed dsh và claude-v2 PASS: đúng provider/model/account/effort/placement, patch 1 dòng riêng, no-apply, mỗi key 1 row; đã review-approve/archive đúng child.
- Gate3 PASS trên 0.35.6: stop exact child, confirmed method `root_group+tracked_tree+env_marker`, root + descendant setsid biến mất, reservation nhả tự động.
- Code đổi: `legacy_attestation.py` thêm ngoại lệ có proof; admission/state/controller/completion/recovery/CLI tích hợp terminal/release; containment thêm group probe; hh-ps sửa terminal projection.
- Test controller/admission/CLI thêm đúng 3 nhóm; README mô tả ngoại lệ/rủi ro; manifest/CHANGELOG release 0.35.6. Chi tiết từng file bên dưới.
- QA Sol: 40 narrow tests PASS; full suite đúng 1 lần: 513 tests PASS / 76.019s; validate mặc định, JSON, 7 link nội bộ và diff-check PASS.
- Cả `~/.claude` và `~/.claude-hand` update chính thức; plugin list hai repo × hai account đều 0.35.6, đúng readFromFolder/cache path.
- Cleanup PASS: 3 child mới closed/archived, 4 marker scan authoritative/0 match/0 lỗi, không còn reservation pilot; không gọi claude-v1 hoặc restart/reload daemon.
- Điểm Opus cần biết: tuổi record cũ do operator xác nhận, không có version tự chứng thực; rủi ro process bỏ marker và thoát cây còn nguyên. Phiên Claude đang mở cần reload theo CLI.

## Phạm vi và baseline

Đã đọc đầy đủ `hpa-pilot4.md`, AGENTS main/worktree và skills ext-hand/paseo. Sol làm review/QA/release/live; code/test/README do hand thực hiện. Không gửi tin sang brain hay phiên khác; bàn giao bằng file này và `.done`.

- Main ban đầu `baec927`/0.35.5; worktree `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`, branch `side/hpa-pilot-fix`, fast-forward main trước giao code.
- **B** = `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix/.pilot5` (brief, QA và evidence; giữ nguyên).
- Sol Paseo `a2811578-5b32-4721-ba12-00b3bca31607`; scope/canonical parent `ca406ab2-f738-4b54-afe4-9f107fa5080c`.
- Giữ nguyên docs WIP, `.pilot/` đến `.pilot4/`, output/worktree/history có sẵn. Không reset/stash, sửa config/settings/credential/installation ledger bằng tay, mở side-session hay đổi slots/order/model/effort.

## Delegation và review

Mỗi lượt chạy `hand-ext pick --json --cwd WORKTREE` trước. Pick thực trả codex / gpt-6.1-sol / low / account gpt, native=true; brief yêu cầu shell nên cả hai lượt dùng wrapper `run --backend auto --mode shell --cwd WORKTREE --keep-worktree`. Không spawn native.

Acceptance viết trước trong `B/implementation-brief.md`, tối đa 3 nhóm: (a) legacy-attest đủ điều kiện, refusal matrix, final-scan revision race, 5 hook/release/repeat; (b) admission reject và recover intent cũ thành terminal; (c) không lộ env/argv/exception text. Mỗi brief có luật dữ liệu nguyên văn, scope executor, chỉ đọc trong execution worktree, cấm ps/pgrep/liệt kê phiên, raw runtime/transcript và gọi API trả phí.

| Run/report ID (dưới WORKTREE/output/llm/hand-ext/) | Backend | Exit | Input / cached / output | Duration | USD~ offline |
|---|---|---:|---|---:|---:|
| 20261109-200057-035183-hpa-pilot5-implementation-codex | gpt-6.1-sol/low | 0 | 2971920 / 2899200 / 21832 | 592.6s | 0.653680 |
| 20261109-201139-283260-hpa-pilot5-correction-codex | gpt-6.1-sol/low | 0 | 1551972 / 1500160 / 10527 | 319.8s | 0.358910 |

Wrapper sample cả hai lượt: account tuần 15%, reset `2026-11-16T06:19:22+00:00`; đây không phải quota dùng riêng bởi hand. USD~ từ helper canonical pricing, ước tính subscription offline, không phải hóa đơn (`B/hand-usage.json`). Không gọi claude-v1.

Review lượt đầu phát hiện guard modern inventory chỉ từ chối khi đồng thời complete+reaped; containment binding có thể bỏ qua independent dispatch receipt; predicate attested còn kiểm evidence quá ít. Giao lại cùng backend đúng **một** lượt (`B/correction-brief.md`). Bản cuối:

- Chỉ nhận schema legacy không mang inventory/reap/fatal evidence hiện đại; modern incomplete/failed cũng không được attest. Flag/reason do operator xác nhận nguồn gốc trước 0.35.5 vì record cũ không có plugin version.
- Luôn đối chiếu controller/source/backend, completion context/worktree, transport placement/request/cwd/parent/gateway invocation/store, writer-owner và reservation key/id canonical. Hash binding giữ bất biến, không nhân bản env/options vào proof.
- Direct OS owner/root identity, group probe và marker scan cùng user; non-harmless error/EPERM không qua. Live owner trả hint đóng exact child qua public Paseo. Không signal từ recover.
- Apply có pool/lifecycle lock và strict revision fence; lặp fresh proof trước CAS. Attestation giữ confirmed=false, evidence owner/root/group/marker/reason; hook/release chỉ nhận predicate proof hợp lệ, không nới mọi false quiescence.
- Test mô phỏng report sink đã ghi nhưng hook receipt chưa ghi: recover không replay report, vẫn hoàn thành đủ hook rồi release. Byte-identical repeat và refusal không mutation được kiểm.

Sol đọc toàn bộ diff, helper mới và test. Correction hand báo 40-test run ban đầu có 2 lỗi tương thích, rồi sửa và chạy lại các ca liên quan; Sol không coi đó là full narrow pass cho đến khi tự chạy lại 40 test xanh.

## File đã đổi

Các lib dưới `hybrid-hands/plugins/hybrid-hands/lib/`:

| File | Lý do |
|---|---|
| hand_ext/legacy_attestation.py (mới) | Proof/operator exception, never-admitted recovery, attestation predicate và settlement idempotent. |
| hand_ext/execution_admission.py | not_admitted trước reservation/dispatch; safe kind/holding-key; release attestation có binding. |
| hand_ext/execution_state.py | Loại not_admitted khỏi unsettled. |
| hand_ext/paseo_controller.py | Nhận terminal attestation và in diagnostic exit 8 an toàn. |
| hand_ext/paseo_completion.py | Năm hook chấp nhận riêng authority attested đã kiểm. |
| hand_ext/paseo_recovery.py | Route cờ attestation và evidence OS start. |
| hand_ext/cli.py | Cờ recover/reason/OS start và hint owner alive. |
| hand_ext/process_containment.py | Read-only group existence probe; permission uncertainty không bị coi absent. |
| hh_ps/paseo_source.py | Chiếu not_admitted thành terminal failure. |
| hybrid-hands/tests/test_hand_paseo_controller.py | Nhóm legacy proof/refusal/race/crash/repeat. |
| hybrid-hands/tests/test_hand_paseo_admission.py | Nhóm reject và legacy never-admitted, chặn reservation-before-CAS. |
| hybrid-hands/tests/test_hand_paseo_cli.py | Nhóm CLI flags/owner hint/exit 8 và secret sentinel. |
| hybrid-hands/README.md | Contract ngoại lệ, tuổi record do operator xác nhận, rủi ro process bỏ marker và thoát cây. |
| .claude-plugin/plugin.json | Bump 0.35.6 trên main. |
| CHANGELOG.md | Ghi release 0.35.6 và giới hạn attestation. |

Hai file cuối thuộc `hybrid-hands/plugins/hybrid-hands/`. Không đổi statusline/panel/config hay phần plugin khác.

## QA, release và cài đặt

Ở worktree, Sol chạy:

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_paseo_controller test_hand_paseo_cli test_hand_paseo_admission test_hand_paseo_execution test_hand_paseo_gateway test_hand_paseo_transport test_hand_paseo_completion test_hand_process_containment test_hh_ps_paseo_hand -v
python3 -m unittest discover -s hybrid-hands/tests -v
claude plugin validate hybrid-hands/plugins/hybrid-hands
git diff --check
```

Kết quả: narrow **40 tests OK / 15.513s** (`B/narrow-0356.txt`); full **513 tests OK / 76.019s**, đúng một lần (`B/full-suite-0356.txt`). Validate mặc định exit0 ở worktree và main sau bump. Directory profile chưa đạt do LICENSE_MISSING/ICON_MISSING baseline; không sửa ngoài scope, không claim directory submission pass. JSON manifest hợp lệ, 7 link nội bộ README tồn tại, diff-check sạch (`B/final-validation.json`).

Release đều bằng `git -C`, stage đúng file plugin/test/README:

1. Code commit **`45255b3bbd146d713c9727307c50a78d0e282829`**, push `origin side/hpa-pilot-fix`.
2. Merge main **`4f66714`**; bump manifest/CHANGELOG, commit **`055336a57809c3a3dce26993a7e9ad37b7a1d06e`**, push `origin main`.
3. `git ls-remote origin refs/heads/main refs/heads/side/hpa-pilot-fix` đối chiếu đúng hai SHA trên. Không release 0.35.7.

Chạy tuần tự cho hai account:

```sh
CLAUDE_CONFIG_DIR=/Users/anhtp/.claude claude plugin update hybrid-hands@hybrid-hands-local --scope user --json
CLAUDE_CONFIG_DIR=/Users/anhtp/.claude-hand claude plugin update hybrid-hands@hybrid-hands-local --scope user --json
```

Cả hai exit0, 0.35.5→0.35.6. Official `plugin list --json` ở `/Users/anhtp/app/claude-plugins` và `/Users/anhtp/app/live-tiktok-games` cho từng account: **4/4 exit0, enabled=true, version/folderVersion=0.35.6**, readFromFolder `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`, cache path đúng account/0.35.6 (`B/installation-0356-verified.json`). Không cài/bật cho account/repo khác. CLI báo Restart to apply changes cho phiên đang mở; không reload/restart daemon hay agent khác. Managed workers mới được tạo sau release; shared source/provider hiện có dùng được, không cần sửa provider config.

## Legacy recover — PASS

Exact key `597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1`, child `6690365c-6cc5-4778-a502-622a3705827a`, reservation `c9d729cfa7d0287e1b2ef8d8abc0fa6946719c72a36e88eb97ac61a35efd8d93`.

Baseline chỉ đọc: owner37655 còn sống, OS start `1794225413:805677` khớp pilot4; root37676 vắng. Public inspect đúng child/provider/model/cwd. Trong khi hand chạy, record từ revision20 lên21 bởi runtime đang tồn tại; chỉ ghi nhận, không suy nguyên nhân. `B/records-baseline.json` giữ hash revision21 mới.

Sau release, reverify public inspect trước thao tác live: **child closed, Archived=false, owner37655 đã vắng** (`B/legacy-public-archive.json`). Do đó **không chạy archive/stop child cũ**; không claim Sol đã đóng gateway. Điều kiện cần đóng nếu owner còn sống không còn áp dụng.

Lệnh CLI main, lần lượt dry-run, thêm `--apply`, rồi lặp `--apply`:

```sh
hand-ext managed recover --cwd /Users/anhtp/app/claude-plugins --key 597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1 --legacy-attest --reason "người dùng duyệt 09/11/2026; xác nhận record trước 0.35.5" --owner-os-start 1794225413:805677
```

Cả3 exit0. Dry-run record/reservation byte-identical. Apply: awaiting_review, outcome cancelled/exit-15, revision33, **confirmed=false**, details.attested=true, method operator_legacy_attest; owner/root absent, group absent, marker_matches0, authoritative=true, diagnostics[]. Không tạo root_reaped/inventory_complete. Cả5 hook completed; record.reservation=null và pool file đã mất qua admission release chuẩn. Repeat hash record giữ **`218563ef27c249300d33b0d5aca60365c57d04da5cf9b981a3090ad61af7aa30`** (`B/recover-0356-summary.json`). finished_at ở đây là mốc settlement/attestation, không phải chứng cứ giờ backend lịch sử thoát.

Recover cùng đường cho hai intent cũ với `--legacy-attest --reason "người dùng duyệt 09/11/2026; xác nhận intent chưa admission"`, mỗi key dry-run/apply/repeat đều exit0, dry không ghi/repeat cùng hash (`B/recover-intents-0356.json`):

- dsh `9d939fbb-61ba-46b7-bcc0-93af0dd5477b:9c960316-9a77-477e-b6fb-b7f127bd72ca:1` → not_admitted, exit8, không reservation/child.
- claude-v2 `b6a7f87a-a8e7-444a-b984-79a3dc2f9587:9a9858bf-886c-4a88-906b-e21a22055e74:1` → not_admitted, exit8, không reservation/child.

`managed ls` mỗi key đúng1 row; legacy lifecycle awaiting_review, hai intent not_admitted. hh-ps JSON/text mỗi key đúng1 terminal row ✗ (projection status failed vì exit-15/8), không unknown/✓ (`B/recovery-projection-0356.json`, `B/final-projection-0356.json`). Không chạy thêm live AdmissionConflict chỉ để tạo intent; exit8 kind/holding key được kiểm bằng fixture/CLI test thực thi.

## Gate5 managed smoke — PASS cả hai backend

Mỗi smoke có `pick --json --cwd MAIN` ngay trước. Run theo mẫu:

```sh
hand-ext run --backend BACKEND --mode paseo-required --brief B/smoke-BACKEND-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply --keep-worktree --label hpa-pilot5-smoke-BACKEND --timeout-min 4 --max-tokens 800000
```

| Backend | Exact key | Exact child | Kiểm thực tế |
|---|---|---|---|
| dsh | b06f8b6f-cd22-4a94-8253-25d29887ebe2:8aee4320-b42e-4514-8d34-5d3b067736a9:1 | a5f366bc-f551-4238-aef2-86541c04e5d4 | Exit0; hh-hand-dsh/deepseek-v4.1-flash/off/accountdsh; project prj_7a322b4848a466f5, workspace wks_c46b8fc30a950fd1. |
| claude-v2 | 3853c89c-535f-41e6-b374-7f6fe255d135:dae566fa-abe7-4fdf-823d-17058cac035e:1 | e0a76161-0459-4af5-91bc-c6187ba99592 | Exit0; hh-hand-claude-v2/claude-opus-5-5/low/accountclaude-v2; config_dir resolves ~/.claude-hand; cùng project, workspace wks_afc61ffbb79c2506. |

Public inspect đối chiếu exact child/provider/model/Thinking/cwd; mỗi cwd là isolated worktree riêng, target key trùng verified project. Sol đọc report/patch, đọc lại scratch: đúng tên riêng và đúng1 dòng+newline, source scratch không tồn tại, finalize files đúng1, added1/removed0/no_apply. Một probe QA ban đầu dùng git diff HEAD bỏ sót file untracked nên assert fail; đã đổi sang patch/finalize.files và đối chiếu nội dung trực tiếp, **không phải lỗi plugin hay smoke**.

Dsh token input43928/cached28672/output461; claude-v2 input63209/cached39421/output475. Không suy quota từ token. UI cuối USD~ dsh <0.01, claude-v2 ~0.11; nguồn canonical/offline, account quota thiếu vẫn ?. Hai record confirmed, đủ5hook, reservation tự nhả; hh-ps JSON đúng1 row/key, text ✓. Sau review chạy `managed review-approve` rồi `managed archive` đúng key: cả4 lệnh exit0. Public cuối cả2 closed/Archived=true (`B/smoke-*-reviewed.json`, `B/final-cleanup-0356.json`). Không bị guard/quota chặn, không gọi claude-v1.

## Gate3 stop setsid trên 0.35.6 — PASS

Sau hai smoke đã archive, pick lại, chạy `--backend codex --mode paseo-required --no-apply --keep-worktree --label hpa-pilot5-stop-0356 --timeout-min 4 --max-tokens 1000000 --brief B/stop-brief.md`.

Brief chỉ chạy hữu hạn `python3 -c 'import subprocess; child = subprocess.Popen(["/bin/sleep", "120"], start_new_session=True); child.wait(timeout=130)'` trước scratch. Quan sát deadline40s, chỉ chọn root/descendants từ exact record. Public inspect trước stop khớp child running/provider/model/cwd.

- Key **`67f2b634-cbd0-4154-aa7e-d2ec8b040874:bb3b8d26-5313-46bb-8151-4001e8af1a71:1`**; child **`6a5a51e0-81e5-4210-8e3e-f3e73d1e3103`**.
- Root PID/PGID99497, OS start1794230746:453368; sleep PID/PGID1363, PPID1361, start1794230755:338171 (setsid thực).
- `paseo stop 6a5a51e0-81e5-4210-8e3e-f3e73d1e3103 --json` exit0/stoppedCount1, đúng1 agentId. Wrapper exit1 **vì cancelled**, không phải gate fail.
- Record awaiting_review/cancelled/exit-15, confirmed=true, method **root_group+tracked_tree+env_marker**, root_reaped=true/inventory_complete=true/first_fatal=null; đủ5hook, reservation=null tự động.
- Direct OS identity sau stop: cả6 identity quan sát trước (99497,99529,317,1359,1361,1363) đều vắng. `ps` exact root+sleep sau stop exit1/output rỗng. Không signal thủ công process nào.
- Marker scan ngay sau stop authoritative/0lỗi: chỉ owner gateway99454 còn marker và đúng protected identity trong certificate; không còn backend/descendant marker. Đây là owner sống giữ UI review, không phải escaped child.
- Review patch rỗng/files[], source scratch vắng; hh-ps đúng1 row/key ✗. Review-approve/archive exact key đều exit0. Public cuối closed/Archived=true, marker scan sau archive **0 match/0lỗi/authoritative**.

Evidence: `B/stop-0356-before.json`, `stop-0356-public-command.json`, `stop-0356-after.json`, `stop-0356-reviewed.json`, `final-cleanup-0356.json`. ps trước stop chỉ nhắm PID thuộc cây task đã xác minh, không liệt kê host process/agent khác; field comm của npm có process title chứa command arguments công khai nên không nhân bản dòng đó ở bàn giao.

## Trạng thái cuối, giới hạn và phần còn lại

`B/final-projection-0356.json`: 6 key liên quan, đúng1 hh-ps row mỗi key; 2 smoke ok/✓, 2 not_admitted + legacy cancelled + gate3 cancelled đều terminal ✗. managed ls đúng state tương ứng. Không tạo duplicate writer/intent trong pilot5.

`B/final-cleanup-0356.json`: không reservation nào thuộc6 invocation; legacy và3 invocation có process đều scan marker cùng user authoritative=true, matches[], diagnostics[]. Ba child mới đều review-approved/archived/closed; wrappers shell hand/QA/live commands đã thoát, descendant gate3 không còn. Legacy target giữ awaiting_review, child cũ đã closed từ trước live recover; không approve/archive record/parent pilot cũ ngoài bước được giao. Không stop/archive tiktok, phiên chính, parent hay agent khác; không restart/reload daemon, không dọn output/worktree/history.

Tracked main/worktree sạch sau release; chỉ docs WIP untracked có sẵn, các `.pilot*` và hai file bàn giao được giao. Không còn bước bắt buộc trong brief pilot5. Những điều chưa được chứng minh: tuổi record legacy bằng machine version (không có nguồn), containment tuyệt đối cho process vừa bỏ marker vừa thoát cây; không mở rộng claim sang các gate ngoài pilot5. Phiên Claude đang mở vẫn cần reload để nhận plugin mới theo CLI.
