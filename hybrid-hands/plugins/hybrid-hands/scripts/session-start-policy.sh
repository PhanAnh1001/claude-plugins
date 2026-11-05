#!/bin/bash
# SessionStart hook (startup|resume|clear|compact): bơm khuôn brief, luật chọn hand, luật hạn mức MỘT LẦN.
# Nội dung cố định; giá trị động duy nhất là đường dẫn bin của plugin (cố định theo bản cài) để prefix cache ổn định.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BRIEF="$(cat "$ROOT/templates/hand-brief.md")"
RULES="$(cat << 'EOT'
Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).

LUẬT CHỌN HAND (brain chạy trên gói Claude chính; giữ hạn mức gói chính cho brain):
1. Hand ngoài (`hand-ext run --backend auto`) là MẶC ĐỊNH cho việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Chạy trên GÓI subscription thứ hai (mặc định backend dsh, opencode theo `order` trong mục `ext_hand` của `.claude/hybrid-hands.json`; codex, claude, gemini chỉ gọi tường minh bằng `--backend`). Brief theo cùng khuôn, ghi vào file tạm trong scratchpad; gọi `hand-ext run --brief <file> --label <nhãn>` bằng tool Bash với run_in_background rồi chờ thông báo khi lệnh thoát (không tự viết vòng chờ); đọc report.md theo đường dẫn được in. `hand-ext run` mặc định chạy trong git worktree sạch chỉ có file tracked cùng thay đổi chưa commit/untracked không bị ignore (file bị ignore như `.env` không có trong workspace); đừng tắt bằng `--isolation none` khi repo có secret. `--browser` chỉ dùng với `--backend dsh`/`auto` (Playwright MCP cô lập, chỉ trang công khai, không đăng nhập/form/mua/captcha, không TikTok). Codex, DeepSeek Harness (dsh) và OpenCode KHÔNG chịu hook của Claude Code: LUẬT BẮT BUỘC của brief phải chép nguyên văn luật cấm của repo (đặc biệt: "Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`."), PHẠM VI GHI hẹp tới từng file. Backend claude (gói Claude thứ hai) thì hook của repo vẫn chạy, nhưng brief vẫn chép luật cấm.
   LUẬT DỮ LIỆU: Không giao hand ngoài (dsh, opencode, codex, gemini — gửi dữ liệu lên dịch vụ ngoài) việc phải đọc hoặc gửi: secret (`.env`, token, mật khẩu, URL DB có mật khẩu), dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân). Những việc đó dùng hand Claude. Được giao hand ngoài: code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.
2. Hand Claude (Agent với `hybrid-hands:hand`, gói chính): việc cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), việc chạy lệnh trả phí của dự án; và dự phòng khi `hand-ext` thoát 7 (mọi gói thứ hai hết hạn mức hoặc chưa đăng nhập) hoặc lỗi.
3. Phiên phụ (`side-session start`): gói việc dài nhiều bước (ước trên 1 giờ) cần ngữ cảnh brain riêng; tối đa theo `max_parallel` trong `.claude/hybrid-hands.json`; đồng bộ bằng ListAgents/SendMessage, đọc bàn giao bằng `side-session handoff <tên>`.
Chi tiết: skill `hybrid-hands:ext-hand`, `hybrid-hands:side-session`.

LUẬT HẠN MỨC hand ngoài: không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức (hết thì dùng backend kế tiếp hoặc hand Claude). Gói không tính tiền theo lượt nên không cần bảng USD; sau mỗi lượt báo backend, token, % hạn mức và thời điểm reset từ khối tóm tắt của `run`; xem trạng thái các gói bằng `hand-ext status`, tổng lượt bằng `hand-ext report`.

LUẬT TIẾP VIỆC (cache của hand chỉ sống 5 phút; tiếp việc khi cache đã nguội thì phải ghi lại toàn bộ ngữ cảnh hand ở giá 1,25x, đắt ngang tạo hand mới):
- Cache NÓNG: brain giao tiếp việc ngay trong lượt nhận báo cáo, không có chờ người dùng, chờ hand khác hay lệnh dài xen giữa. Khi cache nóng và việc kế tiếp chạm cùng file/module hand vừa đọc/sửa: SendMessage tới hand đó (brief bổ sung cùng khuôn, chỉ ghi phần thay đổi). Có việc tiếp thì giao ngay, trước khi hỏi người dùng hay làm việc dài khác.
- Cache NGUỘI (đã qua một lượt chờ người dùng, hoặc hand xong hơn 5 phút trước): xem kích thước ngữ cảnh hand (subagent_tokens trong usage của thông báo hoàn thành). Không quá 80k thì vẫn SendMessage. Trên 80k thì sinh hand MỚI với brief gọn, chép sẵn các phát hiện kèm file:dòng từ báo cáo hand cũ để hand mới không phải đọc lại.
- Sinh hand MỚI khi: việc độc lập hoặc khác vùng code; hand cũ đã làm nhiều việc khác nhau hoặc ngữ cảnh trên 200k; hand cũ đang chạy (không gửi chồng việc ghi cho hand đang chạy).
- Hand ngoài không nhận SendMessage: việc tiếp là một `hand-ext run` mới với brief gọn chép sẵn phát hiện từ report.md lượt trước.
LỆNH DÀI: lệnh dự kiến chạy quá 4 phút (full test suite, build image, e2e, deploy) giao cho một hand riêng chỉ chạy lệnh đó (ngữ cảnh nhỏ nên mất cache cũng rẻ), không gắn vào cuối một hand đã đọc nhiều. Hand làm việc chính chỉ chạy test hẹp liên quan.

LUẬT REVIEW: review do brain tự làm, với cả hand Claude lẫn hand ngoài. Sau khi hand báo xong việc ghi, brain tự đọc diff/các file hand đã đổi (git diff hoặc Read) để review trước khi báo người dùng. Không giao hand review, kể cả review việc của hand khác. Nếu review phát hiện lỗi, brain giao sửa (theo LUẬT TIẾP VIỆC: SendMessage cho hand Claude vừa làm nếu cache còn nóng hoặc ngữ cảnh hand không quá 80k; hand ngoài thì một lượt `hand-ext run` mới), rồi brain review lại.
EOT
)"
TEXT="POLICY hybrid-hands - KHUÔN BRIEF (bắt buộc khi gọi Agent với hybrid-hands:hand và khi viết brief cho hand-ext; điền đủ các mục, ngắn gọn):
${BRIEF}
${RULES}
Lệnh của plugin (nếu không có trong PATH thì gọi bằng đường dẫn tuyệt đối): ${ROOT}/bin/hand-ext, ${ROOT}/bin/side-session, ${ROOT}/bin/hh-ps, ${ROOT}/bin/cc-switch"
jq -n --arg ctx "$TEXT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
