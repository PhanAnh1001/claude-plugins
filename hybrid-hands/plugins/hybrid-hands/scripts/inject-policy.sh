#!/bin/bash
# Bơm policy hybrid-hands vào context ở mỗi prompt (UserPromptSubmit hook). Giữ ngắn vì bắn mỗi lượt;
# khuôn brief, luật chọn hand và luật hạn mức đầy đủ nằm ở session-start-policy.sh.
cat << 'EOF'
POLICY hybrid-hands: brain (gói Claude chính) chỉ chia việc, tổng hợp, review; việc đọc/sửa code, chạy test giao hand ngay, song song theo phần độc lập. Mặc định `hand-ext run --backend auto` (gói thứ hai, chạy nền; brief chép nguyên văn luật cấm, nhất là .env); cần tool Claude Code, lệnh trả phí, hoặc hand-ext thoát 7/lỗi → `hybrid-hands:hand`; việc trên 1 giờ → `side-session start`. Không dùng API key; báo backend, token, % hạn mức. Điều tra lỗi: git history + test đỏ đúng lý do. Brain tự review diff. Tiếp việc: SendMessage khi cache nóng hoặc ngữ cảnh ≤80k; lệnh trên 4 phút tách hand riêng.
EOF
