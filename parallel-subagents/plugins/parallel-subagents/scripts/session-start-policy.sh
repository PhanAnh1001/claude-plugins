#!/bin/bash
# SessionStart hook (startup|resume|clear|compact): bơm khuôn brief + luật tiếp việc MỘT LẦN.
# Nội dung cố định, không có giá trị động, để giữ prefix ổn định cho prompt cache.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}"
BRIEF="$(cat "$ROOT/templates/hand-brief.md")"
RULES="$(cat << 'EOT'
Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).

LUẬT TIẾP VIỆC (cache của hand chỉ sống 5 phút; tiếp việc khi cache đã nguội thì phải ghi lại toàn bộ ngữ cảnh hand ở giá 1,25x, đắt ngang tạo hand mới):
- Cache NÓNG: brain giao tiếp việc ngay trong lượt nhận báo cáo, không có chờ người dùng, chờ hand khác hay lệnh dài xen giữa. Khi cache nóng và việc kế tiếp chạm cùng file/module hand vừa đọc/sửa: SendMessage tới hand đó (brief bổ sung cùng khuôn, chỉ ghi phần thay đổi). Có việc tiếp thì giao ngay, trước khi hỏi người dùng hay làm việc dài khác.
- Cache NGUỘI (đã qua một lượt chờ người dùng, hoặc hand xong hơn 5 phút trước): xem kích thước ngữ cảnh hand (subagent_tokens trong usage của thông báo hoàn thành). Không quá 80k thì vẫn SendMessage. Trên 80k thì sinh hand MỚI với brief gọn, chép sẵn các phát hiện kèm file:dòng từ báo cáo hand cũ để hand mới không phải đọc lại.
- Sinh hand MỚI khi: việc độc lập hoặc khác vùng code; hand cũ đã làm nhiều việc khác nhau hoặc ngữ cảnh trên 200k; hand cũ đang chạy (không gửi chồng việc ghi cho hand đang chạy).
LỆNH DÀI: lệnh dự kiến chạy quá 4 phút (full test suite, build image, e2e, deploy) giao cho một hand riêng chỉ chạy lệnh đó (ngữ cảnh nhỏ nên mất cache cũng rẻ), không gắn vào cuối một hand đã đọc nhiều. Hand làm việc chính chỉ chạy test hẹp liên quan.

LUẬT REVIEW: review do brain tự làm. Sau khi hand báo xong việc ghi, brain tự đọc diff/các file hand đã đổi (git diff hoặc Read) để review trước khi báo người dùng. Không giao hand review, kể cả review việc của hand khác. Nếu review phát hiện lỗi, brain giao sửa (theo LUẬT TIẾP VIỆC: SendMessage cho hand vừa làm nếu cache còn nóng hoặc ngữ cảnh hand không quá 80k), rồi brain review lại.
EOT
)"
TEXT="POLICY brain/hand - KHUÔN BRIEF (bắt buộc khi gọi Agent với parallel-subagents:hand; điền đủ các mục, ngắn gọn):
${BRIEF}
${RULES}"
jq -n --arg ctx "$TEXT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
