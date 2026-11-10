# Plan: mô hình 3 tầng Opus / Sol / dsh

## Tóm tắt

- **Mục tiêu:** làm theo spec `2026-11-07-ba-tang-opus-sol-dsh-spec.md`. Có 5 nhóm: phiên Sol trên Codex, backend `claude-main`, policy mới, kiểm thực tế, và (thêm 07/11) dự phòng 429 bằng Sol low cùng hạn mức GPT trên Paseo và statusline.
- **Trạng thái (07/11/2026, 16:35):** xong mọi task trừ 5.6. Nhánh `feat/ba-tang-opus-sol-dsh` đã merge fast-forward vào `main` và push (người dùng đồng ý 07/11). Hai plugin đọc thẳng từ thư mục repo (`hybrid-hands` 0.24.0, `statusline` 0.19.1), `claude plugin validate` đạt. `paseo daemon restart` đã chạy lúc 15:40 (lệnh tắt luôn phiên brain chạy dưới Paseo, mã 137); panel đã hiện dòng `GPT tuần`.
  - Test đầy đủ: hybrid-hands 396/396 (16:35), statusline 187/187 (15:40). Lỗi chập chờn có từ trước `test_cc_switch_self.CcSwitchSelfTest.test_worker_sigterms_tui_then_reloads_paseo` (fail khi chạy cả bộ, chạy riêng xanh); chưa xử lý.
  - Lịch sử các lượt sửa và kiểm thực tế ghi ở từng task mục 4 và 5.
  - **Phiên brain sau làm tiếp:**
    1. **5.6:** còn một lượt hand codex low thật để sổ có `cost_usd`, rồi xem `hh-ps` và thanh trạng thái hiện đủ USD và %; Paseo không còn tài khoản `~/.codex`. Gộp: ẩn `GPT 5h ?` trên cây khi tài khoản không có cửa sổ 5h; typecheck TS `hh-tree-pane`, `paseo-hh-tree`; xem UI trên điện thoại (người dùng tự xem).
    2. Phiên `sol-paseo` do phiên brain khác mở, không động vào.
    3. Đo lại 4.3 trong khoảng 14-21/11/2026.
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

- [x] 4.1 Chạy spec mục 5.1 (phiên Sol làm một task L0 thật).
- [x] 4.2 Chạy spec mục 5.2 (`claude-main`, cả nhánh bị chặn).
- [x] 4.3 Ghi số đo ban đầu cho spec mục 5.3 vào plan này, hẹn đo lại sau 1-2 tuần (khoảng 14-21/11/2026).
  - Baseline 07/11/2026 (0h đến 14:55, +07; mọi USD là ước tính từ token):

    | Chỉ số | 07/11 | Nguồn |
    |---|---|---|
    | Opus 5.5, mọi repo | 493 tin; output 430k, cache write 1,79M, cache read 50,5M token; ~42,26 USD API | `statusline/plugins/statusline/scripts/usage_ledger.py --since 2026-11-07T00:00:00+07:00` |
    | Opus trên mỗi task | không tách được: ledger chỉ tách theo phiên (2 phiên claude-plugins: ~7,85 và ~7,48 USD) | như trên |
    | Sol, % tuần | 3,0% (sáng 2,0%), reset 09/11 13:19 +07; tài khoản không có cửa sổ 5h (`secondary` null) | `~/.hybrid-hands/codex_usage.jsonl`, `rate_limits` rollout `~/.codex-hand` |
    | Sol, token theo phiên (input/cached/output) | sol-411 5,21M/5,12M/21k; sol-51-52 15,80M/15,66M/57k; sol-412-414 và sol-53 mỗi phiên khoảng 6,5M (đang chạy) | `total_token_usage` cuối của rollout |
    | dsh | 23 lượt; input 98,1M (cached 95,7M), output 786k; ~2,23 USD Go. Lượt nặng nhất sol-51-52: 30,9M/174k, ~0,57 USD | `~/.hybrid-hands/go_usage.jsonl` |
    | Lỗi Opus bắt được mà Sol bỏ sót | 2 (test giá null tường minh; dòng báo `start` codex) | mục 4.11 |

  - Lúc đo lại: tính Opus theo task bằng cách ghép mã phiên với task; tính số dsh từ `go_usage.jsonl`, không dùng `hand-ext report` (lỗi 4.15).
