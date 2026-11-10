## Tóm tắt

- Kết quả: **G3 + setup provider xong offline**, Sol review từng diff; commit **`f73f09a`** trên `side/hpa-p2`, base `54480e7`; worktree sạch.
- 18 file: controller/completion/provider mới; nối CLI/config/run_cmd/gateway/worker/admission/transport; ba module test + hai fixture; spec/plan tick G3. Chi tiết từng file bên dưới.
- Aggregate yêu cầu chạy đúng **một lần**: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_*.py'` → **198 tests OK, 27.234s, exit 0**.
- Sol chạy narrow controller/completion/provider: **3/3 mỗi nhóm**, regression parallel **3/3**, config-worktree **2/2**; default plugin validation, bridge syntax và diff checks pass.
- Pilot: `ext_hand.mode="auto"`, `ext_hand.paseo.package_root` + `target`; override `run --mode paseo-required`. Lệnh thực là **`hand-ext provider setup --dry-run|--apply`** và **`provider status`**, không phải alias `paseo-provider`.
- Shell vẫn là mode hiệu lực; chưa bật pilot. Apply chỉ test bằng home giả, không đăng ký provider hay mutate agent/workspace/project/daemon thật.
- G4/G5/live/release còn lại; chưa kiểm stop/reopen/placement thật, containment descendant và recovery mất process authority vẫn là gate. Directory validation còn LICENSE_MISSING/ICON_MISSING.
- Không bump version/CHANGELOG, không install/runtime update, không push/merge/main; native hand usage/token/USD~/quota **?**, không tạo hand-ext ledger giả.

## Nhánh, phạm vi và commit

Worktree `/Users/anhtp/app/claude-plugins-wt/hpa-p2`, nhánh `side/hpa-p2`, base `54480e7` của giai đoạn 1. Một commit tính năng: `f73f09a feat(hand-ext): integrate managed Paseo execution and provider setup`. Sol commit sau narrow/aggregate xanh và review; hands không commit. Không push/merge hoặc commit vào main. Sau commit `git status --short` rỗng. Bàn giao này và `.done` nằm ở repo chính theo đường dẫn được giao, không commit vào main.

Không sửa side_session/hh_ps/skills/templates/README/OVERVIEW/UI/statusline, cấu hình repo/daemon thật, credential/settings/sổ cài đặt. Không dọn `output/llm/`. Không chạy model/API thật, tạo key hoặc cài dependency/plugin. Version giữ nguyên theo brief. Metadata cấu hình đọc qua helper xác nhận `max_parallel=4`, mode hiệu lực `shell`; không in config hiện hữu.

## File đã đổi và lý do

Đường dẫn tính từ `hybrid-hands/` trong worktree hpa-p2:

