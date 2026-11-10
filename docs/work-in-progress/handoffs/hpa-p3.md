## Tóm tắt

- Kết quả: **G4 + G5 + G7 offline xong**, Sol review từng diff; nhánh `side/hpa-p3`, base `f73f09a`, HEAD `bba2dfe`, worktree sạch.
- Commits: `2e7dddd` CLI managed; `a5fb53b` policy/docs; `6f6bb07` hh-ps; `2db961f` G7 fake integration; `bba2dfe` spec/plan + bằng chứng reload.
- 19 file: 7 module hh-ps, 2 module hand-ext, 5 policy/docs, 3 test, 2 spec/plan; lý do từng file ở dưới.
- Full suite chạy **đúng một lần** từ cwd worktree `hybrid-hands`: **487 tests OK, 90.876s, exit 0** trên source/test head `2db961f`; sau đó chỉ docs/bàn giao.
- CLI: `hand-ext managed ls|review-approve|archive|followup --cwd REPO`; ba lệnh cuối thêm `--key INVOCATION:ATTEMPT:EPOCH`; followup bắt buộc `--brief FILE`.
- **Paseo 0.15.0 có explicit hot reload providers, không bắt buộc restart**: `paseo daemon reload --home HOME --json`; source `daemon-config-store.js:99,310–357`, CLI `dist/commands/daemon/reload.js:22–42`; chuỗi đầy đủ bên dưới.
- Không dựa vào auto-watch; reload áp mọi delta reloadable đang chờ. Opus giữ provider hiện có, kiểm paths kết quả và catalog trước pilot; chưa chạy reload thật.
- Pilot theo thứ tự: tích hợp commits → xác minh target/package + quyền/trần live → provider dry-run/apply → public daemon reload → opt-in config repo → status → run → kiểm cây/stop → review/archive/followup → smoke backend/account → release.
- Narrow G4/G5/G7 xanh; default plugin validation + Node bridge syntax pass. Directory còn `LICENSE_MISSING`/`ICON_MISSING`; skill validator thiếu `yaml`, Ruby YAML/links pass.
- Chưa live/API/model thật, provider apply/config/restart/install/runtime update, bump version/changelog, push/merge/main. G7 live và release/install thuộc Opus.
- Rủi ro còn: stop/reap/containment, ACK recovery/reopen/placement thật và smoke từng backend/account chưa chứng minh; native hand token/USD~/quota **?**, không tạo ledger hand-ext giả.

## Nhánh, phạm vi và commits

Worktree `/Users/anhtp/app/claude-plugins-wt/hpa-p3`; nhánh `side/hpa-p3`; base `f73f09aa21c152fec11912c291dd0a1cb9b2a1b1`. Năm commit sau đều do Sol điều phối sau review; hands không commit:

| Commit | Gói |
| --- | --- |
| `2e7dddd` | `feat(hand-ext): add managed review archive and follow-up commands` |
| `a5fb53b` | `docs(hybrid-hands): route new native intents through managed Paseo` |
| `6f6bb07` | `feat(hh-ps): project managed Paseo executions once per epoch` |
| `2db961f` | `test(hand-ext): cover managed Paseo lifecycle offline end to end` |
| `bba2dfe` | `docs(hybrid-hands): record stage three offline gates and provider reload evidence` |

Sau commit cuối `git status --short` rỗng, diff base→HEAD đúng 19 file trong phạm vi, diff checks pass. Không push/merge hoặc commit vào main. Bàn giao này và `.done` nằm ở repo chính theo hợp đồng, không commit vào main.

Không sửa `lib/side_session/*`, panel `paseo-hh-tree/src/**`, statusline, AGENTS.md, manifest/version/CHANGELOG, settings/credential/sổ cài đặt hay cấu hình repo/daemon thật; không dọn `output/llm/`. Không chạy provider setup apply thật, restart/reload daemon thật, tạo/send/stop/archive agent/workspace/project thật, cài plugin/dependency hoặc gọi API trả phí.

## File đã đổi và lý do

Đường dẫn tính từ `hybrid-hands/` trong worktree; `H = plugins/hybrid-hands`.

