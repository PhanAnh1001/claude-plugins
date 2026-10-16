# claude-plugins

## Tóm tắt

- **Mục đích:** nơi chứa các plugin Claude Code cá nhân. Mỗi plugin là **một marketplace tự host
  riêng**, nằm trong một thư mục con cùng tên, có README riêng.
- **Git:** cả thư mục này là **một git repo duy nhất** (remote
  `https://github.com/PhanAnh1001/claude-plugins.git`) chứa mọi plugin; các thư mục plugin không
  có git repo riêng. `parallel-subagents` trước đây là repo riêng `brain-hand-plugins`, `dev-workflow` cũng từng là
  repo riêng, nay đều gộp vào đây; lịch sử git cũ của chúng (và của `jira-tools`) không được giữ.
- **Plugin hiện có (5):** `dev-workflow`, `jira-tools`, `parallel-subagents`, `statusline`,
  `summary-first-docs`.
- **Cài đặt:** clone repo này, rồi mỗi plugin hai lệnh
  `claude plugin marketplace add <thư-mục-repo>/<plugin>` rồi
  `claude plugin install <plugin>@<plugin>-local --scope user`; chi tiết trong README của
  từng thư mục con.
- **Việc cần làm khi sửa plugin:** tăng `version` trong `plugin.json`, chạy
  `claude plugin validate`, rồi `claude plugin marketplace update` và `claude plugin update`.

## Danh sách plugin

| Thư mục | Marketplace | Plugin | Nội dung |
|---|---|---|---|
| `dev-workflow/` | `dev-workflow-local` | `dev-workflow` | quy trình phát triển có AI: 12 skill (phân làn L0–L3, spec/plan, điều tra bug, truy vết, chốt phiên, Jira), wrapper `dw`, hook SessionStart và PreToolUse(Skill) |
| `jira-tools/` | `jira-tools-local` | `jira-tools` | CLI Jira Server (REST v2, PAT Bearer), skill `jira`, SessionStart hook |
| `parallel-subagents/` | `parallel-subagents-local` | `parallel-subagents` | điều phối brain/hand: agent `hand`, hook bơm policy |
| `statusline/` | `statusline-local` | `statusline` | thanh trạng thái 3 dòng (thư mục/nhánh git; model, tokens, ctx, skill gần nhất; rate limit), skill `setup` |
| `summary-first-docs/` | `summary-first-docs-local` | `summary-first-docs` | bốn skill tài liệu dùng chung mọi dự án |

### summary-first-docs

Bốn skill, không hook, không agent; đường dẫn và ngôn ngữ theo `AGENTS.md` / `CLAUDE.md` của
dự án nếu có:

- `structuring-documents`: mọi tài liệu mở bằng tóm tắt (mục đích, kết luận/quyết định, con số
  chính, việc người đọc cần làm), trình bày top-down nhóm -> nhánh.
- `citing-sources`: mỗi số liệu, sự kiện, kết luận có link `http(s)` nguồn mới nhất kèm ngày dữ
  liệu; nhãn chưa xác minh, vendor tự công bố, suy luận, đã bị thay, chưa có nguồn internet.
- `documenting-solutions`: mỗi giải pháp đang hiệu lực một file
  `docs/solutions/<group>/<branch>/<solution>.md`, mục lục `docs/solutions/README.md`.
- `saving-research`: nghiên cứu nhiều nguồn lưu ở `docs/research/<YYYY-MM-DD>-<slug>/`
  (`report.md`, `notes/<topic>.md`) và mục lục `docs/research/README.md`.

## Cài đặt

Thay `<thư-mục-repo>` bằng nơi clone repo này:

```sh
git clone https://github.com/PhanAnh1001/claude-plugins.git <thư-mục-repo>
claude plugin marketplace add <thư-mục-repo>/summary-first-docs
claude plugin install summary-first-docs@summary-first-docs-local --scope user
claude plugin list
```

Các plugin còn lại cài tương tự với thư mục và tên marketplace trong bảng trên; `statusline`
cần thêm một bước setup (skill `statusline:setup`), xem `statusline/README.md`.

## Cập nhật

```sh
claude plugin validate <thư-mục-repo>/<thư-mục-con>
claude plugin validate <thư-mục-repo>/<thư-mục-con>/plugins/<plugin>
claude plugin marketplace update <plugin>-local
claude plugin update <plugin>@<plugin>-local
```

Marketplace kiểu thư mục chép plugin vào cache lúc cài; luôn tăng `version` trước khi cập nhật
để bản cache được làm mới.
