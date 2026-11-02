# Auto-compact ở main thread

## Tóm tắt

- **Mục đích:** ghi số đo chi phí cache quanh mỗi lần auto-compact; nghiên cứu phụ, không thành giải pháp của plugin (đây là config người dùng).
- **Điểm chính:** sau compact chỉ đọc lại được prefix system+tools (~28,7k) và phải ghi lại median 52,6k; hạ ngưỡng compact từ ~367k xuống ~267k giảm chi phí mỗi request 9,7% (mẫu nhỏ).
- **Nguồn:** số đo nội bộ, transcript `~/.claude/projects/**/*.jsonl` (2026-09-30 → 2026-11-02) + [tools/cache-metrics/compact_cache.py](../../../../tools/cache-metrics/compact_cache.py) và [compare_periods.py](../../../../tools/cache-metrics/compare_periods.py); chưa có nguồn internet (dữ liệu riêng).
- **Việc cần làm:** xem lại sau lần đo 2026-11-16 khi giai đoạn B có thêm mẫu.

## Sự kiện compact

- 120 lần compact ở main thread (118 auto, 2 manual).
- preTokens auto-compact: tháng 10 median 366.708 (n=117); tháng 11 268.752 (n=1).
- Request đầu sau compact: read median 28.742 (p25 27.464, p75 30.740); write median 52.588 (p25 43.138, p75 59.716), n=113.
- Mỗi chu kỳ compact median 88 request; tăng ngữ cảnh mỗi request median 1.577 token (mean 2.481).

## Lịch sử config và so sánh hai giai đoạn

- A (đến 2026-10-28, `autoCompactWindow` 400000, compact ~367k): 11.964 request, 103 compact, ngữ cảnh TB 199.510, chi phí TB 23.835 token quy đổi input/request.
- B (từ 2026-10-29, `modelSettings.claude-opus-5-5.autoCompactWindow` 300000, compact ~267k): 1.263 request, 15 compact, ngữ cảnh TB 171.142, chi phí TB 21.523/request → giảm 9,7%. Mẫu nhỏ, chưa kết luận chắc.

## Ngưỡng tối ưu (suy luận)

- Mô hình chi phí (read 0,05x, write 1h 2x, tham số B/S/g ở trên) cho ngưỡng compact tối ưu T ≈ 200–260k token, tương ứng `autoCompactWindow` ≈ 230–300k (suy luận từ số đo nội bộ và hệ số giá ở [cache-pricing.md](cache-pricing.md); hệ số giá chưa kiểm chứng trên internet).
