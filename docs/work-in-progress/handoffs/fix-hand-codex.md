## Tóm tắt
- Kết quả: xong phần triển khai và review, version 0.25.3; gồm brief gốc và phần song song bổ sung.
- Doctor Codex không chặn model/effort/sandbox đã được CLI đè; máy thật doctor exit 0, không sửa config.toml.
- Prompt bắt buộc giao code/test/tài liệu L0/L1 theo ext_hand.order; exit 7 doctor trước dự phòng.
- Mặc định 4 Sol, mỗi Sol 4 hand độc lập; khóa slot chống race, lượt thứ 5 exit 8; cùng file tuần tự.
- File đổi: backend/config/slot để sửa chọn hand và giới hạn; prompt/hooks/skills/README/CHANGELOG để đồng bộ luật; manifest/UA lên 0.25.3; test liên quan chứng minh hành vi. Danh sách từng file bên dưới.
- Test hẹp doctor/template/slot/default/scope đạt; full bản gộp 408 test: 407 đạt, 1 lỗi wording policy đã được hand sửa và 4 test policy sau sửa đều đạt.
- Không chạy lại full sau sửa wording theo yêu cầu giữ số lần full; lượt full cũ đã khởi chạy trước khi nhận brief bổ sung, chi tiết dưới.
- Còn mở: chưa mở thật 4 Sol × 4 model hand; scope screen/Paseo đã kiểm tra payload, slot đã kiểm tra bằng tiến trình thật. Chưa cài/cập nhật plugin vào cache.
- Không commit/push; không sửa .claude/hybrid-hands.json, không đụng live-tiktok-games hay docs/ có sẵn ngoài hai file bàn giao này.

