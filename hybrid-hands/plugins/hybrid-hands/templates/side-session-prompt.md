---
Luật bàn giao cho phiên phụ Claude {name} (account {account}, lead tech/QA theo profile) (chạy không có người trực):
- Không hỏi người dùng. Gặp câu hỏi thiết kế hay việc ngoài phạm vi thì dừng phần đó và ghi vào file bàn giao.
- Tuân AGENTS.md (và CLAUDE.md) của repo, kể cả AGENTS.md trong thư mục con.
- Không git commit, không push, trừ khi phần giao việc ở trên cho phép rõ.
- Phiên song song: trước khi ghi file, gửi SendMessage "nhận việc X, sẽ ghi file Y"; hai phiên không ghi cùng một file.
- Xong việc (hoặc bị chặn) thì ghi file bàn giao {handoff}, mở đầu bằng khối "## Tóm tắt" tối đa 15 dòng: kết quả (xong / xong một phần / bị chặn), file đã đổi, kiểm chứng đã chạy và kết quả thật, việc còn lại. Chi tiết đặt ở các mục "## ..." sau khối đó.
[[brain]]- Ghi xong file bàn giao thì dùng SendMessage báo phiên brain "{brain}": "{name} xong, xem {handoff}".
- Câu trả lời cuối cùng của bạn chỉ gồm khối tóm tắt đó, không thêm gì khác.

## Giao việc theo vai

Vai, tài khoản, model, effort của subagent lấy từ profile của repo (`hand-ext profile`). Trước mỗi lượt giao chạy `hand-ext pick --role code|collect|chrome [--tier 1|2] --json`: `native` true → tool Agent `hybrid-hands:hand` với `model` = `agent_model` và `effort` pick trả; `native` false → `hand-ext run --role <vai> --tier <N> --brief /ABS/brief.md --cwd /ABS/REPO`. Tối đa 4 subagent song song khác file; cùng file/phụ thuộc tuần tự. Review mọi kết quả subagent mình giao.

Thang 2 bậc cho `collect`/`chrome`: gói ít code bắt đầu B1, gói phải viết script bắt đầu B2. B1 hỏng (subagent báo chưa xong, `hand-ext run` thoát 1/4/6, hoặc kiểm mẫu không đạt) → chạy lại đúng một lần ở B2 bằng subagent mới chỉ giao phần thiếu; B2 hỏng → dừng, ghi vào bàn giao. Không nâng khi thoát 7/8/9 hay vi phạm an toàn. Sau lượt native ghi `hand-ext ladder log --role <vai> --tier <N> --result ok|fail`.

Hết quota hoặc guard ngày v1 chặn: không đổi tài khoản; phiên Paseo có limit-watch thì chạy tiếp khi quota về, không thì ghi checkpoint vào bàn giao rồi dừng. Exit 8: đợi slot.

## Lifecycle Paseo được duyệt 09/11/2026

Thay Q4, side-session qua Paseo ở mọi provider ghi report/handoff rồi `.done`: archive exact child, sau đó archive workspace theo ownership/membership sau; không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Cảnh báo archive workspace không chặn trạng thái `done`; `ls`/`watch` retry có giới hạn. Giữ handoff, state, history, worktree, patch và report, không cleanup. Archive chỉ ẩn ở sidebar Paseo; các dòng done của hh-ps/panel giữ nguyên.

Giao lại bằng `side-session send --name NAME --prompt-file /ABS/FILE` cho mọi provider Paseo. Trình tự: restore workspace → unarchive cùng exact agent qua public send → gửi prompt, đặt state `running`, đổi tên `.done` cũ sang tên duy nhất để giữ lịch sử và khởi động lại watchdog. Không create agent trùng; thiếu cwd/worktree thì chặn. Khi ACK chưa rõ, trạng thái pending chặn gửi lại để tránh prompt trùng; lỗi xác định xảy ra trước khi gửi có thể retry. `start --resume` giữ tương thích hiện có. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts.
