## Tóm tắt
- Kết quả: xong Gói C; Sol đã review, commit `9436d00` trên `side/cfg-goi-c`; worktree sạch, chưa push/merge.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py`: defaults `native.claude/codex=auto`.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/config.py`: field native cuối dataclass, nạp qua loader chung và validate auto/off.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/cli.py`: pick thêm `native`, `native_reason`, giữ preflight/guard/order.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/native.py`: eligibility theo provider/account, Claude model/effort đối chiếu frontmatter thật.
- `hybrid-hands/tests/test_hand_ext_native.py`: đúng 2 ca plan, global Claude off và effort mismatch.
- Test hẹp: `python3 -m unittest discover -s hybrid-hands/tests -p test_hand_ext_native.py` → 2 OK; tương tự `test_hand_ext_defaults.py` → 2 OK.
- Full suite bằng hand riêng, đúng 1 lần cuối: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py'` → 492 OK, 0 skip/fail/error, exit 0, 92.011 s.
- `git diff --check` và `git diff --cached --check` đạt; pick thực từ bin worktree trả Codex cùng account, `native:true`.
- Chưa kiểm chứng spawn native thật/tool availability; `native:true` là eligibility, reason yêu cầu caller kiểm capability và dùng model/effort pick.
- Opus cần kiểm cách hiểu eligibility này; version/changelog/tài liệu, cập nhật runtime và tích hợp main dành cho Opus theo brief.

## Phạm vi và hành vi

Chỉ đổi 4 file trong `lib/hand_ext/` và 1 file test ở trên; không sửa `lib/shared_config.py`, `lib/side_session/`, `lib/cc_switch/`, AGENTS.md, README, CHANGELOG, version hay cấu hình thật. Không tạo global config thật; các test dùng HOME/HYBRID_HANDS_CONFIG tạm.

`ExtConfig.native` được thêm cuối với default riêng mỗi instance, giữ tương thích constructor cũ. DEFAULTS mới đi vào loader chung của Gói A nên global/repo vẫn merge sâu. Giá trị phải là object chỉ gồm claude/codex và auto/off.

Pick giữ nguyên backend/model/effort/account/skipped và các guard cũ; không backend dùng được vẫn có `native:false` và reason. Backend không hỗ trợ, native off, caller không xác định/khác provider, account không khớp, frontmatter thiếu/hỏng hoặc model/effort Claude mismatch đều false. Claude aliases và vN dùng options hiệu lực sẵn có; so account bằng config_dir/home đã chuẩn hóa. Frontmatter đọc từ `PLUGIN_DIR/agents/hand.md`, không sinh hay đổi agent.

Caller Codex nhận qua CODEX_THREAD_ID, Claude qua CLAUDECODE=1. Hai marker active cùng có thì fail closed. CLAUDE_CODE_SESSION_ID kế thừa từ cha không làm Codex thành ambiguous. Không đọc credential, runtime config, transcript hay RPC để quyết eligibility.

## Review của Sol và giới hạn cần Opus đọc

Hand đầu giữ native luôn false do CLI không thể chứng minh tool availability. Sol review phát hiện điều này vô hiệu hóa nhánh auto, đồng thời việc dùng parent Claude session ID như active runtime marker làm Sol Codex bị ambiguous. Đã giao lại đúng một lần cho cùng backend Codex; bản sửa đã được Sol đọc toàn bộ helper, config và diff/test, rồi chốt trước full suite.

Cách hiểu triển khai: `native` là policy eligibility, không phải dispatch hay bằng chứng tool đã được expose. Lý do thành công ghi rõ `native eligible; caller must verify native tool capability and select pick model/effort for Codex`. Không thêm key/env capability ngoài spec, không suy khả năng spawn từ env marker. Brain vẫn phải có native tool và chọn đúng model/effort. Nếu Opus muốn `native:true` đồng nghĩa đã xác minh tool thực tế, cần chốt nguồn capability riêng; CLI hiện chưa có nguồn đó. Chưa spawn native Claude/Codex thật trong Gói C.

Không tăng version/cập nhật plugin runtime theo yêu cầu brief. Lệnh pick kiểm chứng dùng bin trong worktree; các lượt delegate dùng bin tuyệt đối ở repo chính như yêu cầu. Runtime đang cài chưa nhận patch Gói C.

