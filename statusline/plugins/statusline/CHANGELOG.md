# Changelog

## 0.23.0 — 2026-11-10

- Dòng Claude đổi nhãn `Claude v1 ultra` (`~/.claude`); thêm dòng `Claude v2 pro` (`~/.claude-hand`) ngay dưới, cùng cột 5h/7d. Hai dòng lấy số cùng một cách: tài khoản của phiên đang vẽ (theo `CLAUDE_HOME`) dùng `rate_limits` live và lưu vào cache riêng `<home tài khoản>/.statusline-cache.json`; tài khoản còn lại đọc cache riêng của nó, có `~`, ô thiếu hoặc đã qua reset hiện `?`. Không còn đọc cache hiệu chỉnh 5 phút của hybrid-hands cho v2. Ô 5h của tài khoản đang vẽ dùng cache của chính nó (có `~`) khi payload chưa có `rate_limits` và reset còn ở tương lai.
- GPT chuyển sang tài khoản `~/.codex` (thay `~/.codex-hand` và sổ hand-ext): % 5h/7d là mẫu `rate_limits` mới nhất theo timestamp trong rollout `sessions/` và `archived_sessions/` (chỉ đọc file sửa trong 7 ngày), nhãn theo `window_minutes` (300 = 5h, 10080 = 7d; thiếu thì primary = 5h, secondary = 7d), ô kèm giờ reset, thiếu/hết hạn hiện `?`. "hôm nay ~$" tính từ token delta hôm nay theo từng thread × giá trong `model-prices.json`, model chưa có giá hiện `?`. `STATUSLINE_CODEX_DIR` đổi thư mục (để test).
- Dòng `Go` giữ căn cột với bảng nhưng in ở dòng cuối cùng của statusline (sau nhóm phiên, hand và skill).

## 0.22.0 — 2026-11-09

- Đọc cache hiệu chỉnh Claude ngoài dùng chung với hybrid-hands để ước tính phần Claude riêng giữa các tài khoản; không gọi mạng để lấy calibration khi vẽ. Rate pin vẫn ưu tiên, thiếu rate hiệu chỉnh hợp lệ thì giữ nguyên fallback hiện có, kể cả prior; chỉ thay ước tính riêng khi rate mới sẵn sàng.
- Rate được đo từ USD~/quota tuần delta của hai quan sát cùng tài khoản/reset, chỉ sẵn sàng sau hai mẫu hợp lệ và delta ≥2 điểm phần trăm với quota số nguyên (nguồn có phần lẻ thực cần delta dương); không dựng baseline lịch sử. Giữ độ chính xác nguồn, % hiển thị một chữ số lẻ vẫn là ước tính, không phải hoá đơn hoặc phép đo chính xác riêng từng tài khoản.

- Nguồn ưu tiên live/cache Claude hand trực tiếp còn mới, dự phòng report Paseo khớp metadata auth Claude; chỉ lưu identity đã hash. Lấy mẫu khoảng 120 giây, cache Paseo tối đa 5 phút; nguồn trực tiếp không cần đổi settings. USD~ lượt cũ thiếu cache split/session correlation vẫn unknown.

## 0.21.0 — 2026-11-08

- GPT quota dùng nguồn account chung từ ledger và rollout local cố định `.codex-hand`, chọn sample mới nhất riêng từng cửa sổ; USD hôm nay vẫn chỉ thuộc ledger.
- Claude 5h thiếu payload dùng cache chung còn mới và reset hợp lệ; thiếu nguồn giữ dấu thiếu.
- Dòng hand hiện nhãn `GPT riêng (đo)` khi có weekly delta rate-limit đo được; không suy quota từ token/USD.

## 0.20.0 — 2026-11-07

- Thêm khối phiên hiện tại và descendants từ JSON hh-ps: session, subagent, hand-ext,
  provider/backend, model/effort, USD~, quota account, ended và elapsed; không hiện giờ bắt đầu.
- Adapter chỉ đọc, timeout ngắn, fail-open; tìm source sibling hoặc installed plugin,
  hỗ trợ override HYBRID_HANDS_HH_PS và tắt bằng STATUSLINE_HANDS=0.
- Giữ nguyên bảng hạn mức và nhóm phiên hiện có; dữ liệu thiếu hiện ?, không tự suy giá.

- Ledger dùng chung `model-prices.json` qua override/source/installed latest, bỏ giá family
  và cache multiplier hardcode; ledger v4 có fingerprint để tính lại USD khi giá đổi.
- Adapter truyền UUID hiện tại bằng `--main-session`, kể cả Codex; hand lost thiếu end
  hiện ended/elapsed `?`, không hiện đang chạy.
- Ước tính Go đang chạy cũng đọc file giá chung theo model, bỏ bảng giá Go hardcode.
