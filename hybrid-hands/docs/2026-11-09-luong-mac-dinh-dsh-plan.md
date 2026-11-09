# Plan: luồng mặc định Opus → Sol → dsh

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-09-luong-mac-dinh-dsh-spec.md`.
- **Trạng thái (09/11/2026, 13:10):** người dùng đã duyệt. Gói A (`side/luong-a` `9c041c5`) và B (`side/luong-b` `fc5d786`) xong, chưa merge; bàn giao ở `docs/work-in-progress/handoffs/luong-a.md`, `luong-b.md`.
  - A.1 làm dở: tắt thinking xác minh được (`effort off` → `thinking:{type:disabled}`, cần thêm `off` vào `reasoningEfforts` của template dsh); ID 1017 chưa xác minh (Go chỉ công bố `deepseek-v4.1-flash`). Chờ người dùng quyết.
  - A.3: order và codex low xong; phần dsh chờ A.1.
  - Chỉ dùng cấu hình repo cho `claude_accounts`, không thêm nguồn cấu hình người dùng (Opus chốt 09/11).
  - Bước sau: phiên Sol `luong-c` merge A + B, nối adapter sổ tài khoản của B sang loader của A, làm dsh theo quyết định A.1, rồi gói C (gồm 2 template mới `side-session-prompt-claude.md`, `main-session-prompt-claude.md`).
- **Cách làm:**
  - Gói A (`lib/hand_ext`) và gói B (`lib/side_session`) chạm vùng code khác nhau, giao 2 phiên Sol song song bằng `side-session start --provider codex`, nhánh riêng. Gói B đọc sổ `claude_accounts` qua đúng tên khoá ở spec mục 2.1; nếu A đổi tên khoá thì B chỉnh lúc merge.
  - Gói C (văn bản policy) cần tên cờ và lệnh chốt từ A và B, nên mở sau khi A và B xong.
  - Gói D do Opus điều phối.
  - Mỗi Sol giao hand theo order hiện hành (`codex` low, vì dsh chưa bật lại) và tự review code. Opus đọc bàn giao.
  - Mức test: tối thiểu.
- **Lệnh kiểm chứng:**
  - Trong lúc làm, chạy test hẹp ghi ở từng task.
  - Ở cuối, chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -q`.
- **Khi xong:** bump hybrid-hands 0.32.2 → 0.33.0 (cả `USER_AGENT` của dsh), CHANGELOG, `claude plugin validate`, cập nhật cài đặt ở mọi repo đang dùng plugin, commit, merge `main`, push.

## A. Hand ngoài (Sol 1)

- [ ] A.1 Kiểm chứng spec mục 2.3 (ID model bản 1017; cách tắt thinking của dsh) và ghi kết quả có nguồn, ngày vào plan này. Thiếu một trong hai thì dừng gói A, ghi vào bàn giao.
- [x] A.2 Sổ `claude_accounts` và backend `claude-v<N>` theo spec mục 2.1. Alias `claude-main` → `claude-v1`, `claude` → `claude-v2`. Chặn %/ngày theo `max_day_pct` của từng tài khoản.
- [ ] A.3 `lib/hand_ext/constants.py`: order `["dsh", "codex", "claude-v1", "claude-v2"]`; `codex` low; dsh model/effort theo A.1. Thêm entry giá vào `config/model-prices.json`.
- [x] A.4 `auto` thử lần lượt theo order (bỏ qua backend hết hạn mức, chưa đăng nhập hoặc bị chặn ngày), exit 7 khi hết mọi backend. Bỏ đường "codex medium".
- [x] A.5 Thêm lệnh `hand-ext pick [--json]` theo spec mục 2.4.
- [x] A.6 `hh-ps`, panel và đọc ledger nhận cả tên backend cũ lẫn mới (chỉ ánh xạ tên, không đổi bố cục).
- [x] A.7 Test tối thiểu (spec mục 5.1, gói A), thêm vào test sẵn có của `hand_ext`. Test hẹp: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext*.py'`.

## B. Phiên phụ và phiên chính chọn tài khoản (Sol 2)

- [x] B.1 `side-session start --provider claude --account v1|v2|v…` theo spec mục 3, đọc `config_dir` từ `claude_accounts` của gói A; `v1` giữ chặn ngày hiện có.
- [x] B.2 `--main --provider claude --account v2` mở phiên chính Opus 5.5 high tài khoản mới; `--main` mặc định giữ Sol high.
- [x] B.3 Phiên phụ Claude nhận template theo tài khoản (chỉ chọn file; nội dung để gói C viết).
- [x] B.4 Test tối thiểu (spec mục 5.1, gói B). Test hẹp: `-p 'test_side_session*.py'`.

## C. Policy và tối ưu cache (Sol 3, sau A và B)

- [ ] C.1 Sửa đồng bộ các file ở spec mục 4.1 theo spec mục 1 đến 3: bảng 1.2, leo thang 1.3, Ngoại lệ A mở rộng, exit 7 mới.
- [ ] C.2 Spec mục 4.2: `inject-policy.sh` ≤300 ký tự; bỏ đoạn trùng AGENTS.md trong `session-start-policy.sh`; đảo thứ tự khuôn brief.
- [ ] C.3 Cập nhật `tests/test_policy_brain_context.py`. Test hẹp: `-p 'test_policy_brain_context.py'`.
- [ ] C.4 `README.md`, `AGENTS.md` gốc repo: chỉ các đoạn ở spec mục 4.1.

## D. Opus điều phối

- [ ] D.1 Đọc bàn giao A, B, C; chạy test đầy đủ một lần.
- [ ] D.2 Bump version, CHANGELOG, `claude plugin validate`, cập nhật cài đặt plugin ở mọi repo đang dùng, kiểm version và đường dẫn được nạp.
- [ ] D.3 Bỏ khối `ext_hand` trong `claude-plugins/.claude/hybrid-hands.json` (spec mục 2.2).
- [ ] D.4 Kiểm thực tế spec mục 5.2.
- [ ] D.5 Commit, merge `main`, push.
- [ ] D.6 Thay memory `tam-dung-dsh-dung-sol-low` bằng luồng mới.
- [ ] D.7 Đặt lịch đo spec mục 5.3 vào 16/11/2026.
