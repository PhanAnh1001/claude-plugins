# Giá và TTL prompt cache

## Tóm tắt

- **Mục đích:** ghi các hệ số giá và TTL cache dùng để quy đổi chi phí trong báo cáo.
- **Điểm chính:** cache read rẻ (0,05x với Opus 5.5), ghi cache đắt hơn input (1,25x với TTL 5 phút, 2x với TTL 1 giờ); subagent dùng TTL 5 phút.
- **Trạng thái nguồn:** chưa kiểm chứng trên internet trong phiên này; nguồn là tài liệu skill claude-api đi kèm Claude Code 2.1.316 (cập nhật 2026-10-06). Link chính thức để kiểm lại: [docs prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [bảng giá](https://www.anthropic.com/pricing).
- **Việc cần làm:** khi có mạng, đối chiếu các dòng dưới với hai trang chính thức và sửa nếu lệch.

## Hệ số giá (bội số giá input)

Nguồn chung cho cả mục: [docs prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [bảng giá](https://www.anthropic.com/pricing) (chưa kiểm chứng trên internet; tài liệu skill claude-api, Claude Code 2.1.316, 2026-10-06).

- Cache read: 0,05x với claude-opus-5-5 ($0,20 / $4 mỗi triệu token); 0,1x với phần lớn model khác.
- Ghi cache TTL 5 phút: 1,25x.
- Ghi cache TTL 1 giờ: 2x.
- Output: 5x.

## TTL quan sát trong transcript

- Main thread: 100% cache write loại 1 giờ; subagent: 100% loại 5 phút. Số đo nội bộ (transcript `~/.claude/projects/**/*.jsonl` 2026-09-30 → 2026-11-02, script trong [tools/cache-metrics/](../../../../tools/cache-metrics/)); chưa có nguồn internet về việc Claude Code chọn TTL theo loại agent.