## File đã đổi

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/codex.py`: Bỏ model/effort/sandbox khỏi lỗi required vì build_command đè bằng -m/-c/-s; thêm thông tin override không chặn; giữ cài đặt, đăng nhập và service_tier required.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py`: Đồng bộ User-Agent 0.25.3 với manifest; sửa lỗi VersionTest của lượt full ban đầu.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py`: Thêm max_parallel mặc định/trần 4, biến scope và exit 8.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/config.py`: Nạp ext_hand.max_parallel, validate số nguyên 1..4; field cuối có default giữ tương thích constructor.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/parallel.py`: Module mới: slot flock không blocking theo scope, tự nhả khi đóng descriptor/process chết; độc lập registry best-effort.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/run_cmd.py`: Giữ một slot toàn cmd_run, kể cả retry/fallback; từ chối trước backend/worktree khi đầy.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/constants.py`: Đổi default max_parallel từ 2 thành 4, thêm tên biến scope.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/config.py`: Validate max_parallel trong 1..4, không nhận bool/chuỗi.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/commands.py`: Export HYBRID_HANDS_HAND_SCOPE=uuid của Sol khi mở Codex qua screen.
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`: Truyền uuid scope riêng vào env payload Paseo; giữ nguyên CODEX_HOME và parent session.
- `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt-codex.md`: Bắt buộc giao hand theo order, ngoại lệ có lý do/mã thoát; doctor trước fallback7; chạy nền tối đa4 brief độc lập/mỗi Sol, chờ đủ rồi review, cùng file tuần tự, exit8 chờ slot.
- `hybrid-hands/plugins/hybrid-hands/scripts/session-start-policy.sh`: Thúc Opus chia gói L1 độc lập, lấp tối đa4 Sol; thống nhất lane/order và xử lý exit7/8.
- `hybrid-hands/plugins/hybrid-hands/scripts/inject-policy.sh`: Policy ngắn cập nhật hai tầng song song, hand bắt buộc/order/doctor; giữ thuật ngữ hand Claude cho dữ liệu nhạy cảm và giới hạn <1800 ký tự.
- `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md`: Đồng bộ nghĩa vụ giao hand, default/cap4, scope và mã thoát7/8.
- `hybrid-hands/plugins/hybrid-hands/skills/side-session/SKILL.md`: Đồng bộ default4 Sol và4 hand/mỗi Sol, vai trò/lane/order và bàn giao.
- `hybrid-hands/README.md`: Mô tả doctor và delegation, ví dụ cấu hình max_parallel4 cho cả hai tầng, scope và xử lý mã thoát.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: Thêm changelog0.25.3 gồm doctor, prompt và song song.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`: Tăng0.25.2 lên0.25.3. Marketplace không có version cần đồng bộ.
- `hybrid-hands/tests/test_hand_ext_codex.py`: Ca config lệch/thiếu vẫn là ứng viên auto; auth None vẫn bị loại; argv override và config không đổi; giữ service_tier/API-key login.
- `hybrid-hands/tests/test_hand_ext_parallel.py`: 3 ca hành vi:4 slot/exit8 trước chạy; tranh slot bằng5 tiến trình và thu hồi khi chết/lỗi; scope độc lập và validation.
- `hybrid-hands/tests/test_side_session.py`: Default4, validation1..4; test giới hạn cũ dùng cấu hình2 tường minh.
- `hybrid-hands/tests/test_side_session_codex.py`: Assert prompt render thật, luật giao hand/song song/doctor và scope screen.
- `hybrid-hands/tests/test_side_session_paseo.py`: Assert env scope đúng uuid Sol trong payload.
- `hybrid-hands/tests/test_policy_brain_context.py`: Assert cả2 hook có song song/order/doctor/exit8, giữ giới hạn policy ngắn.

## Quyết định và ngoại lệ Sol tự sửa

- Lượt `hand-ext run --brief ... --backend auto` đầu tiên exit **7**: codex bị loại vì doctor chưa đạt. Chạy doctor ngay sau đó xác nhận CLI và ChatGPT login đạt, chỉ `model_reasoning_effort` lệch.
- Để gọi được hand bằng đúng auto, Sol tự sửa tạm một dòng doctor: không đưa các khóa `_keys(options)` đã được runtime đè vào danh sách lỗi. Lý do: plugin đang tự chặn backend duy nhất nên không thể giao hand trước khi mở chặn. Không sửa config máy, không tách home. Sau đó giao toàn bộ hoàn thiện code/test/docs qua auto cho codex gpt-6.1-sol low; Sol review tổng diff, kể cả dòng bootstrap. Đây là ngoại lệ tự code sau hand-ext exit7.
- Các brief chép nguyên văn luật cấm đọc .env/credential và API key; hand chạy trong worktree, patch áp về gốc thành công; brief tạm đã xóa sau khi kết thúc. Bản brief/prompt/report được hand-ext giữ trong output/llm/hand-ext.
- Không bỏ qua backend_ready hay lỗi đăng nhập. `service_tier` không có runtime override nên vẫn bắt buộc như trước.

## Bổ sung song song: 4 Sol × mỗi Sol 4 hand

- Hai cấu hình `side_session.max_parallel` và `ext_hand.max_parallel` mặc định4, cho phép giảm trong1..4; không sửa config riêng của repo. Có đủ gói độc lập thì chủ động lấp slot; cùng file/phụ thuộc phải tuần tự.
- Mỗi Sol có uuid scope riêng qua screen/Paseo. Thứ tự scope hand: `HYBRID_HANDS_HAND_SCOPE` → `CODEX_THREAD_ID` → `CLAUDE_CODE_SESSION_ID` → repo root. Khi không có session env, các lượt cùng repo chia slot.
- Giữ slot suốt cmd_run kể cả backend fallback/retry. Đầy slot trả exit8, chờ lượt đang chạy; không coi là hết quota, không đổi backend hoặc Sol tự code. Khóa không blocking và tự nhả khi process chết; không dựa vào registry có thể stale/best-effort. Registry unwritable vẫn chỉ cảnh báo theo test cũ.
- Slot flock lưu dưới thư mục temp theo user + hash scope; không ghi secret/prompt. Cơ chế áp dụng Unix/macOS hiện tại.
- Đã thực sự giao hai gói độc lập A/B song song qua hand-ext auto; cả hai patch áp thành công, Sol review cả hai.

## Kiểm chứng và kết quả thật

Mức test: tối thiểu. Hand không chạy full suite; Sol chạy kiểm chứng tổng hợp.

- Doctor/template: `python3 -m unittest discover -s hybrid-hands/tests -p test_hand_ext_codex.py`: **11 đạt**; module `test_side_session_codex.py`: **13 đạt** ở phần đầu. Test hồi quy với doctor cũ thất bại đúng lỗi config override.
- Parallel: module `test_hand_ext_parallel.py -v`: **3/3 đạt**, gồm5 tiến trình thực tranh4 slot, kill process rồi lấy lại slot. Registry/default/config-worktree: **12/12 đạt**; `test_hand_ext_dsh.py -k VersionTest`: **1/1 đạt**.
- Sol/policy/scope: **6 test chọn lọc đạt**, bổ sung assert scope screen kiểm lại đạt. Pytest không có trong môi trường; dùng unittest. Không thiếu dependency cho suite unittest.
- Full cũ: `python3 -m unittest discover -s hybrid-hands/tests -q` đã khởi chạy ngay trước khi brief bổ sung đến. **405 test /45.837s,404 đạt,1 lỗi UA0.25.2 khác manifest0.25.3**. Hand A đã sửa UA và test VersionTest đạt.
- Full bản gộp, chạy **một lần** sau review cả hai phần: cùng lệnh trên, **408 test /46.529s,407 đạt,1 lỗi wording `hand Claude` trong inject-policy.sh**. Không có lỗi logic doctor/slot/scope/config/template khác trong lượt này.
- Giao hand sửa đúng một cụm `dữ liệu nhạy cảm giao Claude` → `dữ liệu nhạy cảm giao hand Claude`; **`PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_isolation.PolicyTextTest test_policy_brain_context`:4/4 đạt sau sửa**. Sol review patch một file. Không chạy lại full theo yêu cầu giữ một lượt full bản gộp; vì vậy không tuyên bố đã có lượt408/408 xanh trên cây cuối.
- `git diff --check`: đạt. Manifest parse0.25.3; marketplace không có version cần cập nhật.
- `hand-ext doctor --backend codex` trên máy thật: **exit0**, CLI0.166.0, đăng nhập chatgpt đạt, cấu hình đạt; thông tin -m/-c/-s không chặn.
- Load config repo thật: `order=[codex]`, effortlow, **hai max_parallel=4** bằng default; không sửa `.claude/hybrid-hands.json`.
- `~/.codex-hand/config.toml`: checksum và mtime không đổi giữa các mốc trong phiên; không chạy setup máy thật, không ghi đè config. Không đọc/in giá trị .env/auth/credential trong thao tác điều tra.

## Lượt hand và hạn mức

Tất cả dùng backend auto → codex `gpt-6.1-sol` effortlow. Sol đã review report và diff của từng lượt.

| Lượt | Input | Cached input (thuộc input) | Output | Report |
|---|---:|---:|---:|---|
| fix-hand-codex |543299|491520|6015|output/llm/hand-ext/20261107-204005-906627-fix-hand-codex-codex/report.md|
| fix-hand-parallel |324739|299392|5161|output/llm/hand-ext/20261107-204525-171706-fix-hand-parallel-codex/report.md|
| fix-sol-parallel |491120|456832|5153|output/llm/hand-ext/20261107-204525-171719-fix-sol-parallel-codex/report.md|
| fix-policy-wording |99883|89856|822|output/llm/hand-ext/20261107-204951-007449-fix-policy-wording-codex/report.md|

Mốc quota lớn nhất báo cuối mỗi lượt:8%, reset2026-11-09T06:19:15Z (13:19:15 giờ Việt Nam). Không suy ra tỷ lệ tiêu riêng task từ con số tổng tài khoản.

## Việc còn mở và giới hạn kiểm chứng

- Không còn lỗi triển khai đã biết sau sửa wording; lượt full cuối trước sửa wording chưa xanh hoàn toàn, trạng thái kiểm chứng cuối là full407/408 +4 test policy sau sửa đạt.
- Chưa mở4 phiên Sol thật đồng thời và16 lượt model thật. Kiểm chứng scope bằng payload screen/Paseo và concurrency bằng tiến trình Python thật; tránh đốt thêm lượt model chỉ để stress test.
- Chưa update marketplace/install plugin cache; patch ở workspace, không commit/push theo yêu cầu. Phiên đã chạy vẫn dùng prompt cũ; prompt mới áp khi tạo phiên từ template đã cập nhật.
- Không tìm thấy AGENTS.md/CLAUDE.md áp dụng ở gốc hay subtree hybrid-hands trong lần kiểm tra; không phát sinh cập nhật docs/solutions bắt buộc. docs/ untracked có sẵn được giữ nguyên, chỉ thêm handoff này và .done theo hợp đồng.