| File | Lý do |
| --- | --- |
| `H/lib/hand_ext/cli.py` | CLI managed local ls và lifecycle exact execution; output JSON chọn lọc, lỗi machine code. |
| `H/lib/hand_ext/paseo_controller.py` | Archive/followup kiểm review đúng epoch và terminal evidence trước mutation. |
| `H/lib/hh_ps/paseo_source.py` | Projection read-only durable ExecutionRecord, parser totals, identity/artifacts và native aliases. |
| `H/lib/hh_ps/models.py` | Bổ sung cuối HandRun các identity/artifact fields có default; giữ managed unknown. |
| `H/lib/hh_ps/registry_source.py` | Khám phá execution roots hiệu lực và khử trùng meta/registry với managed execution. |
| `H/lib/hh_ps/native_source.py` | Bỏ managed rollout aliases khỏi native root/child discovery; giữ fixed sessions source. |
| `H/lib/hh_ps/tree.py` | Nối mapping/dedup, gắn parent canonical trực tiếp, ledger enrichment phải khớp execution key. |
| `H/lib/hh_ps/render.py` | JSON thêm managed execution/placement/artifact fields. |
| `H/lib/hh_ps/compact.py` | Managed unknown hiện `?`, không dấu done giả. |
| `H/skills/ext-hand/SKILL.md` | Q3 routing intent mới và lifecycle managed; giữ guard/account/pool/legacy. |
| `H/skills/paseo/SKILL.md` | Managed setup/reload/status và phân biệt với đường native cũ. |
| `H/templates/side-session-prompt-codex.md` | Brief Sol mới dùng routing Q2–Q7 và lệnh lifecycle. |
| `README.md` | Recipe operator, opt-in/fallback, commands và giới hạn live. |
| `paseo-hh-tree/OVERVIEW.md` | Giải thích placement/projection/lifecycle, không đổi panel code. |
| `tests/test_hh_ps_paseo_hand.py` | 3 ca mapping/dedup/parser, epochs/live tokens và unknown/error/legacy. |
| `tests/test_hand_paseo_cli.py` | 3 ca CLI local ls/parser, review/archive/followup và lifecycle guards. |
| `tests/test_hand_paseo_integration.py` | 1 ca end-to-end offline qua worker/completion/snapshot/CLI thật với runner/client giả. |
| `docs/2026-11-09-hand-paseo-agent-spec.md` | Interface thực G4/G5, source reload, G7/full suite và gate live/release. |
| `docs/2026-11-09-hand-paseo-agent-plan.md` | Tick G4/G5/G7 offline, full suite; giữ G7 live/release chưa tick. |

## Hành vi và review

Một managed invocation/attempt/epoch trở thành một HandRun dưới `Invocation.parent_session` canonical, không tạo side-session root hay ăn giới hạn 6 phiên phụ. Backend/model/effort từ invocation; placement từ attempt; artifact paths từ receipts. Followup có run_id null dùng SHA256 exact execution key như completion, nên epoch mới không đè epoch cũ dù reuse agent/workspace.

Nguồn token ưu tiên outcome parser rồi completion/registry metadata đã khớp execution key, hoặc live registry khớp run_id và exact worker_run_dir. Các nguồn thay thế nhau, không cộng. Registry.start counters 0 chưa có observation giữ unknown; measured zero từ outcome vẫn là 0. Ledger Codex run-id-only không được lấp usage/quota cho managed epoch không khớp. USD~ vẫn từ canonical pricing/enrichment hiện có; thiếu token/giá/quota giữ `?`, không suy quota từ USD.

Meta/RunRegistry trùng bị loại theo execution key, run_id hoặc worker directory; native Codex aliases bị loại theo exact agent/thread ID hoặc absolute resolved isolated cwd (không prefix/substring source cwd). Cả native root không có parent_thread_id và native child đều được xử lý. Legacy native/shell giữ đường cũ. Status lỗi canonical được giữ; exit khác 0 ưu tiên failed; unresolved không biến thành done từ mtime/sink/UI idle. JSON giữ started cho metadata; không thêm giờ bắt đầu vào text.

