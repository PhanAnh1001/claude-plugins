---
id: plan-build-dev-workflow
title: Xây plugin dev-workflow và skill nghiệp vụ
status: completed
last-reviewed: 2026-10-09
workflow: plan
---

# Xây plugin dev-workflow và skill nghiệp vụ

## Tóm tắt

- **Mục tiêu:** hiện thực toàn bộ đề xuất trong [skill-proposal.md](../skill-proposal.md) và
  [ai-dev-workflow.md](../ai-dev-workflow.md).
- **Quyết định đã chốt:**
  - Plugin `dev-workflow` đặt trong repo này. Repo đồng thời là marketplace.
  - Skill, template và script viết bằng tiếng Anh vì dành cho agent. Mô tả skill có thêm cụm từ
    tiếng Việt người dùng hay gõ. Tài liệu do skill sinh ra viết bằng tiếng Việt.
  - Mỗi repo khai báo tham số trong `.claude/dev-workflow.toml`. Đường dẫn docs theo cấu trúc sẵn có
    của repo, không ép dùng `docs/<feature>/` của ai4ba.
  - Jira nằm trong `dev-workflow` (skill `jira-workflow` gọi `jira-cli` của plugin `jira-tools`). Không sửa `jira-tools`.
  - Gợi ý dùng skill bằng hook SessionStart của chính `dev-workflow`, chỉ bật khi repo có `.claude/dev-workflow.toml`.
    Không sửa `parallel-subagents`.
  - Skill nghiệp vụ đặt trong `.claude/skills/` của `slt-ocr-pro` và `tcp-assistant`. Không commit hai repo đó.
  - Commit và push repo này khi xong.
- **Cách chạy thử:** unit test script, validate plugin, cài plugin cục bộ, chạy thử headless trên tình huống mẫu.

## Cấu trúc

```text
.claude-plugin/marketplace.json
plugins/dev-workflow/
  .claude-plugin/plugin.json
  skills/<name>/SKILL.md
  templates/            # design, plan, traceability, cr, bug, adr, dev-workflow.toml mẫu
  scripts/              # dw_config.py, trace_check.py, session-start.sh
  hooks/hooks.json
tests/                  # python3 -m unittest discover -s tests
```

## Việc cần làm

### A. Khung plugin, template, script

- [x] A1. `marketplace.json`, `plugin.json`, `AGENTS.md` và `CLAUDE.md` cho repo
- [x] A2. Template: `design.md`, `plan.md`, `traceability.md`, `cr.md`, `bug.md`, `adr.md`, `dev-workflow.example.toml`
- [x] A3. `scripts/dw_config.py`: đọc và kiểm tra `.claude/dev-workflow.toml`, có giá trị mặc định
- [x] A4. `scripts/trace_check.py`: quét ID trong SRS, plan và test → sinh `traceability.md`, mã thoát ≠ 0 khi thiếu liên kết
- [x] A5. Hook SessionStart: gợi ý `dev-triage`/`session-closeout` khi có config, fail-open
- [x] A6. Unit test cho A3–A5, chạy xanh

### B. Skill quy trình (plugin)

- [x] B1. `dev-triage`
- [x] B2. `spec-plan`
- [x] B3. `self-review`
- [x] B4. `session-closeout`
- [x] B5. `jira-workflow`
- [x] B6. `bug-investigation`
- [x] B7. `measurement-evidence`
- [x] B8. `db-migration`
- [x] B9. `resume-work`
- [x] B10. `port-between-repos`
- [x] B11. `ui-review-iterate`
- [x] B12. `trace-check` (hướng dẫn chạy script A4)

### C. Skill nghiệp vụ `slt-ocr-pro`

- [x] C1. `.claude/dev-workflow.toml`
- [x] C2. `ocr-debug`, `extract-template`, `vlm-change`, `review-export`

### D. Skill nghiệp vụ `tcp-assistant`

- [x] D1. `.claude/dev-workflow.toml`
- [x] D2. `ingest-debug`, `drawing-figure-qa`, `answer-path-perf`, `rag-question-eval`, `infra-triage`

### F. Bổ sung phát sinh khi review

- [x] F1. Wrapper `scripts/dw` tự chọn Python có `tomllib` (máy chỉ có `python3` 3.9), fallback `uv`; thêm khoá `[paths].migrations`, `[frontend]`
- [x] F2. Sửa mọi skill gọi `dw config` / `dw trace` thay cho `python3 …/dw_config.py`
- [x] F3. `trace_check`: miễn trừ `[trace.waivers]`, phát hiện ID trùng và ID sai định dạng
- [x] F4. `jira-cli worklog` trong plugin `jira-tools` (CLI cũ không log work được; các phiên trước phải gọi REST tay), cập nhật skill `jira-workflow`
- [x] F5. `dw template <name>`: lấy template của repo nếu có (design ↔ `spec.md`), thiếu thì dùng template plugin; skill gọi lệnh này

### E. Chạy thử, chọn phương án, phát hành

