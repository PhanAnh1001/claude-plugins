# hh-tree-pane

Mod Claude Code: pane cạnh khung chat trong terminal, hiển thị cây phiên của hybrid-hands
(phiên brain → subagent → lượt hand ngoài) lấy từ `hh-ps --since 3h --json`, làm mới mỗi 5 giây.

- Đầu pane có khối `Hạn mức` đúng một dòng **tuần** cho mỗi gói: `Claude tuần   máy này 6.2% · máy khác 3.8% · tổng 10.0% · reset T6 13:00`, cùng dạng cho Go; kỳ 5h và tháng bị bỏ hẳn (client cũng lọc `window === "tuần"`). Go `máy này` = USD sổ trong cửa sổ reset tuần ÷ `7d.limit_usd`; Claude lấy `local`/`other` của statusline; `máy khác` = tổng − máy này (kẹp 0.0%); thiếu nguồn thì `?`, số ước tính có `~`.
- Định dạng gọn dùng chung với `hh-ps` (xem README của hybrid-hands, mục `hh-ps`): dòng phiên `<dấu> <tên>  <im|giờ dừng>  <trạng thái>  <USD>  <% tuần>`, dòng con `<dấu> <loại>  <thời lượng>  <giờ xong>  <USD>  <% tuần>  <mô tả>  [trạng thái lỗi]` (số đứng trước nên pane hẹp cắt mô tả, không cắt số; trạng thái lỗi sau mô tả nên dòng ổn không có khoảng trống thừa); không in cwd hay repo. Dòng phiên, dòng phiên phụ và dòng con dùng chung một bảng cột nên ô USD và ô `%` (căn phải) thẳng cột ở mọi độ sâu; mô tả cắt 16 cột. Không hiện số token nào (kể cả `ctx`, `out`). USD dạng `$0.42`, dưới `$0.01` ghi `<$0.01`, không dùng gì ghi `$0`, không có giá ghi `-`. `%` là phần hạn mức **tuần** đã dùng, 1 chữ số thập phân (`12.3%`, khác 0 mà dưới 0.05% ghi `<0.1%`), đúng công thức statusline: Claude `USD / usd_per_pct`, Go (`dsh`) `USD / 7d.limit_usd × 100`; dòng thiếu nguồn hiện `-`, số ước tính có `~`. Dưới tiêu đề có chú giải `▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · $ ước tính theo giá niêm yết · % = phần hạn mức tuần đã dùng`.
- Phiên đang mở pane (`▶`) đứng đầu. Mọi phiên (phiên của pane, phiên ở tab khác, phiên phụ) liệt kê việc con theo cùng một luật: mọi việc đang chạy (subagent chạy/im lặng, lượt hand chạy, phiên phụ sống) trước, rồi tối đa 3 việc xong hoặc lỗi gần nhất (theo giờ kết thúc), cuối cùng dòng mờ `+N xong · M lỗi` cho phần không hiện (`M lỗi` màu đỏ). Phiên `busy` im quá 15 phút ghi `kẹt?`.
- Phiên phụ là một việc con của phiên cha: `<dấu> phụ:<tên>  <im/thời lượng>  <giờ dừng>  <USD>  <% tuần>  <tiêu đề tự động>`, chung bảng cột với dòng phiên và dòng con nên USD và `%` thẳng cột ở mọi độ sâu; tiêu đề lấy từ `ai_title` trong JSON (cắt 16 cột như mô tả hand), việc của nó lồng thêm một cấp theo cùng luật.
- `hh-ps` mặc định đã ẩn cây phiên đã kết thúc hết; tiêu đề pane ghi số phiên bị ẩn.
- Giờ xong `HH:MM` theo giờ máy (khác ngày: `dd/mm HH:MM`). Các cột đệm theo độ rộng hiển thị (bỏ ký tự tổ hợp), tính cả thụt lề; mục tiêu là dòng con ≤ 100 cột và dòng phiên ≤ 92 cột (mẫu thực tế dài nhất 82 cột, test biên 91 cột).
- Lệnh `/hh-tree` mở lại pane. Terminal cần rộng từ khoảng 110 cột.

## Bật cho mọi phiên

Thêm thư mục này vào `CLAUDE_CODE_PLUGIN_DIRS` trong khối `env` của `~/.claude/settings.json`:

```json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "~/app/claude-plugins/hybrid-hands/hh-tree-pane" } }
```

Phiên mở sau đó tự nạp mod; sửa file trong thư mục thì phiên đang chạy tự nạp lại.

## Kiểm tra

`claude plugin validate ~/app/claude-plugins/hybrid-hands/hh-tree-pane`

Test định dạng dòng: `node --experimental-strip-types --test hybrid-hands/hh-tree-pane/tests/tree.test.ts` (chạy từ gốc repo).