- [x] 4.15 Lỗi: `hand-ext report --since ... --cwd <repo>` lọc theo cwd nên bỏ sót các lượt chạy trong worktree (`~/app/claude-plugins-wt/*`, `~/.hybrid-hands/worktrees/*`): ngày 07/11 report đếm 15 lượt, sổ có 23. Không truyền `--cwd` thì report in "Tổng lượt: 0". Sửa: các lượt có git common dir trùng repo thì tính cho repo đó. Thêm 1 test.
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
- [x] 4.11 Lỗi (phát hiện 07/11, 13:55): `side-session ls` hiện cùng `49792/272000` cho cả `sol-l0-test` và `sol-l0-test2`.
  - Nguyên nhân: `lib/side_session/tokens.py:69-78` `codex_rollout`: rollout Codex không mang uuid của side-session trong tên, nên rơi về rollout mới nhất có mtime ≥ `started`. `~/.codex-hand` dùng chung với backend `codex` của hand-ext, nên rollout của lượt hand (ví dụ `fix-47-48b`) bị tính cho mọi phiên Sol. Phiên đang chạy cũng có thể bị đếm nhầm.
  - Sửa: lúc `watch` gặp rollout đầu tiên tạo sau `started` mà sự kiện `session_meta` có `cwd` trùng workdir của phiên, ghi đường dẫn rollout vào state rồi luôn dùng đường đó. Phiên cũ không ghim được thì hiện `?`, không đoán. Thêm 1 test.
  - Thêm (14:15): dòng báo của `side-session start` provider codex vẫn in `cap 300000`; đổi thành trần context 272000 (giao phiên sau, không thuộc lượt `sol-411`).

