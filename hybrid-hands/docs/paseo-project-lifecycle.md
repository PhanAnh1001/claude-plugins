# Side-session và project Paseo

## Nguyên nhân đã xác minh từ source cài đặt

Nguồn CLI: `@getpaseo/cli/dist`; nguồn daemon dưới
`@getpaseo/cli/node_modules/@getpaseo/server/dist/server/server/`.

- `session/workspace-provisioning/workspace-provisioning-service.js:92,128`:
  directory workspace thiếu `projectId` gọi `findOrCreateProjectForDirectory(cwd)`;
  registry chọn root bằng đường dẫn chính xác, dù Git projectKey có thể trùng.
- `session.js:5149`: directory source truyền `source.projectId` vào provisioning.
  Bridge cũ bỏ trường này nên mỗi worktree phụ có một project persistent riêng.
- `session.js:4893`: project list lấy mọi project chưa archived, không đòi có
  workspace hoạt động. Vì vậy archive agent/workspace rồi mở app lại vẫn còn project.
- `workspace-reconciliation-service.js:190`: project tồn tại cho đến khi explicit
  remove, kể cả không có active workspace; reconciliation giữ identity/membership.
  Đây là record còn tồn tại, chưa có bằng chứng runtime cho việc bị tái tạo.
- `session.js:2716`: removeProject archive toàn bộ active workspace của project,
  đóng agents/terminals rồi remove registry/icon. Không được gọi theo tên project
  hay projectKey chung; có thể ảnh hưởng main hoặc agent đang chạy.

## Thay đổi

Start đăng ký/tìm project bằng `addProject(cfg.repo)` rồi truyền `projectId` vào
directory workspace; cwd vẫn là worktree phụ. Không tạo worktree bằng Paseo,
không sửa UI và không remove project tự động. Client thiếu API hoặc response lỗi
dừng trước createWorkspace. `finish` từ chối state có role main.

Thay đổi này ngăn project riêng mới theo worktree; không di chuyển membership
hay dọn project/workspace legacy. Finish vẫn archive đúng agent, giữ workspace.
Nếu cấu hình repo chính nó là một worktree riêng thì project vẫn theo root cấu
hình đó; không suy root theo remote URL/projectKey.

## Runtime do brain thực hiện

1. Nạp bản plugin đã sửa vào đường CLI thực sự được dùng. Bridge được import mỗi
   lần chạy side-session nên không cần restart daemon để nạp bridge. Watchdog cũ
   có thể vẫn giữ Python module cũ; không restart main/agent để áp bản sửa.
2. Qua installed client, lấy metadata `listProjects`, workspace gồm archived,
   và agent membership/status, không lấy timeline. Đối chiếu projectRootPath/cwd,
   projectId, workspaceId, agentId với state side-session, role và marker done.
3. Chỉ candidate project có root đúng worktree phụ đã done, không main, mọi
   workspace đã archive và không agent đang hoạt động mới được brain cân nhắc
   `removeProject(projectId)`. Trước mutation đọc lại membership; tránh có start
   đồng thời. Không tự dọn project dùng chung hoặc membership chưa chứng minh.
   CLI project delete gọi removeProject; kiểm target/ID, không dùng bulk theo tên.
4. Xác nhận project ID biến mất khỏi listProjects, main/running giữ nguyên,
   worktree/code còn nguyên. Mở lại app và kiểm metadata sau reconciliation.
5. Lần start phụ kế tiếp phải có workspace.projectId bằng project của cfg.repo,
   cwd vẫn đúng worktree; sau done chỉ agent đó archived, main vẫn nguyên.

Không thêm archiveWorkspace vào finish: archive theo scope có thể đóng toàn bộ
agents/terminals của workspace và xóa backing directory nếu Paseo-owned.
`workspace-archive-service.js:134,200` chỉ bảo đảm giữ filesystem khi ownership
tường minh false; chưa có kiểm chứng runtime cho membership/ownership ở máy thật.
Không dùng việc archive 70 workspace trước đó làm bằng chứng project đã remove.

Giới hạn: đã trace server registry/API gốc, chưa có source frontend cài đặt để
chứng minh selector sidebar, chưa chạy runtime/UI hay mutation nào. Cần brain
hoàn tất đối chiếu metadata và dọn legacy an toàn; chưa thể claim hết lỗi thực tế.
