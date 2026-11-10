## Tóm tắt
- Kết quả: xong 2 lỗi theo dõi Codex cho screen/Paseo; version 0.25.1, chưa commit/push.
- `lib/side_session/actions.py`: cảnh báo idle thiếu `.done`; cleanup theo transport, lỗi thì giữ slot/watch để thử lại.
- `lib/side_session/tokens.py`: nhận idle từ lifecycle của đúng rollout đã pin, turn mới trở lại running.
- `lib/side_session/constants.py`: thêm `idle_no_done` vào trạng thái active.
- `lib/side_session/paseo.py`: ánh xạ idle và gọi finish đúng agent/target đã lưu.
- `lib/side_session/paseo_bridge.mjs`: cancel/archive native, giữ lịch sử/workspace, không delete.
- `tests/test_side_session_codex.py`: 2 test mới đỏ→xanh, gồm quit lỗi giữ slot rồi retry thành công.
- `tests/test_side_session_paseo.py`: 1 test mới đỏ→xanh, gồm idle, cleanup timeout và agent đã mất.
- `skills/side-session/SKILL.md`: mô tả trạng thái và hợp đồng cleanup; `.claude-plugin/plugin.json`: bump 0.25.1.
- `lib/hand_ext/backends/dsh.py`: chỉ đồng bộ hằng USER_AGENT thành 0.25.1 theo test version.
- Kiểm chứng: 18 test hẹp xanh; full chạy đúng 1 lần, 405 test có 1 lỗi version; sửa và test version riêng xanh.
- Còn mở: chưa thử daemon/điện thoại thật; không chạy lại full sau sync version để tuân giới hạn một lần.

## Hành vi sau sửa
Các đường dẫn rút gọn `lib/`, `skills/`, `.claude-plugin/` ở trên thuộc `hybrid-hands/plugins/hybrid-hands/`; `tests/` thuộc `hybrid-hands/`.

- Screen: chỉ lifecycle `event_msg` của rollout đã pin quyết định idle. `task_complete` hoặc `turn_aborted` đặt idle, token_count/metadata phía sau không làm mất idle; `task_started` mới trả về running. Rollout thiếu/không đọc được không tự kết luận idle.
- Paseo: dùng trạng thái daemon, `idle` của Codex thành `idle_no_done`; `initializing`/`running` vẫn running. `watch` và `ls` cảnh báo rõ thiếu `.done`, không gửi thêm prompt. Phiên idle tiếp tục được theo dõi, giữ slot max_parallel và chặn trùng tên.
- Khi có `.done`, helper `_finish_codex` dùng `_quit` cho screen hoặc bridge `finish` cho Paseo. Chỉ persist done khi cleanup thành công; sau đó không chiếm slot. Screen quit lỗi nhưng còn sống, lỗi OSError, hoặc cleanup Paseo lỗi/timeout đều giữ active/watch để retry. Agent Paseo đã mất coi là cleanup xong. Không hồi sinh trạng thái terminal.
- Worktree, bàn giao, rollout và lịch sử hội thoại được giữ. `ls` cũng thực hiện cleanup pending `.done`; nếu cleanup chưa thành công thì không hiển thị done giả.

## Giao hand và review
Đã dùng skill `ext-hand`: `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md`.

Sol viết tiêu chí và 3 test trước khi giao hand; cả 3 đỏ đúng lỗi gốc. Đã tìm AGENTS.md/CLAUDE.md ở repo, plugin, thư mục cha và đường dẫn liên quan, gồm hidden/ignored: checkout này không có file luật áp dụng. Brief chép nguyên văn luật người giao về `.env`, credential/API key, không commit/push và không xoá output/llm/.

Lượt `--backend auto` thoát 7 trước khi chạy hand vì doctor phát hiện lệch `model_reasoning_effort`; cài đặt và đăng nhập subscription đều đạt. Không sửa config dùng chung, không dùng dsh. Dùng nhánh dự phòng đã giao `--backend codex --effort medium`, vẫn cách ly worktree:

