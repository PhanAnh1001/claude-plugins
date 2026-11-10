# Brief: tự mở lại workspace khi phiên Sol đã done được gửi tiếp việc

## Tóm tắt

- **Mục tiêu:** phiên Sol Paseo đã done (agent + workspace riêng đã archive) mà sau đó agent hoạt động lại thì `side-session ls`/`watch` tự gọi `restoreWorkspace` để phiên hiện lại trên sidebar Paseo; khi agent bị archive lại thì archive lại workspace riêng.
- **Người dùng chốt (09/11/2026):** giữ archive workspace khi done (433b85c), thêm tự mở lại. Chấp nhận chỉ tự sửa khi có lệnh side-session chạy. Không gom vào workspace chính (Paseo 0.15.0 ép cwd agent về cwd workspace: `session.js:3333,3346`, bàn giao `docs/work-in-progress/handoffs/sol-ws-chung.md`).
- **Đã làm tay hôm nay:** Opus gọi `restoreWorkspace` cho 6 workspace tiktok qua client cài đặt; inspect trước trả `action=unarchive`, sau đó 6 workspace active lại. Đây là bằng chứng API chạy được.

## MỤC TIÊU

Tự phát hiện agent Sol done đã sống lại và mở lại workspace riêng của nó; archive lại workspace khi agent bị archive lần nữa; không bao giờ archive ngay phiên vừa sống lại.

## NGỮ CẢNH

- Luồng hiện tại: `lib/side_session/actions.py:_finish_codex` (đặt `status=done`, `paseo_workspace_archived=True`), `ls` (`actions.py` khoảng dòng 360-380) và `watch_tick` (khoảng 574) gọi lại `_finish_codex` khi done mà `paseo_workspace_archived` còn false. `paseo.py:finish` gọi bridge `finish` (`paseo_bridge.mjs`: `archiveExactAgent`, `privateWorkspace`, `archivePrivateWorkspace`).
- Bẫy cần tránh: nếu restore xong chỉ đặt `paseo_workspace_archived=False` thì nhánh 433b85c trong `ls`/`watch_tick` sẽ archive lại ngay agent đang chạy. Cần trạng thái riêng, ví dụ thêm cuối `SessionState` field `paseo_revived: bool = False` (default giữ tương thích state cũ).
- API đã xác minh (gốc `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`): `node_modules/@getpaseo/client/dist/daemon-client.d.ts:969-970` `inspectWorkspaceRecovery(workspaceId)` / `restoreWorkspace(workspaceId)`; `daemon-client.js:2135-2156`; server `session/workspace-recovery/workspace-recovery-service.js:37-38,65-74` (directory còn thì `unarchive`, còn `restore` thì tạo lại worktree). `fetchAgent({agentId})` trả agent có `workspaceId`, `archivedAt`.
- Nhánh `side/luong-c` (chưa merge, 0.33.0) sửa `lib/side_session/{config,constants,state,tokens,handoff}.py`, `tests/test_side_session*.py`. Base `main`; thêm field vào cuối dataclass, thay đổi tối thiểu ở file chung để Opus merge.

## Hành vi cần có

1. Bridge thêm lệnh `revive`: nhận `agentId`, `expectedWorkspaceId`, `expectedTargetKey`. Đọc `fetchAgent`; agent không tồn tại, workspaceId khác expected → lỗi mã riêng, không mutation. Agent `archivedAt` khác null → trả `{revived:false}`. Agent chưa archive → `inspectWorkspaceRecovery`; chỉ khi `action=unarchive` mới `restoreWorkspace`, sau đó inspect/kiểm workspace active rồi trả `{revived:true}`. `action=restore` (phải tạo lại worktree) hoặc kiểu khác → lỗi `WORKSPACE_RECOVERY_UNSUPPORTED`, không mutation. Workspace đã active sẵn → `{revived:true}` không gọi restore.
2. `ls` và `watch_tick`: với phiên codex/paseo, role khác main, `status=done`, `paseo_workspace_archived=True`, chưa `paseo_revived` → gọi `revive`; thành công thì `paseo_workspace_archived=False`, `paseo_revived=True`, lưu state; lỗi thì in cảnh báo một dòng giống cảnh báo `.done cleanup` hiện có, không đổi state.
3. Phiên `paseo_revived=True`: không gọi `_finish_codex` tự động dù `.done` còn. Khi `fetchAgent` cho thấy agent đã archive lại → archive workspace riêng (dùng lại kiểm tra `privateWorkspace` + `archivePrivateWorkspace`, không archive agent lần nữa), rồi `paseo_workspace_archived=True`, `paseo_revived=False`.
4. Không đổi luồng start, luồng done lần đầu, phiên main, phiên screen/claude/dsh.
5. Cập nhật `hybrid-hands/docs/paseo-project-lifecycle.md` (chỉ cơ chế đang áp dụng, mở đầu bằng tóm tắt; thêm mục tự mở lại và lý do không gom workspace chính kèm file:line), CHANGELOG, bump `plugin.json` 0.32.2 → 0.32.3.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`, `paseo_bridge.mjs`, `actions.py`, `state.py` (chỉ thêm field cuối dataclass)
- `hybrid-hands/tests/test_side_session_paseo.py`, `hybrid-hands/tests/test_side_session_native.py`
- `hybrid-hands/docs/paseo-project-lifecycle.md`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`, `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` theo hợp đồng side-session.

## KHÔNG ĐƯỢC ĐỤNG

- Không mutation runtime Paseo nào (kể cả thử nghiệm): test dùng client giả như `test_side_session_native.py` đang làm. Không archive/stop/delete agent/workspace thật, không `paseo project delete`/`removeProject`.
- Không sửa `lib/side_session/{config,constants,tokens,handoff}.py` trừ khi bắt buộc (ghi lý do). Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings, không bật parallel-subagents. Không sửa repo `live-tiktok-games`.
- Không xoá/di chuyển/dọn `output/llm/`. Không commit vào `main`, không merge/push, không cập nhật cài đặt plugin: Opus làm sau. Được commit trên nhánh phiên của mình.
- Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol là lead tech/QA: giao code/test/tài liệu L0/L1 qua `hand-ext run --backend auto` theo `ext_hand.order`, review code hand mình giao; chỉ tự làm khi hand-ext lỗi (ghi lý do/mã thoát). Exit 7 chạy doctor trước; exit 8 chờ slot. Brief giao hand phải chép nguyên văn luật dữ liệu trên.

## KIỂM CHỨNG

- Test hẹp trong lúc làm: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py'` và `-p 'test_side_session_native.py'`.
- Cuối, chạy đúng một lần: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'`; `claude plugin validate hybrid-hands/plugins/hybrid-hands`.
- Mức test: tối thiểu. Ca: (1) done + agent sống lại + `action=unarchive` → gọi restore, state `revived`, không gọi finish ngay; (2) `action=restore` hoặc workspaceId lệch → không mutation, state giữ nguyên; (3) revived rồi agent archive lại → archive workspace, state về archived.
- Xong khi: test xanh, đã review diff hand, commit trên nhánh, bàn giao ghi lệnh/kết quả thật và phần chưa kiểm chứng.

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: commit, file đổi, kết quả test/validate, phần chưa kiểm chứng (runtime thật).
