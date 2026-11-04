#!/bin/bash
# Bơm policy hybrid-hands vào context ở mỗi prompt (UserPromptSubmit hook). Giữ ngắn vì bắn mỗi lượt;
# khuôn brief, luật chọn hand và luật chi phí đầy đủ nằm ở session-start-policy.sh.
cat << 'EOF'
POLICY hybrid-hands: brain chỉ chia việc, tổng hợp, review; mọi việc đọc/tìm code, chạy test, sửa file giao hand ngay từ đầu, song song tối đa theo phần độc lập. Chọn hand: việc code/tài liệu tự chứa → `hand-gpt run` (estimate + bảng chi phí trước, duyệt khi từ approval_usd, chạy nền; brief chép nguyên văn luật cấm, nhất là cấm đọc .env); cần tool Claude Code, lệnh trả phí, hook repo hoặc hand GPT lỗi → `hybrid-hands:hand`; gói việc dài trên 1 giờ → `side-session start`. Tối đa 2 lệnh trả phí cùng lúc. Điều tra lỗi: brief yêu cầu tra git history + test tái hiện đỏ đúng lý do. Review diff do brain tự làm. Tiếp việc: SendMessage khi cache nóng (dưới 5 phút) hoặc ngữ cảnh hand ≤80k; lệnh trên 4 phút tách hand riêng.
EOF
