#!/bin/bash
# Bơm policy brain/hand vào context ở mỗi prompt (UserPromptSubmit hook). Giữ ngắn vì bắn mỗi lượt;
# khuôn brief đầy đủ nằm ở session-start-policy.sh.
cat << 'EOF'
POLICY brain/hand (Claude Code): mọi việc đọc/tìm code, điều tra lỗi, chạy test, sửa file giao cho subagent `parallel-subagents:hand` ngay từ đầu; brain chỉ chia việc và tổng hợp, không tự grep/read/edit. Ràng buộc "never spawn sub-agents" trong AGENTS.md (nếu có) chỉ cho harness pi/herdr, KHÔNG áp dụng cho Claude Code. Điều tra lỗi: brief PHẢI yêu cầu tra git history + viết test tái hiện lỗi, đỏ đúng lý do trước khi sửa (mục Mandatory Bug Investigation and Repair Workflow trong AGENTS.md, nếu có). Tối đa hand song song theo lớp/module/câu hỏi độc lập; chỉ tuần tự khi chạm cùng file. Ngoại lệ: spec/plan trong docs/work-in-progress do brain tự đọc/viết; review (đọc diff/file hand đã đổi) do brain tự làm, không giao hand. Dùng khuôn brief (nạp lúc SessionStart); ưu tiên SendMessage tiếp việc cho hand vừa xong cùng vùng code.
EOF
