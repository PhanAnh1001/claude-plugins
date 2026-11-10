## Tóm tắt
- **Kết quả: xong**, phát hành hybrid-hands **0.36.1**; nhánh `side/ws-names` và `main` đã push tại `b7e2f92544ef993949cec405e111f4288ce2895d`.
- Agent/workspace phiên phụ dùng `<tên> · <loại> phụ`; managed hand dùng `<tên cha> › hand <backend> · <label>`, tối đa 60 ký tự.
- Đổi 22 file: side-session naming/CLI/state, managed naming/transport/recovery, hai nhóm fixtures/test, README/3 skill/changelog/manifest; lý do từng file ở bảng dưới.
- Sol đã review mọi hand và chạy lại **41 test hẹp xanh**; full suite chạy **đúng một lần: 526 test xanh, 87,704 giây**.
- Manifest/marketplace validate mặc định thành công; JSON, link tài liệu mới, `git diff --check`, Node syntax checks đều đạt.
- Cập nhật chính thức cả `~/.claude` và `~/.claude-hand`; plugin list tại claude-plugins và live-tiktok-games đều version/folderVersion **0.36.1**, nạp từ source main.
- Live: cả agent/workspace `ws-names · Sol phụ`; hand smoke có tên `ws-names › hand codex · ws-names-smoke`, đúng parent canonical.
- Scratch một dòng, `--no-apply`, đã review-approve; child/workspace smoke archived, reservation null, quiescence confirmed; giữ toàn bộ artifacts/worktree.
- Còn lại: không còn việc code; phiên Claude đang mở cần reload để nhận skill mới. Không restart/reload daemon. Chưa smoke live các provider Claude/dsh hoặc followup; các nhánh đó được kiểm offline.

## Release và cài đặt

- Base: `main` 0.36.0, `4e38c39dcc1138d2292de19523d33accde19e547`; worktree `/Users/anhtp/app/claude-plugins-wt/ws-names`.
- Commit `b7e2f92 feat(hybrid-hands): release 0.36.1 with readable Paseo names`; đã push `origin/side/ws-names`, merge fast-forward bằng `git -C /Users/anhtp/app/claude-plugins merge --ff-only side/ws-names`, rồi push `origin/main`.
- Kiểm cuối: `main`, `origin/main`, `side/ws-names` đều trỏ cùng SHA trên. Không có tracked diff còn lại; giữ nguyên mọi untracked của người khác.
- Đã chạy `CLAUDE_CONFIG_DIR=/Users/anhtp/.claude claude plugin update hybrid-hands@hybrid-hands-local --scope user` và tương tự `/Users/anhtp/.claude-hand`: cả hai báo cập nhật 0.36.0 → 0.36.1.
- `claude plugin list --json` trong cả `/Users/anhtp/app/claude-plugins` và `/Users/anhtp/app/live-tiktok-games`, với cả hai account, đều `enabled=true`, `scope=user`, `version=folderVersion=0.36.1`.
- Install paths: `/Users/anhtp/.claude/plugins/cache/hybrid-hands-local/hybrid-hands/0.36.1` và `/Users/anhtp/.claude-hand/plugins/cache/hybrid-hands-local/hybrid-hands/0.36.1`.
- Cả bốn kiểm tra báo `readFromFolder=/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`. Python CLI mới nhận code trên source này ngay khi chạy mới; các phiên Claude đang mở cần reload để nhận nội dung skill/hook đã nạp. Không tự reload daemon hay phiên chính.

## File đã đổi và lý do

Các đường dẫn dưới thuộc repo; tiền tố `P` = `hybrid-hands/plugins/hybrid-hands`.

