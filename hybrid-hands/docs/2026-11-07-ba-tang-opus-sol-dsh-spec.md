# Spec: mô hình 3 tầng Opus / Sol / dsh

## Tóm tắt

- **Mục tiêu:** chia việc theo vai để giảm chi phí gói Claude chính mà vẫn giữ chất lượng.
  - **Opus** (phiên brain chính, gói Claude chính): thư ký, solution architect, BA, product manager.
  - **Sol** (phiên phụ Codex, GPT `gpt-6.1-sol` trên tài khoản ChatGPT riêng, `CODEX_HOME=~/.codex-hand`): lead tech, lead QA.
  - **dsh** (hand ngoài, gói OpenCode Go): dev, tester.
  - **Hand Opus `low`** (gói Claude chính): việc sáng tạo như UI design, câu chữ hiển thị.
- **Quyết định đã chốt với người dùng (07/11/2026):**
  - Sol có quyền ngang Opus, kể cả với secret và dữ liệu khách hàng. Sol không bắt buộc đẩy việc lên Opus.
  - Opus không review code. Opus chỉ review spec, plan và giải pháp của Sol. Sol review code của dsh.
  - Mức test "kỹ" chỉ gồm 2 nhóm: (1) tính năng tạo hứng thú, giữ chân khiến người dùng trả tiền; (2) bảo mật chống tấn công từ ngoài. Mức kỹ phải đánh giá hiệu quả bằng chạy thực tế. Mọi việc khác là "tối thiểu".
  - Không có gói Claude thứ hai, nên hand Opus của phiên Sol chạy trên gói chính, có chặn hạn mức.
- **Đã kiểm:** `~/.codex-hand` đăng nhập ChatGPT. `gpt-6.1-sol` chạy được. Tên `gpt-sol-6.1` bị từ chối.
- **Phải làm:** 4 nhóm thay đổi trong plugin, theo thứ tự mục 2 đến 5: phiên phụ Sol chạy được trên Codex, backend `claude-main` cho hand sáng tạo, policy mới, kiểm thực tế. Chi tiết ở plan `2026-11-07-ba-tang-opus-sol-dsh-plan.md`.
- **Người đọc cần làm:** spec đã duyệt; Q1 và Q2 đã chốt ở mục 6.

## 1. Vai trò và luồng việc

### 1.1 Chia việc theo lane

| Lane | Ai viết spec/plan | Ai duyệt | Ai làm | Ai review code |
|---|---|---|---|---|
| L0 (sửa nhanh) | Không viết spec | Không duyệt | dsh | Sol |
| L1, không có lựa chọn giải pháp | Sol | Không duyệt, Opus đọc bàn giao | dsh | Sol |
| L1 có lựa chọn giải pháp, hoặc thuộc mức kỹ | Sol, mở đầu bằng tóm tắt quyết định 1 trang | Opus đọc tóm tắt | dsh | Sol |
| L2/L3 | Opus | Người dùng | Opus cắt thành các gói cỡ L1, giao các phiên Sol | Sol |

- Opus nhận yêu cầu từ người dùng, phân lane, rồi mở phiên Sol. Nhiều việc L0 gom vào một phiên Sol để chia nhau chi phí mở phiên.
- Mỗi task một phiên Sol. Xong thì Sol ghi bàn giao rồi đóng phiên, không giữ phiên qua nhiều task.
- Tóm tắt quyết định của Sol gồm: vấn đề, các phương án, phương án chọn, rủi ro, kèm file:dòng để Opus khỏi phải tra code. Opus gom nhiều tóm tắt để duyệt trong cùng một lượt.

### 1.2 Kiểm kết quả

- Sol là lead QA: viết tiêu chí chấp nhận và tối đa 3 ca test trước khi giao dsh code, rồi review diff của dsh.
- Opus không đọc diff. Opus đọc bàn giao của Sol: kết quả test, danh sách lỗi Sol đã tìm và đã xử lý, việc còn mở.

### 1.3 Việc thư ký của Opus

- Opus chỉ quyết nội dung. Phần ghi cơ học giao hand rẻ:
  - Việc cần PAT Jira (secret) giao hand Claude với `model: haiku` hoặc `sonnet`.
  - Tài liệu không chứa secret giao dsh.

### 1.4 Việc sáng tạo

