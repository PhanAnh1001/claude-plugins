# Xác minh công khai câu 3–5

Ngày đối chiếu: **2026-11-10**. Phạm vi: câu 3–5 mục 7 của [spec.md](spec.md). Đã search và mở nội dung trang chính thức, không dùng snippet làm bằng chứng. Không đọc home/account thật, không chạy CLI thật, không kiểm tra nội dung hook hay MCP thật. Kết luận tài liệu không cấp quyền apply.

## 3. Claude hooks và import

- [Environment variables](https://code.claude.com/docs/en/env-vars#environment-variables): `CLAUDE_CONFIG_DIR` đổi thư mục cấu hình mặc định `~/.claude`; settings/history/plugins ở đó. Biến được nhận từ shell/user/managed settings, bị bỏ qua ở project/local settings. Giá trị đường dẫn trong settings phải tuyệt đối. **Đã xác minh cơ chế**, không phải bằng chứng hook tự ghi đúng account.
- [Hooks reference: security considerations](https://code.claude.com/docs/en/hooks#security-considerations): command hook chạy với toàn quyền user. Interactive chờ workspace trust, kể cả user hooks; `-p`/SDK coi workspace trusted, không hiện dialog. Docs yêu cầu kiểm tra và thử từng command, khuyến nghị đường dẫn tuyệt đối. **Không suy permission rule của tool sẽ cô lập hook**.
- **Suy luận triển khai:** command chứa đường dẫn tuyệt đối source-v1 vẫn trỏ source-v1; đổi `CLAUDE_CONFIG_DIR` không chứng minh có rewrite. Hook dùng biến đó để ghi cũng có thể truy cập account đích. Symlink script không chứng minh nơi ghi, subprocess hay dữ liệu script sẽ đọc. **Blocked từng hook** đến khi brain/chủ tài sản duyệt code, đích ghi, biến môi trường và dependency; hand này không xác nhận hook cụ thể an toàn.
- [Memory: import additional files](https://code.claude.com/docs/en/memory#import-additional-files): `@path` hỗ trợ đường dẫn tuyệt đối/tương đối, tối đa bốn hop; tương đối tính từ file chứa import. Dấu cách cần escape bằng backslash, không bọc cả path trong quote/code fence. User-scope import được tin cậy ở Claude Code; project external import cần duyệt. Cowork có hạn chế riêng, không dùng kết luận này cho Cowork.
- **Triển khai được có điều kiện:** file CLAUDE.md đích một dòng import tuyệt đối nguồn đã duyệt, escape path đúng, chỉ tạo khi thiếu và giữ conflict như spec. Chưa kiểm chứng discovery khi đổi home trên bản CLI cài thực tế; không đồng bộ trust/permissions và không tự bật hooks.

## 4. Codex: path và symlink là hai điều kiện riêng

Các URL developers.openai.com dưới đây đã mở; tại ngày đối chiếu chúng chuyển hướng sang tài liệu chính thức learn.chatgpt.com, URL đích được ghi kèm. Không dùng nguồn bên thứ ba.

| Item | Đã xác minh từ trang đã fetch | Chưa xác minh / quyết định cho overlay spec |
|---|---|---|
| `CODEX_HOME` | [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) → [trang đích](https://learn.chatgpt.com/docs/agent-configuration/agents-md): home mặc định `~/.codex`, đổi được bằng biến này | Chỉ xác minh chọn home; không chia sẻ nguyên home, không đụng config/state |
| Global `AGENTS.md` | Cùng trang: đọc `AGENTS.override.md` trước, nếu không có thì `AGENTS.md`; chỉ file không rỗng đầu tiên ở cấp global | Không thấy bảo đảm symlink/discovery trong trang hoặc search chính thức. **Blocked symlink AGENTS.md riêng**; override có thể che file định đồng bộ |
| `rules/` | [Rules](https://developers.openai.com/codex/rules) → [trang đích](https://learn.chatgpt.com/docs/agent-configuration/rules): scan `.rules` dưới active config layers khi startup; project layer cần trusted | Không thấy bảo đảm symlink. **Blocked rules symlink riêng**; discovery file thật không đủ chứng minh discovery link |
| `agents/` | [Subagents](https://developers.openai.com/codex/subagents) → [trang đích](https://learn.chatgpt.com/docs/agent-configuration/subagents): personal `~/.codex/agents/`, project `.codex/agents/`; mỗi file TOML khai `name`, `description`, `developer_instructions` | Trang không xác nhận symlink, cũng chưa chứng minh discovery personal agents dưới custom home. **Blocked agents symlink riêng** |
| User skills | [Skills](https://developers.openai.com/codex/skills) → [trang đích](https://learn.chatgpt.com/docs/build-skills): user `$HOME/.agents/skills`, repo `.agents/skills`, admin `/etc/codex/skills`; hỗ trợ symlink skill folders và theo target khi scan các vị trí này | **Có bằng chứng symlink + discovery ở các path được liệt kê**. Không thấy `CODEX_HOME` trên trang. **Blocked riêng overlay `~/.codex/skills` → `~/.codex-hand/skills` như spec**; không suy custom home thay `$HOME/.agents/skills` |

[Config reference](https://developers.openai.com/codex/config-reference) → [trang đích](https://learn.chatgpt.com/docs/config-file/config-reference) có `allow_symlinked_codex_home`: điều khiển writable sandbox roots trên macOS, mặc định false; **không phải bằng chứng discovery** cho AGENTS/rules/agents/skills. Không đề xuất đổi khóa này hay config.toml.

**Kết luận P1 Codex:** chưa bật các overlay hiện mô tả trong spec. Skills có cơ chế được tài liệu hóa nhưng path/scope tài khoản không khớp giả định; brain cần chốt lại thiết kế hoặc bằng chứng bổ sung. Không tự thay sang user skills chung vì có thể phá tách tài khoản. “Không thấy bằng chứng” không có nghĩa CLI chắc chắn không hỗ trợ; đây là blocked theo tiêu chí brief.

## 5. Plugin CLI, P4 và MCP

### Scope

[Install and manage plugins](https://code.claude.com/docs/en/discover-plugins#choose-an-install-scope) xác nhận:

| `claude plugin install <id> --scope ...` | Hiệu lực |
|---|---|
| `user` (mặc định) | User ở mọi project; user settings |
| `project` | Repo, shared `.claude/settings.json`; collaborator vẫn phải install |
| `local` | User trong repo; `.claude/settings.local.json` |

**Triển khai được có điều kiện:** adapter phải chọn scope tường minh và cwd repo đúng. Không suy scope từ enabledPlugins hay tự cài user để chữa thiếu project/local. Quyền cài marketplace/plugin vẫn cần duyệt; nghiên cứu này không cài gì.

### Metadata và lệnh chính thức

Đối chiếu [Plugin commands reference](https://code.claude.com/docs/en/plugins/cli-reference), các mục `plugin list`, `plugin marketplace list`, `plugin update`, `plugin validate`:

- `claude plugin list --json`: array; bắt buộc `id:string`, `version:string`, `scope:string`, `enabled:boolean`, `installPath:string`. Optional có `readFromFolder`, `folderVersion`, `projectPath`, `mcpServers`, diagnostics.
- `claude plugin marketplace list --json`: array; `name`, `source`, `repo?`, `url?`, `path?`, `ref?`, `installLocation?` là string; hosted entries có `marketplaceId`, `organizationUuid`, `scope?`, `status`.
- P4: `claude plugin marketplace update <name>`; `claude plugin update <id> --scope <scope>`; `claude plugin validate <path> --strict --json`. Update nhận bản mới nhất marketplace, không chứng minh pin version. Validate không theo symlink bên trong. Reload: phiên mới hoặc `/reload-plugins`.
- Mutation `--json`: chỉ dòng stdout cuối là result (`command`, `outcome`, `message`); có thể có command in trước đó.

**Đề xuất adapter (chính sách của thiết kế, không phải bảo đảm bảo mật của CLI):**

- Capture stdout/stderr trong runtime tin cậy; không echo, log, dump raw hoặc đưa nguyên exception/output vào report. JSON không đồng nghĩa đã loại secret: `mcpServers`, URL, command và diagnostics là vùng không được xuất.
- Projection plugin chỉ `name` từ id hợp lệ, `version`, `enabled`, `scope`, `path`; nhận diện marketplace riêng trong nội bộ. Kiểm kiểu/schema, giới hạn độ dài và ký tự điều khiển; field lạ bỏ qua. Schema sai/CLI thiếu capability → blocked, không fallback đọc sổ cài đặt.
- `enabled` là trạng thái merged, không tự chứng minh ownership theo scope. Giữ các bản cài khác scope riêng; thiếu bằng chứng ownership → blocked thay vì enable/install lại.
- Path nạp: `readFromFolder` nếu có, nếu không `installPath`; version thực ở folder dùng `folderVersion` nếu có. Không có version quan sát được thì unknown, không bịa version. Lọc path ngoài root được duyệt; không công bố personal path ngoài nhu cầu báo cáo.
- Marketplace chỉ xuất tên đã duyệt và action; source URL/path dùng nội bộ sau allowlist. URL chứa credential hoặc nguồn không rõ → blocked, báo reason cố định không kèm giá trị. Không xuất các định danh hosted.
- Không dùng `--available`, `--data-size`, configure hay get MCP để mở rộng dữ liệu. Không auto-accept command-source/headersHelper; capability lạ → blocked. Lọc cả result `message`, không chỉ stdout trước JSON. Mock subprocess bằng fixtures công khai khi triển khai; chưa kiểm runtime/version cài thực tế.

### MCP payload

[MCP: add servers from JSON configuration](https://code.claude.com/docs/en/mcp#add-mcp-servers-from-json-configuration) mô tả JSON positional: `claude mcp add-json <name> '<json>'`, có `--scope`. Trang đã fetch không cung cấp stdin/file option cho toàn bộ payload. `--client-secret` masked prompt/env là cơ chế riêng, không chứng minh hỗ trợ stdin JSON; `plugin configure --values-stdin` cũng không áp dụng cho MCP.

**Blocked apply MCP có payload nhạy cảm**: không truyền qua argv, không phát minh `-`, `@file`, `--stdin` hoặc shell substitution làm đường an toàn. `--mcp-config` chỉ là cấu hình phiên, không thay thế add-json/persistence đã duyệt. Chưa server nào được duyệt nên **toàn bộ MCP apply vẫn blocked**, kể cả payload không secret; chỉ được thiết kế/test bằng fixture giả ở brief triển khai khác. Không gọi account thật, không đọc `.claude.json` để tự lấy payload.

## Kiểm chứng và giới hạn

- Đã đọc AGENTS.md gốc và spec; không có AGENTS.md/CLAUDE.md bổ sung trong nhánh docs áp dụng.
- Search chủ đề OpenAI cụ thể rồi mở trang; tìm bổ sung symlink AGENTS/rules/agents và MCP stdin. Kết luận thiếu bằng chứng chỉ trong tập tài liệu đã đối chiếu, không khẳng định vắng tính năng tuyệt đối.
- Chỉ tạo tài liệu này; không code/test/release, không CLI/account thật. Test mới: 0; dòng test/code thêm: 0/0 (không áp dụng tỷ lệ).
- Chưa xác minh: từng hook, discovery trên binary/version thực tế, metadata trên fixture theo version đích, quyền ghi/apply. Các việc này thuộc brief tiếp theo sau brain duyệt; không có lệnh dài chưa chạy.
