# Gói E — executor code/test, L1
Bạn là hand executor, không phải Sol. Làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Không commit/push/merge.

PHẠM VI GHI: chỉ hybrid-hands/plugins/hybrid-hands/lib/cc_switch/ và hybrid-hands/tests/ trong worktree được giao. Không sửa AGENTS/README/CHANGELOG/version/settings/credential/config thật. Không chuyển phiên thật, tạo agent thật, kill TUI thật, gọi daemon thật. Test chỉ fixtures giả, HOME và HYBRID_HANDS_CONFIG tạm. Không sửa global ~/.hybrid-hands/config.json. Đọc AGENTS.md áp dụng trước khi sửa.

Mục tiêu: cc-switch paseo --self giữ account Claude hiện tại khi mở lại phiên dưới Paseo, spec 4.2 và Gói E. Hiện self_cmd.spawn_worker kế thừa env, rồi run_self_worker gọi run_paseo; paseo_cli.import_session gọi `paseo import <sid> --provider claude --cwd <cwd> --json` nhưng không gửi env tới daemon. Chỉ set env cho subprocess paseo KHÔNG đủ vì agent chạy từ daemon.

Tiêu chí chấp nhận đã chốt:
1. Nếu phiên có CLAUDE_CONFIG_DIR (vd ~/.claude-hand), request tạo/resume agent Paseo phải truyền đúng thư mục account qua env của agent, cùng session/cwd. Chỉ truyền biến cần thiết, không copy toàn môi trường. Default khi không đặt biến giữ tương thích.
2. Dry-run phản ánh request/lệnh thực tế mà không tạo agent; logic worker --self không mất account.
3. Thay đổi nhỏ gọn, API Paseo có thật; không thêm cờ import --env giả. CLI đã cài `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/dist/commands/agent/import.js` không hỗ trợ --env, protocol importAgent cũng không có env. Có thể đọc source package công khai đã cài (không credential/config/log thật) để tìm đường create/resume có env thực sự. Nếu cần bridge JS nhỏ, chỉ đặt lib/cc_switch/. Dùng API chính thức tương tự side_session/paseo_bridge.mjs, không tự đọc credential. Không suy env tiến trình CLI là env agent. Nếu có lựa chọn giải pháp hoặc API không hỗ trợ, ghi rõ bằng chứng/blocker trong report; không giả lập thành công.
4. Existing reload giữ an toàn; không tự tạo duplicate agent khi kết quả không rõ. Không mở rộng sang term direction/security spec 7.2.

Một ca test mới DUY NHẤT: fixture phiên v2 có CLAUDE_CONFIG_DIR trỏ HOME tạm/.claude-hand, kiểm dry-run và request tạo agent giả chứa env CLAUDE_CONFIG_DIR chính xác cùng session id. Dùng seam fixture/mock ở boundary createAgent để chứng minh env đã tới request agent chứ không chỉ subprocess. Có thể chỉnh assertions cũ nếu giao diện hợp lệ đổi; không thêm nhóm test dư. Chạy đúng ca mới và các test cc_switch cần thiết, KHÔNG chạy full suite (Sol sẽ giao hand khác cuối). Báo lệnh/kết quả thật, file đổi, chưa kiểm chứng, API source evidence. Không gọi API model trả phí hay key.

Luật dữ liệu (nguyên văn):
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
