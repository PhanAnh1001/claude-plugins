## Tóm tắt

- Kết quả: xong; commit `a207f50519e5c85161af342e60028ee32dc7cfba` trên `side/sol-ws-hoi`, plugin **0.33.1**.
- `lib/side_session/paseo.py`: wrapper revive/rearchive có guard main/ID, trả lỗi an toàn.
- `lib/side_session/paseo_bridge.mjs`: kiểm exact agent/workspace/target; unarchive tại chỗ, archive lại chỉ workspace riêng.
- `lib/side_session/actions.py`: ls/watch đối soát done; `paseo_revived` chặn finish từ `.done` cũ, mỗi vòng chỉ một bước.
- `lib/side_session/state.py`: chỉ thêm cuối dataclass `paseo_revived=False`, tương thích state cũ.
- `tests/test_side_session_paseo.py`, `test_side_session_native.py`: client/state giả kiểm revive, fail closed, archive lại và cleanup đầu.
- `docs/paseo-project-lifecycle.md`: cơ chế hiện hành, mở đầu tóm tắt, lý do giữ workspace riêng kèm source file:line.
- `plugins/hybrid-hands/CHANGELOG.md`: mục 0.33.1 mô tả lifecycle mới.
- `plugins/hybrid-hands/.claude-plugin/plugin.json`: bump 0.33.0 → 0.33.1 theo bổ sung Opus.
- Test: Paseo **10 OK**, native **6 OK**; cuối chạy `test_side_session*.py` đúng một lần: **99 OK**.
- Validate: exit 0 / **Validation passed**; catalog riêng báo thiếu LICENSE và icon; JSON, Node syntax, diff whitespace đều hợp lệ.
- Chưa kiểm chứng runtime/UI thật; không mutation Paseo, không push/merge/cài plugin; Opus làm phần triển khai sau.

## Commit và phạm vi

- Commit: `a207f50519e5c85161af342e60028ee32dc7cfba` — `fix(side-session): revive private Paseo workspaces for resumed agents`.
- Base worktree: `a76826aa1e3ef0ae2ed10aa9b42d066c70c9a070`; không rebase/merge main trong phiên.
- Worktree: `/Users/anhtp/app/claude-plugins-wt/sol-ws-hoi`; nhánh `side/sol-ws-hoi`.
- 9 file đổi, chỉ trong scope brief. Các đường dẫn `lib/side_session/*` ở phần tóm tắt nằm dưới `hybrid-hands/plugins/hybrid-hands/`; test/docs nằm dưới `hybrid-hands/`.
- Không sửa `config/constants/tokens/handoff.py`, config repo/account/settings/credential hay repo live-tiktok-games. Không dọn `output/llm/`.
- Git worktree sạch sau commit. Bàn giao này và `.done` được ghi ở đường dẫn brain yêu cầu ngoài worktree, không commit vào main.

## Hành vi cuối đã review

1. Done Codex/Paseo, không main, workspace đã archive và chưa revived: bridge `revive` fetch exact agent, workspace đã lưu và target. Agent còn archived trả `revived:false`. Agent unarchived thì inspect; chỉ `recoverable/action=unarchive` mới restore; inspect lần sau phải xác nhận đúng workspace `unavailable/reason=workspace_not_archived`. Workspace active sẵn không restore. Recovery `restore`, shape không hỗ trợ hoặc ID mismatch không mutation.
2. Thành công: giữ status done, đặt `paseo_workspace_archived=False`, `paseo_revived=True` và save. `.done` cũ không gọi automatic finish. ls/watch chỉ finish hoặc reconcile một bước mỗi lần, không revive ngay cùng vòng vừa finish/rearchive.
3. Revived: bridge `rearchive` fetch agent. Chỉ khi archivedAt nonnull mới private check (có cả archived sibling) và archive workspace. Không cancel/archiveAgent. Thành công đưa flags về archived=True/revived=False; lỗi giữ flags/state và warning một dòng.
4. Watch chỉ tiếp tục khi done đã revived; agent còn archive hoặc đã rearchive thì watch kết thúc như contract. Tự mở lại chỉ xảy ra khi có ls/watch chạy, không tạo watchdog mới. Start/first done/main/screen/Claude/dsh giữ nguyên hành vi.

## Kiểm chứng thật

Test hẹp đã chạy trong các lượt hand/native; Sol cũng tự chạy lại Paseo trong review:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py'
# Ran 10 tests, OK
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_native.py'
# Ran 6 tests, OK; Node khả dụng, không skip
```

Cuối, Sol chạy đúng một lần:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'
# Ran 99 tests in 15.815s, OK; exit 0
claude plugin validate hybrid-hands/plugins/hybrid-hands
# Validation passed; exit 0
```

