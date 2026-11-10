Bạn là hand executor, làm trực tiếp; không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác, không commit/push/cài runtime. Đọc AGENTS.md repo (không dev-workflow). Chỉ code và fixtures giả; không đọc home thật, subprocess CLI mock. Không sửa config/settings/state/credential thật hoặc output/llm. Shell workdir/absolute, không cd &&. Giữ thay đổi người khác.

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

PHẠM VI GHI: docs/work-in-progress/dong-bo-tai-khoan/verification.md duy nhất.
Làm nghiên cứu công khai câu 3–5 spec.md (đọc file đó). Dùng tài liệu chính thức code.claude.com và developers.openai.com, fetch trang thật không chỉ snippet; ghi URL, ngày 2026-11-10, nội dung xác minh/chưa xác minh, lựa chọn blocked đúng mức. Không đọc home thật hoặc gọi CLI trên account thật. Có thể dùng web tool hoặc urllib fetch public docs không cần key. Áp dụng OpenAI Docs skill (đã đọc bởi Sol): tìm chính thức 2–6 từ chủ đề cụ thể trước, fetch trang phù hợp; chỉ official OpenAI domains cho Codex.
Cần xác minh:
3. Claude hooks: CLAUDE_CONFIG_DIR, absolute source-v1 command paths, permissions/trust, import CLAUDE.md; không tuyên hook cụ thể an toàn vì docs không biết nội dung.
4. Codex CODEX_HOME, global AGENTS.md, rules/, agents/, skills path, symlink support từng loại. Mỗi loại không có bằng chứng symlink + discover => blocked riêng, không đoán.
5. Claude plugin install --scope user/project/local, plugin list --json/marketplace list metadata schema và bảo mật output; official update/validate command cho P4. MCP add-json payload có stdin/file hỗ trợ chính thức không? Nếu chỉ positional argv thì blocked an toàn, KHÔNG tự phát minh stdin. MCP chưa server nào duyệt: chỉ code fixture, tuyệt đối không dùng account thật.
Kết luận ngắn triển khai được/blocked theo từng item và hướng adapter CLI metadata lọc tên/version/enabled/scope/path (cấm raw output). Giữ output nghiên cứu không secret. Không test/code/release.
