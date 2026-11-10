## Tóm tắt
- Kết quả: **bị chặn tại gate API**, dừng theo điều kiện rõ trong brief; chưa sửa plugin, chưa mutation Paseo.
- Paseo CLI cài đặt đúng **0.15.0**: `createAgent({workspaceId, cwd})` ghi đè cwd agent bằng cwd workspace (`session.js:3325–3346`); không đáp ứng workspace chính + cwd worktree.
- `createWorkspace({source, agent})` cũng đi qua cùng hàm tạo agent (`session.js:3109–3118`); không khắc phục được gate.
- Probe hàm source cài đặt với fixture giả: **PASS**, tái hiện cwd bị ghi đè; không tạo agent/workspace hay gọi model.
- Có API `inspectWorkspaceRecovery` / `restoreWorkspace`; cả 6 workspace trả `recoverable/action=unarchive`.
- 6 agent trước/sau: giữ nguyên ID/membership, archivedAt=null; 2 running, 4 idle lúc đọc; workspace vẫn không nằm trong 8 workspace active.
- File ghi: chỉ bàn giao này và `sol-ws-chung.done`; lý do: ghi bằng chứng blocker và báo hoàn tất theo hợp đồng.
- Nhánh `side/sol-ws-chung`, HEAD `7d170ec39f9204b12509cf3630daf2cd8f18f674`; **không tạo commit**, không push/merge/cập nhật cài đặt.
- Chưa chạy unit suite / plugin validate vì dừng trước sửa code; chưa nhìn UI.
- Còn mở: Opus chọn hướng xử lý API/cwd và quyết định tách khôi phục 6 workspace khỏi gate DỪNG; không tự chọn phương án khác.

## Phạm vi và quyết định dừng

Brief ghi: “Nếu Paseo 0.15.0 không cho agent có cwd khác thư mục workspace thì DỪNG, ghi bằng chứng (file:line source đã cài) và đề xuất phương án vào bàn giao, không tự chọn hướng khác.”

Đường public client `createAgent` mà bridge hiện dùng không giữ được cwd worktree khi gắn workspace chính. Do đó dừng trước bước sửa start/finish, trước giao hand và trước mọi mutation runtime, kể cả khôi phục. Không đổi version/changelog/lifecycle để tránh mô tả một cơ chế chưa áp dụng. Không sửa code luồng C, state repo tiktok, cài đặt hay config. Không spawn hand vì chưa có gói triển khai hợp lệ vượt gate; không có lỗi hand-ext hay ngoại lệ tự code.

## Bằng chứng source đã cài

Gốc package: `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`.
`package.json` báo `version=0.15.0`.
Các đường dưới đây tính từ gốc package, không phải source repository trên mạng.

1. `node_modules/@getpaseo/client/dist/daemon-client.d.ts:194–202`: options có cả cwd, workspaceId, callerAgentId; sự hiện diện trong type **không chứng minh** server giữ cwd.
2. `node_modules/@getpaseo/client/dist/daemon-client.js:1919–1931`: createAgent gọi creations.createAgent với config từ options. Nhánh legacy tại `1933–1942` cũng truyền config/workspaceId sang request.
3. `node_modules/@getpaseo/server/dist/server/server/session.js:3010–3027`: modern creation cuối cùng gọi createSessionAgent.
4. `node_modules/@getpaseo/server/dist/server/server/agent/create-agent/intent.js:18–26`: explicitWorkspaceId gọi resolveWorkspace; nhánh caller mặc định lấy cả workspaceId/cwd caller.
5. **`node_modules/@getpaseo/server/dist/server/server/session.js:3325–3334`**: với workspaceId tường minh, đọc workspace active rồi `return { workspaceId, cwd: workspace.cwd }` (dòng 3333).
6. **Cùng file `session.js:3346`**: `config = { ...config, cwd: intent.cwd }`; cwd worktree truyền vào bị thay. Dòng `3251–3270` dùng resolved config này để tạo agent thực.
7. Cùng file `session.js:3101–3118`: createWorkspace kèm agent chỉ cho cwd bên trong source, tính relative, rồi gọi createSessionAgent với workspaceId; tiếp tục gặp cùng phép ghi đè. Hai worktree sibling cũng không vượt được kiểm tra `..` ở `3105–3108`.
8. `node_modules/@getpaseo/client/dist/daemon-client.d.ts:952–955` và `node_modules/@getpaseo/server/dist/server/server/agent/lifecycle-command.js:62–74`: updateAgent chỉ đổi name/labels. Chưa tìm thấy API public client chuyển workspace cho agent hiện có. Không dùng sửa registry/storage để giả lập di chuyển.