Sol đọc toàn bộ source/diff và test mới, kiểm invariants parent/epoch/usage/authority và đối chiếu source reload. Trong lượt G4 đang triển khai, Sol yêu cầu hoàn thiện live registry token projection, khử trùng rollout root không parent và giữ capped/quota/not_logged_in; final diff đạt. Không phát hiện lỗi cần chuyển backend hoặc ngoại lệ tự code sau hand-ext lỗi. Các tác vụ code/test/docs đều native `gpt-6.1-sol low`, `fork_turns=none`, sau pick codex/gpt/low; tối đa 3 hand đồng thời, không mở side-session/recursion. Usage token/USD~/quota native không có số được cung cấp: **?**; không suy hoặc tạo ledger giả.

## Lệnh CLI managed chính xác

```sh
hand-ext managed ls --cwd /ABS/REPO
hand-ext managed review-approve --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH
hand-ext managed archive --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH
hand-ext managed followup --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH --brief /ABS/fresh-brief.md
```

`--cwd` bắt buộc, phải đúng source cwd của execution. Key gồm ba phần phân cách `:`, epoch nguyên >=1. `ls` chỉ đọc metadata local và không probe daemon; summary không in brief/env/options/receipt. `review-approve` không cần daemon. Archive/followup dùng PaseoController/transport hiện có, từ chối key cũ, sai repo, chưa review đúng epoch, còn reservation hoặc thiếu terminal evidence. Admission full trả 8; lỗi lifecycle trả JSON code loại lỗi và exit 1.

Done giữ hiện cho Sol đọc report/diff trước approve. Archive chỉ exact child, giữ parent/workspace/worktree/history. Followup dùng latest key, tạo epoch/request/brief và baseline mới; cùng child/workspace, không hứa CLI context resume. Nếu mutation/ACK/outcome chưa rõ, giữ execution/reservation, dùng local ls để tìm exact key; không gọi run mới để tạo writer thay thế. CLI chưa có lệnh reconcile riêng; không tự dọn state/lock để mở slot.

## Reload agents.providers: câu trả lời bằng source

**Có public reload khi daemon đang chạy; không bắt buộc restart chỉ để thêm providers.** Dùng `paseo daemon reload --home /ABS/DAEMON_HOME --json` sau setup ghi trực tiếp `<home>/config.json`. Không tìm thấy watcher config trong các paths config/store/persisted/bootstrap đã khảo sát; không dựa vào tự reload khi file đổi. Đây là kết luận đọc source, chưa chạy reload thật.

Package cài đã đối chiếu manifests CLI/server/client đều **0.15.0**. Alias:

- `P=/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`
- `S=P/node_modules/@getpaseo/server/dist/server`
- `C=P/node_modules/@getpaseo/client/dist`

| Source file:line | Bằng chứng |
| --- | --- |
| `P/dist/commands/daemon/reload.js:22–42` | Official CLI reload gọi client, xuất applied/restart-required/override paths; mô tả reload không restart. |
| `C/daemon-client.js:3717–3722` | Public `reloadDaemonConfig()` gửi `daemon.config.reload.request`. |
| `S/server/session/daemon/daemon-session.js:179–184`; `S/server/session.js:515` | Handler response nối callback tới `daemonConfigStore.reload()`. |
| `S/server/daemon-config-store.js:78–100,126` | `agents.providers` thuộc RELOADABLE_PATHS, map thành mutable providers. |
| `S/server/daemon-config-store.js:310–357` | Đọc lại persisted config, resolve, tính applied/restart/override paths, apply replacement. |
| `S/server/config.js:415–440` | Resolve provider overrides từ `persisted.agents.providers`. |
| `S/server/websocket-server.js:423–427`; `S/server/agent/mutable-provider-config-owner.js:4–28` | Store onApply chuẩn bị/commit provider config vào agent registry với rollback. |
| `S/server/agent/provider-snapshot-manager.js:346–401` | Rebuild registry/generation; invalidate catalog/bindings của provider đổi và warmup. |
| `S/server/agent/agent-manager.js:361–384`; `S/server/agent/provider-snapshot-manager.js:141–160` | Registry update không đóng mọi agent; chỉ vòng retiredProviders gọi close, state của mutable update không có trường retiredProviders. |

