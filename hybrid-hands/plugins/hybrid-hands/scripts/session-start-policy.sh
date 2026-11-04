#!/bin/bash
# SessionStart hook (startup|resume|clear|compact): bơm khuôn brief, luật chọn hand, luật chi phí MỘT LẦN.
# Nội dung cố định; giá trị động duy nhất là đường dẫn bin của plugin (cố định theo bản cài) để prefix cache ổn định.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BRIEF="$(cat "$ROOT/templates/hand-brief.md")"
RULES="$(cat << 'EOT'
Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).

LUẬT CHỌN HAND (chọn loại rẻ nhất làm được việc):
1. Hand GPT (`hand-gpt run`, GPT-6.1 Sol Flex qua Codex): việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Brief theo cùng khuôn, ghi vào file tạm trong scratchpad; gọi `hand-gpt run --brief <file> --label <nhãn>` bằng tool Bash với run_in_background rồi chờ thông báo khi lệnh thoát (không tự viết vòng chờ). Codex KHÔNG chịu hook của Claude Code: LUẬT BẮT BUỘC của brief phải chép nguyên văn luật cấm của repo (đặc biệt: "Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`."), PHẠM VI GHI hẹp tới từng file.
2. Hand Claude (Agent với `hybrid-hands:hand`): việc cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), việc chạy lệnh trả phí của dự án, việc cần hook của repo bảo vệ; và dự phòng khi hand GPT lỗi hoặc Flex bị từ chối (flex_rejected).
3. Phiên phụ (`side-session start`): gói việc dài nhiều bước (ước trên 1 giờ) cần ngữ cảnh brain riêng; tối đa theo `max_parallel` trong `.claude/hybrid-hands.json`; đồng bộ bằng ListAgents/SendMessage, đọc bàn giao bằng `side-session handoff <tên>`.
Chi tiết: skill `hybrid-hands:gpt-hand`, `hybrid-hands:side-session`.

LUẬT CHI PHÍ hand GPT: trước mỗi `run` chạy `hand-gpt estimate --brief <file>` và báo bảng chi phí trong chat (mọi lượt trả phí đều báo bảng). Trần tối đa từ `approval_usd` của dự án trở lên: báo bảng rồi chờ người dùng duyệt mới chạy `run --approved`; dưới ngưỡng: báo bảng rồi chạy luôn. Tối đa 2 lệnh trả phí chạy cùng lúc. Sau lượt báo USD thật (khối tóm tắt của `run` hoặc `hand-gpt report`).

LUẬT TIẾP VIỆC (cache của hand chỉ sống 5 phút; tiếp việc khi cache đã nguội thì phải ghi lại toàn bộ ngữ cảnh hand ở giá 1,25x, đắt ngang tạo hand mới):
- Cache NÓNG: brain giao tiếp việc ngay trong lượt nhận báo cáo, không có chờ người dùng, chờ hand khác hay lệnh dài xen giữa. Khi cache nóng và việc kế tiếp chạm cùng file/module hand vừa đọc/sửa: SendMessage tới hand đó (brief bổ sung cùng khuôn, chỉ ghi phần thay đổi). Có việc tiếp thì giao ngay, trước khi hỏi người dùng hay làm việc dài khác.
- Cache NGUỘI (đã qua một lượt chờ người dùng, hoặc hand xong hơn 5 phút trước): xem kích thước ngữ cảnh hand (subagent_tokens trong usage của thông báo hoàn thành). Không quá 80k thì vẫn SendMessage. Trên 80k thì sinh hand MỚI với brief gọn, chép sẵn các phát hiện kèm file:dòng từ báo cáo hand cũ để hand mới không phải đọc lại.
- Sinh hand MỚI khi: việc độc lập hoặc khác vùng code; hand cũ đã làm nhiều việc khác nhau hoặc ngữ cảnh trên 200k; hand cũ đang chạy (không gửi chồng việc ghi cho hand đang chạy).
- Hand GPT không nhận SendMessage: việc tiếp là một `hand-gpt run` mới với brief gọn chép sẵn phát hiện từ report.md lượt trước.
LỆNH DÀI: lệnh dự kiến chạy quá 4 phút (full test suite, build image, e2e, deploy) giao cho một hand riêng chỉ chạy lệnh đó (ngữ cảnh nhỏ nên mất cache cũng rẻ), không gắn vào cuối một hand đã đọc nhiều. Hand làm việc chính chỉ chạy test hẹp liên quan.

LUẬT REVIEW: review do brain tự làm, với cả hand Claude lẫn hand GPT. Sau khi hand báo xong việc ghi, brain tự đọc diff/các file hand đã đổi (git diff hoặc Read) để review trước khi báo người dùng. Không giao hand review, kể cả review việc của hand khác. Nếu review phát hiện lỗi, brain giao sửa (theo LUẬT TIẾP VIỆC: SendMessage cho hand Claude vừa làm nếu cache còn nóng hoặc ngữ cảnh hand không quá 80k; hand GPT thì một lượt run mới), rồi brain review lại.
EOT
)"
TEXT="POLICY hybrid-hands - KHUÔN BRIEF (bắt buộc khi gọi Agent với hybrid-hands:hand và khi viết brief cho hand-gpt; điền đủ các mục, ngắn gọn):
${BRIEF}
${RULES}
Lệnh của plugin (nếu không có trong PATH thì gọi bằng đường dẫn tuyệt đối): ${ROOT}/bin/hand-gpt, ${ROOT}/bin/side-session"
jq -n --arg ctx "$TEXT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
