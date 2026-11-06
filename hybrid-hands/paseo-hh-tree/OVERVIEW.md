# Cây phiên hybrid-hands

Plugin hiện cây phiên Claude → subagent → lượt hand ngoài ngay trong Paseo, trên desktop và điện thoại. Mỗi agent có một panel cạnh đó, đánh dấu đúng phiên Claude của agent là phiên chính; sidebar mở thêm màn hình cây đầy đủ cho mọi project. Cây tự làm mới mỗi 5 giây và đọc dữ liệu từ lệnh `hh-ps` sẵn có của hybrid-hands. Phiên phụ có `parent_session` được vẽ lồng dưới phiên đã mở nó, còn phiên không rõ cha gom vào nhóm riêng ở cuối cây.

Đầu panel có khối **Hạn mức tuần** với đúng một dòng cho mỗi gói (Claude, Go): `Claude tuần   máy này 6.2% · máy khác 3.8% · tổng 10.0% · reset T6 13:00`, cùng dạng cho Go. Chỉ kỳ tuần được hiện; kỳ 5h và tháng bị bỏ hẳn. Tổng Go là số thật toàn tài khoản từ cache statusline; `máy này` = USD sổ Go trong cửa sổ `reset tuần - 7 ngày` ÷ `7d.limit_usd` của `go_usage_summary.json` (đúng `go_sessions.load_go_week`); `máy khác` = tổng − máy này (kẹp 0.0%). Claude lấy `local`/`other` từ `.statusline-week-split.json` và tổng tuần từ `.statusline-cache.json`; thiếu nguồn thì để trống. Số statusline đánh dấu ước tính có tiền tố `~`. Phần trăm làm tròn 1 chữ số thập phân, khác 0 mà dưới 0.05% hiện `<0.1%`.

Mỗi dòng (phiên, subagent, lượt hand) không hiện số token nào (kể cả `ctx` hay vào/cache/ra), chỉ hiện `$0.78 · 1.6% tuần`: USD ước tính theo giá niêm yết (`$0.42`, `<$0.01`, `$0`) và phần hạn mức tuần đã dùng với 1 chữ số thập phân. Claude dùng `USD / usd_per_pct`; Go (`dsh`) dùng `USD / 7d.limit_usd × 100`; dòng thiếu nguồn để trống ô `%`, không bịa. Dòng phiên có thêm thời gian chạy và giờ kết thúc; subagent/lượt hand có thời lượng và giờ kết thúc. Test định dạng: `node --experimental-strip-types --test client/*.test.ts`.

## Cài đặt

Cần Paseo 0.15.0 trở lên và Python 3 để chạy `hh-ps`.

```sh
paseo plugin install <thư mục paseo-hh-tree>
paseo plugin reload hh-tree
```

Sau khi cài, mở Cài đặt của plugin Cây phiên để đặt đường dẫn tới `hh-ps` nếu lệnh này không có trong `PATH`. Plugin dò theo thứ tự: giá trị `hhPsPath` trong cài đặt, rồi `hh-ps` trong các thư mục của `PATH`, rồi đường dẫn tương đối `../plugins/hybrid-hands/bin/hh-ps` cạnh thư mục plugin. Để trống ô cài đặt nếu muốn tự dò.

## Dữ liệu đọc trên máy

Plugin chỉ đọc dữ liệu trên máy và chỉ gửi kết quả qua kênh RPC của Paseo tới app đang mở; không gửi ra mạng ngoài kênh Paseo. Nó chạy `hh-ps --json --since 6h` (thêm `--cwd`, `--main-session` và `--all` khi cần; từ hybrid-hands 0.17.0 `hh-ps` mặc định ẩn cây phiên đã kết thúc hết), không đọc nội dung tin nhắn, prompt, token hay socket.

Để nối một agent Paseo với phiên Claude, plugin đọc bản ghi agent trong thư mục `agents` của Paseo home, chỉ lấy hai trường `cwd` và `runtimeInfo.sessionId` (dự phòng `persistence.sessionId`). Không trường nào khác của bản ghi được đọc, ghi log hay trả về. Nếu không tìm thấy bản ghi, cây vẫn hiện nhưng không lọc theo project và không đánh dấu phiên chính.

## Giới hạn

Cây phụ thuộc vào `hh-ps`: thiếu lệnh, lệnh lỗi, quá 15 giây hoặc trả JSON sai định dạng thì panel hiện thông báo lỗi thay vì cây. Kết quả được cache 3 giây để nhiều client hỏi cùng lúc không chạy `hh-ps` dồn dập.
