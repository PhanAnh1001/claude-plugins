# Plan: hand-ext lưu brief/prompt/meta/timestamp và lệnh đo test code (hybrid-hands 0.22.0)

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-06-hand-ext-run-audit-spec.md`. Lượt hand-ext nào cũng chạy lại được và đo được, rồi chốt % giảm test code của luật "Test tối thiểu" trên lượt thật.
- **Trạng thái:** chưa bắt đầu. Đã có 0.21.0, đã commit và push ngày 06/11/2026, gồm luật Test tối thiểu, ngân sách test và ngoại lệ doanh thu.
- **Cách làm:** brain giao từng nhóm task cho hand ngoài (`hand-ext run --backend auto`), dùng mức test tối thiểu. Brain tự review diff.
- **Lệnh kiểm chứng:**
  - trong lúc làm, chỉ chạy test hẹp, ví dụ `python3 -m unittest hybrid-hands.tests.test_hand_ext_dsh -q`;
  - ở cuối, chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -q` từ gốc repo.
- **Khi xong:** bump 0.22.0 ở `plugin.json` và cả `USER_AGENT` trong `lib/hand_ext/backends/dsh.py:66`, chạy `claude plugin validate`, commit, merge, push, rồi `claude plugin marketplace update` và `claude plugin update`.

## 1. Lưu dữ liệu lượt

- [ ] 1.1 Ghi `brief.md` và `prompt.md` vào thư mục lượt trước khi khởi backend (`lib/hand_ext/run_cmd.py:202`, gần chỗ gọi `build_prompt`). Thêm assert vào một test sẵn có của run_cmd.
- [ ] 1.2 Ghi `meta.json` (`base_commit`, `dirty`, `dirty_files`, `plugin_version`, `backend`, `model`, `label`) và `changes.base.patch` khi repo nguồn có thay đổi chưa commit, ở chỗ tạo worktree trong `lib/hand_ext/isolation.py`. Thêm 1 test.
- [ ] 1.3 Runner gắn `ts` vào mỗi dòng event trước khi ghi `events.jsonl` (`lib/hand_ext/runner.py`). Thêm 1 test kiểm có `ts` và nội dung event giữ nguyên.

## 2. Lệnh đo

- [ ] 2.1 Viết `lib/hand_ext/measure.py`: đếm dòng test/code/docs từ `changes.patch`, đếm lệnh test và thời gian của chúng từ `events.jsonl` (cần `ts`), đọc `meta.json` để nhóm theo `plugin_version`. Phân loại theo spec mục 2.2.
- [ ] 2.2 Thêm lệnh con `hand-ext measure --runs <dir>... [--backend dsh] [--since YYYY-MM-DD]`, in một bảng theo lượt và một phần gộp chia theo version. Thêm 1 test với patch mẫu nhỏ.
- [ ] 2.3 Cập nhật `skills/ext-hand/SKILL.md` và `hybrid-hands/README.md`: thư mục lượt có thêm những file mới nào, và cách dùng `hand-ext measure`.

## 3. Đo trên lượt thật

- [ ] 3.1 Sau khoảng 20 lượt dsh thật trên 0.22.0, chạy `hand-ext measure` cho các runs_dir: `output/llm/hand-ext` của claude-plugins và các worktree, cùng `sessions/hybrid-hands/hand-ext` của live-tiktok-games.
- [ ] 3.2 So với baseline 52,6% (13 lượt trước 0.21.0) và kết quả A/B ở spec. Nếu tỉ lệ test vẫn trên 35% thì xem lại ngân sách test trong `templates/ext-hand-preamble.md` và `templates/ext-hand-test-reminder.md`.
- [ ] 3.3 Kiểm riêng các lượt thuộc ngoại lệ doanh thu (thanh toán, billing, quà/gift, combo, phần thưởng…): hand có test kỹ và có ghi bước kiểm chứng thực tế không. Nếu không, sửa câu chữ ngoại lệ.
