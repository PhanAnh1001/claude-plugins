# Bổ sung 1 cho Sol `native-child` (từ Opus, người dùng yêu cầu 07/11)

## Tóm tắt

Mở rộng phạm vi: ngoài subagent native và exit code, panel Paseo (`hybrid-hands/paseo-hh-tree/`, cả panel agent lẫn sidebar) cần thêm màu trạng thái, giờ kết thúc, phần USD~/% riêng của từng dòng và dòng tổng của máy ở trên cùng. Mọi phần khác của brief gốc giữ nguyên: phạm vi ghi, luật, mức test, full chạy một lần ở cuối, bản 0.29.0. Gộp phần này vào cùng bản phát hành và cùng bàn giao.

## Yêu cầu người dùng (nguyên văn)

"panel paseo thiếu màu hiển thị trạng thái đang chạy, done, false,... giờ kết thúc, usd và % của phiên/subagent đã dùng claude/gpt; vẫn hiển thị usd % máy này dùng claude/gpt ở trên cùng"

## Việc thêm

1. **Màu trạng thái**: tô màu icon (và tên nếu cần) theo trạng thái. Đang chạy: xanh dương. Xong: xanh lá. Lỗi (failed/exit ≠ 0/timeout/killed): đỏ. Rảnh/idle hoặc im lặng: vàng. Không rõ/mất: xám. Dòng đếm `X✓ Y✗` tô ✓ xanh lá, ✗ đỏ. Lấy màu từ theme/token có sẵn của Paseo nếu có; phải đọc được cả nền sáng lẫn nền tối.
2. **Giờ kết thúc**: dòng đã kết thúc hiện giờ local `HH:MM`, thêm `dd/mm` nếu khác ngày hôm nay. Dòng đang chạy không hiện giờ. Vẫn KHÔNG hiện giờ bắt đầu.
3. **USD~ và % riêng mỗi dòng**: mỗi phiên/phiên phụ/subagent/hand hiện USD~ và phần % quota tài khoản mà chính dòng đó đã dùng, kèm nhãn nhà cung cấp (Claude hoặc GPT). Ví dụ: `~$0.39 · GPT riêng 0.8% tuần`. % chỉ hiện khi có nguồn; thiếu thì `?`. Không suy token/USD thành quota GPT (luật AGENTS.md).
4. **Dòng tổng của máy ở trên cùng** panel/sidebar, tách theo nhà cung cấp: Claude là USD~ tổng máy cộng % tài khoản 5h/tuần; GPT tương tự. Dòng này thay cho phần quota mà `panel-gon` đặt trên dòng phiên chính. Dòng phiên chính chỉ giữ phần riêng của nó.
5. Giữ nguyên các thứ `panel-gon` đã làm: dòng gọn, tối đa 4 phiên phụ, chỉ phiên gần nhất có tối đa 4 subagent, dòng đếm `+N cũ`, không có nhóm orphan.
6. Cập nhật contract panel trong `AGENTS.md`/`README` cho khớp.

## Kiểm chứng thêm

Thêm tối đa 1 ca test: dòng xong có giờ kết thúc và phần riêng; dòng đang chạy không có giờ; dòng tổng máy ở đầu. Màu chỉ kiểm bằng mẫu render hoặc ảnh chụp, không viết test cho màu. Trong mẫu trước/sau của bàn giao, ghi rõ màu từng trạng thái.
