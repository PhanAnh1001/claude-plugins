# Plan: mô hình 3 tầng Opus / Sol / dsh

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-07-ba-tang-opus-sol-dsh-spec.md`. Có 4 nhóm: phiên Sol trên Codex, backend `claude-main`, policy mới, kiểm thực tế.
- **Trạng thái (07/11/2026, 11:50):** nhóm 1-3 xong, 380 test xanh, hybrid-hands 0.24.0, đã commit trên nhánh `feat/ba-tang-opus-sol-dsh` (chưa merge main, chưa push).
  - Lần chạy thử 4.1 (phiên Sol `sol-l0-test`) **thất bại**, phát hiện 3 lỗi: 4.4, 4.5, 4.6.
    - Sol đã tìm ra nguồn ResourceWarning: `test_worker_gives_up_when_pid_ignores_sigterm` tạo `stdout=PIPE` mà không đóng.
    - Sol chưa sửa được file nào, chưa có file bàn giao.
  - **Phiên brain sau làm tiếp:**
    1. Sửa 4.4, 4.5, 4.6. Đây là task L1 trên plugin, chính lỗi ở đây làm phiên Sol chạy không được, nên giao dsh từ phiên Opus.
    2. Chạy lại 4.1 và 4.2.
    3. Thử nhánh chặn của `claude-main` bằng `.claude/hybrid-hands.json` tạm đặt `ext_hand.backends.claude-main.max_day_pct` = 1. Kết quả phải là thoát mã 7. Thử xong thì xoá file tạm.
    4. Commit các bản sửa lên cùng nhánh, rồi hỏi người dùng có merge vào main không.
- **Cách làm:**
  - Nhóm 1 và 2 chạm vùng code khác nhau, nên giao 2 hand dsh song song (`hand-ext run --backend auto`), mức test tối thiểu.
  - Nhóm 3 là văn bản policy, giao 1 hand dsh sau khi nhóm 1-2 xong để chép đúng tên cờ và khoá.
  - Nhóm 4 do brain điều phối, có chạy thật.
  - Brain tự review diff của từng nhóm.
- **Lệnh kiểm chứng:**
  - Trong lúc làm, chạy test hẹp của từng nhóm (ghi ở task).
  - Ở cuối, chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -q`.
- **Khi xong:**
  - Bump hybrid-hands lên 0.24.0, cả `USER_AGENT` trong `lib/hand_ext/backends/dsh.py`.
  - Chạy `claude plugin validate`.
  - Commit khi người dùng đồng ý.

## 1. Phiên phụ Sol trên Codex

- [x] 1.1 Trong `lib/side_session/cli.py` và `commands.py`:
  - thêm cờ `--model`, `--effort` cùng khoá `side_session.codex_model`/`codex_effort` (mặc định `gpt-6.1-sol`/`high`, đặt ở `constants.py`);
  - argv codex thêm `-m`, `-c model_reasoning_effort=`, approval `never`, sandbox theo Q1;
  - `ext_argv` truyền model/effort.
- [x] 1.2 Tạo `templates/side-session-prompt-codex.md` theo spec mục 2.3. Provider codex dùng template này, không còn nhắc `SendMessage`.
- [x] 1.3 Hợp đồng `.done` (spec mục 2.4): `watch`/`ls` báo `done` khi có `<handoff_dir>/<name>.done`.
- [x] 1.4 Test tối thiểu, tối đa 2 ca, thêm vào `tests/test_side_session_codex.py`:
  - argv codex có model, effort, approval;
  - có `.done` thì trạng thái là `done`.
  - Test hẹp: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'`.

## 2. Backend `claude-main`

