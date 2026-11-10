# Brief: gom phiên Sol vào workspace chính của project trên sidebar Paseo

## Tóm tắt

- **Mục tiêu:** mọi phiên phụ Sol (Paseo transport) hiện trong workspace chính của repo trên sidebar Paseo, kể cả khi đã done rồi được gửi tiếp việc; đồng thời đưa 6 phiên Sol tiktok đang bị ẩn quay lại sidebar.
- **Hướng đã được người dùng chốt (09/11/2026):** tạo agent Sol trong workspace chính của repo (cwd agent vẫn là worktree phụ). Không tạo workspace riêng cho từng Sol, không archive workspace khi done; done chỉ archive agent. Nếu Paseo 0.15.0 không cho agent có cwd khác thư mục workspace thì DỪNG, ghi bằng chứng (file:line source đã cài) và đề xuất phương án vào bàn giao, không tự chọn hướng khác.
- **Khôi phục:** cả 6 agent tiktok chưa archive nhưng workspace đã archive. Không archive/stop/xoá agent nào, không đụng phiên chính.

## MỤC TIÊU

Side-session Paseo đặt agent Sol vào workspace chính của project; 6 agent tiktok đang ẩn hiện lại trên sidebar.

## NGỮ CẢNH (Opus đã xác minh 09/11/2026)

- Daemon hiện có 2 project: `claude-plugins` (`prj_7a322b4848a466f5`), `live-tiktok-games` (`prj_62a9abb49382f288`). Workspace active (`paseo workspace ls --json`) chỉ 8, gồm workspace chính `opus tiktok` `wks_4667ce1947e172b2`, `sol tiktok` `wks_beb1925db9835946` (cwd `/Users/anhtp/app/live-tiktok-games`), `opus plugin` `wks_95ace75b24e9d085`, `sol plugin` `wks_b791dd57b1641d61` (cwd `/Users/anhtp/app/claude-plugins`).
- Nguyên nhân: `start` tạo directory workspace riêng cwd = worktree (gắn projectId từ `0ed6b71`); `finish` archive agent rồi archive workspace riêng (`433b85c`, `lib/side_session/paseo_bridge.mjs` `privateWorkspace`/`archivePrivateWorkspace`, `actions.py:_finish_codex` đặt `paseo_workspace_archived=True`). Sau đó phiên được gửi tiếp việc, agent tự hết archived và chạy lại nhưng workspace vẫn archived nên sidebar không hiện.
- Agent đang ẩn (Archived=false, state side-session `done`, `paseo_workspace_archived=true`), state ở `/Users/anhtp/app/live-tiktok-games/sessions/hybrid-hands/side-sessions/<NAME>.json`:
  - SOL-WP72 `82585551-59a1-4210-9caa-b69e67720fd2` running, workspace `wks_e6b8efbc2af23da5`
  - SOL-RV67 `660777f7-a6f3-4f2f-8e21-2d02315d928f` running, `wks_00a33c23fc7872f6`
  - SOL-RV77 (idle) `wks_f7f6ed3fecdf9cb3`, SOL-RV66 (idle) `wks_495046b6374b5ad4`, SOL-WP67 (idle) `wks_dd3da0d2482d4537`, SOL-WP66 (idle) `wks_5c40f0f05b7dcbbd`. Agent ID lấy bằng `paseo ls -g --json`.
- Tài liệu hiện hành: `hybrid-hands/docs/paseo-project-lifecycle.md`, `hybrid-hands/paseo-hh-tree/OVERVIEW.md` (ghi API Paseo 0.15.0 đã trace: `CreateAgentRequestOptions` có `callerAgentId`, server `agent/create-agent/intent.js` mặc định dùng workspace caller). Source Paseo đã cài: package `@getpaseo/cli` (xem `paseo-hh-tree/node_modules/@getpaseo` hoặc bản global).
- Song song: nhánh `side/luong-c` (chưa merge, bump 0.33.0) có sửa `lib/side_session/{config,constants,state,tokens,handoff}.py` và `tests/test_side_session*.py`. Nhánh của bạn base `main`; giữ thay đổi tối thiểu ở các file chung để Opus merge.

