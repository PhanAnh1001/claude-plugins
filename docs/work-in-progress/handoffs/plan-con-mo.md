## Tóm tắt

- Kết quả: xong một phần; 4.6 và race PID đã đóng, 5.6 có bằng chứng và lý do còn mở.
- Việc 1 — 4.6 đã đóng: một lượt `hand-ext run --backend auto --isolation worktree` L0 chỉ đọc exit 0, worktree tạo/dọn thành công, patch rỗng.
- Việc 2 — 5.6 còn mở: `hh-ps --once` và statusline source + payload exit 0, đủ số liệu hand; provider Paseo `codex` vẫn Enabled/available; chưa xem bản cài/GUI/điện thoại.
- Lượt hand thật: backend `codex`, model `gpt-6.1-sol`, effort `low`; input 89543 (gồm cached_input 62464), output 264; quota tuần 14%, 5h `?`; USD~0.063044 (ước tính offline subscription, không phải hoá đơn).
- Việc 3 — race PID đã sửa: trước 26/30 pass, sau 30/30; regression fail trước/pass sau; ba module cc-switch 58 tests/24.872s OK exit 0, không full suite.
- File đổi: `lib/cc_switch/proc.py` recheck PID khi ps thiếu state; `tests/test_cc_switch_self.py` thêm đúng một regression với hai subtest; plan chỉ 4.6/5.6; bàn giao và artifacts `plan-con-mo/`.
- Changelog đề xuất: Fix cc-switch --self falsely reporting a reaped TUI PID as live when it exits between the liveness probe and ps.
- Code/test và tài liệu giao native `gpt-6.1-sol` low, `fork_turns=none`, đúng ngoại lệ A; Sol đã review diff code. Native token/quota/USD~ `?`, không dùng số của hand-ext cho native.
- Chưa kiểm: full suite (panel-gon làm cuối), bản cài, GUI/điện thoại, nguyên nhân config daemon/provider, Linux/PID reuse. Không cập nhật bản cài, commit/push.

## 1. Worktree và lượt hand thật

[Brief](../plan-con-mo/brief.md) giao ba việc; [brief L0 chỉ đọc](../plan-con-mo/read-only-brief.md) được dùng cho lệnh thực tế sau (exit 0):

```sh
HYBRID_HANDS_HAND_SCOPE=cf7e978c-0dd5-4d33-ac1b-5f68287e07b1 hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --brief /Users/anhtp/app/claude-plugins/docs/work-in-progress/plan-con-mo/read-only-brief.md --label plan-con-mo-readonly --cwd /Users/anhtp/app/claude-plugins --isolation worktree --timeout-min 10
```

L0 đọc README trả ba dòng, không ghi file. Run dir `output/llm/hand-ext/20261107-230817-631024-plan-con-mo-readonly-codex/`; worktree tạo/dọn thành công, `changes.patch` rỗng. Đây là bằng chứng tick 4.6 trong [plan](../../../hybrid-hands/docs/2026-11-07-ba-tang-opus-sol-dsh-plan.md). Xem [kết quả](../plan-con-mo/hand-ext-result.txt) và [metadata runtime](../plan-con-mo/hand-runtime.json).

Runtime: backend `codex`, model `gpt-6.1-sol`, effort `low`; input=89543, cached_input=62464 đã nằm trong input, output=264. USD~0.063044 tính offline theo [giá canonical](../../../hybrid-hands/plugins/hybrid-hands/config/model-prices.json), không phải hoá đơn. Quota account tuần=14%, 5h=`?` vì thiếu nguồn; không suy quota từ token/USD. Duration=16.011154890060425s, ended 07/11/2026 23:08:34 +07. Parent canonical `ca068dab-0484-4a0e-bfbb-ac32b74cb627` map runtime Paseo/thread thành side session đúng tên `plan-con-mo`; scope chỉ giới hạn đồng thời, không phải parent ID.

## 2. Hiển thị runtime và phần còn mở của 5.6

`hybrid-hands/plugins/hybrid-hands/bin/hh-ps --once --main-session ca068dab-0484-4a0e-bfbb-ac32b74cb627` exit 0. [Text](../plan-con-mo/hh-ps.txt) có dòng hand `codex gpt-6.1-sol/low 16s 2026-11-07 23:08 ~$0.06 GPT 5h ? · tuần 14.0% plan-con-mo-rea…`; [JSON](../plan-con-mo/hh-ps.json) có đúng `usage.usd=0.063044`. Không phát hiện lỗi `lib/hh_ps`, không sửa hh_ps hoặc test hh_ps.

Statusline chạy source bằng `bash statusline/plugins/statusline/scripts/statusline.sh`, payload JSON có session_id canonical và workspace cwd repo; `CLAUDE_HOME=docs/work-in-progress/plan-con-mo/statusline-runtime`, `STATUSLINE_GO_LIVE=0`, `STATUSLINE_WEEK_SPLIT=0`, `HYBRID_HANDS_HH_PS` trỏ bin/hh-ps source. Exit 0; [output](../plan-con-mo/statusline.txt):