- [x] 2.1 Đăng ký backend `claude-main` (spec mục 3.1): dùng lại `backends/claude.py`, trỏ vào gói chính, mặc định `claude-opus-5-5`/`low`, hạn mức ghi theo khoá riêng, không vào `order`.
- [x] 2.2 Chặn hạn mức (spec mục 3.2): tính USD máy này từ 0h ngày hôm đó bằng `usage_ledger.window_messages` (nạp như `hh_ps/week.py` đang làm), chia USD/1% ghim; không tự viết lại cách tính giá. Máy này dùng từ `max_day_pct` (mặc định 5) % Claude trong ngày thì thoát mã 7; không tính được thì chặn.
- [x] 2.3 Test tối thiểu, tối đa 2 ca, thêm vào `tests/test_hand_ext_claude.py`:
  - `claude-main` chạy với config_dir của gói chính, trong khi `claude` vẫn bị chặn;
  - % dùng trong ngày từ 5 trở lên thì thoát mã 7.
  - Test hẹp: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_claude.py'`.

## 3. Policy mới

- [x] 3.1 Sửa đồng bộ các file ở spec mục 4 theo nội dung 4.1 đến 4.5. `inject-policy.sh` giữ dưới 1800 ký tự.
- [x] 3.2 Cập nhật `tests/test_policy_brain_context.py` nếu marker đổi. Test hẹp: `-p 'test_policy_brain_context.py'`.
- [x] 3.3 Cập nhật `README.md`, `skills/side-session/SKILL.md`, `skills/ext-hand/SKILL.md`: bảng 3 tầng, cờ mới, backend `claude-main`, hợp đồng `.done`.

## 4. Kiểm thực tế

- [ ] 4.1 Chạy spec mục 5.1 (phiên Sol làm một task L0 thật).
- [ ] 4.2 Chạy spec mục 5.2 (`claude-main`, cả nhánh bị chặn).
- [ ] 4.3 Ghi số đo ban đầu cho spec mục 5.3 vào plan này, hẹn đo lại sau 1-2 tuần.
- [ ] 4.4 Lỗi phát hiện ở 4.1: Codex TUI dừng ở màn "Trust this folder?", nên phiên Sol chạy không người trực bị kẹt.
  - Sửa: trước khi mở phiên, `side-session start` ghi `[projects."<workdir>"] trust_level = "trusted"` vào `<codex_home>/config.toml`, chỉ khi workdir chưa có mục này. Workdir có thể là worktree mới.
  - Cột TOKENS báo 0 trong lúc kẹt là đúng: lúc đó chưa có rollout.
  - Thêm 1 test.
- [ ] 4.5 Lỗi: `watch` đếm token Codex bằng `total_tokens`, gồm cả `cached_input_tokens` (`lib/side_session/tokens.py:6`).
  - Hậu quả: phiên Sol chạm cap 300k sau khoảng 2 phút làm việc (304k input, trong đó 260k cache; 4,8k output) và bị dừng (trạng thái `capped`).
  - Sửa: đếm `input_tokens - cached_input_tokens + output_tokens`, giống cách đếm của Claude (không tính cache read).
  - Thêm 1 test.
- [ ] 4.6 Lỗi: lượt `hand-ext run --backend claude-main` do Sol gọi trong sandbox lỗi ngay ở bước tạo worktree. Report chỉ có "Lỗi: Preparing worktree (detached HEAD 3a56c5c)", run dir `output/llm/hand-ext/20261107-113756-sol-l0-test-creative-claude-main/`.
  - Giả thuyết: sandbox `workspace-write` của Codex giữ `.git` ở chế độ chỉ đọc, nên `git worktree add` không ghi được `.git/worktrees`.
  - Điều tra: tái hiện bằng `codex exec -s workspace-write` với một lệnh `git worktree add` nhỏ. Kiểm xem thêm `<repo>/.git` vào `writable_roots` có đủ không.
  - Nếu không đủ, đưa người dùng chọn: Sol gọi hand-ext với `--isolation none`, hay chuyển sandbox của Sol sang `danger-full-access`.
  - Lượt dsh `20261107-113905-sol-l0-test-fix-dsh` bị dừng giữa chừng khi phiên Sol bị cap. Kiểm và dọn worktree còn sót trong `~/.hybrid-hands/worktrees`.

