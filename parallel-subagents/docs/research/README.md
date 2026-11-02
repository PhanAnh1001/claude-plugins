# Nghiên cứu của plugin parallel-subagents

## Tóm tắt

- **Mục đích:** lưu các nghiên cứu đo đạc làm căn cứ cho policy của plugin; không được ship cùng plugin.
- **Số nghiên cứu:** 1.
- **Cách thêm:** tạo `docs/research/<YYYY-MM-DD>-<slug>/report.md` + `notes/<chủ-đề>.md`, rồi thêm mục vào đầu danh sách dưới (mới nhất trước).

## Danh sách

### 2026-11-02 - Prompt cache của subagent

- **Câu hỏi:** chi phí prompt cache của hand lãng phí ở đâu và policy nào giảm được?
- **Kết luận:**
  - Subagent ghi cache TTL 5 phút (1,25x giá input), read 0,05x với Opus 5.5 [docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [pricing](https://www.anthropic.com/pricing) (chưa kiểm chứng trên internet; tài liệu skill claude-api, Claude Code 2.1.316, 2026-10-06).
  - 655 lần miss lớn sau nghỉ 5–60 phút: 341 do resume khi cache nguội, 313 do Bash dài ở cuối hand to (số đo nội bộ, transcript 2026-09-30 → 2026-11-02; chưa có nguồn internet).
  - Policy 2.1.0 ước tính giảm ~11–12% chi phí subagent (suy luận, chưa đo; đo lại 2026-11-16).
  - Phụ: hạ ngưỡng auto-compact main thread giảm 9,7% chi phí/request (mẫu nhỏ, số đo nội bộ).
- **Quyết định:** policy 2.1.0, xem [solutions](../solutions/README.md).
- **Links:** [report](2026-11-02-subagent-prompt-cache/report.md), [notes](2026-11-02-subagent-prompt-cache/notes/)
