# Hand executor: repo-scoped parallel_subagents L1

Bạn là hand executor: làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Không commit/push/merge/cập nhật runtime. Đọc AGENTS.md áp dụng. Chỉ code/fixtures giả công khai; không đọc transcript/log thật. Giữ mọi thay đổi người khác và docs/work-in-progress untracked.

## TIÊU CHÍ CHẤP NHẬN (Sol viết trước khi giao)

H=hybrid-hands/plugins/hybrid-hands. Version 0.36.1 → 0.37.0.
1. Shared loader default parallel_subagents.enabled=false. Bool thật mới hợp lệ; sai kiểu => false + warning stderr, không crash hook. True chỉ hiệu lực provenance repo (CLI nếu có, không cần tạo CLI mới); global true bỏ qua + warning. Giữ provenance/worktree fallback. Consumer config không thấy global true hiệu lực.
2. Helper mới H/lib/policy_mode.py render luật dùng chung cả hai hook. Disabled output byte-for-byte hiện tại (kể cả rút đoạn trùng AGENTS). Enabled mỗi hook có dòng đầu "chế độ parallel_subagents bật bởi <đường dẫn config repo>" (SessionStart trong additionalContext), chỉ biến thể luật, không bơm hai bộ. Cwd payload > CLAUDE_PROJECT_DIR > PWD cho cả hai hook. Config lỗi => warning không lộ giá trị, policy thường và exit 0. Payload lỗi/thiếu cũng fallback.
3. Enabled: brain chia gói độc lập khác file, native Agent hybrid-hands:hand song song <= ext_hand.max_parallel thực (1..4), cùng file/phụ thuộc tuần tự. Admission thật ngoài scope, chỉ nhắc luật. Brain review code hand mình giao; thay phân vai Sol/Opus và bảng giao theo order xung đột. Vẫn hand-ext pick --json trước native để guard v1 >=5%/ngày (thiếu nguồn chặn); native v1 chỉ pick thực trả claude-v1/model claude-opus-5-5/low, đúng account/capability. Pick dsh/codex không chứng minh guard v1; hand-ext run --backend claude-v1 enforce guard, guard chặn không spawn native v1, không sửa config/order. Không dùng run như preflight giả hay tạo writer trùng. Giữ nguyên nguyên văn LUẬT DỮ LIỆU, KHUÔN BRIEF, LUẬT TEST TỐI THIỂU, LUẬT TIẾP VIỆC, LUẬT NGỮ CẢNH BRAIN và luật commit đang có. Có thể helper dùng phần chung từ rules shell để khỏi nhân bản dài; không mang delegate/review thường xung đột vào variant.
4. AGENTS.md sửa tối thiểu hai câu cấm parallel-subagents: plugin cũ luôn tắt mọi repo; thay bằng mode parallel_subagents.enabled hybrid-hands chỉ người dùng chốt cho repo đó mới bật qua repo config, brain/hand không tự bật. Giữ không đổi slots/config và cấm sửa .claude/hybrid-hands.json việc usage panel. Thêm key mục cấu hình ưu tiên. README mục cấu hình: key/default/bool/provenance, JSON ví dụ repo; migrate tắt plugin cũ, bật key, mở phiên mới vì luật đã nạp còn hiệu lực. Chỉ tài liệu, KHÔNG thực sự bật. Version 0.37.0 + changelog + marketplace version nếu có.

## PHẠM VI GHI

H/lib/shared_config.py; helper mới H/lib/policy_mode.py (tài nguyên helper mới chỉ trong H/lib nếu cần); H/scripts/session-start-policy.sh; H/scripts/inject-policy.sh; hybrid-hands/tests/ test mới hẹp + fixture giả; hybrid-hands/README.md; H/CHANGELOG.md; H/.claude-plugin/plugin.json; hybrid-hands/.claude-plugin/marketplace.json nếu có version; AGENTS.md.
KHÔNG ĐỤNG parallel-subagents/, statusline/, .claude/hybrid-hands.json, settings/credential/installed_plugins.json; không xoá/di chuyển output/llm. Không mở rộng scope, không full suite.

## KIỂM CHỨNG (tối thiểu, tối đa 3 ca)

(a) không key: output CẢ HAI hook bằng byte baseline 0.36.1; dùng hash với normalize ROOT thay snapshot dài, tính baseline trước sửa (không assert với chính implementation mới); có AGENTS nếu hợp lý.
(b) repo true: CẢ HAI hook variant có nguồn config, max_parallel thực, review brain và không luật hybrid xung đột. Có thể gom bool sai kiểu/fallback config/cwd vào cùng test function, vẫn <=3 functions không parametrization tăng ca.
(c) global true không repo: CẢ HAI hook luật thường + warning stderr.
Chạy python3 -m pytest hybrid-hands/tests/test_policy_mode.py -q (hoặc file mới tương đương). Không test tài liệu; validate JSON manifests, shell syntax. Báo lệnh/kết quả thật, baseline evidence và chưa kiểm chứng. Runtime/commit do Sol làm.

## LUẬT DỮ LIỆU (nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
