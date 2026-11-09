# Side-session và lifecycle workspace Paseo

Tóm tắt: start đăng ký `addProject(cfg.repo)` rồi tạo workspace directory riêng cho
worktree phụ; finish chỉ archive workspace đó sau khi chứng minh nó riêng (kể cả
agent archived khác); nếu người dùng unarchive agent đã done, `side-session ls`/watch
tự revive workspace riêng; khi agent archive lại, chỉ archive lại workspace
(`revive`/`rearchive`). Không recreate worktree, không archive phiên chính, không
tự finish lại phiên vừa revive dù `.done` cũ còn.

## Nguyên nhân đã xác minh từ source cài đặt

Nguồn CLI: `@getpaseo/cli/dist`; nguồn daemon dưới
`@getpaseo/cli/node_modules/@getpaseo/server/dist/server/server/`.

- `session/workspace-provisioning/workspace-provisioning-service.js:92,128`:
  directory workspace thiếu `projectId` gọi `findOrCreateProjectForDirectory(cwd)`;
  registry chọn root bằng đường dẫn chính xác, dù Git projectKey có thể trùng.
- `session.js:5149`: directory source truyền `source.projectId` vào provisioning
  (`createWorkspaceForDirectory`).
  Bridge cũ bỏ trường này nên mỗi worktree phụ có một project persistent riêng.
- `session.js:4893` (`handleProjectListRequest`): project list lấy mọi project chưa
  archived, không đòi có workspace hoạt động. Vì vậy archive agent/workspace rồi mở
  app lại vẫn còn project.
- `workspace-reconciliation-service.js`: project tồn tại cho đến khi explicit
  remove, kể cả không có active workspace; reconciliation giữ identity/membership.
- `session.js`: removeProject archive toàn bộ active workspace của project, đóng
  agents/terminals rồi remove registry/icon. Không được gọi theo tên project hay
  projectKey chung; có thể ảnh hưởng main hoặc agent đang chạy.
- `session.js:3333`: resolve workspace trả `return {workspaceId, cwd: workspace.cwd}`
  cho phiên phụ.
- `session.js:3346`: `config = {...config, cwd: intent.cwd}` gán `config.cwd` về cwd
  của workspace chính. Vì cwd bị ép về main, phiên phụ không gom vào workspace chính
  mà dùng workspace riêng.
- `session/workspace-recovery/workspace-recovery-service.js:20-25`: workspace chưa
  archived trả `{kind:"unavailable", reason:"workspace_not_archived"}`; đây là kiểm
  tra "workspace đang active" của bridge.
- `workspace-recovery-service.js:37-38`: workspace archived còn thư mục trả
  `{kind:"recoverable", action:"unarchive"}`; restore chỉ unarchive record.
- `workspace-recovery-service.js:65-74`: `action:"restore"` tạo lại worktree; bridge
  từ chối loại này (`WORKSPACE_RECOVERY_UNSUPPORTED`), không recreate worktree.
- Client cài đặt: `inspectWorkspaceRecovery` trả payload `state` trực tiếp và
  `restoreWorkspace` trả void (throw khi host từ chối).

## Start và finish

Start đăng ký/tìm project bằng `addProject(cfg.repo)` rồi truyền `projectId` vào
directory workspace; cwd vẫn là worktree phụ. Không tạo worktree bằng Paseo, không
sửa UI và không remove project tự động. Client thiếu API hoặc response lỗi dừng
trước createWorkspace. `finish` từ chối state có role main.

`finish` archive đúng agent (yêu cầu `archivedAt`) rồi archive workspace riêng. Kiểm
riêng dùng `fetchAgents` gồm cả archived sibling; chỉ khi không agent khác cùng
`workspaceId` mới mutation. Archive theo scope có thể đóng toàn bộ agents/terminals
của workspace, nên workspace dùng chung không bao giờ bị archive.

## Revive và rearchive sau done

Trạng thái done của phiên Paseo lưu `paseo_workspace_archived` và `paseo_revived`.
`side-session ls` đọc archive state của toàn bộ agent bằng một bridge invocation
`agent-archive-states` (`fetchAgents(includeArchived:true)`, có phân trang) trước khi
đối soát. Chỉ gọi revive cho agent đã unarchive có workspace flag archived, hoặc
rearchive cho phiên revived có agent đã archive. Snapshot thiếu/lỗi, lệch target hay
workspace thì bỏ toàn bộ đối soát lượt đó với một warning, giữ nguyên state.
Watch một phiên giữ flow riêng hiện có, không đọc directory theo lô.
Cả hai chỉ đối soát khi side-session chạy:

1. `status=done`, chưa revived, workspace đã archive: bridge `revive` fetch đúng
   agent id và workspace đã lưu trước mọi mutation. Agent còn `archivedAt != null`
   thì `{revived:false}`, không restore. Agent đã unarchived: inspect recovery; chỉ
   `action:"unarchive"` mới `restoreWorkspace`, sau đó inspect và kiểm
   `workspace_not_archived` đúng workspace trước khi trả `{revived:true}`. Workspace
   đã active trả `{revived:true}` không restore; `action:"restore"` hay shape khác
   trả `WORKSPACE_RECOVERY_UNSUPPORTED`.
2. Revive thành công: `archived=false, revived=true`, lưu state. Phiên này không
   bao giờ chạy finish tự động, kể cả còn `.done` cũ. Mỗi lần `ls` được gọi đều đối
   soát lại state này; watch tiếp tục chạy trong lúc revived để thấy lần archive sau
   của agent.
3. Agent archive lại: bridge `rearchive` fetch đúng agent/workspace; nếu agent còn
   archived (`archivedAt != null`) và workspace riêng, chỉ `archiveWorkspace`. Không
   `cancelAgent`/`archiveAgent`. Thành công: `archived=true, revived=false`, lưu state.
   Agent chưa archived thì không mutation.

Lỗi bridge/identity giữ nguyên state và in một dòng warning theo dạng `workspace reconcile lỗi`;
lần ls/watch sau retry. `status` vẫn `done` nên slot/cap/start không đổi. Mỗi lần gọi
`ls`/watch chỉ finish hoặc đối soát một bước; phiên vừa finish trong vòng đó không
revive ngay, và phiên vừa rearchive không revive/finish lại trong cùng vòng.

## Runtime

Runtime và cập nhật plugin cho các repo đang dùng do Opus thực hiện sau khi merge; tài
liệu này chưa kiểm chứng lần chạy thật đó.

## Giới hạn

Chỉ `ls`/watch thực hiện revive/rearchive; restart agent không tự mở lại workspace.
Không recreate worktree, không phục hồi thư mục đã mất (`workspace_directory_missing`
vẫn là unsupported), không tự dọn project/workspace legacy. Watch chỉ thấy archive sau
nếu state còn revived khi có lần đối soát; `ls` đối soát mỗi lần gọi. Đã trace source
server/client cài đặt; chưa chạy mutation runtime thật hay UI.
