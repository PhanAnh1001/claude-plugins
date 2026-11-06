# Plan: dòng Claude tuần trên cây Paseo cập nhật khi mọi phiên chạy qua Paseo

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-06-paseo-claude-week-live-spec.md`.
  - Giai đoạn 1: panel ngoại suy % tuần từ USD máy này khi cache statusline cũ.
  - Giai đoạn 2: tìm và nối nguồn % sống không cần statusline render.
- **Trạng thái (06/11/2026, 23:15):** code giai đoạn 1 và 2 xong trong hybrid-hands 0.23.0. Còn mở task 2.5: người dùng duyệt sửa `~/.paseo/config.json` để bật wrapper `claude-tee`, rồi kiểm số sống trên panel.
  - Ngoại suy chạy thật: panel 12,7% (cache 10%, `/usage` 15%). Phần thiếu khớp sai số của USD/1% ghim.
  - Nguồn sống đã kiểm có thật: `rate_limit_event` trong stream-json, `seven_day.utilization` 0.15.
- **Nền có sẵn trước khi làm:**
  - statusline 0.19.0, commit `1626df6`: ghim USD/1% = 13,74 và `usage_ledger.py --since/--until`.
  - Paseo tin nhãn `pin`, commit `cd37f76`.
- **Cách làm:**
  - Brain giao task code cho hand ngoài (`hand-ext run --backend auto`), mức test tối thiểu.
  - Task 2.x phải đọc luồng hoặc log của phiên Claude (có thể chứa nội dung hội thoại), nên giao hand Claude (`hybrid-hands:hand`), không giao hand ngoài.
  - Brain tự review diff.
- **Lệnh kiểm chứng:**
  - Trong lúc làm, chạy test hẹp `python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_limits.py`.
  - Ở cuối, chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -q` và `python3 -m unittest discover -s statusline/tests -q`.
- **Khi xong mỗi giai đoạn:**
  - Bump hybrid-hands (0.23.0 cho giai đoạn 1), cả `USER_AGENT` trong `lib/hand_ext/backends/dsh.py`.
  - Chạy `claude plugin validate`, rồi commit.
  - `hh-ps` chạy code từ repo, nên panel có hiệu lực ngay, không cần cài lại.

## 1. Giai đoạn 1: ngoại suy khi cache cũ

- [x] 1.1 Trong `hh_ps/week.py`, khi cache cũ hơn `SUMMARY_STALE_SECONDS` và có `usd_per_pct`:
  - Tính USD máy này từ thời điểm cache tới hiện tại, dùng lại hàm của statusline (`usage_ledger.window_messages` hoặc `UsdIndex.total`). Không tự viết lại cách tính giá.
  - Cộng `USD / usd_per_pct` vào % tuần và phần "máy này", kẹp trong [pct_cache, 100].
  - Ghi `source` có `extrapolated`.
  - Ghi chú: hh_ps hiện đọc file của statusline. Nếu import code statusline từ hybrid-hands không hợp lệ (khác plugin), đọc thẳng `.statusline-local-usage.json` (ledger) mà statusline đã ghi. Hand chọn cách nào phải báo lý do.
- [x] 1.2 Test tối thiểu, thêm vào `hybrid-hands/tests/test_hh_ps_limits.py`, tối đa 2 ca:
  - Cache cũ + ledger có USD sau cache_ts → % tăng đúng USD/usd_per_pct và `estimated=True`.
  - Reset tuần đã qua → không ngoại suy.
- [x] 1.3 Kiểm thực tế: chạy `hh-ps --json`.
  - Dòng Claude tuần phải lớn hơn 10% và gần mức `/usage` hiện tại.
  - Người dùng đọc `/usage` để đối chiếu; ngày 06/11 lúc 22:12 là 15%.
  - Kết quả 06/11 lúc 23:03: `total_pct` 12,7%, source `statusline_cache+week_split+extrapolated`, có đánh dấu ước tính. Số này lớn hơn 10% nhưng thấp hơn 15%, phù hợp giới hạn ở spec mục 1.3.
  - USD lấy tươi từ transcript qua `usage_ledger.window_messages`, nạp lúc chạy từ statusline đã cài hoặc từ repo. Không có thì đọc ledger, rồi giữ hành vi cũ.
- [x] 1.4 Cập nhật `hybrid-hands/README.md` (phần cây Paseo): dòng tuần ngoại suy khi cache cũ, kèm giới hạn ở spec mục 1.3.

## 2. Giai đoạn 2: nguồn % sống

- [x] 2.1 (hand Claude, chỉ đọc) Kiểm ứng viên A:
  - Paseo daemon lưu luồng stream-json hay log của phiên ở đâu.
  - Trong đó có sự kiện rate limit với % `seven_day`/`five_hour` không.
  - Chỉ trích tên trường và giá trị số, không in nội dung hội thoại.
  - Kết quả: Paseo không lưu và bỏ qua sự kiện rate limit (spec mục 2.5).
- [x] 2.2 (hand Claude, chỉ đọc) Kiểm ứng viên B: transcript có trường rate limit không. Kết quả: không có.
- [x] 2.3 Brain chọn nguồn theo spec mục 2.4 và ghi kết luận vào spec. Ứng viên C cần người dùng duyệt trước khi làm.
  - Người dùng duyệt hướng wrapper. Chạy thử một lượt claude haiku xác nhận có `rate_limit_event` (spec mục 2.5).
- [x] 2.4 Nếu có nguồn:
  - Ghi mẫu mới nhất vào một file trạng thái.
  - `hh_ps/week.py` lấy mẫu mới hơn giữa nguồn đó và cache statusline.
  - Khi có mẫu sống thì tắt ngoại suy.
  - Thêm 1 test.
  - Đã làm:
    - `bin/claude-tee` tee stdout và ghi `~/.claude/.hh-claude-rate-limit.json`. File chỉ có `utilization`, `resets_at`, `status`, `ts` theo cửa sổ, không có `session_id` hay nội dung hội thoại.
    - `hh_ps/live_rate.py` đọc mẫu. `week.py` ưu tiên mẫu sống mới hơn cache. Mẫu cũ hơn 30 phút thì ngoại suy tiếp từ mẫu đó.
    - Source trong JSON là `rate_limit_event+week_split`.
    - Test: `test_claude_tee.py` (3 ca), `test_hh_ps_limits.py` (1 ca mới).
    - README mục 8.1 và skill paseo có hướng dẫn bật.
- [ ] 2.5 Bật wrapper trên máy này (cần người dùng duyệt sửa `~/.paseo/config.json`):
  - Thử trước bằng provider riêng `"claude-tee": {"extends": "claude", "command": ["<repo>/hybrid-hands/plugins/hybrid-hands/bin/claude-tee"]}`, rồi `paseo reload`.
  - Chạy một phiên Paseo bằng provider đó, kiểm file trạng thái có mẫu và `hh-ps --json` ra source `rate_limit_event…`.
  - Ổn thì ghi đè provider `claude` để mọi phiên Paseo đều đi qua wrapper.
