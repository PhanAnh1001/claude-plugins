# Plan: dòng Claude tuần trên cây Paseo cập nhật khi mọi phiên chạy qua Paseo

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-06-paseo-claude-week-live-spec.md`.
  - Giai đoạn 1: panel ngoại suy % tuần từ USD máy này khi cache statusline cũ.
  - Giai đoạn 2: tìm và nối nguồn % sống không cần statusline render.
- **Trạng thái:** chưa bắt đầu (06/11/2026). Đã có sẵn:
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

- [ ] 1.1 Trong `hh_ps/week.py`, khi cache cũ hơn `SUMMARY_STALE_SECONDS` và có `usd_per_pct`:
  - Tính USD máy này từ thời điểm cache tới hiện tại, dùng lại hàm của statusline (`usage_ledger.window_messages` hoặc `UsdIndex.total`). Không tự viết lại cách tính giá.
  - Cộng `USD / usd_per_pct` vào % tuần và phần "máy này", kẹp trong [pct_cache, 100].
  - Ghi `source` có `extrapolated`.
  - Ghi chú: hh_ps hiện đọc file của statusline. Nếu import code statusline từ hybrid-hands không hợp lệ (khác plugin), đọc thẳng `.statusline-local-usage.json` (ledger) mà statusline đã ghi. Hand chọn cách nào phải báo lý do.
- [ ] 1.2 Test tối thiểu, thêm vào `hybrid-hands/tests/test_hh_ps_limits.py`, tối đa 2 ca:
  - Cache cũ + ledger có USD sau cache_ts → % tăng đúng USD/usd_per_pct và `estimated=True`.
  - Reset tuần đã qua → không ngoại suy.
- [ ] 1.3 Kiểm thực tế: chạy `hh-ps --json`.
  - Dòng Claude tuần phải lớn hơn 10% và gần mức `/usage` hiện tại.
  - Người dùng đọc `/usage` để đối chiếu; ngày 06/11 lúc 22:12 là 15%.
- [ ] 1.4 Cập nhật `hybrid-hands/README.md` (phần cây Paseo): dòng tuần ngoại suy khi cache cũ, kèm giới hạn ở spec mục 1.3.

## 2. Giai đoạn 2: nguồn % sống

- [ ] 2.1 (hand Claude, chỉ đọc) Kiểm ứng viên A:
  - Paseo daemon lưu luồng stream-json hay log của phiên ở đâu.
  - Trong đó có sự kiện rate limit với % `seven_day`/`five_hour` không.
  - Chỉ trích tên trường và giá trị số, không in nội dung hội thoại.
- [ ] 2.2 (hand Claude, chỉ đọc) Kiểm ứng viên B: transcript có trường rate limit không.
- [ ] 2.3 Brain chọn nguồn theo spec mục 2.4 và ghi kết luận vào spec. Ứng viên C cần người dùng duyệt trước khi làm.
- [ ] 2.4 Nếu có nguồn:
  - Ghi mẫu mới nhất vào một file trạng thái.
  - `hh_ps/week.py` lấy mẫu mới hơn giữa nguồn đó và cache statusline.
  - Khi có mẫu sống thì tắt ngoại suy.
  - Thêm 1 test.