Có một đường MCP nội bộ **khác** với public client trên: `node_modules/@getpaseo/server/dist/server/server/agent/create-agent/create.js:139–144` có resolver giữ resolvedCwd khi explicit workspace, rồi dùng intent.cwd ở `163`. Điều này không thay đổi kết luận về bridge/client đang dùng; **không kết luận mọi đường nội bộ của Paseo đều cấm cwd khác**. Chưa trace đủ điều kiện public transport, validation/membership hay runtime để đưa MCP vào triển khai; chuyển sang đường này là thay đổi giải pháp, chỉ ghi đề xuất.

## Probe và kiểm chứng thực chạy

- Đọc source bằng `rg`, `nl -ba ... | sed -n ...` trên các file source cụ thể; không đọc credential/.env/transcript/timeline.
- `node --input-type=module` đọc chính đoạn `resolveSessionCreateAgentIntent` từ source cài đặt, import `resolveCreateAgentIntent`, chạy với fake registry và fixture công khai: requested cwd `/public-fixture/project-wt/sol`, workspace cwd `/public-fixture/project`, workspaceId `wks_public_fixture`.
- Hai assert kiểm config.cwd thành `/public-fixture/project` và workspaceId vẫn `wks_public_fixture`: **PASS**, Node exit 0. Probe chỉ hàm resolver, không nối daemon hay tạo agent. Đây là bằng chứng hành vi resolver, chưa phải end-to-end start thật.
- Hai lần `paseo workspace ls --json`: exit 0, **8 active workspaces**, không có 6 workspace mục tiêu.
- Hai lần `paseo ls -g --json`: exit 0, **25 agents**, lọc đúng 6 tên và đối chiếu UUID; không đọc hội thoại.
- Installed official client `fetchAgent({agentId})` và `inspectWorkspaceRecovery(workspaceId)` đọc tuần tự đúng 6 cặp ID: exit 0, kết quả trong bảng dưới. Chỉ xuất metadata ID/status/cwd/archivedAt và recovery action.
- `git status --short` đầu và cuối sạch; không thay đổi trong worktree.
- Không chạy `test_side_session_paseo.py`, `test_side_session_native.py`, `test_side_session*.py` hay `claude plugin validate`: dừng tại gate source trước implementation. Không claim test xanh cho tính năng chưa làm.
- Không có tiến trình nền do phiên này tạo; không gọi API model, không có token/quota usage hand để báo (?).

## API khôi phục đã xác minh, chưa gọi mutation

- `node_modules/@getpaseo/client/dist/daemon-client.d.ts:969–970`: inspectWorkspaceRecovery / restoreWorkspace.
- `node_modules/@getpaseo/client/dist/daemon-client.js:2135–2156`: inspect gửi `workspace.recovery.inspect.request`, restore gửi `workspace.recovery.restore.request`, kiểm accepted.
- `node_modules/@getpaseo/server/dist/server/server/session/workspace-recovery/workspace-recovery-service.js:37–38`: directory còn tồn tại thì action **unarchive**.
- Cùng file `:65–74`: restore chỉ recreate worktree khi action=restore; action=unarchive gọi deps.unarchiveWorkspace trên workspace hiện có.
- `node_modules/@getpaseo/server/dist/server/server/session.js:363–370`: callback gọi ensureWorkspaceRecordUnarchived; `:4476–4491` phát cập nhật sau recovery.
- Không gọi restoreWorkspace, archive/cancel/stop/delete/move hay sửa state nào. Việc khôi phục đã được giao trong brief, nhưng phiên dừng toàn bộ thay đổi tại gate DỪNG, không tự diễn giải thành cho phép bỏ qua gate để tiếp tục mutation.