Validator có kiểm catalog bổ sung: `LICENSE_MISSING` là lỗi để nộp catalog, `ICON_MISSING` là warning; chúng không làm profile validate mặc định fail. Không thêm license/icon vì ngoài phạm vi brief.

Các kiểm phụ: `node --check hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs`, `git diff --check`, parse manifest bằng Python JSON đều pass. Tài liệu lifecycle không có Markdown link nội bộ, nên không có link nội bộ hỏng; dẫn source cài đặt dùng file:line. Không chạy suite ngoài pattern đã giao.

Ca chính/biên đã xác minh bằng dữ liệu giả:

- Unarchive → restore đúng workspace → inspect active; workspace active sẵn không restore; agent còn archived không restore.
- Recovery action restore, recovery shape/ID không hợp lệ và agent.workspaceId lệch: không mutation. Python warning và flags không đổi.
- Restore xong chưa active: `WORKSPACE_RESTORE_UNCONFIRMED`, không xác nhận revived.
- Revived còn `.done`: không automatic finish; vừa finish không revive cùng vòng; cleanup done legacy vẫn retry.
- Agent archive lại: chỉ archiveWorkspace. Shared workspace với sibling trả `WORKSPACE_SHARED`, ledger không cancel/archiveAgent/archiveWorkspace.

## Giao hand và review

Áp dụng skill [ext-hand](/Users/anhtp/app/claude-plugins-wt/sol-ws-hoi/hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md). Không tự viết implementation/test/docs sản phẩm.

- Preflight ban đầu chọn dsh `deepseek-v4.1-flash`, effort off. Giao một gói tuần tự qua hand-ext auto, rồi giao lại cùng dsh đúng một lần khi review phát hiện lỗi.
- Vòng dsh 1 exit 0 nhưng có regression P0: mất guard status DONE ở watch, tự finish active agent chưa có `.done`; 2 test cũ đỏ. Report hand nói “đỏ sẵn” sai: Sol chạy 8 test cũ với actions.py từ HEAD bằng exec source trong bộ nhớ, **8 OK**. Sau sửa, cả 10 test Paseo xanh.
- Vòng dsh 2 sửa P0/provider guard/finish-vs-reconcile nhưng tự thêm private gate vào cuối revive và còn thiếu ca shared rearchive thực. Sol không chấp nhận phần đó.
- Opus cập nhật order main ở `6d3e9c7` trong lúc dsh 2 đang chạy: để dsh xong, không writer trùng, không sửa config worktree. `hand-ext pick` worktree vẫn trả dsh do config cũ; theo chỉ đạo tường minh mới, phần còn lại giao native **gpt-6.1-sol low**, `fork_turns=none`, full brief và luật dữ liệu nguyên văn.
- Native sửa đúng 4 file được giao: bỏ gate ngoài contract của revive, test shared rearchive đúng agent đã archived, thêm kiểm post-restore chưa active, dọn fixtures và changelog. Sol review diff cuối đạt scope/contract; native không commit hay tạo hand-ext ledger.
- Không có hand-ext exit lỗi/7/8; không cần doctor. Cả hai lượt dsh và native đều đã kết thúc; không còn tiến trình nền do Sol tạo.

Report dsh (chỉ tài liệu của task này):

- `output/llm/hand-ext/20261109-134004-552815-sol-ws-hoi-dsh/report.md`
- `output/llm/hand-ext/20261109-140021-604279-sol-ws-hoi-fix-dsh/report.md`

Usage wrapper báo: dsh 1 input=29,043,159, cached_input=28,834,432, output=85,221; dsh 2 input=8,974,770, cached_input=8,854,656, output=42,336. Sau dsh 2: Go thật 2% 5h (reset 18:39), 1% tuần (reset 16/11 07:00), 15% tháng (reset 04/12 15:17), theo output wrapper tại thời điểm chạy. USD~ riêng các lượt chưa lấy: `?`. Native token/USD~/quota: `?`, không suy từ số khác.

## Chưa kiểm chứng / Opus làm tiếp

- Không thực hiện bất kỳ read/mutation daemon Paseo thật để test; không UI runtime. Chỉ đọc source client/server cài đặt và dùng fake client.
- Opus quyết định tích hợp commit nhánh này vào main và cập nhật plugin các repo đang dùng theo công cụ chính thức. Không push/merge/cài plugin trong phiên này theo brief.
- Sau cập nhật cần kiểm path/version nạp thực tế và reload các tiến trình Python/watch cũ nếu cần; chưa claim đã hot load.
- Phạm vi chỉ recovery in-place `action=unarchive`; không recreate worktree đã mất. Nếu user unarchive rồi archive agent giữa hai lần đối soát mà side-session chưa từng thấy revived thì không có nguồn quan sát lần sống lại đó; contract chấp nhận đối soát khi có lệnh.