Chỉ thêm `hh-hand-*` và giữ provider Opus hiện dùng; source không cho thấy đường này bắt buộc restart/reload session Opus. Tuy nhiên không suy bảo đảm runtime/context cho mọi kiểu thay provider. Reload áp **mọi delta reloadable đang chờ** trong config, không chỉ provider vừa thêm. Opus kiểm delta an toàn, `appliedPaths`, `restartRequiredPaths`, `overrideControlledPaths`, rồi provider catalog. Nếu kết quả thật yêu cầu restart cho thay đổi khác, dừng pilot và xử lý riêng; không tự restart phiên Opus.

## Thứ tự live pilot cho Opus ở repo claude-plugins

Các bước dưới là recipe **chưa thực hiện**. Opus thực hiện trong giai đoạn live đã có quyền disposable resources/account và trần thời gian/chi phí; không coi test fake là live gate.

1. Tích hợp đủ 5 commits theo thứ tự vào nhánh pilot của `/Users/anhtp/app/claude-plugins`, giữ thay đổi đang có. Dùng binary ở checkout ổn định này để provider command không trỏ worktree tạm hpa-p3. Chưa release/bump/install ở lượt này.
2. Xác minh đúng daemon target/home đang chứa parent Opus/Sol và version runtime tương thích package official 0.15.0; không suy home từ HOME mặc định. Kiểm cấu hình delta dự định, giữ existing providers và không in credential/env/config nhạy cảm. Chốt task fixture/disposable, account và trần live trước mutation/model thật.
3. Chạy official-schema setup dry-run rồi apply trên đúng home. Tiếp theo **public daemon reload**, không restart mặc định. Kiểm các paths kết quả, giữ Opus đang mở. Lệnh mẫu:

```sh
PILOT_HAND_EXT=/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext
PILOT_PASEO_HOME=/ABS/VERIFIED_DAEMON_HOME
PILOT_PASEO_PACKAGE=/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli
"$PILOT_HAND_EXT" provider setup --home "$PILOT_PASEO_HOME" --package-root "$PILOT_PASEO_PACKAGE" --dry-run
"$PILOT_HAND_EXT" provider setup --home "$PILOT_PASEO_HOME" --package-root "$PILOT_PASEO_PACKAGE" --apply
paseo daemon reload --home "$PILOT_PASEO_HOME" --json
```

4. Gộp pilot settings **chỉ repo claude-plugins** vào ext_hand hiện có: `mode=auto`, `paseo.package_root` official path, `paseo.target={kind:instance,home:<verified-home>}`, state_root optional. Giữ các khóa/order/account khác. Đây là cấu hình plugin repo được giao riêng cho Opus, không sửa credential/settings/sổ cài đặt. Chạy `provider status --cwd /Users/anhtp/app/claude-plugins`, phải thấy đủ providers khả dụng từ catalog; file config có entry chưa đủ.
5. Từ đúng parent context có PASEO_AGENT_ID, pick trước rồi dispatch task nhỏ với `run --backend auto --mode paseo-required --brief /ABS/pilot-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply`. Verify child có workspace/isolated cwd riêng, cùng verified project, caller/parent canonical đúng, track/tab cha, model/account/effort đúng. `hh-ps --once`/JSON phải thấy đúng một hand row với tokens/USD~/ended/elapsed đúng nguồn, không rollout root trùng.
6. Trên task disposable kiểm live admission cả UI/pool, cancel/stop/reap và ACK recovery theo G7; đòi authoritative quiescence/settlement, không UI idle. Unknown giữ reservation; không blind retry/run mới hoặc tự xoá state. Đây vẫn là gate chưa pass.
7. Sau done, đọc diff/report và terminal evidence; dùng `managed ls`, `review-approve`, `archive` exact key. Verify chỉ child archived, parent/workspace còn. Followup bằng latest key + brief tự chứa mới; verify reopen cùng agent/workspace, epoch 2, key/request/baseline/artifacts mới, epoch 1 còn và không áp patch hai lần. Không cleanup worktree.
8. Smoke từng backend/account trước quảng bá supported; kiểm reopen với cwd/workspace còn, missing-cwd blocked, fallback auto chỉ trước dispatch. Ghi bằng chứng live và rủi ro/chi phí thật. Sau gate Opus mới xử lý license, version/CHANGELOG, validate/release và official plugin update ở repo đang dùng, kiểm loaded version/path/reload như AGENTS; phiên hpa-p3 không làm các bước đó.

