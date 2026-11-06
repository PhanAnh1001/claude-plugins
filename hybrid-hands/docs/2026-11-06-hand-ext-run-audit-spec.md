# Spec: lưu brief, prompt và mốc thời gian của mỗi lượt hand-ext để đo lại được

## Tóm tắt

- **Mục đích:** mỗi lượt `hand-ext run` phải lưu đủ dữ liệu để chạy lại (replay) và đo được. Cần lưu brief, prompt thực gửi đi, commit gốc và thời điểm của từng event. Từ đó đo được luật "Test tối thiểu" (hybrid-hands 0.21.0) trên lượt thật, không phải dựng lại thủ công.
- **Vì sao cần:** khi đo 0.21.0 (06/11/2026) không chạy lại được các lượt cũ, vì 3 lý do:
  - thư mục lượt không có brief hay prompt;
  - không biết commit gốc khi repo nguồn có thay đổi chưa commit;
  - `events.jsonl` của dsh không có timestamp nên không tính được thời gian chạy test.
- **Kết quả đo hiện có**, để so sánh sau này. Đo A/B trên repo sạch, cùng brief week-pct-paseo, mỗi bên n=3:
  - dòng test giảm 39,1% theo trung bình (415 → 253) và 45,7% theo trung vị;
  - tỉ lệ test/(test+code) giảm từ 39,9% xuống 30,7%;
  - thời gian lượt giảm 14,1%;
  - số lệnh test tăng 31,8%.
  - Baseline trước khi đổi, 13 lượt dsh: test chiếm 52,6% dòng thêm.
- **Quyết định:**
  - thêm `brief.md`, `prompt.md` và `meta.json` (commit gốc, có thay đổi chưa commit hay không, version plugin) vào thư mục lượt;
  - hand-ext tự gắn timestamp nhận được vào mỗi dòng event;
  - thêm lệnh `hand-ext measure` để đếm dòng test/code/docs và thời gian chạy test qua nhiều lượt.
- **Người đọc cần làm:** làm theo plan `2026-11-06-hand-ext-run-audit-plan.md`, bump hybrid-hands lên 0.22.0, rồi sau khoảng 20 lượt dsh thật thì chạy `hand-ext measure` để chốt % giảm test code.

## 1. Dữ liệu lưu cho mỗi lượt

### 1.1 Brief và prompt

- `brief.md`: brief đúng như brain đưa vào, kể cả khi đọc từ stdin (`--brief -`). Nguồn: `lib/hand_ext/prompt.py:13-14` (`read_brief`).
- `prompt.md`: prompt đầy đủ gửi tới backend, tức preamble, luật browser (nếu có), `## BRIEF` và đoạn `## NHẮC LẠI LUẬT TEST`. Nguồn: `lib/hand_ext/run_cmd.py:202` (`build_prompt`).
- Ghi cả hai file trước khi khởi backend. Không thêm nội dung nào ngoài những gì đã gửi đi: brief không được chứa secret (đã có luật cấm), nên lưu không làm lộ thêm gì.

### 1.2 meta.json

- Gồm `base_commit` (HEAD của repo nguồn), `dirty` (true/false), `dirty_files` (danh sách đường dẫn, không có nội dung), `plugin_version`, `backend`, `model` và `label`.
- Khi `dirty` là true, đặt `changes.base.patch` (diff chưa commit tại thời điểm tạo worktree) cạnh `changes.patch`. Có file này thì dựng lại được gốc chính xác bằng `base_commit` + `changes.base.patch`.

### 1.3 Timestamp của event

- Runner (`lib/hand_ext/runner.py`) gắn `ts` (ISO 8601, giờ máy) vào mỗi dòng event lúc nhận được, trước khi ghi `events.jsonl`. Không sửa nội dung event của backend.
- Thời gian một lệnh = `ts` của `tool_result` trừ `ts` của `tool_call` tương ứng.

## 2. Lệnh đo `hand-ext measure`

### 2.1 Đầu vào và đầu ra

- Đầu vào: `--runs <thư mục runs_dir>` (lặp lại được), `--backend dsh`, `--since <ngày>`.
- Đầu ra cho từng lượt và phần gộp:
  - dòng test, code và docs thêm (lấy từ `changes.patch`);
  - tỉ lệ test/(test+code);
  - số lệnh test và tổng thời gian chạy lệnh test;
  - thời gian lượt;
  - `plugin_version`, để tách nhóm trước và sau 0.21.0.

### 2.2 Phân loại file

- **Test:** nằm trong `tests/`, `test/`, `__tests__/` hoặc `spec/`; hoặc tên dạng `test_*`, `*_test.*`, `*.spec.*`, `*.test.*`, `*.bats`.
- **Docs:** `.md`, `.rst`, `.txt` hoặc nằm trong `docs/`.
- **Code:** mọi file còn lại.
- Lấy theo script đo ngày 06/11, trước đây là `/tmp/hh-test-min/count.py` (file tạm, có thể đã mất), nên viết lại trong `lib/hand_ext/`.
- Lệnh test nhận theo mẫu: `pytest`, `unittest`, `bats`, `npm test`, `npx vitest`, `go test`, `cargo test`.

## 3. Ngoài phạm vi, chỉ ghi nhận

- Khi chạy A/B, dsh từng đọc git history để chép lời giải có sẵn (`git diff HEAD <commit>`). Việc đó chỉ ảnh hưởng thí nghiệm, nên không cấm trong preamble vì điều tra lỗi cần git history. Thí nghiệm sau phải dùng repo sạch một commit.
- Ở một số lượt A/B, cả bản cũ lẫn bản mới đều thiếu vài file so với lời giải gốc (`week.py`, `LimitsBlock.tsx`). Chưa đọc diff nên chưa kết luận được có thiếu chức năng hay không.