```text
· ↳ hand-ext/codex plan-con-mo-readonly | model:gpt-6.1-sol | effort:low | ~$0.0630 | account:GPT | 5h:? | tuần:14% | ended:07/11 23:08:34 | elapsed:16s
GPT 5h:-- | 7d:14% | hôm nay ~$?
```

USD hôm nay `?` vì sổ ngày có lượt thiếu cost, không suy số. Đây là runtime source + payload; chưa xem thanh trạng thái thật bản cài, chưa cập nhật bản cài.

`paseo provider ls --json` exit 0 trả `codex` và `codex-hand` đều Enabled/available; xem [snapshot](../plan-con-mo/paseo-providers.json). `paseo provider models codex --json` exit 0 trả `gpt-6-luna`, `gpt-5.6-terra`, `gpt-5.6-luna`; `codex-hand` trả `gpt-6.1-sol`. Vì provider `codex` chưa disabled nên 5.6 giữ `[ ]`.

Ranh giới nguyên nhân: CLI cài sẵn `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/dist/commands/provider/ls.js:28` lấy daemon `getProvidersSnapshot`, dòng 35 lấy enabled từ `entry.enabled`; `models.js:28` gọi daemon `listProviderModels`. Đây là trạng thái runtime daemon/provider ngoài phạm vi, không phải renderer hh_ps; nguyên nhân gốc config/chưa reload chưa xác minh. Không mở `~/.paseo/config.json`, không kết luận đã đọc auth/home `~/.codex`, không tuyên bố lỗi code panel. Chuyển `panel-gon`/Opus kiểm daemon/provider config theo quyền riêng; không reload/restart daemon vì phiên khác đang chạy. Bản cài và GUI/điện thoại vẫn chưa kiểm.

## 3. Race PID cc-switch

[proc.py](../../../hybrid-hands/plugins/hybrid-hands/lib/cc_switch/proc.py):38–44 trước đây kiểm `pid_alive` true, rồi ps trả None khi process đã được reap nhưng fallback vẫn true. [sessions.py](../../../hybrid-hands/plugins/hybrid-hands/lib/cc_switch/sessions.py):40 lọc live qua helper; [paseo_cmd.py](../../../hybrid-hands/plugins/hybrid-hands/lib/cc_switch/paseo_cmd.py):138 vì vậy từ chối reload PID đã chết. Sửa tối thiểu: khi ps thiếu state, gọi `pid_alive` lại. [Test](../../../hybrid-hands/tests/test_cc_switch_self.py):208 thêm đúng một hàm regression với hai subtest missing/live PID; không sửa timing integration. Sol đã review diff và chấp nhận phạm vi này.

Test `test_cc_switch_self.CcSwitchSelfTest.test_worker_sigterms_tui_then_reloads_paseo`: trước sửa 30 lượt, 26 pass/4 fail (lượt 3, 7, 11, 25); regression deterministic fail trước sửa. Sau sửa regression pass và integration 30/30 pass. Lệnh tổng hẹp từ repo root:

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest test_cc_switch_self test_cc_switch test_cc_switch_term_self
```

Tương đương lệnh hand chạy với cwd `hybrid-hands/tests`: `python3 -m unittest test_cc_switch_self test_cc_switch test_cc_switch_term_self`; 58 tests/24.872s OK, exit 0. Không full suite, không chạy test ngoài cc-switch. Xem [báo cáo kỹ thuật](../plan-con-mo/pid-race-report.md) và [kết quả test](../plan-con-mo/pid-race-tests.txt). Chưa kiểm Linux/PID reuse; recheck không tạo snapshot process-table nguyên tử.

## Phạm vi bàn giao và kiểm chứng tài liệu

Các file của task: code/test PID nêu trên, plan (chỉ 4.6/5.6), bàn giao này và artifacts [plan-con-mo](../plan-con-mo/). Không coi toàn bộ dirty repo là thay đổi của task. [Baseline plan](../plan-con-mo/before/hybrid-hands/docs/2026-11-07-ba-tang-opus-sol-dsh-plan.md) dùng để kiểm chỉ hai mục đã đổi; header trạng thái cũ và các mục khác giữ nguyên theo phạm vi giao.

Hand tài liệu chỉ dùng dữ kiện Sol cung cấp và báo cáo kỹ thuật fixtures giả, không mở runtime evidence để xác minh lại. Kiểm diff và resolve đường dẫn liên kết nội bộ của hai file; không chạy unittest cho tài liệu. Code/test PID và tài liệu dùng native hand theo ngoại lệ A, không recursive, không có hand-ext report/ledger cho native; runtime không cấp usage thì token/quota/USD~ ghi `?`. Full suite và bản cài để `panel-gon` thực hiện cuối; Sol tạo `.done` sau khi đủ hand kết thúc và review xong, không commit/push.
