# hh-tree-pane

Mod Claude Code: pane cạnh khung chat trong terminal, hiển thị cây phiên của hybrid-hands
(phiên brain → subagent → lượt hand ngoài) lấy từ `hh-ps --since 3h --json`, làm mới mỗi 5 giây.

- Định dạng gọn dùng chung với `hh-ps` (xem README của hybrid-hands, mục `hh-ps`): dòng phiên `<dấu> <tên>  <im|giờ dừng>  <trạng thái>  <đọc|cđọc|cghi|ra>  <USD>  ctx <N>`, dòng con `<dấu> <loại>  <thời lượng>  <giờ xong>  <đọc|cđọc|cghi|ra>  <USD>  <cỡ>  <mô tả>  [trạng thái lỗi]` (số đứng trước nên pane hẹp cắt mô tả, không cắt số; trạng thái lỗi sau mô tả nên dòng ổn không có khoảng trống thừa); không in cwd hay repo. Dòng phiên, dòng phiên phụ và dòng con dùng chung một bảng cột nên khối token, USD và ô `ctx`/`out` bắt đầu cùng cột hiển thị ở mọi độ sâu; mô tả cắt 16 cột. Khối token `read|cache_read|cache_write|out` căn phải từng số, các `|` thẳng cột; thiếu số ghi `-`; USD dạng `$0.42`, dưới `$0.01` ghi `<$0.01`, không dùng gì ghi `$0`, không có giá ghi `-`. Dưới tiêu đề có chú giải `▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · token: đọc|cache đọc|cache ghi|ra · $ ước tính theo giá niêm yết`.
- Phiên đang mở pane (`▶`) đứng đầu. Mọi phiên (phiên của pane, phiên ở tab khác, phiên phụ) liệt kê việc con theo cùng một luật: mọi việc đang chạy (subagent chạy/im lặng, lượt hand chạy, phiên phụ sống) trước, rồi tối đa 3 việc xong hoặc lỗi gần nhất (theo giờ kết thúc), cuối cùng dòng mờ `+N xong · M lỗi` cho phần không hiện (`M lỗi` màu đỏ). Phiên `busy` im quá 15 phút ghi `kẹt?`.
- Phiên phụ là một việc con của phiên cha: `<dấu> phụ:<tên>  <im/thời lượng>  <giờ dừng>  <đọc|cđọc|cghi|ra>  <USD>  ctx <N>  <tiêu đề tự động>`, chung bảng cột với dòng phiên và dòng con nên khối token, USD và `ctx` thẳng cột ở mọi độ sâu; tiêu đề lấy từ `ai_title` trong JSON (cắt 16 cột như mô tả hand), việc của nó lồng thêm một cấp theo cùng luật.
- `hh-ps` mặc định đã ẩn cây phiên đã kết thúc hết; tiêu đề pane ghi số phiên bị ẩn.
- Giờ xong `HH:MM` theo giờ máy (khác ngày: `dd/mm HH:MM`). Các cột đệm theo độ rộng hiển thị (bỏ ký tự tổ hợp), tính cả thụt lề; sau khi thêm khối token/USD, mục tiêu là dòng con ≤ 100 cột và dòng phiên ≤ 92 cột (mẫu thực tế dài nhất 82 cột, test biên 91 cột).
- Lệnh `/hh-tree` mở lại pane. Terminal cần rộng từ khoảng 110 cột.

## Bật cho mọi phiên

Thêm thư mục này vào `CLAUDE_CODE_PLUGIN_DIRS` trong khối `env` của `~/.claude/settings.json`:

```json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "~/app/claude-plugins/hybrid-hands/hh-tree-pane" } }
```

Phiên mở sau đó tự nạp mod; sửa file trong thư mục thì phiên đang chạy tự nạp lại.

## Kiểm tra

`claude plugin validate ~/app/claude-plugins/hybrid-hands/hh-tree-pane`