- Kết quả lượt `sol-411` + `sol-51-52` (07/11, 13:38-14:34): 4.1 đạt (không kẹt hỏi duyệt, `.done` đúng chỗ, dsh trong sandbox Sol chạy được shell nhờ 4.9); 4.2 đạt (`claude-main` thoát 0, trả 3 câu ≤80 ký tự). Brain áp diff hai worktree, điền giá mặc định Q5b, sửa 1 test cho giá null tường minh, sửa dòng báo `start` của codex thành "context 272000 (tự nén)"; 392 test xanh.
- [x] 4.12 Test chưa cô lập biến `CODEX_SANDBOX`: chạy bộ test bên trong phiên Sol thì `test_hand_ext_dsh.BuildCommandTest.test_argv_env_and_stdin` (`tests/test_hand_ext_dsh.py:108`) fail vì nhận `danger-full-access`. Sửa: các test hand-ext gỡ `CODEX_SANDBOX` khỏi env (setUp chung), chỉ test seatbelt đặt nó.
- [x] 4.13 Cảnh báo dsh trong sandbox Sol: `permission (@deepseek-ai/dsh-permission-presets): Error: permission: unknown preset "danger-full-access" (known: read-only, workspace-write)` (stderr của `output/llm/hand-ext/20261107-133926-sol-411-fix-dsh/`). Preset thêm ở `templates/dsh-hand.yml` không được plugin nhận; entry permission không kích hoạt, shell vẫn chạy. Cần điều tra mã nguồn `dsh-permission-presets` (bản 0.2.1-rc.5): preset có cố định không; permission không kích hoạt thì hành vi approval ra sao; chọn cách cấu hình đúng.
- [x] 4.14 Hand `codex` do Sol gọi (`hand-ext run --backend codex`, ví dụ nhánh dự phòng 429 → Sol low) không chạy được shell: `sandbox-exec: sandbox_apply: Operation not permitted`, exit 71, vì lồng sandbox như 4.9. CLI vẫn thoát 0 với report "bị chặn". Sửa giống 4.9: khi `CODEX_SANDBOX=seatbelt`, backend codex chạy `-s danger-full-access` thay `workspace-write` (seatbelt của Sol vẫn giới hạn quyền ghi), `read-only` thì từ chối; ghi mode thật vào meta. Thêm 1 test.
- Kết quả lượt `sol-412-414` (07/11, 14:40-14:55, Sol đã review; patch 17 file, +218/-83):
  - 4.12: `tests/hand_ext_case.py` dùng chung, gỡ `CODEX_SANDBOX` cho 12 module test hand-ext.
  - 4.13: preset không cố định. Lỗi do bản sao setup `~/.dsh-hand/hand.patch.yml` cũ thiếu `danger-full-access`. Sửa: mỗi lượt chụp template hiện tại vào `run_dir/hand.patch.yml` và nạp đầu argv `--patch`; không sửa shared patch, không vá gói dsh.
  - 4.14: `backends/sandbox.py` mới; codex trong seatbelt chạy `danger-full-access`, `read-only` thì từ chối, mode thật ghi vào meta.
  - Lỗi lộ thêm khi chạy thật: `templates/dsh-hand.yml` đặt `retryPolicy.initialDelayMs`/`maxDelayMs` sai cấp (phải nằm dưới `backoff`), dsh báo NO_ADAPTER. Shared patch cũ che lỗi này. Sol đã sửa.
  - Test: 394/394 trong worktree (seatbelt); chạy thật codex low và dsh trong sandbox Sol, exit 0, không hỏi duyệt, không `sandbox_apply`.
- [x] 4.16 Lỗi nhỏ: `side-session stop` provider codex vẫn in `(146296/300000 tokens)`; đổi giống dòng báo `start` (context 272000, tự nén). Gộp vào gói 4.15.
- Kết quả lượt `sol-415` (07/11, 15:40-16:30, Sol đã review; 5 file): `lib/hand_ext/report.py` mới gom sổ theo git common dir (gồm lượt trong worktree, dedup, dùng metadata còn sót), report in rõ phạm vi lọc; `side-session stop` codex báo context 272000 (tự nén). Report thật ở repo chính: 16 lượt ngày 07/11. Không khôi phục được lượt của worktree đã xoá sạch metadata, nên vẫn tính baseline dsh từ `go_usage.jsonl`. 396 test xanh ở repo chính.
- Ghi nhận chi phí: lượt dsh của `sol-51-52` chạy 45 phút (13:39-14:24), 30,9M token input (30,3M cache), 174k output, rồi chết vì 429 quá tải. Nhánh 5.1 giúp lần sau chuyển sớm hơn, nhưng thời gian dsh tự thử lại theo `retryPolicy` trước khi trả 429 vẫn dài. Xem lại `maxRetries`/`maxDelayMs` ở 4.3.

## 5. Dự phòng 429 bằng Sol low, hiện hạn mức GPT trên Paseo và statusline

Người dùng yêu cầu (07/11, 14:00), duyệt 14:10. Lane L2: brain cắt thành gói L1 giao phiên Sol; đồng thời dùng làm lượt chạy lại 4.1. Mức test tối thiểu.