| File | Lý do |
| --- | --- |
| `hybrid-hands/README.md` | Hướng dẫn quy ước tên và hai CLI names dry-run/apply. |
| `P/.claude-plugin/plugin.json` | Tăng version 0.36.1. |
| `P/CHANGELOG.md` | Ghi release naming ngày 09/11/2026. |
| `P/lib/side_session/names.py` | Format tên, guard state, retry tối đa 3 lần và manual names. |
| `P/lib/side_session/paseo_names.mjs` | Public rename và membership guard cho agent/workspace riêng. |
| `P/lib/side_session/paseo_bridge.mjs` | Nhánh request names riêng khỏi lifecycle. |
| `P/lib/side_session/paseo.py` | Title khi create và best-effort workspace/agent naming sau start. |
| `P/lib/side_session/actions.py` | Naming khi send/revive, retry ls/watch, route tidy --names. |
| `P/lib/side_session/cli.py` | Cờ tidy --names, giữ tidy archive cũ. |
| `P/lib/side_session/state.py` | Default trạng thái số lần thử và naming done, tương thích state cũ. |
| `P/lib/hand_ext/paseo_names.py` | Parent canonical, format hand, provenance qua epoch, retry bounded. |
| `P/lib/hand_ext/paseo_bridge.mjs` | Create title/public rename; exact child, main/shared/membership guard. |
| `P/lib/hand_ext/paseo_transport.py` | Đưa title vào create, naming trước send và khi reconcile/wait. |
| `P/lib/hand_ext/cli.py` | managed names dry-run/apply và naming warning không chặn ls. |
| `P/lib/hand_ext/paseo_recovery.py` | Cho metadata naming vào receipt whitelist; không coi nó là worker-start evidence. |
| `P/skills/side-session/SKILL.md` | Đồng bộ tên phiên phụ và lệnh bảo trì tên. |
| `P/skills/ext-hand/SKILL.md` | Đồng bộ tên hand theo cha và manual managed names. |
| `P/skills/paseo/SKILL.md` | Đồng bộ public API và ownership/lifecycle naming. |
| `hybrid-hands/tests/test_side_session_names.py` | Ba nhóm format, bounded retry và dry-run/ownership/error quan trọng. |
| `hybrid-hands/tests/test_side_session_paseo.py` | Mock naming cho fixture lifecycle cũ và kiểm title create. |
| `hybrid-hands/tests/test_hand_paseo_names.py` | Ba nhóm tên cha/backend/60 ký tự, retry, dry-run/shared guard. |
| `hybrid-hands/tests/fixtures/hand_paseo/transport/run.mjs` | Fake public rename API và phản hồi không xác nhận, không dữ liệu thật. |

Không sửa hh-ps hoặc panel: kiểm source thấy `hh_ps/tree.py` dùng side state name, `hh_ps/paseo_source.py` dùng registry/completion label; panel `server/agent-record.ts` chỉ đọc cwd/session IDs. Chúng không hiện title Paseo trực tiếp, nên không cần đổi projection hoặc cấu trúc cây cho yêu cầu có điều kiện này.

## Public API Paseo 0.15.0 đã đối chiếu

Source cài tại `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`, package version 0.15.0:

- `dist/commands/agent/update.js`: `--name` thành `{name}`, gọi `client.updateAgent(agentId, updates)`; title đọc lại ở `agent.title`.
- `dist/commands/workspace/rename.js`: gọi `client.setWorkspaceTitle(workspaceId, title)`, trả `{title}`.
- `node_modules/@getpaseo/client/dist/daemon-client.js`: xác nhận các method trên và `createAgent` title/config.
- `node_modules/@getpaseo/protocol/dist/messages.js`: public create config nhận `title`; workspace title dùng public title-set request.

Không đưa rename method vào required capabilities: thiếu API/lỗi rename chỉ safe warning, giữ dispatch/send/done. Agent và workspace xác minh riêng; shared workspace luôn giữ title dù có nhiều member đều do plugin tạo. Không nhóm ownership theo cwd. Cha hand lấy side state canonical, main state role main → `chính`, thiếu/ambiguous → `?`.

## Giao hand và review

`hand-ext.max_parallel=4`; pick effective là `codex / gpt-6.1-sol / low / gpt`, native eligible nhưng brief yêu cầu shell/managed nên không spawn native. Code/test/docs được giao qua `hand-ext run --backend auto --mode shell --cwd <worktree> --keep-worktree`; ba phần khác file chạy song song. Không có hand-ext exit lỗi, không dùng ngoại lệ Sol tự code/test/docs. Các brief chứa nguyên văn luật dữ liệu và giới hạn chỉ đọc worktree, không ps/pgrep/phiên khác.

