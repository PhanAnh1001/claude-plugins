## Tóm tắt
- Kết quả: **xong**, đã release **0.36.0**, merge/push `main` commit `4e38c39dcc1138d2292de19523d33accde19e547`.
- Side-session: done archive agent+workspace riêng (kể cả local); `send` restore exact IDs; `tidy` dry-run mặc định, có ownership guard.
- Managed: tích hợp `c1c99f3` + correction `6bc9faa`; settle đủ hooks tự archive, followup review rồi restore cùng child/workspace, epoch mới.
- Main Claude: config compact mặc định 272000 cho phiên main MỚI mọi account, Paseo/screen; side/hand không nhận override.
- File đổi: side_session/* — lifecycle/env; hand_ext/paseo_* — managed; shared_config/backend Claude — validation/env; tests — fixtures; docs/skills/templates/AGENTS/version — contract 0.36.0.
- Kiểm chứng: full tích hợp **520 test xanh** một lần; correction managed **40 test xanh**; node checks + validate mặc định đạt.
- Smoke live side và managed: archive → restore cùng IDs → done/archive lần hai, thư mục còn; managed epoch 2, đủ 5 hooks, không reservation.
- Official update v1/v2 đạt; plugin list tại claude-plugins/live-tiktok-games cả hai account xác nhận **0.36.0**, đúng source/cache path.
- Các lệnh hand/smoke frontend đã thoát; watcher smoke không còn; không restart daemon, không dọn worktree/output hay sửa config/settings thủ công.
- Cần Opus lưu ý: Claude đang mở cần reload phiên; compact chỉ có hiệu lực khi mở main MỚI; watcher khởi chạy trước upgrade giữ code cũ (chi tiết cuối).

## Quyết định và tiêu chí chấp nhận

1. Side-session: mọi provider Paseo thấy marker done thì đóng/archive exact agent, archive workspace thuộc plugin khi mọi thành viên cùng workspaceId đã archived; bảo vệ main và thành viên lạ. Giao lại bằng `side-session send --name NAME --prompt-file FILE`, không tạo agent mới.
2. Managed: sau quiescent/report/5 hooks/release tự archive child+workspace, review không còn là điều kiện archive; followup vẫn cần review đúng epoch, restore trước tạo epoch mới. hh-ps/panel giữ outcome/usage semantics.
3. Lỗi và giữ dữ liệu: archive workspace lỗi không mất done/outcome; restore lỗi không tạo epoch/writer mới; send mơ hồ giữ pending, retry hữu hạn. Chỉ recovery action unarchive được nhận, không recreate cwd mất. Thư mục/artifact/history giữ nguyên.

Membership lấy public agent.workspaceId, tuyệt đối không lấy cwd. Side local riêng được archive dù trùng cwd checkout với workspace khác. Side chỉ nhận owner states cùng target/workspace, chặn main/unknown/active/pending. Managed workspace luôn riêng nên gate bảo thủ chỉ nhận exact child; mọi sibling, kể cả archived hay có label plugin, đều chặn archiveWorkspace. Không đụng parent workspace.

`tidy [--name NAME] [--apply]` mặc định dry-run, chỉ xét workspace có owner state plugin; empty workspace cần owners terminal và không pending. Không suy ownership từ cwd, không dọn workspace tùy ý. Marker done cũ được rename UUID giữ lịch sử, không xoá handoff; definite pre-send failure phục hồi marker không ghi đè lịch sử, ambiguous ACK giữ fence.

Main Claude config nhận số nguyên 100000..1000000, default 272000; null hoặc exact "auto" không đặt env. Giá trị khác báo lỗi kèm file nguồn/key. Launch main mới qua screen/Paseo set env CLAUDE_CODE_AUTO_COMPACT_WINDOW; main đã lưu applied window thì ls hiện window đó + `(tự nén)`. Main cũ không có applied window giữ hiển thị cũ để không nhận sai rằng env đã áp dụng. Không sửa settings của bất kỳ account nào.

## File đã đổi

Đường dẫn tương đối root repo; danh sách tính từ main 0.35.6 (`055336a`) tới release.

| File | Lý do |
| --- | --- |
| `AGENTS.md` | Thay Q4: done tự archive; workspaceId ownership và followup review gate. |
| `hybrid-hands/README.md` | Hướng dẫn archive/send/tidy, managed lifecycle và main Claude compact. |
| `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` | Tăng minor version 0.36.0. |
| `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` | Ghi thay đổi release 0.36.0 và tương thích main cũ. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/claude.py` | Lọc env compact kế thừa khỏi hand Claude. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs` | Archive child+workspace, membership exact ID fail closed và restore trước refresh. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_completion.py` | Worker archive sau settlement; khóa ACK, timeout và retry hữu hạn. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_controller.py` | Auto archive trước review, review vẫn chặn followup; restore trước epoch mới. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_transport.py` | Durable lifecycle receipts, settlement authority và reconcile ACK loss. |
| `hybrid-hands/plugins/hybrid-hands/lib/shared_config.py` | Default/validation/provenance main Claude compact window. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py` | Done cleanup, retry workspace, official send và tidy idempotent. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/cli.py` | CLI send và tidy dry-run mặc định. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/commands.py` | Env compact chỉ main Claude qua screen; lọc ambient cho side. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/constants.py` | Tên env compact canonical. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py` | Public bridge payload ownership và main-only compact env. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs` | Public archive/recovery/send, workspaceId membership, bảo vệ main/unknown và ACK. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/state.py` | Lưu pending send và compact window thực sự áp dụng. |
| `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md` | Contract managed auto archive và followup review/restore. |
| `hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md` | Policy archive workspace riêng local/worktree và lifecycle public API. |
| `hybrid-hands/plugins/hybrid-hands/skills/side-session/SKILL.md` | Cách send/tidy, ownership guard và main compact. |
| `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt-claude.md` | Prompt giao phiên cập nhật done/archive/reassign và bảo vệ workspace. |
| `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt-codex.md` | Prompt giao phiên cập nhật done/archive/reassign và bảo vệ workspace. |
| `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt.md` | Prompt giao phiên cập nhật done/archive/reassign và bảo vệ workspace. |
| `hybrid-hands/tests/fixtures/hand_paseo/transport/run.mjs` | Fake public API archive/restore/membership và ACK loss, không daemon thật. |
| `hybrid-hands/tests/test_hand_ext_claude.py` | Kiểm cấu hình/argv/env compact và tương thích mặc định. |
| `hybrid-hands/tests/test_hand_paseo_cli.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_hand_paseo_completion.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_hand_paseo_controller.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_hand_paseo_integration.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_hand_paseo_transport.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_shared_config.py` | Kiểm cấu hình/argv/env compact và tương thích mặc định. |
| `hybrid-hands/tests/test_side_session.py` | Kiểm cấu hình/argv/env compact và tương thích mặc định. |
| `hybrid-hands/tests/test_side_session_config_b.py` | Kiểm cấu hình/argv/env compact và tương thích mặc định. |
| `hybrid-hands/tests/test_side_session_native.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |
| `hybrid-hands/tests/test_side_session_paseo.py` | Kiểm chứng fixture lifecycle/ownership/followup và lỗi thật quan trọng. |

## Giao hand, review và tích hợp

- Code/test/docs đã giao shell hand-ext theo pick/order và backend auto; Sol review diff/report, không dùng native/subagent và không bật parallel-subagents. Brief hand có luật dữ liệu nguyên văn, chỉ đọc worktree được giao và không liệt kê process/phiên khác.
- Phần side public send ACK ban đầu cần correction: Codex + một lượt sửa chưa đủ; chuyển backend tiếp theo claude-v1 qua wrapper, review/test lại đạt. Không tự viết implementation theo ngoại lệ lỗi hand.
- Khi Opus tách lane managed, patch của hand managed cũ do tôi giao đã được reverse đúng phần do nó tạo. Chỉ tích hợp nhánh peer side/ws-archive-hand.
- Review peer `c1c99f3` phát hiện archived sibling vô danh được archive workspace trái hợp đồng mới; trả correction cho peer. `6bc9faa` bổ sung gate exact child + fixture chặn unknown/main-shaped/plugin-labelled sibling cả archive và reconcile; Sol review đạt. Không sửa đồng thời file lane peer.
- Handoff peer: [ws-archive-hand.md](ws-archive-hand.md), gồm lịch sử hand, 40 test hẹp và full 515 test của lane peer. Lead không claim full 515 đó là full tích hợp.
- Nhánh side/ws-archive đã push (`2c639f4`); merge main mới nhất 055336a trước khi tích hợp/release; main release `4e38c39` đã push, HEAD và origin/main khớp. Tracked working tree main sạch. WIP/brief/report/patch/worktree giữ nguyên.

## Kiểm chứng offline thật

| Lệnh | Kết quả |
| --- | --- |
| python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py' | 109 xanh / 14.772s |
| PYTHONPATH=hybrid-hands/tests python3 -m unittest test_shared_config test_hand_ext_claude | 21 xanh / 1.809s |
| python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py' -q | **520 xanh / 80.305s**, full tích hợp chạy một lần |
| python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py' -q | **40 xanh / 15.934s**, sau correction membership cuối |
| node --check lib/side_session/paseo_bridge.mjs và lib/hand_ext/paseo_bridge.mjs | đạt |
| claude plugin validate hybrid-hands/plugins/hybrid-hands --json | success true, manifest errors/warnings rỗng |
| git diff --check; manifest JSON; link tương đối docs đã đổi | đạt; version 0.36.0; 14 link/9 Markdown tồn tại |

Full suite đã chạy trước correction cuối chỉ đổi managed bridge gate + fixture; sau correction chạy lại nhóm 40 managed, không lặp full. Evidence ở worktree lead docs/work-in-progress/ws-archive-integrated-full-qa.txt, ws-archive-integrated-managed-qa.txt, ws-archive-final-side-qa.txt, ws-archive-final-config-qa.txt, ws-archive-release-validate.json. Fixture không gọi daemon thật. Không chạy suite statusline ngoài phạm vi. Validate profile mặc định đạt; directory submission profile vẫn có LICENSE_MISSING và ICON_MISSING vốn có, không claim profile directory đạt.

## Release và runtime update

- `claude plugin update hybrid-hands@hybrid-hands-local --scope user --json` với CLAUDE_CONFIG_DIR=/Users/anhtp/.claude và /Users/anhtp/.claude-hand: cả hai updated 0.35.6 → 0.36.0.
- `claude plugin list --json` chạy đủ 4 tổ hợp account v1/v2 × repo claude-plugins/live-tiktok-games: version và folderVersion đều 0.36.0, enabled true, readFromFolder `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`.
- Cache path v1: `/Users/anhtp/.claude/plugins/cache/hybrid-hands-local/hybrid-hands/0.36.0`; v2 tương tự dưới `/Users/anhtp/.claude-hand/plugins/cache/.../0.36.0`.
- Không tự bật plugin tại repo khác, không sửa sổ cài đặt/config/settings/credential thủ công, không restart/reload Paseo daemon. CLI update báo Claude phiên đang mở cần restart/reload phiên để nhận hooks/skills mới.

## Smoke live sau release

Chỉ dùng resource mới của ws-archive; metadata kiểm qua pinned public client @getpaseo/cli 0.15.0, không đọc transcript/log thật. Helper read-only allowlist/timeout ở worktree lead `docs/work-in-progress/ws-archive-live-probe.mjs`.

### Side-session ws-archive-smoke

- Agent `a2250df2-46a3-4805-8c5f-9b41712f6eca`, workspace `wks_4c5ca3685d5375c4`, worktree `/Users/anhtp/app/claude-plugins-wt/ws-archive-smoke`, provider codex-hand.
- Start từ main release bằng side-session start --worktree, task chỉ ghi một dòng handoff + marker done. Lần đầu state done/workspaceArchived true; agent closed/archived true; workspace mất khỏi active directory, recovery recoverable/action unarchive; cwdExists true.
- Official side-session send cùng tên bằng prompt mới, chờ hữu hạn 20s trong task: cả hai ID giữ nguyên, agent archived false, workspace hiện lại active, cwdExists true. Marker cũ rename giữ 1 history, không tạo agent mới.
- Lần hai handoff đúng `ws-archive smoke followup pass`; state done, pending false, workspaceArchived true; agent+workspace lại archived, cwdExists true.
- Exact `tidy --name ws-archive-smoke` dry-run và --apply trên workspace đã archived đều idempotent. Không chạy tidy/ls rộng lên resource của phiên khác.
- Watcher smoke đã tự thoát; exact screen quit trả No screen session found. Lượt query -Q trước đó không hỗ trợ ở screen 4.00.03, đã thay bằng exact quit, không liệt kê session/process.

### Managed smoke

- Invocation `2f383796-2b3b-4d18-a949-6b706cf66c2b`; epoch 1 attempt `22ecefb7-144e-45b5-a847-b5d0687b2c5c`; epoch 2 attempt `f140bc01-bf0c-4f14-a30d-072e142e525f`.
- Exact child `c5afe44c-6e84-4027-a9ee-5920dda7800c`, workspace `wks_6c4b3dde7752474e`; provider hh-hand-codex gpt-6.1-sol low; parent exact ws-archive agent, project đã xác minh.
- Worktree `/Users/anhtp/.hybrid-hands/worktrees/claude-plugins-20261109-211144-960854-ws-archive-managed-smoke-codex`.
- Pick rồi run backend auto mode paseo-required --no-apply --keep-worktree, timeout 5 phút. Task chỉ ghi một file smoke công khai trong worktree cô lập. Exit 0; đủ năm hook; outcome ok, reservation none; child+workspace archived **trước** review approval.
- Sol đọc report+patch (chỉ một dòng), review-approve epoch1 rồi official managed followup bằng brief tự chứa, sleep20 hữu hạn. Quan sát public exact child/workspace cùng ID đều unarchived/active, cwdExists true, epoch2 mới đang running.
- Epoch2 exit0, đủ năm hook, outcome ok, reservation none, lifecycle_error none; child+workspace lại archived, cwdExists true. Sol đọc report+patch thay dòng epoch1→epoch2, review-approve epoch2. Exact managed archive lặp lại trả archived thành công.
- Reports/patch giữ dưới output/llm/hand-ext/20261109-211144-960854-ws-archive-managed-smoke-codex/{a7d6f16f7597b5ebdb626abc5181029aa208bfce40816634292677d8d25f56e2,9a61f8d438c1c89cde2e19dcd7501e70f10324ee746ce62295ef9909a985bac6}/. Không apply patch về main.

Hai agent smoke cuối cùng closed/archived, hai workspace archived và thư mục còn; không còn frontend tool session hay watcher smoke chạy. Không archive/stop parent, tiktok, main hoặc workspace khác.

## Điểm Opus cần lưu ý

- Không còn phần code/release/smoke bị chặn. Live private LOCAL archive và lỗi archive/restore được kiểm bằng fixture; live smoke chỉ dùng worktree riêng như brief, không thao tác lỗi có chủ đích trên daemon thật.
- Main Claude hiện tại không nhận env mới hồi tố: mở main MỚI bằng side-session start --main --provider claude --account v2 (hoặc account khác) để compact 272000 có hiệu lực. Không tự dừng/đổi main đang chạy.
- Watcher của chính phiên ws-archive được khởi chạy trước upgrade, giữ Python cũ; bridge file mới được đọc động nhưng watcher cũ có thể chỉ archive agent và ghi cờ workspaceArchived cũ. Sau khi nhận `.done`, nếu workspace LOCAL của phiên này vẫn hiện, Opus chạy exact lệnh bản 0.36.0 `side-session tidy --name ws-archive --apply` từ root. Lệnh tự kiểm ownership/workspaceId/main/unknown, không dùng cwd để dọn. Tôi không thay watcher đang giữ lifecycle của phiên này hay tạo thêm background cleaner trước bàn giao.
- Workspace own ws-archive đã xác minh trước smoke: agent fd39b959-86ff-429e-a04f-4784a1ab6801, workspace wks_e86576f56f84abd0, local_checkout, cwd root; đây là side riêng, không phải main. Không đụng workspace được cấm wks_95567480628a52bc.
