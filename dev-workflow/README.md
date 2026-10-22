# dev-workflow

## Tóm tắt

- **Mục đích:** chuẩn hoá quy trình phát triển phần mềm có AI (Claude Code) cho các dự án của nhóm bằng
  một plugin dùng chung. Mỗi repo khai báo tham số riêng trong `.claude/dev-workflow.toml`.
- **Thành phần:**
  - **13 skill quy trình:** khởi tạo dự án mới, phân luồng L0–L3, spec/plan, điều tra bug, đo đạc, migration, review,
    chốt phiên, Jira, truy vết, khôi phục việc, port giữa repo, chỉnh UI.
  - **Wrapper `dw`:** đọc config, kiểm tra truy vết, chọn template.
  - **Hook SessionStart:** nhắc agent dùng skill, chỉ bật khi repo có config.
  - **Hook báo nạp skill (PreToolUse, tool `Skill`):** luôn bật, mỗi lần nạp skill (của bất kỳ plugin nào) hiện dòng
    "🔧 Skill: <tên skill>". Trong phiên tương tác, dòng này chỉ hiện khi mở transcript (`Ctrl+O`); với
    `claude -p --output-format stream-json` nó là bản tin `informational`. Muốn luôn thấy thì dùng statusline.
  - **Statusline:** không nằm trong plugin này; dùng plugin `statusline` riêng để luôn thấy skill nạp gần nhất
    (mục 1.4).
  - **7 template tài liệu** tiếng Việt.
- **Trạng thái:**
  - Phiên bản 0.6.0, đã chạy thử headless. 7/7 ca phân đúng làn; ca chỉ cập nhật Jira đã sửa để vào thẳng `jira-workflow`.
  - Plugin `jira-tools` có thêm lệnh `jira-cli worklog`, dùng khi chuyển task sang Done.
- **Vị trí:** thư mục `dev-workflow/` của repo `https://github.com/PhanAnh1001/claude-plugins.git`, marketplace
  `dev-workflow-local`.
- **Việc cần làm khi dùng:**
  1. Cài plugin (mục 1).
  2. Thêm `.claude/dev-workflow.toml` vào repo (mục 2).
  3. Bắt đầu việc bằng câu tiếng Việt bình thường. Hook sẽ nhắc agent bắt đầu bằng `dev-triage` và kết thúc bằng `session-closeout`.

## 1. Cài đặt

### 1.1 Cài plugin

Thay `<thư-mục-repo>` bằng nơi clone repo `claude-plugins`:

```bash
claude plugin marketplace add <thư-mục-repo>/dev-workflow
claude plugin install dev-workflow@dev-workflow-local --scope user
```

### 1.2 Cập nhật sau khi sửa plugin

1. Tăng `version` trong `plugins/dev-workflow/.claude-plugin/plugin.json`.
2. Chạy `claude plugin marketplace update dev-workflow-local` rồi `claude plugin update dev-workflow@dev-workflow-local`.
3. Mở phiên Claude Code mới.

### 1.3 Yêu cầu

- Python ≥ 3.11 (có `tomllib`) hoặc `uv`. Wrapper `dw` tự chọn trình thông dịch.
- Plugin `jira-tools` ≥ 1.0.1 nếu dùng Jira.

### 1.4 Hiện skill trên statusline

Chức năng này nằm trong plugin `statusline` (thư mục `statusline/` cùng repo `claude-plugins`, marketplace
`statusline-local`), cài riêng theo máy:

```bash
claude plugin marketplace add <thư-mục-repo>/statusline
claude plugin install statusline@statusline-local --scope user
```

Sau đó gọi skill `statusline:setup` để trỏ statusline của Claude Code sang plugin. Statusline hiện
`🔧 <skill nạp gần nhất>`. Hook PreToolUse của dev-workflow vẫn ghi `🔧 Skill: <tên>` vào transcript và statusline
dùng dòng đó làm nguồn dự phòng.

## 2. Dùng trong một repo

### 2.1 Cấu hình

1. Chép `plugins/dev-workflow/templates/dev-workflow.example.toml` vào `<repo>/.claude/dev-workflow.toml`.
2. Sửa các nhóm khoá:

