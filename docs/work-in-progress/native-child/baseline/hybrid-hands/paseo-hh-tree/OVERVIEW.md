# Cây phiên hybrid-hands

Plugin hiện panel cạnh agent và sidebar Paseo, lấy JSON `hh-ps` và làm mới mỗi 5 giây. Không hiện nhóm orphan hand-ext.

Mỗi dòng giữ icon ● chạy / ✓ xong / ✗ lỗi / ? chưa rõ, tên ngắn, model·effort, elapsed và USD~. Quota tài khoản 5h/tuần mỗi account plan trong cây chỉ hiện ở root, thiếu nguồn `?`. Không hiện cwd, description, nhãn model/effort, mốc bắt đầu/kết thúc hay header/footer giải thích. Elapsed running tăng theo now−started; đã xong cố định theo ended hoặc duration có sẵn.

Mỗi cây flatten tối đa 4 phiên phụ: running trước, rồi ended/started mới nhất; tie giữ thứ tự duyệt cây/agent đầu vào. Phần dư `+N cũ: X✓ Y✗`, thêm ●N/?N khi có. Phiên gần nhất của từng cây được chọn bằng max last_activity/ended/started và mốc agent con, không ưu tiên is_main. Chỉ phiên đó mở tối đa 4 subagent/hand có cha chung pool; các agent khác gộp `N subagent: X✓ Y✗`. Phiên bị ẩn vẫn giữ đủ số đếm; nếu là phiên gần nhất thì các agent mở có nhãn tên phiên dưới phần gộp. Lỗi/exit khác 0/timeout/killed ưu tiên trên running cũ; unknown không tính là thành công.

USD~ là ước tính offline subscription, không phải hoá đơn. Giá lấy từ [nguồn canonical](../plugins/hybrid-hands/config/model-prices.json); quota tài khoản chỉ dùng cache/sample đúng nguồn, không suy từ token/USD. Native Codex child chưa được hh-ps xuất; panel không tự dựng nguồn này. Xem [contract panel, mục 8](../README.md#8-xem-cây-trên-paseo). Test hẹp: `node --experimental-strip-types --test client/*.test.ts`.

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