- **Quyết định (người dùng chốt 07/11, 14:10):**
  - Q5a: dsh trả 429 quá tải (`CAPACITY_RE` ở `lib/hand_ext/backends/base.py:24`) với `--backend auto`:
    - **dsh đã sửa nhiều** (patch ≥ `backends.dsh.capacity_wait_min_lines` dòng thêm + xoá, mặc định 30): đợi. Giữ worktree, chờ 3 phút rồi chạy dsh tiếp trên worktree đó (brief kèm ghi chú "đã có patch, làm tiếp"), tối đa 2 lần. Vẫn 429 thì trả `failed` và giữ patch.
    - **dsh sửa ít** (dưới ngưỡng, kể cả rỗng): bỏ patch dsh, chạy lại brief bằng backend `codex`, model `gpt-6.1-sol`, effort `low`.
    - Report ghi rõ nhánh đã đi.
  - Q5b: USD GPT là **ước tính** từ token × đơn giá API của `gpt-6.1-sol` (input, cached input, output mỗi 1M token), ở khoá `backends.codex.price_per_mtok`. Brain tra giá công khai (kèm link và ngày) rồi đặt làm mặc định; thiếu giá thì hiện `?`.
    - Giá đã tra (07/11/2026, [OpenAI API pricing](https://developers.openai.com/api/docs/pricing), trang không ghi ngày cập nhật): `gpt-6.1-sol` mức Standard, context ≤272k: input $2,00, cached input $0,10, output $10,00 mỗi 1M token. Context >272k: $4,00 / $0,20 / $15,00. Batch/Flex rẻ hơn một nửa; Fast và Ultrafast đắt hơn.
    - Mặc định `backends.codex.price_per_mtok` = `{input: 2.00, cached: 0.10, output: 10.00}`, vì Codex tự nén ở 272k nên các lượt gần như luôn ở mức context ngắn. Đặt mặc định sau khi gói `sol-51-52` xong (gói đó để `null`).
  - Q5c (đúng như đề xuất): account GPT free cũ là `~/.codex` (model `gpt-5.6-terra`/`luna`), account mới là `~/.codex-hand`. Tạm tắt `~/.codex` nghĩa là Paseo, hh-ps, statusline không đọc hay hiện nó, và hand-ext, side-session không dùng nó. Không đăng xuất, không xoá.
- [x] 5.1 Dự phòng 429 (Q5a): `lib/hand_ext/run_cmd.py`, logic chọn backend của `auto`. Cập nhật policy (`hooks/inject-policy.sh` dòng Dự phòng, giữ dưới 1800 ký tự), `skills/ext-hand/SKILL.md` (mục 429), README. 1 test.
- [x] 5.2 Ghi số liệu GPT cho mỗi lượt hand codex: hand-ext đã đọc `rate_limits` (`backends/codex.py:44` `quota_from_rate_limits`). Thêm ghi vào sổ (giống `~/.hybrid-hands/go_usage.jsonl`, ví dụ `codex_usage.jsonl`): `run_id`, `ended`, `model`, `effort`, token, `cost_usd` ước tính (Q5b), `used_percent` 5h và tuần kèm `resets_at`, `codex_home` dạng tên thư mục. Không ghi hội thoại. 1 test.
- [x] 5.3 Panel Paseo (`hh-ps`/`hh-tree`, `lib/hh_ps/`):
  - mỗi phiên hand codex và phiên Sol hiện USD ước tính và % hạn mức GPT;
  - thêm dòng hạn mức tài khoản GPT `~/.codex-hand` (5h, tuần, giờ reset), cạnh dòng Claude tuần, lấy mẫu mới nhất từ sổ 5.2 hoặc rollout `~/.codex-hand`;
  - không đọc `~/.codex` (Q5c).
  - Trước khi sửa, hand đọc `limits.py`, `week.py`, `tree.py`, `render.py` để theo cách dòng Claude tuần đang làm. 1 test.
  - Đã làm (phiên `sol-53`, 07/11 14:40-15:30; 14 file, +760/-74): module mới `lib/hh_ps/codex.py` đọc sổ 5.2 và rollout đã ghim, USD ước tính `~$`; dòng `GPT tuần` cạnh dòng Claude tuần; `hh-ps --json` có trường tương ứng; pane `hh-tree-pane` và plugin `paseo-hh-tree` nhận schema mới; `skills/paseo/SKILL.md` mục 4 đã cập nhật. 395 test xanh ở repo chính.
  - Chạy thật (15:35): `GPT tuần tổng 4.0% · reset 09/11 13:19`; phiên Sol hiện `~$1.02  GPT 5h ? · tuần 4.0%`.
  - Còn lại (gộp vào 5.6): tài khoản không có cửa sổ 5h nên nên ẩn `5h ?` thay vì hiện `?`; chưa typecheck TS đủ dependency và chưa xem UI trên điện thoại.
- [x] 5.4 Statusline (plugin `statusline/`): thêm đoạn ngắn % tuần và 5h của tài khoản GPT `~/.codex-hand` cùng USD GPT hôm nay, từ sổ 5.2. Không có mẫu trong 24 giờ thì ẩn. 1 test.
  - Đã làm (phiên `sol-54`, 07/11 15:00-15:35; 7 file, +280/-15): `scripts/gpt_usage.py` mới chỉ đọc sổ, lọc `.codex-hand`; hàng GPT trong `statusline.sh` sau hàng Go; statusline 0.19.1. Chạy thật: `GPT 5h:-- | 7d:3% | hôm nay ~$?` (1 trong 2 lượt hôm nay thiếu `cost_usd` nên tổng là `?`).
  - Test: ở repo chính 187/187 xanh. Trong sandbox Sol, 1 test hiệu năng đỏ cả trên bản gốc, do sandbox chậm.
  - Còn lại (5.6): cập nhật plugin statusline đã cài lên 0.19.1 rồi xem thanh trạng thái thật.
- [x] 5.5 Paseo app (`~/.paseo/config.json`, sửa khi người dùng đã duyệt mục 5):
  - thêm provider tuỳ biến `codex-hand` (`extends: "codex"`, `env.CODEX_HOME=/Users/anhtp/.codex-hand`, model `gpt-6.1-sol`) theo `skills/paseo/SKILL.md` mục 4;
  - tạm tắt provider `codex` mặc định (`~/.codex`) nếu Paseo 0.15.0 có khoá tắt provider, không thì ghi đè `codex` bằng `env.CODEX_HOME` của `~/.codex-hand`;
  - `paseo reload`, kiểm `paseo provider models codex-hand`;
  - sao lưu config trước khi sửa; hoàn tác bằng cách khôi phục bản sao lưu rồi `paseo reload`.
  - Đã làm (hand Claude, 07/11 14:25): sao lưu `~/.paseo/config.json.bak-20261107`; thêm `agents.providers.codex = {enabled: false}` (khoá chính thức "Disabling a provider" trong docs custom-providers) và provider `codex-hand` (`extends: codex`, `env.CODEX_HOME=/Users/anhtp/.codex-hand`, model `gpt-6.1-sol`). `paseo reload` OK; `codex-hand` Ready, có `gpt-6.1-sol`; `codex` báo "Provider codex is disabled". Hoàn tác: `cp ~/.paseo/config.json.bak-20261107 ~/.paseo/config.json && paseo reload`.
  - Paseo 0.15.0 không có lệnh xem hạn mức hay usage, nên hạn mức GPT trên panel phải do 5.3 tự hiện (đọc sổ 5.2).
  - Paseo báo các khoá `plugins.hh-tree.*` đổi từ trước, cần `paseo daemon restart` mới áp dụng; chưa restart.
  - Việc nhỏ còn lại: `skills/paseo/SKILL.md` mục 4 đổi id mẫu thành `gpt-6.1-sol` và nhắc `codex: {enabled: false}` (gộp vào gói 5.3).
- [ ] 5.6 Kiểm thực tế cùng lượt chạy lại 4.1/4.2: một lượt hand codex low hiện đủ USD và % trên `hh-ps` và statusline; Paseo không còn hiện tài khoản `~/.codex`.