- Làm phần sáng tạo ngay ở giai đoạn spec: Opus giao hand Opus `low` (`hybrid-hands:hand`, đã khai `claude-opus-5-5`/`low` ở `agents/hand.md:4-5`) làm mockup, design token, câu chữ, rồi đưa kèm spec.
- Việc sáng tạo phát sinh trong phiên Sol: Sol gọi `hand-ext run --backend claude-main` (mục 3). Phần code hoá thiết kế vẫn giao dsh.

## 2. Phiên phụ Sol trên Codex

Hiện trạng (khảo sát 07/11):
- Provider codex chạy TUI trong screen (`lib/side_session/commands.py:72-75`).
- `CODEX_HOME` mặc định `~/.codex-hand` (`constants.py:33`).
- Không có cờ model, effort, sandbox, approval (`cli.py:17-40`).
- Prompt duy nhất Codex nhận là `templates/side-session-prompt.md`. Prompt này bắt dùng `SendMessage`, mà Codex không có tool này. Prompt cũng không có luật `.env` hay luật dữ liệu.
- Không có tín hiệu xong việc: `watch` chỉ thấy phiên chết (`actions.py:289-305`).

Thay đổi:
- **2.1 Model và effort:**
  - Thêm cờ `--model`, `--effort` cho `side-session start`, cùng khoá `side_session.codex_model` (mặc định `gpt-6.1-sol`) và `codex_effort` (mặc định `high`).
  - Truyền `-m` và `-c model_reasoning_effort=` cho codex. Truyền cả qua `ext_argv` cho provider dsh.
- **2.2 Quyền chạy không kẹt:**
  - Codex chạy với approval `never` để không dừng hỏi duyệt khi không có người ngồi máy.
  - Sandbox phải cho Sol chạy `hand-ext` (cần mạng và ghi vào `worktree_root`, `runs_dir`). Cách cấu hình là câu hỏi mở Q1.
- **2.3 Prompt riêng cho Codex:** tạo template mới `templates/side-session-prompt-codex.md`, chép nguyên văn:
  - vai trò lead tech/lead QA và bảng lane;
  - luật `.env`;
  - LUẬT DỮ LIỆU cho dsh (Sol được đọc dữ liệu khách hàng, dsh thì không);
  - LUẬT TEST với định nghĩa mức kỹ mới;
  - cách gọi `hand-ext` (dsh, dự phòng codex, `claude-main`);
  - hợp đồng bàn giao ở 2.4.
- **2.4 Hợp đồng xong việc:**
  - Sol ghi `<handoff_dir>/<name>.md`, sau đó tạo `<handoff_dir>/<name>.done`.
  - `watch` và `ls` báo trạng thái `done` khi thấy file này.
  - Opus chờ bằng `Monitor` trên file `.done`, không hỏi trạng thái.
- **Ngoài phạm vi:** resume phiên Codex. Đã chốt mỗi task một phiên.

## 3. Backend `claude-main` cho hand sáng tạo

Hiện trạng:
- Backend `claude` dùng `config_dir` mặc định `~/.claude-hand` (`lib/hand_ext/constants.py:87`).
- `doctor` cố tình báo lỗi khi `config_dir` là `~/.claude` (`backends/claude.py:107-110`, test `tests/test_hand_ext_claude.py:131-134`).
- Hạn mức ghi theo tên backend (`quota_state.py:39-55`).

Thay đổi:
- **3.1 Backend mới `claude-main`:**
  - Dùng lại code của backend `claude`, nhưng trỏ vào gói chính (`~/.claude`). Mặc định `claude-opus-5-5`, effort `low`.
  - Hạn mức ghi theo khoá riêng `claude-main`.
  - Không vào `order` của `--backend auto`; chỉ gọi khi ghi tường minh.
  - Backend `claude` giữ nguyên check chống trỏ vào gói chính.
- **3.2 Chặn hạn mức theo mức dùng trong ngày của máy này:**
  - Trước khi chạy, tính % đã dùng trong ngày = USD của máy này từ 0h ngày hôm đó (giờ máy) tới lúc chạy, chia cho USD/1% tuần.
    - USD lấy bằng `usage_ledger.window_messages` của statusline, giống cách `hh_ps/week.py` đang làm. Không tự viết lại cách tính giá.
    - USD/1% lấy từ số ghim `~/.claude/statusline-usd-per-pct.txt`. Không có số ghim thì dùng số tự hiệu chỉnh của statusline.
  - Tính trên toàn bộ phiên Claude của máy này (brain, hand, `claude-main`), không riêng `claude-main`.
  - Nếu % đã dùng ≥ `backends.claude-main.max_day_pct` (mặc định 5) thì thoát mã 7 kèm lời nhắn "ghi yêu cầu vào bàn giao để Opus quyết".
  - Không tính được (thiếu ledger, thiếu USD/1%) thì chặn luôn (fail-closed) và báo lý do.
