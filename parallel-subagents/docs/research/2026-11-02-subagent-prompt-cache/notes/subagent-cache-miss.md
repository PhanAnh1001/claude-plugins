# Cache miss lớn ở subagent

## Tóm tắt

- **Mục đích:** phân loại các lần subagent phải ghi lại cache lớn (>20k token) sau khoảng nghỉ 5–60 phút.
- **Điểm chính:** 655 lần miss; gần như chia đôi giữa RESUME khi cache nguội (341) và Bash dài ở cuối hand đã to (313).
- **Nguồn:** số đo nội bộ, transcript `~/.claude/projects/**/*.jsonl` (2026-09-30 → 2026-11-02) + [tools/cache-metrics/resume_miss.py](../../../../tools/cache-metrics/resume_miss.py); chưa có nguồn internet (dữ liệu riêng).
- **Việc cần làm:** không; đầu vào cho [giải pháp tiếp việc](../../../solutions/brain-hand-policy/handoff/cache-aware-handoff.md) và [tách lệnh dài](../../../solutions/brain-hand-policy/long-commands/long-command-isolation.md).

## Tổng quan subagent

- 43.586 request (99,7% claude-opus-5-5), hit rate 0,957; 100% cache write loại 5 phút (261,8 triệu token).
- Cơ cấu chi phí quy đổi input: read 35,7%, write 40,2%, output 24,1%.
- Miss >20k không ngay sau compact theo khoảng nghỉ: 5–60 phút 646 lần / 112,3 triệu token; ≤5 phút 150 / 5,2 triệu; >1 giờ 94 / 15,7 triệu; đầu phiên 771 / 24,7 triệu.

## Phân loại 655 miss (khoảng nghỉ 5–60 phút)

- RESUME (brain SendMessage khi cache đã nguội): 341 lần, 54,8 triệu token write, khoảng nghỉ median 15,1 phút, ngữ cảnh median 164k. Ngữ cảnh lúc resume: >200k 118 lần, 100–200k 163, 50–100k 58, <50k 2.
- Bash dài: 313 lần, 58,6 triệu token write, ngữ cảnh median 196k, thời gian lệnh median 9,6 phút.
- Khác: 1 lần.

## Thời điểm resume

- 1.103 lần resume subagent: ≤5 phút 660 (59,8%), 5–60 phút 350, >1 giờ 93.