## Sáu agent: trước / sau

Lần đọc metadata tại 2026-11-09T13:31:25+07:00. Các UUID lấy từ state side-session chỉ đọc rồi đối chiếu daemon. Mọi state đều status=done, role rỗng, paseo_workspace_archived=true; mọi daemon agent archivedAt=null. Trạng thái chạy là snapshot, có thể tự thay đổi do công việc phiên khác.

| Agent | Agent ID | Workspace ID | Daemon status lúc đọc | Trước → sau do phiên này |
|---|---|---|---|---|
| SOL-WP72 | 82585551-59a1-4210-9caa-b69e67720fd2 | wks_e6b8efbc2af23da5 | idle | workspace archived → giữ nguyên; recovery unarchive |
| SOL-RV67 | 660777f7-a6f3-4f2f-8e21-2d02315d928f | wks_00a33c23fc7872f6 | running | workspace archived → giữ nguyên; recovery unarchive |
| SOL-RV77 | bd1490a5-8a8b-43a3-ab5a-5d541566f8ef | wks_f7f6ed3fecdf9cb3 | idle | workspace archived → giữ nguyên; recovery unarchive |
| SOL-RV66 | 3e5d6d56-7540-43fb-9fff-7bb05f8507e7 | wks_495046b6374b5ad4 | running | workspace archived → giữ nguyên; recovery unarchive |
| SOL-WP67 | 1fa6fcfa-e2cc-42b2-8ed4-9440735e4795 | wks_dd3da0d2482d4537 | idle | workspace archived → giữ nguyên; recovery unarchive |
| SOL-WP66 | 487fd236-25a5-4830-af9d-a465aaf93189 | wks_5c40f0f05b7dcbbd | idle | workspace archived → giữ nguyên; recovery unarchive |

Workspace main vẫn thấy active qua CLI: opus tiktok `wks_4667ce1947e172b2`, sol tiktok `wks_beb1925db9835946`, opus plugin `wks_95ace75b24e9d085`, sol plugin `wks_b791dd57b1641d61`. Không thao tác lên các workspace/agent chính.

## Đề xuất để Opus chốt, chưa thực hiện

1. Xử lý contract public client/server Paseo để explicit workspaceId có thể giữ cwd hợp lệ của worktree (upstream fix/nâng bản có bằng chứng). Sau đó mới triển khai start theo workspace chính, finish chỉ archive agent, compatibility flag và bộ test trong brief, bump 0.32.3 theo lịch release thực tế.
2. Hoặc trace riêng đường MCP giữ cwd nêu trên rồi trình thay đổi giải pháp; chưa đủ bằng chứng để tự chuyển bridge. Không dùng labels đổi membership, không sửa daemon storage, không tạo agent thay thế làm mất hội thoại.
3. Để cứu sidebar ngay độc lập với việc gom workspace, có thể tách gói recovery: đọc lại chính xác từng agent/workspace + inspect(action=unarchive), gọi `restoreWorkspace(exactWorkspaceId)` lần lượt trên 6 ID, kiểm agent ID/cwd/membership/archivedAt giữ nguyên và workspace active sau mỗi thao tác. Đây là fallback đã nêu trong brief, chưa được thực hiện trong phiên bị gate DỪNG này. Không tạo lại worktree nếu inspect chuyển thành action=restore; dừng phần đó để tránh ghi repo tiktok.
4. UI chưa nhìn; metadata thành active chưa tự chứng minh app đang mở đã cập nhật sidebar. Chưa xác minh hot load/cài đặt vì không release.
