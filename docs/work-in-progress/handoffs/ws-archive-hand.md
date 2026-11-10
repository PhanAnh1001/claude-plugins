## Tóm tắt
- Kết quả: **xong**, đã Sol review code và kiểm chứng offline.
- Commit đầu: `c1c99f3`; correction ownership: `6bc9faa5cac8fb3d88649b2103154af98830d996`, đã push `origin/side/ws-archive-hand`.
- Base: `055336a` (0.35.6); worktree `/Users/anhtp/app/claude-plugins-wt/ws-archive-hand`, sạch sau commit.
- Bridge/transport: archive exact child + workspace sau settlement; restore workspace trước reopen child, retry có receipt.
- Controller/completion: không cần review để archive; followup vẫn cần review đúng epoch, restore lỗi giữ key cũ.
- Tests/fixture: cập nhật offline lifecycle, ACK loss, membership, callback/followup và CLI/hh-ps integration.
- Kiểm chứng sau correction: **40 test managed xanh**; full hybrid-hands **515 test xanh trước correction**, không chạy full lại.
- `node --check` bridge và fixture; `git diff --cached --check`: đạt.
- Còn lại cho `ws-archive`: tích hợp commit, docs/release 0.36.0, runtime update và smoke live sau merge.
- Không merge main, bump version, update plugin, reload daemon hay archive/stop agent/workspace thật trong gói này.

## File đã đổi

Tất cả đường dẫn dưới đây tương đối với root repo trong nhánh `side/ws-archive-hand`.

| File | Lý do |
| --- | --- |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs` | Archive child rồi workspace; kiểm membership phân trang bằng workspaceId; restore/unarchive rồi xác minh binding và reopen exact child; reconcile ACK loss. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_transport.py` | Project settled/review đúng epoch; pin lifecycle metadata cho cả workspace dùng lại; giữ pending fences, reconcile trước retry; tương thích key tuple. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_controller.py` | Auto-archive khi dispatch đã settle; review chấp nhận archived; archive tường minh báo unresolved khi chưa xác nhận; restore trước tạo epoch; DSH capacity continuation mở lại đúng child. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_completion.py` | Sau release, lên lịch worker archive độc lập, chờ khóa worker/send; giới hạn retry/timeout, giữ settlement/outcome khi scheduling/archive lỗi. |
| `hybrid-hands/tests/fixtures/hand_paseo/transport/run.mjs` | Fake API archive/restore, membership phân trang và mất ACK. |
| `hybrid-hands/tests/test_hand_paseo_transport.py` | Kiểm archive/restore đúng ID và thứ tự, active/archived sibling, pagination lỗi, ACK loss, giữ sentinel directory. |
| `hybrid-hands/tests/test_hand_paseo_controller.py` | Kiểm review gate, settlement gate, retry không tạo epoch sớm, callback epoch followup, DSH và archive lỗi trên record đã archived. |
| `hybrid-hands/tests/test_hand_paseo_completion.py` | Kiểm callback chỉ archive sau worker nhả khóa và đủ artifact, scheduling lỗi không phá settlement. |
| `hybrid-hands/tests/test_hand_paseo_cli.py` | Cập nhật fake lifecycle/CLI theo auto-archive, review và followup mới. |
| `hybrid-hands/tests/test_hand_paseo_integration.py` | Kiểm hai epoch, cùng child/workspace, patch/usage/outcome và hh-ps projection không đổi ý nghĩa. |

## Hành vi và điểm tích hợp