| Run | Review/kết quả |
| --- | --- |
| `20261109-213136-950855-ws-names-side-codex` | Side code, 3 test mới + 15 lifecycle test xanh; Sol review chấp nhận. |
| `20261109-213138-189773-ws-names-managed-codex` | Managed code; review yêu cầu chặn shared kể cả sibling known, xác nhận public rename, hiện warning và bảo vệ offline ls. |
| `20261109-213139-756511-ws-names-docs-codex` | Docs/manifest; review bắt lỗi ví dụ hand thừa hậu tố loại của cha. |
| `20261109-213338-380693-ws-names-docs-correction-codex` | Cùng backend một lần: sửa 4 ví dụ; review chấp nhận. |
| `20261109-213620-946391-ws-names-managed-correction-codex` | Cùng backend một lần: sửa các guard/confirmation/warning; controller regression whitelist naming đã sửa, Sol chạy lại toàn bộ nhóm hẹp xanh. |

Report các run trên nằm trong `<worktree>/output/llm/hand-ext/<run>/report.md`; worktrees cách ly giữ nguyên. Không giao hand review hand khác, không có recursion hoặc phiên side mới.

## Kiểm chứng thật

Sol chạy:

- `python3 -m unittest discover -s hybrid-hands/tests -p test_side_session_names.py -v`: 3 passed.
- Cùng discovery với `test_side_session_paseo.py -q`: 15 passed.
- Cùng discovery với `test_hand_paseo_names.py -q`: 3 passed; `test_hand_paseo_transport.py`: 7; `test_hand_paseo_cli.py`: 4; `test_hand_paseo_controller.py`: 9. Tổng 41 test hẹp passed.
- **Full suite một lần duy nhất**: `python3 -m unittest discover -s hybrid-hands/tests -q`: **526 tests, 87.704s, OK**, exit 0. Log `/Users/anhtp/app/claude-plugins-wt/ws-names/docs/work-in-progress/ws-names/full-suite.log`.
- `node --check` cho side_session/paseo_bridge.mjs, side_session/paseo_names.mjs và hand_ext/paseo_bridge.mjs: exit 0.
- `git diff --check`, staged diff check: exit 0; JSON manifest/version và link mới/chỉnh trong tài liệu: pass.
- `claude plugin validate <worktree>/hybrid-hands` và `<worktree>/hybrid-hands/plugins/hybrid-hands`; lặp validate hai đường dẫn source main sau merge: mặc định pass, exit 0. Validator có advisory có sẵn của profile directory về thiếu LICENSE/icon; không phải lỗi manifest và không mở rộng phạm vi để sửa license.

Không chạy lại full suite sau khi nó xanh; các bước sau chỉ cập nhật runtime và smoke, không đổi code.

## Smoke live và tidy

### Phiên phụ đang hiện

Dùng CLI mới từ worktree, cwd main:

`side-session tidy --names --name ws-names` → exit 0, `agentEligible=True`, `workspaceEligible=True`, title `ws-names · Sol phụ`. Kiểm public agent sau dry-run vẫn `ws-names`, workspace vẫn `main`.

Thêm `--apply` → exit 0; public agent `9695f133-c160-4c6e-a247-7d09d0cddd73` và workspace `wks_ce4e64ef8219edbd` cùng title `ws-names · Sol phụ`. Lặp dry-run rồi apply bằng CLI source main sau release cũng exit 0, tên không đổi.

Snapshot public archive metadata trước apply cho thấy chỉ hai side state đang hiện: main `opus-v2-pilot` và phiên này `ws-names`; mọi side khác đã archived. Main agent `711ef386-2673-4c8b-8b1a-f24f1e56805e` giữ `opus-v2-pilot`; workspace main `wks_4c1edcdaa18b41e7` giữ `opus v2 plugin`. Không đổi tên/archive main, workspace chung hay agent tiktok.