## Kiểm chứng chi tiết

- Hai test mới là toàn bộ ngân sách Gói C; không thêm ma trận hoặc ca thứ ba. Test thêm 43 dòng, code thêm 117 dòng (theo diff commit), dưới mức 1/2 code.
- Sau lượt sửa, hand chạy hai lệnh unittest hẹp ở tóm tắt với HOME/HYBRID_HANDS_CONFIG tạm; mỗi lệnh 2 test OK. Lượt code đầu cũng chạy cùng nhóm hẹp, tổng 4 OK; không full suite ở hai lượt code.
- Full suite do hand tester riêng `cfg-goi-c-full-test` chạy đúng một lần trên snapshot patch cuối trong worktree cách ly `/Users/anhtp/.hybrid-hands/worktrees/cfg-goi-c-20261109-163048-742651-cfg-goi-c-full-test-codex`. Command chính xác ở tóm tắt, unittest 92.011 s, subprocess 93.088 s; 492 tests, 0 skips/failures/errors, exit 0.
- Subprocess full suite đặt HOME tạm, HYBRID_HANDS_CONFIG tới file tạm chưa tồn tại, HYBRID_HANDS_STATE_DIR/CODEX_HOME/CLAUDE_CONFIG_DIR trong HOME tạm, PYTHONDONTWRITEBYTECODE=1; bỏ CODEX_THREAD_ID/PASEO_AGENT_ID/CLAUDECODE/CLAUDE_CODE_SESSION_ID/HYBRID_HANDS_HAND_SCOPE, giữ PATH. HOME tạm đã dọn; không dọn output/llm có sẵn.
- Full suite không tạo patch; hand không sửa code/test/tài liệu. Tất cả tiến trình hand đã thoát; wrapper đã dọn worktree cách ly của chính lượt chạy theo lifecycle mặc định.
- Sol chạy `git diff --check`, `git diff --cached --check`, xem staged diff/stat trước commit; đều đạt. Sau commit `git status --short` rỗng.
- Sol chạy `/Users/anhtp/app/claude-plugins-wt/cfg-goi-c/hybrid-hands/plugins/hybrid-hands/bin/hand-ext pick --json`: backend codex, model gpt-6.1-sol, effort low, account gpt, skipped rỗng, native true, reason như trên. Không dispatch native.
- Không chạy suite frontend/statusline hoặc cài/reload plugin; không đổi file sau full suite ngoài commit và bàn giao.

## Các lượt hand và bằng chứng

Tất cả dùng backend Codex, model gpt-6.1-sol, effort low; preflight `hand-ext pick --json` trước từng lượt. Lượt code và full test dùng `--backend auto`; sửa review dùng `--backend codex` đúng luật cùng backend một lần. Không có lỗi hand-ext hay ngoại lệ tự code/test; Sol chỉ viết brief, review, commit và bàn giao.

| Lượt | Exit / kết quả | Token input / cached / output | Report |
|---|---|---|---|
| Code | 0 / ok, patch 5 file | 319486 / 282752 / 3830 | `output/llm/hand-ext/20261109-162606-531011-cfg-goi-c-code-codex/report.md` |
| Sửa review | 0 / ok, patch 1 file | 140163 / 119424 / 1226 | `output/llm/hand-ext/20261109-162940-318262-cfg-goi-c-fix-codex/report.md` |
| Full test riêng | 0 / ok, patch rỗng | 479066 / 458240 / 1741 | `output/llm/hand-ext/20261109-163048-742651-cfg-goi-c-full-test-codex/report.md` |

Các report tương đối tính từ `/Users/anhtp/app/claude-plugins-wt/cfg-goi-c`. Wrapper cả ba lượt báo used_percent=10.0, resets_at=2026-11-16T06:19:22+00:00; summary không nêu cửa sổ nên không tự gán 5h/tuần. USD~ chưa lấy (`?`), không suy quota từ token.

## Bàn giao Git

- Branch: `side/cfg-goi-c`.
- Commit: `9436d00` — `feat(hand-ext): expose native eligibility in backend pick`.
- 5 file, 160 insertions(+), 2 deletions(-); worktree sạch.
- Không push, merge main, bump version/changelog hoặc cập nhật cài đặt runtime, theo brief giao riêng cho Opus.