1. `output/llm/hand-ext/20261107-170657-510649-sol-idle-codex/report.md`: code chính; patch 9 file áp thành công.
2. Sol review phát hiện screen.quit False nhưng code vẫn done. Tái hiện bằng mock, giao lượt sửa riêng; test cũ được mở rộng và đỏ đúng assert giữ watch trước sửa.
3. `output/llm/hand-ext/20261107-171110-835945-sol-idle-review-codex/report.md`: sửa cleanup screen và test, patch 2 file áp thành công; Sol review lại.
4. Sol đồng bộ duy nhất hằng version dsh.USER_AGENT sau lỗi full-suite; đây là chỗ sync version được phạm vi giao cho phép.

Cả hai hand dùng `gpt-6.1-sol` effort medium. Tổng usage: input 624838 (cached input nằm trong input: 543104), output 9808; USD quy đổi ước tính 0.315858, không phải phát sinh gọi API. Mẫu hạn mức tuần cuối 6%, reset 2026-11-09 13:19:15 Asia/Ho_Chi_Minh; cửa sổ 5 giờ không có mẫu. Các worktree hand-ext đã được công cụ dọn; patch/report vẫn còn trong output/llm/.

## Kiểm chứng và bằng chứng
Bằng chứng test lưu trong `sol-idle-tests.log` cùng thư mục.

- Trước sửa: 3 test mới đều FAILED đúng assertion (`running != idle_no_done`, `_quit` gọi 0 lần, `idle != idle_no_done`).
- Review bổ sung: test screen quit thất bại đỏ tại `assertTrue(watch_tick(...))`, rồi xanh sau sửa.
- Trên cây chính sau sửa logic cuối: `python3 -m unittest hybrid-hands/tests/test_side_session_codex.py hybrid-hands/tests/test_side_session_paseo.py` — 18 tests OK.
- `node --check hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs` — OK.
- Sol chạy toàn bộ bridge Node với module client/target giả qua stdin/stdout: running gọi fetch→cancel→archive→close, idle gọi fetch→archive→close, chỉ agent được chỉ định; không gọi delete. Không chạm daemon thật.
- `python3 -m unittest discover -s hybrid-hands/tests` — chạy đúng một lần: 405 tests / 47.079s, 404 đạt và 1 FAILED `test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version` vì USER_AGENT còn 0.25.0.
- Đã sửa duy nhất hằng USER_AGENT sang 0.25.1; `PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_dsh.VersionTest` — 1 test OK. Lệnh module-form trước đó thiếu đường dẫn helper `hand_ext_case`, được sửa bằng PYTHONPATH; không phải lỗi code sản phẩm.
- Không chạy lại full suite sau sửa hằng version để giữ yêu cầu đúng một lần. Không tuyên bố đã có một lượt full suite hoàn toàn xanh trên trạng thái cuối.
- `git diff --check` — sạch. Checksum các file người giao cấm sửa và toàn bộ templates/ giữ nguyên.

## Paseo archive và giới hạn kiểm chứng
Đã đọc source Paseo cài trên máy, không dựa trên giả định API. Package được kiểm tra ở `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/` (implementation vẫn tự resolve từ PATH, không hard-code đường dẫn này):

- `dist/commands/agent/archive.js:63`: client.archiveAgent, tách khỏi lệnh delete.
- `node_modules/@getpaseo/server/dist/server/server/agent/lifecycle-command.js:32`: archive xử lý cancellation và nhánh archiveStoredAgent giữ nguyên record đã archive khi retry.
- `node_modules/@getpaseo/server/dist/server/server/agent/agent-manager.js:1248`: agent thường được lưu snapshot/đánh dấu archived rồi close runtime; không xoá conversation/workspace.

Chưa kiểm UI điện thoại/lịch sử archived trên daemon thật; không restart daemon hay stop/kill phiên phụ khác. Watcher Python đang chạy từ trước patch vẫn giữ module cũ trong process; cần lần khởi chạy watcher mới để nhận code mới. Không tự thao tác các watcher/phiên khác.

Không đọc/in `.env` hoặc credential bằng lệnh kiểm tra; không tự gọi API trả phí, không commit/push, không xoá output/llm/. Mọi thay đổi có sẵn của phiên khác được giữ.