| File | Lý do |
| --- | --- |
| `plugins/hybrid-hands/lib/hand_ext/paseo_controller.py` | Dispatcher, fresh policy, lifecycle/latest epoch, fallback/order/capacity và bootstrap gateway tin cậy. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_completion.py` | Binding context bền, finalize/report/ledger/usage sinks, reconciliation theo proof và release. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_provider.py` | Setup custom ACP providers theo schema chính thức, dry-run/backup/atomic write và catalog status. |
| `plugins/hybrid-hands/lib/hand_ext/run_cmd.py` | Route mode managed; giữ shell reservation và đường shell hiện có. |
| `plugins/hybrid-hands/lib/hand_ext/cli.py` | Cờ `run --mode` và lệnh `provider setup/status`. |
| `plugins/hybrid-hands/lib/hand_ext/config.py` | Default `mode=shell`, cấu hình `paseo` và validation keys. |
| `plugins/hybrid-hands/lib/hand_ext/execution_admission.py` | Fail closed khi thiếu checker, dùng giới hạn pool policy hiện tại. |
| `plugins/hybrid-hands/lib/hand_ext/execution_worker.py` | Running registry, safe usage/capacity observation, CAS retry bounded và completion callback. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_gateway.py` | Bind production worker/checker/completion, fresh follow-up, serialized recovery và exit mapping. |
| `plugins/hybrid-hands/lib/hand_ext/paseo_transport.py` | Merge independent worker receipts khi ACK về, giữ transport fence; optional wait đủ settlement. |
| `plugins/hybrid-hands/bin/hand-paseo-acp` | Cập nhật mô tả entry đã có trusted durable binding. |
| `tests/test_hand_paseo_controller.py` | Ba nhóm fixture: mode/fallback; managed CLI/guards/pool/lifecycle; ambiguity/binding/capacity. |
| `tests/test_hand_paseo_completion.py` | Ba nhóm: finalize/apply/ledgers once; crash/sink proof; nonquiescent/failure. |
| `tests/test_hand_paseo_provider.py` | Ba nhóm: no-write/no-disclosure dry-run; apply/preserve/backup; catalog/schema invocation. |
| `tests/fixtures/hand_paseo/provider/package/package.json` | Metadata fake official package pin 0.15.0 cho test độc lập máy. |
| `tests/fixtures/hand_paseo/provider/schema-marker.js` | Marker schema fixture; không vendor upstream schema. |
| `docs/2026-11-09-hand-paseo-agent-spec.md` | G3 interface thực, setup recipe, settlement/lifecycle và gate kiểm chứng. |
| `docs/2026-11-09-hand-paseo-agent-plan.md` | Tick G3 offline, ghi kết quả thật, giữ G4/G5/live/release chưa hoàn tất. |

Không cần sửa `run_registry.py` hoặc `report.py`: worker dùng API `RunRegistry` hiện có cho start/child/tick; completion sở hữu final registry/meta/report và canonical ledger. Regression registry/report nằm trong aggregate 198 tests. Không tạo owner finalize thứ hai.

## Hành vi cuối và review

`shell` là default. `auto` chọn backend qua effective order/doctor/quota/day guard, rồi probe daemon/provider/capability và verify parent/project. Thiếu capability/provider/daemon trước dispatch mới fallback shell; order shell bắt đầu bằng backend đã chọn và phần đuôi, giữ nhánh auto quota/capacity. Explicit backend vẫn explicit. Parent/project hoặc target sai fail closed, không đổi daemon ngầm.

Managed prepare worktree/baseline và validate fixed spec/completion trước create/send. Invocation pin backend/account/model/effort/options/scope/parent; CLI dùng claim bảo thủ `repo:*`. FreshPolicy đọc effective repo policy mới trên mỗi prompt, kể cả duplicate completed attachment; admission dùng pool chung và giới hạn hiện tại. Backend/order hết khả dụng trả 7; full/claims conflict trả 8; transport uncertainty trả lỗi riêng, giữ exact state/reservation. `paseo-required` không fallback shell; hỗ trợ intent mới vốn giao native, không migrate native đang có.

Sau create/send hoặc ACK ambiguity không launch shell hay writer khác. Transport CAS merge chỉ nhánh transport khi intent đó chưa đổi, giữ writer/usage/completion receipts đã được cập nhật trước ACK. Controller đợi `wait_child(..., require_settlement=True)`, không dùng outcome/idle làm đủ điều kiện thành công. Lỗi unresolved in state root và invocation/attempt/epoch để reconcile exact execution.

Completion có năm required hooks: `finalize`, `report`, `ledger`, `go_ledger`, `usage_state`. Chỉ sau authoritative quiescence mới snapshot/check/apply theo policy; failed/cancelled không apply. Patch conflict giữ patch/report, không overwrite source. Hook lưu in_progress/completed và sink proof theo execution/idempotency key; ledger recovery kiểm row đúng key, report kiểm metadata/hash, Go summary phải khớp dữ liệu ledger. Apply ACK mơ hồ không có proof giữ slot, không blind replay. Chỉ đủ required proofs mới release sang awaiting_review. Worktree luôn giữ theo Q6.

Backend quota/login fallback sang invocation managed mới chỉ sau worker cũ settled/released. DSH capacity patch nhỏ dùng đuôi order sau settlement; patch lớn tiếp tục cùng isolated patch/baseline gốc, bounded số continuation hiện có. Nếu continuation sau đó quota/login thì kết thúc nhánh giữ patch, không chuyển backend. Parser/ledger hiện có là nguồn token; ACP chỉ projection. Unknown usage giữ null/? và không suy quota từ token/USD.

Review/archive/follow-up yêu cầu latest exact epoch, shared lifecycle lock với gateway và durable terminal evidence; frontend không kiểm lại bằng numeric PID hay giả có Popen authority của daemon. Archive exact child, không workspace/parent. Follow-up cần review, giữ agent/workspace, brief/request key/epoch mới và baseline mới; không CLI context resume. API lifecycle hiện ở `PaseoController`, chưa có CLI review/archive/follow-up (không được giao thêm trong gói này).

Sol review vòng đầu phát hiện và giao sửa: cross-process quiescence, ACK/CAS và settlement races; current policy/binding validation; stale-epoch archive/epoch allocation; auto shell/order và DSH locked capacity; local limit/isolation validation và output IDs/report marker. Controller/completion/provider đều được cùng native backend sửa một lượt; review vòng hai đạt. Không phải chuyển backend hoặc dùng ngoại lệ tự code sau hand-ext lỗi.

## Setup provider: source và lệnh chính xác

Package source đã đọc: `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`, version 0.15.0. Production dùng Node >=22 và `PersistedConfigSchema.safeParse` của package đó; không nhân bản schema hoặc vendor code.

- `node_modules/@getpaseo/server/dist/server/server/persisted-config.js:294–305,317,333–335`: `agents.providers`, `<daemon-home>/config.json`.
- `node_modules/@getpaseo/server/dist/server/server/agent/provider-registry.js:484–539`: custom provider `extends: acp`, argv và GenericACPAgentClient.
- `node_modules/@getpaseo/protocol/dist/provider-config.js:41–96`: provider overrides/schema.
- `dist/commands/daemon/config.js:80–98`: official persisted config editing path.

Tên CLI đã chốt là **`hand-ext provider`**. Các lệnh dưới là recipe cho giai đoạn được cấp quyền live; **chưa chạy apply/status trên daemon thật**. `/ABS/PASEO_DAEMON_HOME` phải là home của đúng daemon chứa parent agent, không phải mặc định suy từ user HOME.

```sh
/Users/anhtp/app/claude-plugins-wt/hpa-p2/hybrid-hands/plugins/hybrid-hands/bin/hand-ext provider setup --home /ABS/PASEO_DAEMON_HOME --package-root /Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli --dry-run
/Users/anhtp/app/claude-plugins-wt/hpa-p2/hybrid-hands/plugins/hybrid-hands/bin/hand-ext provider setup --home /ABS/PASEO_DAEMON_HOME --package-root /Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli --apply
/Users/anhtp/app/claude-plugins-wt/hpa-p2/hybrid-hands/plugins/hybrid-hands/bin/hand-ext provider status --cwd /Users/anhtp/app/claude-plugins
```

Setup default dry-run ngay cả khi bỏ `--dry-run`. Bốn providers: `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`; mỗi entry có `extends: "acp"`, `command: [<plugin>/bin/hand-paseo-acp]`, `enabled: true`, label mặc định nếu thiếu. Dry-run chỉ in proposed_updates an toàn command/extends/enabled, không echo config/label/env/options đang có và không mkdir/backup. Apply giữ khóa khác, backup bytes gốc private 0600 trước atomic write, từ chối schema/config/package sai. Không tự reload daemon; reload/restart thuộc giai đoạn live riêng rồi `status` phải thấy providers trong catalog khả dụng. Config tồn tại không chứng minh daemon đã nạp.

## Cách bật pilot cho đúng một repo (chưa áp dụng)

Gộp các khóa này vào `ext_hand` hiện có của **chỉ repo pilot** khi Opus triển khai giai đoạn có quyền live; không thay các khóa khác. Đây là recipe, phiên này không sửa `.claude/hybrid-hands.json`.

```json
{
  "ext_hand": {
    "mode": "auto",
    "paseo": {
      "package_root": "/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli",
      "target": {"kind": "instance", "home": "/ABS/PASEO_DAEMON_HOME"}
    }
  }
}
```

`ext_hand.paseo.state_root` optional; mặc định `cfg.machine_state_dir/executions` (thường `~/.hybrid-hands/executions`, theo state-dir helper hiện có), phải ngoài isolated writer cwd. Config chỉ nhận `package_root`, `target`, `state_root`. Transport cũng hỗ trợ pinned endpoint/host. Managed đòi worktree; override CLI model/effort/sandbox phải khớp policy đã pin. Parent lấy `PASEO_AGENT_ID` của caller, canonical parent session qua resolver hiện có.

Override cho task managed/native intent mới, sau khi providers/capability/parent đã đủ:

```sh
/Users/anhtp/app/claude-plugins-wt/hpa-p2/hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --mode paseo-required --brief /ABS/self-contained-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply
```

`--mode shell` ép đường cũ; bỏ config/mode vẫn shell. G5 mới cập nhật policy/template để route native intent mới; gói này không đổi routing policy đang cài.

## Interface cho G4/G5

- `PaseoController(cfg, store, transport, *, supervisor=None, admission=None, completion=None)`: `preflight`, `dispatch`, `approve_review(key)`, `archive(key)`, `followup(key, brief)`, `continue_capacity(key, brief)`.
- `FreshPolicy(store)` callable và `.max_parallel(invocation)` đọc lại policy; `build_gateway(store, invocation_id)` chỉ trả gateway có worker khi controller/completion binding, prepared context, fixed options và policy hợp lệ. Env entry giữ `HYBRID_HANDS_EXECUTION_ROOT` / `HYBRID_HANDS_INVOCATION_ID`, hoặc flags `--state-root` / `--invocation-id`. Thiếu/sai binding deny, không worker.
- `CompletionService(store, supervisor, admission).bind(key, ctx, *, ledger_path, registry_dir, policy='no_apply', go_ledger=None, go_summary=None, go_monthly_limit=0, codex_ledger=None, quota_path=None, label='')`; `.attach(worker)`, `.reconcile(key)`, `.release(key)`. Binding trong `receipt.completion`, safe measurements trong `receipt.usage_observation`; không serialize auth/raw env/arbitrary backend errors.
- `PaseoTransport.wait_child(key, timeout_s, poll_interval=.1, *, require_settlement=False)` tương thích G1; controller dùng True. ACK mất dùng `transport.reconcile(key)` trên exact key/IDs; không re-run CLI để tạo invocation khác. Artifact ambiguity không chứng minh được tiếp tục giữ reservation.
- Mapping G4 authoritative: `ExecutionRecord.invocation` chứa parent canonical/scope/backend/account/model/effort; `Attempt` giữ target/project/workspace/agent IDs, run_id/request_key/epoch. `receipt.worker_run_dir` là base/hash execution key riêng mỗi epoch; artifacts.finalize.result.patch_path và artifacts.report.report/metadata/registry trỏ artifact thật. Follow-up run_id None được dùng hash key riêng, không đè epoch trước.
- Default runner dùng existing RunRegistry start/child/tick; final meta/registry/ledger có execution_key và idempotency_key. Token/usage source vẫn parser worker; không cộng ACP projection hoặc rollout lần hai. Một managed execution là một hand trong pool4, không tạo side-session root. G4 xử lý view/mapping/dedup, G5 xử lý routing/policy/operational commands; không hứa backend context resume.

## Kiểm chứng thật

Sol chạy từ worktree root:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_controller.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_completion.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_provider.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_parallel.py'
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_config_worktree.py'
```