## Kiểm chứng đã chạy

Sol trực tiếp chạy narrow từ worktree (trừ lệnh targeted có cwd tests):

| Lệnh | Kết quả |
| --- | --- |
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_cli.py'` | 3 OK, 1.163s |
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps_paseo_hand.py'` | 3 OK, 0.183s |
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps_native.py'` | 3 OK, 0.201s |
| cwd `hybrid-hands/tests`: `python3 -m unittest test_hh_ps.HhPsTest.test_hand_runs_parent_grouping_orphans_and_lost test_hh_ps.HhPsTest.test_json_schema test_hh_ps.HhPsTest.test_no_secret_key_prompt_or_socket_is_read_or_printed` | 3 OK, 0.224s |
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_integration.py'` | 1 OK, 1.947s |

Hand còn chạy controller narrow **3 OK (4.332s)**, CLI **3 OK (1.503s)**, G4 **3 OK (0.163s)**, native **3 OK (0.145s)**, integration **1 OK (1.475s)** và py_compile file mới. Không dùng kết quả hand thay kết quả full của Sol.

**Full suite duy nhất**, cwd `/Users/anhtp/app/claude-plugins-wt/hpa-p3/hybrid-hands`, source/test head `2db961f`:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

**Ran 487 tests in 90.876s — OK, exit 0.** Không failures/errors nên không cần chạy đối chiếu base. Sau đó chỉ spec/plan và bàn giao; không đổi code/test hoặc lặp full suite.

`claude plugin validate hybrid-hands/plugins/hybrid-hands`: **default Validation passed**; output directory checks có `LICENSE_MISSING` problem và `ICON_MISSING` warning, không claim directory profile pass. `node --check hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs`: pass. Diff/staged diff checks pass. Relative file links: 14 trong policy/docs, 11 trong spec/plan, đều tồn tại; hai skill frontmatter Ruby YAML parse pass. Hand thử skill `quick_validate.py` nhưng thiếu Python dependency `yaml`, không cài dependency và không claim validator pass. CLI help đã đối chiếu bởi hand, không gọi daemon.

Các exec/test đã kết thúc; fixture subprocess/worker threads do tests tạo có cleanup/join hữu hạn. Không để tiến trình nền do phiên tạo tiếp tục chờ bàn giao.

## Việc còn lại và giới hạn

G7 live vẫn chưa pass: exact project/workspace/parent placement, provider readiness thật, stop/reap và containment descendant escape process group, recovery sau mất process authority/ACK, archive/reopen/missing-cwd và smoke các backend/account. Fixture/source không chứng minh các điều này trên daemon thật. CLI không có reconcile subcommand riêng; unresolved cần operator dùng đúng store/controller recovery, không tạo writer khác.

Không migrate native đang chạy; routing intent mới chỉ có hiệu lực sau Opus triển khai policy/config/runtime đúng repo. Legacy native ngoài dispatcher vẫn chưa có admission pre-spawn toàn cục. Mapping cwd chỉ exact isolated path của managed record; không suy usage hay quota ngoài nguồn quan sát được. Reload source đã rõ nhưng chưa live proof về ảnh hưởng tới phiên Opus.

Release còn license distribution, version/CHANGELOG, official install/update và loaded version/path ở các repo đang dùng. Không tự bật plugin ở repo mới. Theo brief, tất cả được giao Opus sau pilot, không làm trong hpa-p3.