- **3.3 Phạm vi:** chỉ việc sáng tạo. Sol vẫn phải dùng dsh cho code và tài liệu thường.

## 4. Policy mới

Các file phải sửa cùng lúc (khảo sát 07/11):
- `scripts/session-start-policy.sh:7-34` (bản dài);
- `scripts/inject-policy.sh:4-6` (bản ngắn, test chặn dưới 1800 ký tự ở `tests/test_policy_brain_context.py:53`);
- `templates/ext-hand-preamble.md:15-16,24-33,42-47`;
- `templates/ext-hand-test-reminder.md:3`;
- `agents/hand.md:34-42,49`;
- `skills/ext-hand/SKILL.md`, `skills/side-session/SKILL.md`, `README.md`.

Nội dung:
- **4.1 LUẬT CHỌN HAND 3 tầng:** bảng lane ở mục 1.1. Việc sáng tạo giao hand Opus `low`. Việc dài, nhiều bước giao phiên Sol (thay ngưỡng "trên 1 giờ").
- **4.2 LUẬT DỮ LIỆU:** dsh, gemini và backend codex dùng làm hand giữ nguyên luật cũ. Phiên Sol được đọc secret và dữ liệu khách hàng như Opus. Luật không hiện giá trị `.env` vẫn áp cho mọi tầng.
- **4.3 LUẬT TEST:** danh sách mức kỹ thay bằng 2 nhóm ở phần Tóm tắt. Mức kỹ đòi đánh giá bằng chạy thực tế:
  - **Nhóm tạo hứng thú/trả tiền:** Opus ghi giả thuyết, chỉ số, ngưỡng thành công, thời gian đo trong spec. Sol đảm bảo có event analytics và feature flag hoặc A/B. Ai đọc kết quả thì chỉ đọc số tổng hợp, không chứa thông tin cá nhân.
  - **Nhóm bảo mật:** Sol chạy SAST, quét dependency, và DAST trên staging của chính dự án.
- **4.4 LUẬT REVIEW:** Sol review code của dsh. Opus review spec, plan, giải pháp và đọc bàn giao, không đọc diff của task đã giao Sol. Vẫn không giao hand review việc của hand.
- **4.5 Dự phòng hạn mức:**
  - dsh hết hạn mức: Sol dùng `hand-ext --backend codex --effort medium`.
  - Sol hết hạn mức: task về Opus, hoặc chờ reset.
  - Máy này đã dùng từ 5% Claude trong ngày: thực hiện như mục 3.2.

## 5. Kiểm thực tế

- 5.1 Chạy `side-session start --provider codex` với một task L0 thật trong repo này. Sol phải gọi được `hand-ext` dsh, review diff, ghi bàn giao và `.done`, mà không có lần nào kẹt hỏi duyệt.
- 5.2 Trong phiên đó, gọi thử một lượt `hand-ext run --backend claude-main` với brief sáng tạo nhỏ. Dùng ngưỡng thấp giả để kiểm cả nhánh bị chặn (thoát mã 7).
- 5.3 Đo sau 1-2 tuần: token Opus trên mỗi task (`usage_ledger.py --since`), % tuần Sol, token dsh (`hand-ext report`), số lỗi Opus bắt được ở bước duyệt mà Sol bỏ sót.

## 6. Quyết định đã chốt (07/11/2026)

- **Q1. Sandbox của phiên Sol:** `workspace-write`, cộng `sandbox_workspace_write.network_access=true` và `writable_roots` gồm `worktree_root`, `runs_dir`, `handoff_dir`. Hand triển khai phải chạy thử để xác nhận đủ quyền gọi `hand-ext`.
- **Q2. Ngưỡng chặn `claude-main`:** chặn khi máy này đã dùng từ 5% hạn mức tuần Claude trở lên trong ngày hôm đó (mục 3.2).