- Archive chỉ có authority khi outcome quiescent, có evidence, không còn reservation và cả 5 hook `finalize/report/ledger/go_ledger/usage_state` completed. Không lấy idle/report-only làm bằng chứng.
- `archive_settled` giữ backend outcome và artifact khi lỗi; ghi `receipt.lifecycle_error` an toàn. Lệnh `managed archive` tường minh trả unresolved nếu thao tác chưa xác nhận, kể cả record trước đó đã mang state archived.
- Child archive trước. Theo correction mới của lead/Opus, workspace managed riêng chỉ chấp nhận exact child đã xác minh, archived và không có sibling nào cùng `workspaceId`. Active sibling chặn; mọi archived sibling cũng chặn (kể cả có nhãn/provider giống plugin hoặc dấu hiệu main_session). Cùng cwd nhưng khác workspace không bị tính cùng nhóm. Parent workspace bị chặn.
- Workspace archived không còn trong `fetchWorkspaces`; bridge dùng exact child identity cùng recovery state đúng workspaceId. Chỉ nhận recovery action `unarchive`, không nhận action `restore` có thể recreate worktree. Sau restore xác minh lại project/workspace/cwd trước refresh child.
- Followup vẫn yêu cầu review đúng epoch. Restore/reopen hoàn tất trước tạo intent/epoch mới; lỗi giữ epoch/key/review cũ để retry. Admission/policy mới vẫn chạy trước send. DSH capacity continuation giữ ngoại lệ capacity hiện có và mở lại child/workspace khi cần.
- Pending lifecycle phải reconcile trước; một lượt không xác nhận giữ unresolved, lượt gọi sau mới được retry helper hữu hạn. Send/create không được mở thêm đường retry writer.
- Callback completion không tự gọi archive trên stack worker đang settle: worker độc lập chờ worker lock nhả, dùng session riêng để sống qua lúc Paseo đóng gateway. Archive đồng bộ ở frontend là đường bổ sung; `.send-lock` ngăn đóng gateway trước khi ACK send được lưu. Timeout worker lock 10s, process 90s, tối đa 2 lượt archive trong worker; từng transport call cũng hữu hạn.
- Không sửa `lib/side_session/*`, hh-ps implementation, manifest, changelog, README, skill, template hay config. Không thay pool/quota/usage semantics.
- Điểm tích hợp với nhánh `ws-archive`: commit này chỉ sửa `lib/hand_ext/paseo_*` và test/fixture tương ứng; lead tích hợp phần side-session, docs và release. Không có dependency mới.

## Kiểm chứng thật

Chạy tại `/Users/anhtp/app/claude-plugins-wt/ws-archive-hand` sau sửa cuối:

```text
python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py' -q
Ran 40 tests in 15.933s — OK

node --check hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs
exit 0

node --check hybrid-hands/tests/fixtures/hand_paseo/transport/run.mjs
exit 0

python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py' -q
Ran 515 tests in 75.658s — OK

git diff --cached --check
exit 0
```

Full suite hybrid-hands chạy đúng một lần cuối; không claim chạy suite riêng của statusline. Toàn bộ lifecycle được kiểm bằng fixture/fake transport. Không smoke live theo brief; chưa xác nhận độ trễ UI/daemon thật của worker archive độc lập. Lead `ws-archive` cần smoke sau merge theo quyền riêng.

## Xác minh source public API đã pin

Sol đọc source cài đặt, không gọi mutation runtime:

- CLI package: `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`, version pin `0.15.0`.
- `node_modules/@getpaseo/client/dist/daemon-client.js`: `archiveWorkspace` khoảng 1843; `inspectWorkspaceRecovery` 2135; `restoreWorkspace` 2145. Restore trả void và throw nếu host từ chối.
- `node_modules/@getpaseo/server/dist/server/server/session.js`: dispatch `workspace.recovery.restore.request` khoảng 2224; handler khoảng 2905; `restoreWorkspaceAndEmit` 4476; archive workspace handler 5680.
- `session/workspace-recovery/workspace-recovery-service.js`: directory còn thì action unarchive; directory mất có thể action restore hoặc unavailable. Bridge chặn recreate.
- `workspace-archive-service.js`: removal chỉ đi vào backing được chứng minh Paseo-owned; directory workspace của hand không sở hữu backing đó. Fixture giữ sentinel, không có delete/recreate API trong bridge.
- `agent/agent-manager.js`: archiveAgent đóng runtime gateway, là lý do worker archive cần độc lập và có khóa ACK send.

## Giao hand và review