| Nhóm | Nội dung |
|---|---|
| `[project]` | Tên, ngôn ngữ tài liệu, trần số dòng mỗi file |
| `[gate]` | Lệnh phải xanh trước khi báo xong, lệnh lint |
| `[paths]` | Thư mục spec, plan, ADR, bug, CR; glob SRS; file truy vết; thư mục template của repo |
| `[docs_map]` | Glob code → tài liệu phải cập nhật cùng |
| `[trace]` | Loại ID, glob test, loại bắt buộc có task/test, miễn trừ |
| `[jira]` | Project, hệ số estimate, ngôn ngữ, các mục của mô tả, runbook |
| `[frontend]` | Lệnh chạy dev, các lệnh kiểm tra, ngôn ngữ giao diện |
| `[lanes]` | Số file tối đa của làn L0 |

Nếu repo dùng `.gitignore` chặn `.claude/*`, cần thêm dòng `!.claude/dev-workflow.toml`.

### 2.2 Lệnh `dw`

```bash
"<plugin>/scripts/dw" config [--get section.key] [--json]   # config đã gộp mặc định
"<plugin>/scripts/dw" trace [--write] [--format md|json]      # truy vết ID → task → test
"<plugin>/scripts/dw" template design|plan|bug|cr|adr|traceability
```

Mã thoát của `dw trace`:
- **0:** đủ liên kết.
- **1:** thiếu task hoặc test bắt buộc, hoặc ID định nghĩa trùng.
- **2:** lỗi config hoặc lỗi cú pháp lệnh.

## 3. Danh sách skill

### 3.1 Skill quy trình (plugin, gọi là `dev-workflow:<tên>`)

| Nhóm | Skill | Khi nào dùng |
|---|---|---|
| Mở đầu | `project-bootstrap` | Dự án mới hoặc mới dựng một phần: đi lần lượt 7 giai đoạn từ luật repo, yêu cầu, ADR, backlog Jira, lộ trình MVP, khung code tới vòng dev từng task; dừng ở từng chốt duyệt |
| Mở đầu | `dev-triage` | Mọi việc sửa code/docs: chọn làn L0–L3, artifact và skill cần nạp |
| Thiết kế | `spec-plan` | Làn L2: design (spec), plan, ADR; cổng duyệt; tick ô |
| Thiết kế | `db-migration` | Đổi schema bằng migration mới, không sửa migration đã chạy |
| Điều tra | `bug-investigation` | Lỗi: tái hiện, test đỏ, git history, nguyên nhân, báo cáo, chờ duyệt |
| Điều tra | `measurement-evidence` | Hiệu năng, độ trễ, tính tất định: một biến, n ≥ 3 |
| Thực hiện | `ui-review-iterate` | Chỉnh giao diện: chụp trước/sau, kiểm từng điểm |
| Thực hiện | `port-between-repos` | Chuyển code/docs giữa repo, giữ trích dẫn nguồn |
| Kết thúc | `self-review` | Checklist review diff trước khi báo xong |
| Kết thúc | `trace-check` | Kiểm FR ↔ task ↔ test, miễn trừ, ID trùng |
| Kết thúc | `session-closeout` | Gate, tick plan, truy vết, Jira, báo cáo cuối phiên |
| Kết thúc | `jira-workflow` | Tìm/tạo task, estimate ×hệ số, log work, Done |
| Khôi phục | `resume-work` | Hết context, lỗi 529, hand chết, mất việc |

### 3.2 Skill nghiệp vụ (nằm trong từng repo)

| Repo | Skill |
|---|---|
| `slt-ocr-pro` | `ocr-debug`, `extract-template`, `vlm-change`, `review-export` |
| `tcp-assistant` | `ingest-debug`, `drawing-figure-qa`, `answer-path-perf`, `rag-question-eval`, `infra-triage` |

## 4. Phát triển plugin

- Luật cho agent: [AGENTS.md](AGENTS.md).
- Test (chạy từ gốc repo `claude-plugins`): `python3.11 -m unittest discover -s dev-workflow/tests`.
- Validate (chạy từ gốc repo `claude-plugins`): `claude plugin validate dev-workflow` và
  `claude plugin validate --strict dev-workflow/plugins/dev-workflow`.

## 5. Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [docs/ai-dev-workflow.md](docs/ai-dev-workflow.md) | Workflow theo phương pháp ai4ba: bước làm tay, phần AI bỏ/gộp, `.md` có cấu trúc, mức tự động, cổng duyệt |
| [docs/skill-proposal.md](docs/skill-proposal.md) | Đề xuất bộ skill từ lịch sử Claude Code: hiện trạng, nguyên tắc chia, lộ trình |
| [docs/plans/2026-10-09-build-dev-workflow.md](docs/plans/2026-10-09-build-dev-workflow.md) | Plan xây plugin và các quyết định sau khi chạy thử |