## Sửa sau review

**R2 đã xong** — commit `2eae0b877a226705cd0209cb012861a4fd6d9100` (`perf(side-session): batch done agent archive states in ls`) trên `side/sol-ws-hoi`, nối sau `a207f50519e5c85161af342e60028ee32dc7cfba`. Giữ plugin **0.33.1** vì đây là sửa review trước merge của cùng thay đổi.

Opus phát hiện ls phát sinh một bridge revive cho mỗi phiên done đã archived dù phần lớn agent còn archived. R2 thêm bridge read-only `agent-archive-states`: một invocation, `fetchAgents(includeArchived:true)` có phân trang; chỉ trả agentId/workspaceId/archivedAt và targetKey. Kiểm trang, ID trùng, cursor lặp, giới hạn 100 trang; không trả snapshot từng phần khi lỗi.

Python xác minh toàn snapshot, target và mọi candidate agent/workspace trước khi reconcile. ls chỉ gọi revive khi agent đã unarchive và workspace flag archived; chỉ gọi rearchive khi phiên revived có agent đã archive lại. Agent còn archived không phát sinh revive. Snapshot lỗi/thiếu/malformed hoặc lệch target/workspace: bỏ reconcile toàn vòng, warning một dòng, không fallback các bridge per-agent. Mutation commands vẫn fetch lại exact agent để bảo vệ trường hợp trạng thái đổi sau snapshot.

`watch_tick` giữ flow một phiên hiện có, không đọc danh sách chung. Warning revive/rearchive và batch đổi sang `workspace reconcile lỗi`; warning cleanup done đầu vẫn giữ nguyên. Luồng finish đầu và display refresh hiện có giữ nguyên.

File đổi (7, tất cả trong scope cũ):

- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs`: command đọc archive state có phân trang, chỉ đọc.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`: wrapper một bridge call và validate toàn snapshot/candidate.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py`: ls chọn ứng viên từ snapshot chung; đổi câu warning reconcile.
- `hybrid-hands/tests/test_side_session_paseo.py`: thêm một test ls nhiều phiên; điều chỉnh fixture lifecycle cho batch và giữ watch không list.
- `hybrid-hands/tests/test_side_session_native.py`: test client giả cho pagination, page lỗi, duplicate ID, cursor lặp và malformed.
- `hybrid-hands/docs/paseo-project-lifecycle.md`: mô tả ls batchread, fail closed, watch riêng và câu warning mới.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: cập nhật mục 0.33.1 với batchread. Không đổi manifest/config/state.py.

Kiểm chứng R2 thật:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py'
# Native hand: Ran 11 tests, OK
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_native.py'
# Native hand: Ran 7 tests, OK
python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'
# Sol chạy đúng một lần cuối cho R2: Ran 101 tests in 14.278s, OK; exit 0
claude plugin validate hybrid-hands/plugins/hybrid-hands
# Sol: Validation passed; exit 0; vẫn có LICENSE_MISSING (catalog) và ICON_MISSING
```

Node syntax, git diff whitespace, parse manifest 0.33.1 và kiểm link nội bộ của tài liệu đều pass. Test mới dựng 27 phiên agent còn archived, thêm một agent unarchived và một revived đã archived lại: danh sách đúng **1** bridge call, revive đúng **1** ứng viên unarchived, rearchive đúng **1** ứng viên revived; không revive 27 agent còn archived. Ca daemon/list thiếu/target lệch/shape sai đều không gọi revive/rearchive, không đổi flags và chỉ một warning. Test bridge thực thi Node với client giả, xác nhận includeArchived và cursor hai trang; không có daemon thật.

Toàn bộ implementation/test/docs R2 giao native **gpt-6.1-sol low**, tái sử dụng hand được mở ban đầu bằng `fork_turns=none`, brief đầy đủ và luật dữ liệu nguyên văn. Preflight worktree vẫn trả dsh vì config cũ; dùng native theo chỉ đạo tường minh Opus, không sửa config. Sol review diff cuối đạt yêu cầu; native không commit hay tạo ledger hand-ext. Token/USD~/quota native: `?`. Không còn hand hoặc tiến trình test nền đang chạy.

**Chưa kiểm chứng:** không đo lại wall-clock ls trên repo tiktok hoặc mutation runtime/UI thật, theo lệnh cấm runtime của brief. Bằng chứng hiệu năng ở đây là số lần gọi bridge bằng client giả; display `paseo.refresh` hiện có vẫn có các lời gọi riêng như trước. Opus đo thời gian thật và cập nhật plugin sau tích hợp. Không push/merge hay cập nhật runtime trong phiên. Git worktree sạch sau commit.

Tín hiệu R2: `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/sol-ws-hoi-r2.done`.