`hand-ext managed names --cwd /Users/anhtp/app/claude-plugins` dry-run: 13 record cũ, 0 workspace eligible; mã chặn `NAME_OWNERSHIP_UNKNOWN`/`PROJECT_UNVERIFIED`. Apply sau smoke: 14 record, 0 workspace eligible vì child smoke đã autoarchived; thêm `NAME_WORKSPACE_BLOCKED`. Không restore/create/archive hay nới guard để đổi tên record đã ẩn. Artifacts `live-managed-dry.json`/`live-managed-apply.json` giữ kết quả safe JSON.

### Managed hand từ chính phiên này

Preflight lại chọn codex low. Đã chạy:

`hand-ext run --backend auto --mode paseo-required --no-apply --keep-worktree --cwd /Users/anhtp/app/claude-plugins --brief /Users/anhtp/app/claude-plugins-wt/ws-names/docs/work-in-progress/ws-names/smoke-brief.md --label ws-names-smoke --timeout-min 5`

- Key `ff9337da-46ff-4b34-9b72-963bab9c51ff:56508070-262b-4bf8-b236-51ddedb08807:1`, backend codex, model gpt-6.1-sol low.
- Parent canonical `2193a02e-88da-47a5-ae11-b149a1cca346` và parent Paseo `9695f133-c160-4c6e-a247-7d09d0cddd73`.
- Child `d0c4a8df-6d7d-438e-962a-d6ef5453574e`, workspace `wks_90abf11efd5a4839`.
- Trong lúc running, public `paseo agent inspect` và `paseo workspace ls` cùng xác nhận **`ws-names › hand codex · ws-names-smoke`**. Naming receipt: attempts=1, done=true, warning=null.
- Report và patch đã đọc/review: đúng một file mới `ws-names-smoke.txt`, đúng một dòng `ws-names managed naming smoke`; policy `no_apply`, file không tồn tại ở repo nguồn.
- Wrapper exit 0, outcome ok; state archived, reservation null; quiescence confirmed, evidence `root_group+tracked_tree+env_marker`. Public child closed/archived; workspace vắng khỏi active directory.
- Sau review đã chạy `managed review-approve --cwd ... --key ...` rồi `managed archive --cwd ... --key ...`: cả hai exit 0, archived, review_approved=true; archive lặp an toàn.
- Report `/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261109-214238-364765-ws-names-smoke-codex/de3a6433ef5c9077cbc827cfa8c7ebff4deac679e7e323b80e46b20968d31ff2/report.md`.
- Giữ worktree `/Users/anhtp/.hybrid-hands/worktrees/claude-plugins-20261109-214238-364765-ws-names-smoke-codex` và mọi output/patch/report; không cleanup.

Bằng chứng metadata live nằm ở `/Users/anhtp/app/claude-plugins-wt/ws-names/docs/work-in-progress/ws-names/{live-side-names.json,live-smoke-running.json,live-final.json}`. Xác minh bằng public metadata/CLI, không claim đã chụp hoặc quan sát trực tiếp UI sidebar.

## Giới hạn và bàn giao

- Không sửa config/order/slots/settings/credential/installed_plugins.json thủ công, không restart daemon, không mở side-session hoặc bật parallel-subagents. Chỉ subscription, không gọi API trả phí hay tạo/dùng API key.
- Các subprocess hand-ext/tests/smoke do phiên này tạo đều đã thoát; managed smoke đã quiescent và archived. Watchdog của phiên này do phiên cha mở giữ nguyên để nhận `.done` theo lifecycle đã duyệt.
- Không đụng statusline, cấu trúc hh-ps/panel, thư mục output/llm hoặc worktree của người khác. Không dọn bất kỳ worktree nào.
- Chưa live tạo phiên Claude/dsh hay managed followup; formatter/transport/lifecycle tương ứng được kiểm offline. Legacy thiếu ownership/current parent giữ unknown/block thay vì đoán.
- File `.done` được tạo sau khi ghi xong bàn giao này, là tín hiệu hoàn tất để side-session tự archive exact child/workspace riêng theo contract.
