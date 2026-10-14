#!/bin/bash
# SessionStart hook (startup|resume|clear|compact): bơm khuôn brief + luật tiếp việc MỘT LẦN.
# Nội dung cố định, không có giá trị động, để giữ prefix ổn định cho prompt cache.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$0")/..}"
BRIEF="$(cat "$ROOT/templates/hand-brief.md")"
RULES="$(cat << 'EOT'
Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).

LUẬT TIẾP VIỆC: sau khi một hand báo xong, nếu việc kế tiếp chạm cùng file/module hand đó vừa đọc hoặc sửa, dùng SendMessage tới hand đó (brief bổ sung cùng khuôn, chỉ ghi phần thay đổi) thay vì sinh Agent mới. Lý do: hand giữ ngữ cảnh đã đọc và prompt cache còn nóng; cache có TTL nên tiếp việc sớm thì rẻ, để lâu lợi thế giảm.
Sinh hand MỚI khi: việc độc lập hoặc khác vùng code; hand cũ đã làm nhiều việc khác nhau, ngữ cảnh phình to; hand cũ đang chạy (không gửi chồng việc ghi cho hand đang chạy).

LUẬT REVIEW: review do brain tự làm. Sau khi hand báo xong việc ghi, brain tự đọc diff/các file hand đã đổi (git diff hoặc Read) để review trước khi báo người dùng. Không giao hand review, kể cả review việc của hand khác. Nếu review phát hiện lỗi, brain giao sửa (ưu tiên SendMessage cho hand vừa làm), rồi brain review lại.
EOT
)"
TEXT="POLICY brain/hand - KHUÔN BRIEF (bắt buộc khi gọi Agent với parallel-subagents:hand; điền đủ các mục, ngắn gọn):
${BRIEF}
${RULES}"
jq -n --arg ctx "$TEXT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
