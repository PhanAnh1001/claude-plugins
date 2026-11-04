---
Luật bàn giao cho phiên phụ {name} (chạy không có người trực):
- Không hỏi người dùng. Gặp câu hỏi thiết kế hay việc ngoài phạm vi thì dừng phần đó và ghi vào file bàn giao.
- Tuân AGENTS.md (và CLAUDE.md) của repo, kể cả AGENTS.md trong thư mục con.
- Không git commit, không push, trừ khi phần giao việc ở trên cho phép rõ.
- Phiên song song: trước khi ghi file, gửi SendMessage "nhận việc X, sẽ ghi file Y"; hai phiên không ghi cùng một file.
- Xong việc (hoặc bị chặn) thì ghi file bàn giao {handoff}, mở đầu bằng khối "## Tóm tắt" tối đa 15 dòng: kết quả (xong / xong một phần / bị chặn), file đã đổi, kiểm chứng đã chạy và kết quả thật, việc còn lại. Chi tiết đặt ở các mục "## ..." sau khối đó.
[[brain]]- Ghi xong file bàn giao thì dùng SendMessage báo phiên brain "{brain}": "{name} xong, xem {handoff}".
- Câu trả lời cuối cùng của bạn chỉ gồm khối tóm tắt đó, không thêm gì khác.
