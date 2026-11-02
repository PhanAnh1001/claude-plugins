# Prompt cache của subagent: vì sao tốn và cách giảm

## Tóm tắt

- **Câu hỏi:** chi phí prompt cache của subagent (hand) trong mô hình brain/hand lãng phí ở đâu, và policy nào giảm được?
- **Kết luận chính:**
  1. Subagent ghi cache với TTL 5 phút (100% số write), main thread với TTL 1 giờ; ghi 5 phút tốn 1,25x giá input, read chỉ 0,05x với Opus 5.5 [docs prompt caching](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [bảng giá](https://www.anthropic.com/pricing) (chưa kiểm chứng trên internet; nguồn tài liệu skill claude-api đi kèm Claude Code 2.1.316, 2026-10-06). Chi tiết: [notes/cache-pricing.md](notes/cache-pricing.md).
  2. 655 lần subagent ghi lại cache lớn sau nghỉ 5–60 phút, chia hai nguyên nhân: 341 lần RESUME khi cache đã nguội (54,8 triệu token write) và 313 lần lệnh Bash dài ở cuối một hand đã to (58,6 triệu token). Số đo nội bộ: [notes/subagent-cache-miss.md](notes/subagent-cache-miss.md).
  3. Chỉ 59,8% số lần resume diễn ra trong 5 phút; 118 lần resume có ngữ cảnh trên 200k.
  4. Policy 2.1.0 (tiếp việc theo trạng thái cache + tách lệnh dài) ước tính tiết kiệm ~75 triệu token write, ~11–12% chi phí subagent (suy luận, chưa đo; dựa trên số đo nội bộ và hệ số giá ở kết luận 1).
  5. Nghiên cứu phụ: hạ ngưỡng auto-compact main thread từ ~367k xuống ~267k giảm 9,7% chi phí/request (mẫu nhỏ); ngưỡng tối ưu ước tính 200–260k (suy luận). Đây là config người dùng, không thành giải pháp plugin. Chi tiết: [notes/auto-compact.md](notes/auto-compact.md).
- **Số liệu chính:** main 13.401 request, subagent 43.586 request; dữ liệu 2026-09-30 → 2026-11-02.
- **Khuyến nghị / việc cần làm:** dùng policy 2.1.0 ([cache-aware-handoff](../../solutions/brain-hand-policy/handoff/cache-aware-handoff.md), [long-command-isolation](../../solutions/brain-hand-policy/long-commands/long-command-isolation.md)); đọc kết quả đo lại tự động ngày 2026-11-16 để xác nhận mức tiết kiệm.
- **Nội dung:** TTL và giá → Nguyên nhân miss ở subagent → Giải pháp và ước tính → Auto-compact (phụ) → Phương pháp → Câu hỏi mở.

## TTL và giá cache

- Hệ số theo bội số giá input: read 0,05x (Opus 5.5; 0,1x model khác), write 5 phút 1,25x, write 1 giờ 2x, output 5x (chưa kiểm chứng trên internet; [docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [pricing](https://www.anthropic.com/pricing); tài liệu skill claude-api, Claude Code 2.1.316, 2026-10-06).
- Hệ quả: một lần SendMessage tới hand 164k token khi cache nguội tốn ~164k × 1,25 ≈ 205k token quy đổi, gấp 25 lần đọc cache cùng ngữ cảnh (suy luận từ hệ số trên).

## Nguyên nhân miss ở subagent

### Resume khi cache nguội

- 341 lần, 54,8 triệu token write, khoảng nghỉ median 15,1 phút, ngữ cảnh median 164k. 308/341 lần do brain (coordinator) gửi tiếp việc.
- Nguyên nhân: policy 2.0.2 chỉ nhắc TTL một cách định tính ("cache có TTL nên tiếp việc sớm thì rẻ, để lâu lợi thế giảm"), không có ngưỡng thời gian hay kích thước ngữ cảnh, nên brain vẫn SendMessage cho hand đã nguội, trong khi brain thường chờ người dùng hoặc hand khác quá 5 phút.

### Lệnh dài ở cuối hand

- 313 lần, 58,6 triệu token write, ngữ cảnh median 196k, lệnh Bash chạy median 9,6 phút.
- Nguyên nhân: hand đã đọc nhiều rồi chạy full test/build; khi lệnh trả về sau hơn 5 phút, toàn bộ ngữ cảnh lớn phải ghi lại.

## Giải pháp và ước tính

- Tiếp việc theo trạng thái cache: nóng → SendMessage ngay; nguội và ngữ cảnh >80k → hand mới, brief gọn; >200k → luôn hand mới. Xem [cache-aware-handoff.md](../../solutions/brain-hand-policy/handoff/cache-aware-handoff.md).
- Lệnh dài (>4 phút) → hand riêng ngữ cảnh nhỏ. Xem [long-command-isolation.md](../../solutions/brain-hand-policy/long-commands/long-command-isolation.md).
- Tiết kiệm ước tính ~75 triệu token write ≈ 11–12% chi phí subagent (suy luận, chưa đo; giả định hand mới chỉ ghi brief gọn + prefix thay vì cả ngữ cảnh cũ).

## Auto-compact ở main thread (nghiên cứu phụ)

- 120 lần compact; sau compact chỉ đọc lại ~28,7k (prefix system+tools), ghi lại median 52,6k.
- `autoCompactWindow` 400000 (compact ~367k) đến 2026-10-28; từ 2026-10-29 `modelSettings.claude-opus-5-5.autoCompactWindow` 300000 (compact ~267k): chi phí/request giảm 9,7% (mẫu nhỏ, 1.263 request).
- Ngưỡng tối ưu T ≈ 200–260k, tức `autoCompactWindow` ≈ 230–300k (suy luận). Chi tiết: [notes/auto-compact.md](notes/auto-compact.md).

## Phương pháp và nguồn

- Dữ liệu: transcript `~/.claude/projects/**/*.jsonl` từ 2026-09-30 đến 2026-11-02 (main 104 file, subagent 1.128 file); đọc trường usage (input, cache_creation 5m/1h, cache_read, output).
- Script: [tools/cache-metrics/](../../../tools/cache-metrics/) (`compact_cache.py`, `resume_miss.py`, `compare_periods.py`); chạy thật ngày 2026-11-02. Cách chạy lại: [tools/cache-metrics/README.md](../../../tools/cache-metrics/README.md).
- Miss lớn: request ghi cache >20k token không ngay sau compact; khoảng nghỉ tính từ request trước cùng file.

## Câu hỏi mở

- Mức tiết kiệm thật của policy 2.1.0: chờ lần đo lại tự động 2026-11-16 09:07 (giờ local, launchd qua `tools/cache-metrics/install_schedule.sh`).
- Ngưỡng 80k và 4 phút là chọn theo phân bố, chưa tối ưu hóa.
- Hệ số giá cần đối chiếu với trang chính thức khi có mạng.
