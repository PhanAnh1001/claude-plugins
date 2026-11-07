# Changelog

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
