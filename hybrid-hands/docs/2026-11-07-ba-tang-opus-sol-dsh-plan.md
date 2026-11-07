# Plan: mô hình 3 tầng Opus / Sol / dsh

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-07-ba-tang-opus-sol-dsh-spec.md`. Có 5 nhóm: phiên Sol trên Codex, backend `claude-main`, policy mới, kiểm thực tế, và (thêm 07/11) dự phòng 429 bằng Sol low cùng hạn mức GPT trên Paseo và statusline.
- **Trạng thái (07/11/2026, 14:00):** nhóm 1-3 xong; đã sửa 4.4, 4.5, 4.6 (commit `e6cf199` trên nhánh `feat/ba-tang-opus-sol-dsh`, chưa merge main, chưa push). Đã sửa 4.7-4.10 và áp diff L0 của `sol-l0-test2`, brain đã review, 388 test xanh, đã commit. Phiên `sol-l0-test2` đã dừng, worktree và nhánh `side/sol-l0-test2` đã dọn, `~/.claude/.claude.json` lạ đã xoá. Mới thêm 4.11 và nhóm 5 (chờ người dùng duyệt).
  - Test đầy đủ: 388 test xanh (07/11, 13:50). Lỗi chập chờn có từ trước `test_cc_switch_self.CcSwitchSelfTest.test_worker_sigterms_tui_then_reloads_paseo` (fail khi chạy cả bộ, chạy riêng 5/5 xanh); chưa xử lý.
  - 4.2 nhánh chặn đã thử: `.claude/hybrid-hands.json` tạm `max_day_pct` = 1 → "máy này đã dùng 2.4% Claude hôm nay (ngưỡng 1%)", thoát mã 7; đã xoá file tạm.
  - Lượt chạy lại 4.1 + 4.2 bằng phiên Sol `sol-l0-test2` (07/11, 12:11-12:18): L0 xong và đúng, nhưng lộ 3 lỗi mới 4.8 (`.done` không ghi được nên `ls` báo `running` mãi), 4.9 (dsh trong sandbox Sol không chạy được shell), 4.10 (`claude-main` trong sandbox Sol báo chưa đăng nhập). Chưa tick 4.1, 4.2.
  - Lượt sửa: `fix-47-48` dsh chết vì Go 429 quá tải, chạy lại `fix-47-48b` bằng `--backend codex --effort medium` (3 phút); `fix-49-410b` dsh (10 phút). Brain tự sửa thêm: 2 kỳ vọng test cũ trong `tests/test_side_session.py`; dsh từ chối `danger-full-access` khi ở ngoài seatbelt (preset mới trong template chỉ dùng cho ca lồng sandbox).
  - **Phiên brain sau làm tiếp:**
    1. Hỏi người dùng duyệt mục 5 (Q5a-Q5c).
    2. Sửa 4.11 (dsh, `lib/side_session/tokens.py`), cùng lúc giao 5.1-5.2 (`lib/hand_ext`). Sau đó giao 5.3 (`lib/hh_ps`) và 5.4 (`statusline/`) song song. 5.5 do brain làm (config máy người dùng).
    3. Chạy lại 4.1 + 4.2 + 5.6 bằng một phiên Sol mới (`side-session start --provider codex --worktree`); đạt thì tick.
    4. Ghi số đo ban đầu 4.3.
    5. Hỏi người dùng có merge vào main không.
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
- [x] 4.4 Lỗi phát hiện ở 4.1: Codex TUI dừng ở màn "Trust this folder?", nên phiên Sol chạy không người trực bị kẹt.
  - Sửa: trước khi mở phiên, `side-session start` ghi `[projects."<workdir>"] trust_level = "trusted"` vào `<codex_home>/config.toml`, chỉ khi workdir chưa có mục này. Workdir có thể là worktree mới.
  - Cột TOKENS báo 0 trong lúc kẹt là đúng: lúc đó chưa có rollout.
  - Thêm 1 test.
  - Đã sửa (lượt dsh `fix-44-45`): module mới `lib/side_session/codex_trust.py`, chạy làm prelude trong screen ngay trước `exec codex`.
- [x] 4.5 Lỗi: `watch` đếm token Codex bằng `total_tokens`, gồm cả `cached_input_tokens` (`lib/side_session/tokens.py:6`).
  - Hậu quả: phiên Sol chạm cap 300k sau khoảng 2 phút làm việc (304k input, trong đó 260k cache; 4,8k output) và bị dừng (trạng thái `capped`).
  - Sửa: đếm `input_tokens - cached_input_tokens + output_tokens`, giống cách đếm của Claude (không tính cache read).
  - Thêm 1 test.
  - Đã sửa cùng lượt `fix-44-45`; 382 test xanh.
- [ ] 4.6 Lỗi: lượt `hand-ext run --backend claude-main` do Sol gọi trong sandbox lỗi ngay ở bước tạo worktree. Report chỉ có "Lỗi: Preparing worktree (detached HEAD 3a56c5c)", run dir `output/llm/hand-ext/20261107-113756-sol-l0-test-creative-claude-main/`.
  - Giả thuyết: sandbox `workspace-write` của Codex giữ `.git` ở chế độ chỉ đọc, nên `git worktree add` không ghi được `.git/worktrees`.
  - Điều tra: tái hiện bằng `codex exec -s workspace-write` với một lệnh `git worktree add` nhỏ. Kiểm xem thêm `<repo>/.git` vào `writable_roots` có đủ không.
  - Kết quả điều tra (brain, 07/11): tái hiện bằng `codex exec -s workspace-write`; chỉ có thư mục đích trong `writable_roots` thì lỗi `could not create leading directories of '.git/worktrees/w1': Operation not permitted`; thêm `<repo>/.git` thì `EXIT=0`. Cách sửa: `codex_writable_roots` thêm git common dir của workdir (`git rev-parse --path-format=absolute --git-common-dir`), giao dsh lượt `fix-46`.
  - Worktree sót: lượt `sol-l0-test-fix` đã được dọn, không còn gì.
  - (Không cần dùng) Nếu không đủ, đưa người dùng chọn: Sol gọi hand-ext với `--isolation none`, hay chuyển sandbox của Sol sang `danger-full-access`.
  - Lượt dsh `20261107-113905-sol-l0-test-fix-dsh` bị dừng giữa chừng khi phiên Sol bị cap. Kiểm và dọn worktree còn sót trong `~/.hybrid-hands/worktrees`.
- [x] 4.7 Người dùng chốt (07/11): **272k token là trần context, không phải 300k là trần token tiêu.** Cap hiện tại của phiên Codex (`max_tokens` 300000, so với tổng token cộng dồn ở `lib/side_session/tokens.py` `codex_tokens`, kể cả sau bản sửa 4.5) là sai ý nghĩa: phiên Sol dài sẽ bị `capped` dù context còn trống.
  - Sửa: phiên Codex không bị dừng theo tổng token tiêu. Đo context hiện tại từ sự kiện `token_count` cuối trong rollout (`info.last_token_usage`, tính cả cached vì cache vẫn nằm trong context; xem thêm `info.model_context_window`) và so với trần 272000, khớp `backends.dsh.compact_at` 272000 của hand-ext.
  - Đã chốt (người dùng, 07/11): khi chạm trần thì để Codex tự nén ngữ cảnh, không dừng phiên. Cách làm dự kiến: truyền `-c model_auto_compact_token_limit=272000` vào argv codex (`lib/side_session/commands.py` `codex_argv`); `watch` không đặt trạng thái `capped` theo tổng token với provider codex. Tổng token cộng dồn chỉ để báo cáo.
  - Kiểm lại cột TOKENS/CAP của `side-session ls`/`watch` và tài liệu (`skills/side-session/SKILL.md`, README) cho đúng ý nghĩa mới; thêm 1 test.

- [x] 4.8 Lỗi phát hiện ở lượt `sol-l0-test2` (07/11): Sol làm xong lúc 12:18 (chạy 7 phút), nhưng `side-session ls` vẫn báo `running`/`alive` gần 1 giờ.
  - Nguyên nhân: `handoff_dir` mặc định `docs/work-in-progress/handoffs` chưa tồn tại ở repo chính. Sandbox chỉ cho ghi trong `handoff_dir`, không cho tạo thư mục cha `docs`, nên `mkdir` báo `Operation not permitted`. Sol ghi bàn giao và `.done` sang `output/llm/hand-ext/sol-l0-test2-orchestration/`, ngoài đường dẫn hợp đồng.
  - Thêm: Codex TUI không tự thoát sau `task_complete`, nên cột LIVE vẫn `alive`.
  - Sửa: `side-session start` tạo sẵn `handoff_dir` (`mkdir -p`, ngoài sandbox) trước khi mở phiên. Thêm 1 test.
- [x] 4.9 Lỗi: dsh do Sol gọi không chạy được lệnh shell nào (4 lần): `sandbox-exec: sandbox_apply: Operation not permitted`. macOS không cho lồng sandbox: dsh mở sandbox `workspace-write` bên trong sandbox của Codex. dsh vẫn sửa file được; Sol phải tự chạy test thay.
  - Đã xác minh (hand điều tra, 07/11): trong `codex sandbox` cấu hình như `codex_argv`, `sandbox-exec` lồng báo `sandbox_apply: Operation not permitted` (rc 71); Codex đặt `CODEX_SANDBOX=seatbelt` cho tiến trình con. Gói `dsh-sandbox` cố ý fail-closed (`lib/index.js:272`). Chế độ chọn qua `DSH_PERMISSION_MODE` (`lib/hand_ext/backends/dsh.py:351`) → `templates/dsh-hand.yml:60-63`, preset ở `:72-81` (chỉ có `read-only`, `workspace-write`).
  - Sửa (brain chốt): khi `CODEX_SANDBOX=seatbelt` và dsh xin `workspace-write` thì chạy dsh `danger-full-access` (thêm preset vào template), seatbelt của Sol vẫn giới hạn quyền ghi; ghi mode thật vào report. Dsh xin `read-only` trong seatbelt thì từ chối (fail-closed) với thông báo rõ, vì seatbelt của Sol cho ghi rộng hơn read-only.
- [x] 4.10 Lỗi: `hand-ext run --backend claude-main` do Sol gọi thoát mã 7, status `not_logged_in`, report "Not logged in · Please run /login" (run `20261107-121314-sol-l0-test2-creative-claude-main`). Ngoài sandbox thì `claude-main` chạy được (đã thử ở 4.2 nhánh chặn).
  - Đã xác minh (hand điều tra, 07/11): không do sandbox. Backend `claude-main` đặt tường minh `CLAUDE_CONFIG_DIR=~/.claude` (`lib/hand_ext/constants.py:17`, `backends/claude.py:88` `_base_env`, `:153` `build_command`); khi biến này có giá trị, Claude Code tìm config ở `~/.claude/.claude.json` thay vì `~/.claude.json` và báo chưa đăng nhập, cả trong lẫn ngoài sandbox (`claude auth status`: không đặt biến → `loggedIn: true`; đặt biến → `false`). Lần thử 4.2 trước chỉ đi nhánh chặn (thoát 7 trước khi gọi claude) nên chưa lộ lỗi.
  - Sửa: `claude-main` không đặt `CLAUDE_CONFIG_DIR`, và gỡ biến này nếu kế thừa từ môi trường. Thêm 1 test.
  - Lượt lỗi đã tạo file lạ `~/.claude/.claude.json` (12:13); người dùng tự quyết có xoá không.
- Kết quả còn lại của lượt `sol-l0-test2`: không lần nào hỏi duyệt; `hand-ext` tạo/dọn worktree trong sandbox được (4.6 đạt); diff L0 của dsh (2 dòng, `tests/test_cc_switch_self.py`, Sol review chấp nhận, 383 test xanh) còn chưa commit trong worktree `~/app/claude-plugins-wt/sol-l0-test2`.
- Hạn chế còn lại của 4.9 (chưa sửa): `--sandbox read-only` truyền bằng cờ CLI với `--backend auto` trong seatbelt thì thoát 2 thay vì bỏ qua dsh, vì `candidates()` gọi `doctor()` không thấy `args.sandbox` (`lib/hand_ext/run_cmd.py`). Read-only lấy từ config thì `auto` bỏ qua dsh đúng.
- [ ] 4.11 Lỗi (phát hiện 07/11, 13:55): `side-session ls` hiện cùng `49792/272000` cho cả `sol-l0-test` và `sol-l0-test2`.
  - Nguyên nhân: `lib/side_session/tokens.py:69-78` `codex_rollout`: rollout Codex không mang uuid của side-session trong tên, nên rơi về rollout mới nhất có mtime ≥ `started`. `~/.codex-hand` dùng chung với backend `codex` của hand-ext, nên rollout của lượt hand (ví dụ `fix-47-48b`) bị tính cho mọi phiên Sol. Phiên đang chạy cũng có thể bị đếm nhầm.
  - Sửa: lúc `watch` gặp rollout đầu tiên tạo sau `started` mà sự kiện `session_meta` có `cwd` trùng workdir của phiên, ghi đường dẫn rollout vào state rồi luôn dùng đường đó. Phiên cũ không ghim được thì hiện `?`, không đoán. Thêm 1 test.

## 5. Dự phòng 429 bằng Sol low, hiện hạn mức GPT trên Paseo và statusline

Người dùng yêu cầu (07/11, 14:00). Lane L2: brain viết, người dùng duyệt mục này trước khi giao. Mức test tối thiểu.

- **Quyết định cần duyệt (đề xuất của brain):**
  - Q5a: Khi dsh trả 429 quá tải (`CAPACITY_RE` ở `lib/hand_ext/backends/base.py:24`) và patch của lượt dsh **rỗng**, `--backend auto` tự chạy lại brief bằng backend `codex`, model `gpt-6.1-sol`, effort `low`. Patch dsh không rỗng thì không chuyển, trả `failed` và giữ patch, để tránh làm lại hoặc ghi đè phần đã sửa.
  - Q5b: USD của GPT là **ước tính** từ token × đơn giá trong khoá `backends.codex.price_per_mtok` (input, cached, output), giống cách ước tính Go. Thiếu đơn giá thì hiện `?`, không tự tra giá. Người dùng điền đơn giá.
  - Q5c: "Account GPT free cũ" là `~/.codex` (đăng nhập ChatGPT mặc định, model `gpt-5.6-terra`/`luna`); account mới là `~/.codex-hand`. Tạm tắt `~/.codex` nghĩa là Paseo, hh-ps và statusline không đọc hay hiện `~/.codex`; hand-ext và side-session không bao giờ dùng nó. Không đăng xuất và không xoá `~/.codex`.
- [ ] 5.1 Dự phòng 429 (Q5a): `lib/hand_ext/run_cmd.py`, logic chọn backend của `auto`. Ghi vào report "dsh 429 quá tải → codex low". Cập nhật policy (`hooks/inject-policy.sh` dòng Dự phòng, giữ dưới 1800 ký tự), `skills/ext-hand/SKILL.md` (mục 429), README. 1 test.
- [ ] 5.2 Ghi số liệu GPT cho mỗi lượt hand codex: hand-ext đã đọc `rate_limits` (`backends/codex.py:44` `quota_from_rate_limits`). Thêm ghi vào sổ (giống `~/.hybrid-hands/go_usage.jsonl`, ví dụ `codex_usage.jsonl`): `run_id`, `ended`, `model`, `effort`, token, `cost_usd` ước tính (Q5b), `used_percent` 5h và tuần kèm `resets_at`, `codex_home` dạng tên thư mục. Không ghi hội thoại. 1 test.
- [ ] 5.3 Panel Paseo (`hh-ps`/`hh-tree`, `lib/hh_ps/`):
  - mỗi phiên hand codex và phiên Sol hiện USD ước tính và % hạn mức GPT;
  - thêm dòng hạn mức tài khoản GPT `~/.codex-hand` (5h, tuần, giờ reset), cạnh dòng Claude tuần, lấy mẫu mới nhất từ sổ 5.2 hoặc rollout `~/.codex-hand`;
  - không đọc `~/.codex` (Q5c).
  - Trước khi sửa, hand đọc `limits.py`, `week.py`, `tree.py`, `render.py` để theo cách dòng Claude tuần đang làm. 1 test.
- [ ] 5.4 Statusline (plugin `statusline/`): thêm đoạn ngắn % tuần và 5h của tài khoản GPT `~/.codex-hand` cùng USD GPT hôm nay, từ sổ 5.2. Không có mẫu trong 24 giờ thì ẩn. 1 test.
- [ ] 5.5 Paseo app (`~/.paseo/config.json`, sửa khi người dùng đã duyệt mục 5):
  - thêm provider tuỳ biến `codex-hand` (`extends: "codex"`, `env.CODEX_HOME=/Users/anhtp/.codex-hand`, model `gpt-6.1-sol`) theo `skills/paseo/SKILL.md` mục 4;
  - tạm tắt provider `codex` mặc định (`~/.codex`) nếu Paseo 0.15.0 có khoá tắt provider, không thì ghi đè `codex` bằng `env.CODEX_HOME` của `~/.codex-hand`;
  - `paseo reload`, kiểm `paseo provider models codex-hand`;
  - sao lưu config trước khi sửa; hoàn tác bằng cách khôi phục bản sao lưu rồi `paseo reload`.
- [ ] 5.6 Kiểm thực tế cùng lượt chạy lại 4.1/4.2: một lượt hand codex low hiện đủ USD và % trên `hh-ps` và statusline; Paseo không còn hiện tài khoản `~/.codex`.