- [x] E1. Brain review toàn bộ diff (A–D)
- [x] E2. Validate plugin và cài cục bộ
- [x] E3. Chạy thử headless: triage 3 tình huống mẫu, trace-check trên fixture, kích hoạt skill bằng cụm từ tiếng Việt
- [x] E4. Sửa theo kết quả chạy thử, chọn phương án tốt nhất, ghi lại quyết định vào plan
- [x] E5. Cập nhật `README.md`: cách cài, cách dùng, danh sách skill
- [x] E6. Commit và push repo này

### G. Bổ sung sau phát hành

- [x] G1. Hook báo nạp skill (0.2.0)
- [x] G2. Statusline hiện skill gần nhất (0.3.0)
- [x] G3. Chuyển last-skill sang plugin statusline (claude-plugins), gỡ khỏi dev-workflow (0.4.0)

## Kiểm chứng

- [x] `python3.11 -m unittest discover -s tests` xanh (71 test)
- [x] Validate plugin không lỗi
- [x] Mỗi `SKILL.md` ≤ 400 dòng, có frontmatter `name` và `description`
- [x] Không có đường dẫn tuyệt đối của máy trong file commit

## Quyết định sau chạy thử

### Kết quả chạy thử (E3)

- **Script và hook:** đúng kỳ vọng ở mọi biến thể. Mã thoát của `dw trace`: thiếu test hoặc ID trùng → 1;
  chỉ có waiver hoặc ID sai định dạng → 0 kèm cảnh báo; lỗi config → 2. Hook chỉ in khi repo có config.
- **Kích hoạt skill:** chạy 7 ca `claude -p` headless, mỗi ca khoảng 0,27 USD. Cả 7 ca phân đúng làn; 6/7 ca gọi đúng
  skill đầu tiên. Ca "update jira theo kết quả" bị `dev-triage` giành, dù hành vi vẫn đúng (hỏi project,
  không bịa).

### Quyết định

| Vấn đề | Phương án chọn | Lý do |
|---|---|---|
| `python3` của máy là 3.9, không có `tomllib` | Wrapper `dw` tự chọn Python ≥ 3.11, nếu không có thì dùng `uv` | Không bắt người dùng cài thêm; skill chỉ gọi một lệnh |
| `jira-cli` không log work được | Thêm `jira-cli worklog` vào `jira-tools` 1.0.1, có đọc lại remaining | Các phiên trước phải gọi REST bằng tay; luật Done yêu cầu log giờ thật |
| Repo đặt tên template khác plugin (`spec.md`) | `dw template <name>` lấy template của repo nếu có, thiếu thì dùng template plugin | Giữ được frontmatter riêng của repo mà vẫn đủ template bug/cr/traceability |
| FR có lý do không cần test tự động | `[trace].waivers` (ID → lý do), hiện trong báo cáo | Lý do miễn trừ được ghi lại và người duyệt nhìn thấy, không im lặng bỏ qua |
| Skill Jira bị `dev-triage` giành | Hook và description tách vai: việc chỉ đụng Jira, chốt phiên hay truy vết thì vào thẳng skill tương ứng | Kết quả chạy thử ca e |
| Chạy lại sau khi sửa: "tạo task jira cho việc sửa upload" vẫn qua `dev-triage` trước rồi mới đến `jira-workflow` | Giữ nguyên | Muốn estimate task Jira thì phải biết phạm vi và làn trước; các ca e, e2 (chỉ đụng Jira) đã vào thẳng `jira-workflow` |
| `tcp-assistant` dùng `UC-01`/`Qn`, không có FR | Giữ `id_types` mặc định, ghi chú trong config | Thêm UC chỉ sinh 24 cảnh báo sai định dạng, 0 ID hợp lệ |
| `tcp-assistant` gitignore `.claude/*` | Thêm `!.claude/dev-workflow.toml` | Để config commit được |
| Skill cũ của `tcp-assistant` trùng skill chung | Giữ nguyên (`measurement-evidence`, `resume-loop`) | Không xoá việc của người dùng; gỡ sau khi đã dùng thử plugin |
| Người dùng không biết skill có thực sự được dùng hay không | Hook PreToolUse khớp tool `Skill`, chỉ trả `systemMessage` "🔧 Skill: <tên>", luôn bật, fail-open | Chạy thử headless thấy thông báo hiện ngay khi nạp skill; hook không chặn hay đổi quyền tool |
| `systemMessage` của PreToolUse có chạy, transcript ghi lại, nhưng TUI không hiện | Statusline đọc transcript: `scripts/last-skill.sh` đọc ngược từ cuối file (tối đa 4 MB), lấy tên từ tool_use `Skill`, dự phòng bằng `hook_system_message`, in `🔧 <tên>` | Statusline luôn hiện, kể cả ở focus mode; không cần hook nên thấy cả skill của plugin khác; chạy khoảng 40 ms với transcript 2,5 MB |
| Có nên chuyển hook báo nạp skill sang PostToolUse | Giữ PreToolUse | Thử thật (15/10): cả `PreToolUse:Skill says: …` và `PostToolUse:Skill says: …` đều chỉ hiện trong `Ctrl+O`, không hiện ở khung chat; PostToolUse không hiện rõ hơn |
| `last-skill` nằm ở cả dev-workflow và statusline | Chỉ giữ trong plugin statusline | statusline là chức năng cá nhân, cài riêng theo máy; tránh hai bản code lệch nhau |