Kết quả tương ứng **3 OK (4.067s), 3 OK (0.652s), 3 OK (0.025s), 3 OK (0.364s), 2 OK (0.267s)**. Controller bao gồm CLI managed success, quota tail, DSH capacity→quota không fallback, invalid limit/isolation trước mutation và ACK ambiguity. Completion có disposable Git worktree snapshot/apply thật với fake runner; provider apply chỉ dưới TemporaryDirectory.

Cuối giai đoạn, chạy đúng **một lần**:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_*.py'
```

**198 tests OK, 27.234s, exit 0**. Bao gồm hand-ext isolation/report/registry/capacity/CLI và hand_paseo; không chạy full suite repo. Sau aggregate chỉ sửa docs/bàn giao, không đổi code/test. Hands còn đã báo narrow execution3/transport3/gateway3/rundir4/capacity2 xanh; không dùng đó thay cho kết quả aggregate của Sol.

Sol chạy thêm:

- `claude plugin validate hybrid-hands/plugins/hybrid-hands`: **default Validation passed**; directory submission báo LICENSE_MISSING problem và ICON_MISSING warning, không claim directory pass.
- `node --check hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs`: pass.
- `git diff --check` và `git diff --cached --check`: pass; kiểm danh sách diff base→HEAD chỉ 18 file trong phạm vi.
- CLI `provider setup --help`, `provider status --help`, `run --help`: pass, xác nhận tên/flags thật, không gọi daemon.
- Dry-run bằng `setup_provider` với installed official 0.15.0 schema và **home giả chưa tồn tại**: PASS, bốn proposed providers, không tạo home/file; không đọc config daemon thật. Unit provider độc lập package cài máy bằng fixture và mock validator.
- Docs: hand kiểm 11 relative Markdown links hợp lệ; Sol review diff docs cuối. Không test prose.

## Delegation và dữ liệu

Ba native executor Sol-low (`fork_turns=none`, brief tự chứa, data rules nguyên văn) theo Ngoại lệ A; preflight `hand-ext pick --json` xác nhận codex/gpt-6.1-sol/low/gpt, skipped rỗng. Controller, completion và provider có ownership khác file; provider sau đó nhận riêng hai docs. Tối đa ba hand active, không thay slots/config, không side-session/recursion/hand review hand khác. Sol review toàn bộ kết quả và yêu cầu cùng backend sửa một lượt; không cần backend tiếp theo/hand-ext fallback, không có mã lỗi ngoại lệ tự code. Native không sinh run/report/token ledger hand-ext; usage/token/USD~/quota chưa đo = `?`.

Không đọc/hiện `.env`, auth/token/credential hay transcript/log thật. Tất cả dữ liệu test là code/fixtures công khai giả; chỉ đọc source package cài sẵn. Không gọi API trả phí hoặc tạo/dùng API key.

## Rủi ro còn lại và phần chưa kiểm chứng

1. Chưa chạy setup apply/status thật hoặc tạo/send/stop/archive/reopen bất kỳ daemon resource thật. Catalog reload/provider startup, placement/project/parent track, ACP prompt end-to-end và từng backend/account còn cần G7 có quyền/trần thời gian/chi phí riêng. Không quảng bá đã supported live chỉ từ fixtures.
2. Process-group authority vẫn giới hạn G1: descendant escape session/group chưa containment; mất retained Popen authority sau gateway restart thì conservative unresolved, không signal PID/PGID chỉ từ metadata. Outcome immutable đã settled dùng được để review; writer chưa settled không được suy dừng từ idle/mtime/PID mất.
3. Apply/hook crash sau side effect nhưng thiếu proof không có bảo đảm exactly-once có thể tự phục hồi; implementation giữ reservation và không replay mù. Cần reconcile exact sink hoặc quyết định vận hành tiếp theo, không tạo duplicate writer.
4. CLI claim `repo:*` là bảo thủ: cùng source repo không chạy đồng thời nhiều managed writer mặc dù pool chung cap4. Lifecycle review/archive/follow-up hiện qua Python API; G5 chưa bổ sung policy/template/UI automation.
5. License distribution và icon catalog vẫn là release gate cũ. Không bump version/CHANGELOG, install/update runtime hay kiểm loaded path/version ở repo khác do brief cấm giai đoạn này. Phiên/runtime đang mở chưa nhận code mới; release/install/reload thuộc giai đoạn sau.

## Trạng thái kết thúc

Commit `f73f09a`, nhánh `side/hpa-p2`, worktree sạch. Aggregate subprocess đã thoát 0; không có tiến trình nền do Sol tạo còn chạy. Các hand hoàn tất, giữ history, không archive parent. Ghi xong file này mới tạo `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/hpa-p2.done`.
