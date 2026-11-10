# L1 executor brief: revive archived Sol Paseo workspace

## LUẬT BẮT BUỘC
Bạn là hand executor trực tiếp, không phải Sol. Làm trực tiếp, không hand-ext, side-session, subagent, recursion, giao tiếp phiên khác hay review hand khác. Không commit/push/merge/cập nhật runtime. Đọc AGENTS.md áp dụng; task-specific scope dưới ưu tiên hơn workflow chung. Chỉ code/fixtures giả công khai được.
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KHÔNG ĐƯỢC ĐỤNG
Không mutation runtime Paseo nào; không gọi client/daemon thật kể cả test read. Mọi test bridge dùng client giả trong test_side_session_native.py. Không sửa config/constants/tokens/handoff.py, settings/credentials/config/installed_plugins, repo khác. Không xoá/di chuyển/dọn output/llm/. Shell cwd/workdir, không cd DIR &&. Không chạy full suite test_side_session*.py hay claude plugin validate: Sol chạy đúng một lần cuối.

## TRẢ VỀ
Report file thay đổi, giải pháp, test lệnh/kết quả, hạn chế. Không bàn giao .done (Sol làm). Không tự review hand khác.

## MỤC TIÊU
Giữ archive workspace riêng khi done lần đầu; tự mở lại workspace khi agent đã unarchive để nhận việc tiếp, chỉ khi side-session ls/watch chạy; khi agent archive lại thì archive workspace riêng mà không archive agent lần nữa. Không bao giờ _finish_codex tự động cho phiên vừa revived dù .done cũ còn.

## NGỮ CẢNH / THIẾT KẾ CHỐT
Base hiện 0.33.0, bump 0.33.1 (không 0.32.3).
state.py: chỉ thêm cuối SessionState `paseo_revived: bool = False`, giữ field hiện tại.
Bridge thêm `revive` nhận agentId/expectedWorkspaceId/expectedTargetKey. Target guard hiện có giữ nguyên. fetchAgent phải có agent/id đúng và workspaceId đúng, lỗi mã riêng trước mọi mutation. archivedAt != null => {revived:false}, không restore. Unarchived agent => inspectWorkspaceRecovery(workspaceId): chỉ action=unarchive mới restoreWorkspace; sau đó inspect/kiểm active trước {revived:true}. Workspace đã active => {revived:true}, không restore. action=restore hoặc shape khác => WORKSPACE_RECOVERY_UNSUPPORTED, không mutation. Không recreate worktree.
Installed client contract đã Sol đọc source xác minh: inspectWorkspaceRecovery trả payload.state trực tiếp, restoreWorkspace trả void. Recovery state archived hiện {kind:"recoverable",workspaceId,action:"unarchive"|"restore",...}; workspace active hiện {kind:"unavailable",workspaceId,reason:"workspace_not_archived",...}. Vì vậy reason workspace_not_archived với đúng workspaceId là kiểm active; không kỳ vọng action=none.
Cho phiên revived, thêm bridge operation riêng (ví dụ rearchive) fetch exact agent và workspace IDs; khi archivedAt != null dùng privateWorkspace + archivePrivateWorkspace, KHÔNG cancelAgent/archiveAgent. Chưa archived thì không mutation. Error không đổi Python state. Guard main ở Python wrappers.
Trong actions.py chung helper được dùng ls/watch_tick để reconcile codex/paseo role != main status=done: archived && !revived => revive; true thì archived=False, revived=True, save. revived => kiểm lại agent archive bằng operation trên; khi archive workspace thành công thì archived=True, revived=False, save. Không chạy _finish_codex tự động cho revived, kể cả .done cũ. Không revive ngay trong cùng vòng vừa finish/rearchive. Trạng thái status vẫn done để không thay slot/cap/start contract. Lỗi warning một dòng theo .done cleanup và giữ state. Watch done archived còn agent archive => có thể false như contract cũ; khi revived cần watch tiếp để thấy archive lần sau. Không thay start/done đầu/main/screen/claude/dsh.
Docs chỉ cơ chế hiện áp dụng, mở đầu tóm tắt. Loại nội dung lỗi thời nói finish không archive workspace hay hướng dẫn cleanup runtime legacy. Mô tả start addProject(cfg.repo)+private workspace; finish private check gồm archived siblings; revive và rearchive; giới hạn ls/watch, không recreate. Lý do không gom workspace chính: Paseo 0.15.0 server/server/session.js:3333 và :3346 resolve workspace.cwd và gán config.cwd=intent.cwd nên cwd side bị ép về main. Source recovery workspace-recovery-service.js:20-25 (active reason), :37-38 unarchive, :65-74 restore. Dẫn file:line rõ, tránh link file không tồn tại trong repo.

## PHẠM VI GHI
Chỉ:
- hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py
- hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs
- hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py
- hybrid-hands/plugins/hybrid-hands/lib/side_session/state.py (append field cuối dataclass only)
- hybrid-hands/tests/test_side_session_paseo.py
- hybrid-hands/tests/test_side_session_native.py
- hybrid-hands/docs/paseo-project-lifecycle.md
- hybrid-hands/plugins/hybrid-hands/CHANGELOG.md (0.33.1)
- hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json (0.33.1)

