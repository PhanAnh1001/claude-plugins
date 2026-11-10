# Quyết định panel-gon (L1, bản cuối)

- Giữ icon ●/✓/✗/?, tên ngắn tối đa 32 ký tự, model·effort, elapsed và USD~. Bỏ nhãn model/effort, root/side session, cwd, mô tả dư, trạng thái bằng chữ, mốc bắt đầu/kết thúc và header/footer giải thích. Thiếu dữ liệu giữ `?`.
- Quota 5h/tuần của từng account plan trong cây hiện một lần ở root. Chọn nguyên sample có nhiều window hơn, tie giữ sample đầu/root trước; không cộng hay ghép window từ hai sample, không suy quota Claude sang GPT. Hoàn toàn thiếu nguồn thì `TK 5h ? · tuần ?`.
- Mỗi root flatten hậu duệ thành tối đa 4 dòng phiên phụ: running trước, sau đó max ended/started mới nhất; tie giữ thứ tự duyệt cây. Phần dư `+N cũ: X✓ Y✗`, thêm `●N` hoặc `?N` khi có.
- Trong từng cây root, latest là phiên có max last_activity/ended/started và mốc hoạt động agent con; tie giữ thứ tự duyệt, không ép is_main. Chỉ latest mở tổng tối đa 4 subagent/hand có parent khớp, cùng luật ưu tiên. Các agent khác gộp số, kể cả phiên ẩn; latest bị ẩn giữ agent dưới nhãn tên phiên trong phần gộp, không thêm full session row thứ năm.
- Error/exit khác 0/timeout/killed ưu tiên trước running; running trước success cũ. Chỉ status thành công rõ hoặc exit 0 xác nhận done; state=finished đơn thuần vẫn unknown. Duration running tăng theo now−start, đã xong cố định ended−start hoặc duration có sẵn.
- `MAX_SIDE_SESSIONS=4`, `MAX_SUBAGENTS=4` chỉ ở panel, không thêm setting. Không render orphan hand-ext. Native/exit metadata chưa có nguồn được ghi là hạn chế, không sửa hh-ps hay dựng dữ liệu giả.