## Việc cần làm

1. Đọc source Paseo đã cài, xác minh: (a) createAgent/createWorkspace cho phép agent có `cwd` = worktree nằm trong workspace chính có cwd khác; (b) API nào gắn/đưa agent hiện có vào workspace khác hoặc mở lại (unarchive) workspace đã archive. Ghi file:line.
2. Sửa `start` (bridge + `paseo.py`): tìm workspace chính active của `cfg.repo` (cwd đúng `cfg.repo`, cùng projectId) hoặc tạo mới nếu chưa có; tạo agent Sol vào đó với cwd worktree. Lưu `paseo_workspace_id` là workspace chính.
3. Sửa `finish`/`_finish_codex`: chỉ archive đúng agent; tuyệt đối không archive workspace chính dùng chung. Giữ tương thích state cũ (`paseo_workspace_archived`).
4. Khôi phục 6 agent: dùng API đã xác minh ở bước 1, ưu tiên cách không mất hội thoại (đưa vào workspace chính, hoặc unarchive workspace riêng nếu không có cách đưa vào). Trước mutation đọc lại trạng thái; mỗi agent một thao tác theo ID chính xác, không bulk theo tên. Ghi trước/sau vào bàn giao. Nếu không có API an toàn thì không mutation, ghi đề xuất.
5. Cập nhật `hybrid-hands/docs/paseo-project-lifecycle.md` (chỉ mô tả cơ chế đang áp dụng, mở đầu bằng tóm tắt), CHANGELOG, bump `plugin.json` 0.32.2 → 0.32.3.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`, `paseo_bridge.mjs`, `actions.py` (chỉ phần finish/ls/watch liên quan workspace)
- `hybrid-hands/tests/test_side_session_paseo.py`, `hybrid-hands/tests/test_side_session_native.py`
- `hybrid-hands/docs/paseo-project-lifecycle.md`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`, `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`
- Runtime Paseo: chỉ thao tác bước 4 trên 6 agent/workspace ghi ở trên.
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` theo hợp đồng side-session.

## KHÔNG ĐƯỢC ĐỤNG

- Không archive/stop/delete agent hay workspace chính, không `paseo project delete`/`removeProject`, không thao tác agent ngoài 6 agent trên.
- Không sửa `lib/side_session/{config,constants,state,tokens,handoff}.py` trừ khi bắt buộc (ghi lý do), không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings, không bật parallel-subagents.
- Không xoá/di chuyển/dọn `output/llm/`. Không sửa repo `live-tiktok-games` (chỉ đọc state side-session của nó).
- Không commit/merge `main`, không cập nhật cài đặt plugin: Opus làm sau khi đọc bàn giao.
- Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol là lead tech/QA: giao code/test/tài liệu L0/L1 qua `hand-ext run --backend auto` theo `ext_hand.order`, review code hand mình giao; chỉ tự làm khi hand-ext lỗi (ghi lý do/mã thoát). Exit 7 chạy doctor trước; exit 8 chờ slot. Phần runtime Paseo (bước 1 đọc source, bước 4 mutation) Sol tự làm, không giao hand.

## KIỂM CHỨNG

- Test hẹp trong lúc làm: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py'` và `-p 'test_side_session_native.py'`.
- Cuối: chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'`; `claude plugin validate hybrid-hands/plugins/hybrid-hands`.
- Mức test: tối thiểu. Ca: (1) start gửi workspace chính + cwd worktree, không tạo workspace riêng; (2) finish chỉ archive agent, không gọi archiveWorkspace; (3) state cũ `paseo_workspace_archived=true` không làm hỏng ls/watch.
- Kiểm thực tế: `paseo workspace ls --json` và `paseo ls -g --json` sau bước 4 cho thấy 6 agent thuộc workspace active.
- Xong khi: test xanh, đã review diff hand, bàn giao ghi lệnh/kết quả thật và phần chưa kiểm chứng (ví dụ chưa nhìn UI).

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: kết luận API (file:line), commit trên nhánh, kết quả test, trạng thái 6 agent trước/sau, phần còn mở.
