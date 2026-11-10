# Gói E lần 2 — hand executor code/test L1
Bạn là hand executor, không phải Sol: làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Không commit/push/merge.
Đọc AGENTS.md áp dụng trước sửa. PHẠM VI GHI: `hybrid-hands/plugins/hybrid-hands/lib/shared_config.py` (chỉ default/validation paseo.claude_providers), `hybrid-hands/plugins/hybrid-hands/lib/cc_switch/`, `hybrid-hands/tests/`. Không sửa AGENTS/README/CHANGELOG/version/side_session/hand_ext hay cấu hình thật/credential, nhất là ~/.paseo/config.json, .claude/hybrid-hands.json thật. Test dùng HOME/HYBRID_HANDS_CONFIG tạm. Không chuyển phiên thật, gọi daemon, tạo agent thật hoặc kill TUI thật. Không chạy full suite: đã chạy lượt trước 490 passed, Opus sẽ chạy cuối đợt.

GIẢI PHÁP OPUS ĐÃ CHỐT:
Account Claude được giữ qua provider Paseo theo account. Thêm top-level shared config default `paseo: {claude_providers: {v1: claude}}`. Nạp bằng lib/shared_config.py, đúng precedence global < repo, không đọc JSON config riêng.
cc-switch lấy CLAUDE_CONFIG_DIR phiên hiện tại (không đặt/empty dùng ~/.claude) so realpath/expanduser với ext_hand.claude_accounts config_dir; relative config path tính từ repo root. Tra `paseo.claude_providers[account]`, dùng provider này cho cả dry-run và paseo import thật. Không truyền --env giả, không chỉ set env CLI.
Thiếu account match, match mơ hồ hoặc provider mapping thiếu/rỗng/sai kiểu: fail-closed trước import, thông báo account (nếu biết), key paseo.claude_providers và yêu cầu operator khai báo provider Claude có env CLAUDE_CONFIG_DIR tương ứng trong cấu hình Paseo; không tự sửa config Paseo. Existing agent cùng session nhưng provider khác mapping: chặn, không reload sai account và không tự tạo duplicate. Đường --self nên preflight mapping/provider trước khi tách worker/đóng TUI nếu đơn giản; worker vẫn kiểm lại ở run_paseo. Giữ default v1 claude tương thích.

ĐÃ XÁC MINH TRƯỚC CODE (Sol): `paseo --help`, `paseo import --help` exit0, import nhận --provider. Source package đã cài `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli` bản0.15.0:
- node_modules/@getpaseo/protocol/dist/provider-config.js:41 có ProviderOverrideSchema extends/env; custom extends claude cần label.
- node_modules/@getpaseo/server/dist/server/server/agent/provider-registry.js:542 tạo custom extends provider và mergeRuntimeSettings env.
- .../provider-launch-config.js collectProviderEnvOverlays dùng runtimeSettings.env; .../providers/claude/agent.js:1228 buildProviderEnv dùng runtimeSettings.
Không cần thử live. Chỉ đọc package code công khai nếu cần; không credential/config/log thật.

TIÊU CHÍ CHẤP NHẬN / TEST TỐI THIỂU ĐÃ CHỐT (2 ca mới, không thêm quá 3):
1. Fixture v2 HOME tạm/.claude-hand + global/repo config tạm mapping v2→claude-hand (default v1 vẫn claude). Chạy dry-run và fake import trong cùng ca, argv --provider claude-hand, sid/cwd chính xác; assert cwd dùng Path.resolve() để sửa diagnostic macOS lần trước. Dry-run không gọi fake paseo. Có thể gộp provider-mismatch reload dưới subTest nếu cần.
2. v2 không mapping: exit khác0, stderr nêu v2/paseo.claude_providers/cấu hình Paseo, KHÔNG gọi import; áp cả dry-run nếu thuận tiện.
Chỉnh fixture mặc định để account fixture khớp v1 (HOME tạm/.claude), HYBRID_HANDS_CONFIG absent trong HOME tạm nhằm không phụ thuộc config máy; đừng mở lỗ unknown-account để giữ test cũ. Các test unit mock HOME/env cũng cần fixture cô lập nếu lookup mới áp vào đó. Không thêm fixture transcript thật.
Chạy 2 ca mới trước rồi test hẹp cc_switch và shared_config nếu đổi. KHÔNG full suite. Báo lệnh/kết quả thật và file đổi/report, không claim live account đã chứng minh. Diff nhỏ gọn, không overengineer.

Luật dữ liệu nguyên văn:
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