- Luôn chạy `hand-ext pick --json` trước dispatch; effective pick là codex `gpt-6.1-sol`, low. Chạy shell theo brief, `--isolation none` để hai writer khác file cùng nằm trong worktree được cấp, `--keep-worktree`; scope riêng `ws-archive-hand`, tối đa 2 hand đồng thời (config max_parallel=4).
- Hai lượt đầu `ws-archive-hand-bridge` và `ws-archive-hand-controller` dừng **exit 4/capped** với cap 160000 token tích lũy; giao tiếp cùng backend với cap 3000000. Không dùng lỗi này làm ngoại lệ để Sol tự viết code.
- Codex hoàn tất bridge, controller/completion và hai fixture CLI/integration. Sol review, giao sửa controller cùng backend đúng một lần.
- Review tiếp còn hai lỗi tuple/latest và báo thành công archive dựa trên state cũ; chuyển backend kế tiếp `claude-v1` qua wrapper (không spawn native, không đổi config). Hand Claude sửa xong nhưng tool chạy pytest trong phiên hand bị chặn approval; Sol đã chạy unittest hẹp và full suite xanh ở trên.
- Các hand-ext run đã thoát. Hand controller báo đã dừng lượt unittest từng kẹt do dùng chung gateway lock; sửa bằng `.send-lock` riêng rồi kiểm lại xanh. Không tạo daemon/background runtime thật cho kiểm chứng, không dọn `output/llm/` hay worktree.

## Đoạn docs đề xuất cho lead tích hợp

> Managed hand tự archive exact child và workspace sau khi execution quiescent, report cùng các hook settlement đã hoàn tất. Không cần chờ review để archive; review-approve vẫn bắt buộc trước managed followup. Followup khôi phục workspace còn thư mục, mở lại cùng child rồi tạo epoch/request key mới với baseline mới. Không recreate workspace/worktree đã mất. Lỗi archive/restore giữ record, receipt và artifact để retry hữu hạn; workspace managed riêng chỉ archive khi directory đầy đủ xác nhận duy nhất exact child đã archived, không có sibling khác cùng workspaceId. Thay đổi lifecycle không đổi outcome/usage hay cách hh-ps phân loại kết quả.

## Bàn giao release

Nhánh remote đã push; tích hợp commit `c1c99f3` vào `side/ws-archive` hoặc theo quy trình của lead. Release 0.36.0, docs/changelog/manifest, cập nhật plugin qua công cụ chính thức và smoke live do `ws-archive` phụ trách. Marker `.done` chỉ báo gói này hoàn tất, không báo đã release.

## Correction ownership sau review tích hợp

- Lead báo đã tích hợp `c1c99f3` và yêu cầu fail-closed với sibling chưa chứng minh ownership/main exclusion. Đã chọn phương án lead cho phép: workspace managed riêng chỉ chứa exact child; không suy ownership từ cwd hay nhãn/provider.
- Commit bổ sung: `6bc9faa5cac8fb3d88649b2103154af98830d996` (`6bc9faa`), parent `c1c99f3`. Lead chỉ cần tích hợp correction này.
- Chỉ đổi `lib/hand_ext/paseo_bridge.mjs` và `tests/test_hand_paseo_transport.py` (14 dòng thêm, 1 dòng bỏ); không sửa side-session/docs/release trong nhánh.
- `archivedMembers` giữ `WORKSPACE_ACTIVE_MEMBER` cho active sibling; archived sibling bất kỳ trả `WORKSPACE_UNOWNED_MEMBER`. Gate dùng chung cho archive và reconcile, trước mọi `archiveWorkspace`.
- Test membership phân trang kiểm unknown archived sibling, sibling có nhãn/provider giống plugin và sibling main-shaped đều chặn; số call `archiveWorkspace` bằng 0. Exact child đơn độc cùng agent khác workspace trùng cwd vẫn thành công. Giữ ACK-loss/reopen tests.
- Giao `hand-ext run --backend auto --mode shell` sau pick, backend codex low, run `ws-archive-hand-ownership`; hand exit 0. Sol đã review diff.
- Hand: 7/7 transport test xanh. Sol sau correction: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py' -q` → **40 test, 15.959s, OK**; `node --check` bridge và `git diff --cached --check` exit 0.
- Không chạy lại full suite theo chỉ đạo lead; số 515 ở trên thuộc commit đầu. Không smoke live, không main/release/runtime update.
