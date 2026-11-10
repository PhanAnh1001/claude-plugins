## MỤC TIÊU
Sửa hai lỗi release-028 tối thiểu, không thêm test mới. Bạn là hand executor trực tiếp, không phải Sol.
## NGỮ CẢNH
Cwd /Users/anhtp/app/claude-plugins. Đọc AGENTS.md ở repo và luật áp dụng, không nạp dev-workflow. Repo có rất nhiều thay đổi chưa commit, cả 3 file được giao đã dirty; giữ nguyên tất cả, so thay đổi của mình với baseline tại docs/work-in-progress/release-028/baseline/. Manifest hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json đã 0.28.0. dsh.USER_AGENT còn 0.27.0. Test Codex assert reset chỉ HH:MM trong khi render hợp lệ có dd/mm khi khác ngày.
## PHẠM VI GHI
- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py: lấy version từ manifest gọn, an toàn, không thêm nguồn version cứng khác. Giữ API USER_AGENT và hành vi còn lại.
- hybrid-hands/tests/test_hh_ps_codex.py: chỉ regex hiện hữu cho ngày tùy chọn trước HH:MM, không đổi renderer/fixture, không thêm test.
- hybrid-hands/plugins/hybrid-hands/CHANGELOG.md: thêm một bullet mục 0.28.0 cho version User-Agent lấy từ manifest.
- docs/work-in-progress/release-028/hand-report.md và hand-two-tests.log, hand-two-tests.json: báo cáo và log kiểm chứng, ghi exit code/thời gian/số test thật.
## KHÔNG ĐƯỢC ĐỤNG
Ngoài scope trên. Không sửa panel/hiển thị paseo-hh-tree/, hh-tree-pane/, lib/hh_ps/render.py, statusline/, AGENTS.md, manifest. Không sửa .claude/hybrid-hands.json, ~/.codex-hand/config.toml, ~/.claude/settings.json, ~/.paseo/config.json, installed_plugins.json, credential/settings. Không xóa/di chuyển/dọn output/llm/. Không commit/push. Không đọc log/transcript runtime thật. Không chạy full suite, CLI cài đặt/reload hay daemon restart. Không tạo release-028.done hoặc bàn giao tổng lúc này.
## LUẬT BẮT BUỘC
Bạn là hand executor: làm trực tiếp, không gọi hand-ext, không mở side-session, không tạo subagent, không recursion, không giao tiếp phiên khác, không review hand khác. Chỉ Sol review phần hand mình giao. Chỉ dùng code và fixtures giả công khai được. Giữ mọi thay đổi chưa commit của người khác; cùng file/phụ thuộc tuần tự. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không cd <dir> && ... . Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo. Không tải/mua/gọi API trả phí hay tạo/dùng API key. Không bật parallel-subagents/sửa config. Không in secrets.
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
## KIỂM CHỨNG
Mức tối thiểu, không thêm test mới. Acceptance: (1) USER_AGENT bằng manifest và không còn literal 0.27.0; (2) assertion Codex nhận reset HH:MM và dd/mm HH:MM, renderer nguyên vẹn; (3) chỉ 3 file đúng scope thay đổi so baseline. Chạy đúng hai test hiện hữu trong một lệnh từ cwd repo: PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version test_hh_ps_codex.CodexPanelTest.test_codex_usd_pct_samples_and_gpt_account_limits -q . Lưu output + exit code, không chạy full, không chạy thêm test không cần.
## TRẢ VỀ
Ghi hand-report.md có file đổi và lý do, lệnh thật, số test/exit code, hạn chế. Final ngắn tương tự, token/quota nếu runtime có, thiếu ghi ?. Native không có meta/report/ledger hand-ext, không bịa quota. Chờ Sol review; không tiếp tục ngoài scope.
