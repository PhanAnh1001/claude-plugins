# Cây phiên hybrid-hands

Plugin hiện cây phiên chính → subagent → lượt hand ngoài và phiên phụ mọi provider/backend trong Paseo (desktop/điện thoại). Mỗi agent có panel cạnh đó; sidebar mở cây mọi project. Dữ liệu từ `hh-ps`, tự làm mới mỗi 5 giây; phiên phụ có `parent_session` được lồng dưới cha. Cả panel cạnh agent và cây sidebar tuyệt đối không hiện nhóm orphan hand-ext; `hh-ps` text/JSON vẫn giữ orphan.

Mỗi dòng hiện model, effort, USD~, quota tài khoản 5h/tuần, ended hoặc `đang chạy`, elapsed. Việc đang chạy tăng elapsed; việc đã xong dùng ended để cố định duration. Không hiện giờ bắt đầu trong UI, JSON/meta giữ started. Không hiện token trong panel. Legacy unknown hoặc thiếu nguồn hiện `?`.

USD~ là ước tính offline trên gói subscription, không phải hoá đơn. Giá canonical: [`config/model-prices.json`](../plugins/hybrid-hands/config/model-prices.json), override `HYBRID_HANDS_PRICING_FILE`, mỗi entry có source/price_date; cache Claude tính đúng giá cấu hình 5m/1h, model lạ không fallback. Quota tài khoản 5h/tuần từ cache/sample sẵn có; không suy token/USD thành quota GPT. Phần riêng hand tuần chỉ thêm khi có nguồn và gắn nhãn riêng. Khối hạn mức giữ reset và dấu ước tính khi nguồn có.

Mặc định đủ việc chạy/vừa xong theo since, không gấp 3 việc hay ẩn cây đã xong. Contract đầy đủ: [README hybrid-hands, mục 6](../README.md#6-theo-dõi-phiên-và-hand-hh-ps). Lệnh kiểm định dạng tham khảo (chạy trong thư mục này): `node --experimental-strip-types --test client/*.test.ts`.

## Cài đặt

Cần Paseo 0.15.0 trở lên và Python 3 để chạy `hh-ps`.

```sh
paseo plugin install <thư mục paseo-hh-tree>
paseo plugin reload hh-tree
```

Sau khi cài, mở Cài đặt của plugin Cây phiên để đặt đường dẫn tới `hh-ps` nếu lệnh này không có trong `PATH`. Plugin dò theo thứ tự: giá trị `hhPsPath` trong cài đặt, rồi `hh-ps` trong các thư mục của `PATH`, rồi đường dẫn tương đối `../plugins/hybrid-hands/bin/hh-ps` cạnh thư mục plugin. Để trống ô cài đặt nếu muốn tự dò.

## Dữ liệu đọc trên máy

Plugin chỉ đọc dữ liệu trên máy và chỉ gửi kết quả qua kênh RPC của Paseo tới app đang mở; không gửi ra mạng ngoài kênh Paseo. Nó chạy `hh-ps --json --since 6h` (thêm `--cwd`, `--main-session` và `--all` khi cần); client dùng metadata/usage tổng hợp từ JSON, không hiển thị nội dung hội thoại, prompt hay credential.

Để nối một agent Paseo với phiên Claude, plugin đọc bản ghi agent trong thư mục `agents` của Paseo home, chỉ lấy hai trường `cwd` và `runtimeInfo.sessionId` (dự phòng `persistence.sessionId`). Không trường nào khác của bản ghi được đọc, ghi log hay trả về. Nếu không tìm thấy bản ghi, cây vẫn hiện nhưng không lọc theo project và không đánh dấu phiên chính.

## Giới hạn

Cây phụ thuộc vào `hh-ps`: thiếu lệnh, lệnh lỗi, quá 15 giây hoặc trả JSON sai định dạng thì panel hiện thông báo lỗi thay vì cây. Kết quả được cache 3 giây để nhiều client hỏi cùng lúc không chạy `hh-ps` dồn dập.