## KIỂM CHỨNG / TIÊU CHÍ CHẤP NHẬN
Mức tối thiểu, tối đa 3 nhóm ca mới (có thể subtest để chạy cùng invariant cho ls/watch):
1. Done archived + agent active + recovery unarchive => restore đúng ID, inspect active, persisted revived=true/archived=false; ls/watch kế tiếp dù marker .done còn KHÔNG finish. Workspace đã active không restore. Archived agent không restore.
2. action restore hoặc workspaceId mismatch => không mutation, state nguyên, warning. Fake bridge calls ledger chứng minh. Cả mismatch agent/target/response unsupported fail closed theo logic hiện có.
3. Revived rồi agent archive => chỉ archiveWorkspace sau private check, state archived=true/revived=false; không cancel/archiveAgent và không revive/finish lại cùng vòng. Shared workspace không mutation.
Chạy test hẹp khi cần: python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py' và tương tự test_side_session_native.py. Không thêm test tài liệu/framework. Sol sẽ review diff và chạy suite/validate cuối.


# REVIEW SOL — yêu cầu sửa một lượt cùng backend (ưu tiên phần này)
Vòng đầu đã áp patch vào worktree Sol. Bạn chỉ sửa các lỗi dưới, giữ scope phía trên. Không commit. Không full suite/validate. Không gọi daemon thật. Không debug framework hay thử git archive/baseline vòng vèo.

1. Regression P0 trong watch_tick: diff làm mất `st.status == C.STATUS_DONE` khỏi nhánh `_finish_codex`, nên mọi Codex/Paseo đang chạy đều bị finish ngay cả chưa .done! Đồng thời `if st.status == DONE: return ...` đứng trước legacy cleanup khiến done cũ archived=False không còn cleanup trong watch. Khôi phục đúng guard status DONE cho legacy branch, xử lý reconcile chỉ trong branch Codex/Paseo/DONE. Dạng đúng:
   - role main return False như cũ.
   - nếu status DONE && provider CODEX && transport PASEO:
     - nếu revived hoặc workspace_archived: reconcile một lần, return st.paseo_revived.
     - còn lại: return not _finish_codex(cfg,st) (done cũ chưa cleanup).
   - status inactive còn lại return False; active giữ nguyên mọi logic cũ kiểm marker done rồi mới finish.
   Không nới test cũ. Sol đã chạy chính xác 8 test cũ với actions.py từ HEAD (exec source trực tiếp, không đổi file); Ran 8 OK. Với patch vòng đầu thì 2 test đỏ dòng 166/514. Nhận định report trước “đỏ sẵn” là SAI.

2. _reconcile_done thiếu provider CODEX guard: thêm, để Claude/dsh/screen không bị gọi revive/rearchive. ls hiện gọi reconcile NGAY SAU _finish_codex trong cùng vòng: sửa thành hai nhánh loại trừ (if finish ... elif reconcile ...), để vừa finish không revive ngay cùng vòng; vừa rearchive cũng không revive/finish. Không đổi luồng start/done đầu. Guard revived chống mọi automatic _finish_codex kể cả marker còn.

3. Test bridge mới chưa kiểm workspaceId agent mismatch (mới test recovery.workspaceId mismatch); thêm subcase request.expectedWorkspaceId khác agent.workspaceId cho revive và rearchive, assert WORKSPACE_ID_MISMATCH và mutation ledger rỗng. Thêm subcase shared workspace rearchive => WORKSPACE_SHARED, không archiveWorkspace. Giữ trong test mới hiện có, không thêm nhóm test thứ tư. Xác minh post-restore inspect chưa active => lỗi/state không đổi; có thể subcase nếu đơn giản. Test lifecycle hiện mock helpers được, nhưng cũng cần kiểm ls finish lần đầu KHÔNG gọi revive trong cùng vòng và watch done legacy cleanup hoạt động (mở rộng test cũ/new cùng nhóm, không nới expectation).

4. Docs: xóa mục Runtime do brain thực hiện hướng dẫn removeProject/cleanup legacy (ngoài cơ chế đang áp dụng). Thay bằng ghi ngắn runtime thật/cập nhật plugin do Opus làm, chưa kiểm chứng. Sửa lý do session.js:3333 là `return {workspaceId,cwd:workspace.cwd}` và :3346 là config.cwd=intent.cwd; giải thích do ép cwd, không nói lỗi archived là lý do không gom. Xóa/sửa câu filesystem ownership sai: bản gốc nói chỉ giữ filesystem khi ownership tường minh false; không cần bàn filesystem nếu không xác minh. “ls thì không” sau theo dõi archive nên viết rõ ls đối soát mỗi lần gọi, watch có thể tiếp tục trong khi revived. Bớt lịch sử và hướng dẫn mutation legacy.

5. Dọn comment bịa "serialized/fused payload inherit prototype" ở agentArchived/test fixtures. Chỉ giải thích archivedAt != null là archived, null/undefined là unarchived. State comment nên ghi “workspace đã được side-session mở lại sau khi agent unarchive”, không nói agent tự unarchive workspace. Không refactor thêm.

Kiểm chứng BẮT BUỘC trước report: python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py' (10 test phải xanh, không baseline excuses) và tương tự test_side_session_native.py. Nếu test đỏ sửa logic, KHÔNG sửa test cũ để che lỗi. Report thật lệnh/kết quả, không claim shared/mismatch đã test nếu chưa chạy.
