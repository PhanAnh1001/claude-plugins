# Cây phiên hybrid-hands

Plugin hiện panel cạnh agent và màn hình “Cây phiên”, mở bằng nút trên header sidebar Paseo, lấy JSON `hh-ps` và làm mới mỗi 5 giây. Không hiện nhóm orphan hand-ext.

## Phân biệt danh sách native và Cây phiên

`index.client.tsx` đăng ký `addAgentPanel`, `addScreen` và `addSidebarHeaderItem`. Sidebar item chỉ là `SidebarRow` mở màn hình Cây phiên; plugin không cung cấp hay lọc các dòng agent trong danh sách native của Paseo. Panel agent và màn hình Cây phiên dùng chung `client/TreeView.tsx`. Server gọi `hh-ps --json --ended --full --since 6h` (`server/hh-ps.ts:buildHhPsArgs`), nên cây vẫn có thể hiện phiên phụ đã kết thúc sau khi agent Paseo được archive. Dữ liệu cây không có trường archive của Paseo.

Đối chiếu source Paseo 0.15.0 đã cài (đường dẫn tương đối từ package `@getpaseo/cli`):

- `dist/commands/agent/ls.js`: `buildAgentLsFetchOptions` chỉ bật `includeArchived` khi có `-a`; `listAgents` còn lọc `!a.archivedAt` khi không có `-a`.
- `node_modules/@getpaseo/server/dist/server/web-ui/_expo/static/js/web/index-c26368bf062ddf91b40b9d95aae94799.js`: `useAggregatedAgents` mặc định `includeArchived=false`; vòng gom agent bỏ qua `archivedAt`. Luồng dựng membership workspace cũng chỉ thêm agent chưa archived; luồng cập nhật workspace loại agent có `archivedAt` khỏi map. Đây là bundle native, nằm ngoài plugin.

Nếu `paseo ls -g` đã không có phiên phụ, `paseo ls -a -g` vẫn có và archive trả `AGENT_ALREADY_ARCHIVED`, không archive lại hay archive phiên chính để xử lý hiển thị. Cần xác định dòng nằm trong danh sách native hay màn hình Cây phiên trước khi sửa bộ lọc. Các kết quả CLI này xác nhận trạng thái archive theo brief; chưa chứng minh client đang xem cùng host hoặc đã nhận cập nhật.

Kiểm tra tải thực tế đề xuất: tải lại trang/app Paseo, chọn đúng host đã dùng cho CLI, mở danh sách active và đối chiếu bốn phiên phụ RV-52/WP-53/WP-51/RV-50; đồng thời xác nhận phiên chính và phiên đang chạy còn hiện. Sau đó mở nút Cây phiên để phân biệt dữ liệu `hh-ps`. Nếu native vẫn hiện các phiên archived sau tải lại, cần chẩn đoán directory sync/cache ở Paseo; reload plugin `hh-tree` chỉ tải lại plugin. Không thay bộ lọc panel agent để chữa danh sách native. Chưa thực hiện kiểm tra UI này trong lượt chẩn đoán source.

Mỗi dòng giữ icon ● chạy / ✓ xong / ✗ lỗi / ? chưa rõ, tên ngắn, model·effort, elapsed, giờ kết thúc local HH:MM (dd/mm HH:MM nếu khác ngày), USD~ và phần riêng của provider theo `usage.week_pct`; thiếu nguồn giữ ?. Phần riêng không lấy quota tài khoản thay thế. Running không hiện giờ kết thúc. Icon running/busy xanh dương, done xanh lá, lỗi/exit khác 0 đỏ, idle/silent vàng, unknown/lost xám; các số ✓/✗ trong dòng gộp cũng có màu tương ứng. Dùng token theme, riêng running dùng accent nếu xanh dương hoặc màu xanh phù hợp nền sáng/tối.

Đầu panel/sidebar luôn có hai dòng Claude/GPT: USD tuần máy này từ `machine_usage` độc lập bộ lọc cây, rồi quota tài khoản 5h/tuần từ một sample nguyên vẹn hoặc limits cùng nguồn. Không cộng USD từ các dòng đang hiện. Thiếu nguồn hiện ?, quota không lặp ở root. Không hiện cwd, description đầy đủ, nhãn model/effort hay giờ bắt đầu. Elapsed running tăng theo now−started; đã xong cố định theo ended hoặc duration có sẵn.

Mỗi cây flatten tối đa 4 phiên phụ: running trước, rồi ended/started mới nhất; tie giữ thứ tự duyệt cây/agent đầu vào. Phần dư `+N cũ: X✓ Y✗`, thêm ●N/?N khi có. Phiên gần nhất của từng cây được chọn bằng max last_activity/ended/started và mốc agent con, không ưu tiên is_main. Chỉ phiên đó mở tối đa 4 subagent/hand có cha chung pool; các agent khác gộp `N subagent: X✓ Y✗`. Phiên bị ẩn vẫn giữ đủ số đếm; nếu là phiên gần nhất thì các agent mở có nhãn tên phiên dưới phần gộp. Lỗi/exit khác 0/timeout/killed ưu tiên trên running cũ; unknown không tính là thành công.

USD~ là ước tính offline subscription, không phải hoá đơn. Giá lấy từ [nguồn canonical](../plugins/hybrid-hands/config/model-prices.json); quota tài khoản chỉ dùng cache/sample đúng nguồn, không suy từ token/USD. Native Codex child từ `hh-ps` nằm trong subagents với tên ngắn từ metadata description/title/agent_path/nickname (thiếu thì `native-codex`), chung pool tối đa 4 và số đếm; completed tính ✓, failed/errored/cancelled tính ✗, exit khác 0 ưu tiên lỗi, thiếu nguồn giữ ?. Panel không tự dựng nguồn native. Xem [contract panel, mục 8](../README.md#8-xem-cây-trên-paseo). Test hẹp: `node --experimental-strip-types --test client/*.test.ts`.

## Thứ tự và tên từ 0.31.3

Panel agent và màn hình mở từ nút sidebar dùng chung forest theo `parent_session` tường minh, không đoán cha từ cwd. Child đến trước root vẫn nằm trong root; phiên phụ có parent không tìm thấy được đặt cuối sau mọi root. Tên ưu tiên description, thu gọn khoảng trắng và cắt ngắn khi hiển thị; dữ liệu description gốc không đổi. Native chỉ đọc metadata description/title/agent_path/nickname, không lấy prompt hoặc hội thoại đặt tên.

Kiểm chứng SDK đã cài `@getpaseo/plugin` 0.15.0: `dist/client/contracts.d.ts:PluginClientContext` chỉ có `addSidebarHeaderItem`/`addSidebarFooterItem`, không có hook đổi hierarchy, thứ tự hoặc nhãn dòng native. `@getpaseo/client/dist/daemon-client.d.ts:CreateAgentRequestOptions` có `callerAgentId` (không có input `parentAgentId`); server `agent/create-agent/intent.js` tạo parent từ caller và mặc định dùng workspace caller nếu không chỉ định workspace. Đây là capability tạo mới, không phải API sửa thứ tự sidebar hay reparent agent hiện hữu. Không đổi bridge placement vì các native Sol trong brief được tạo qua native API, không qua bridge. Không sửa bundle bên ngoài, không tạo/rename/archive agent để chữa UI; chưa sửa được danh sách sidebar native bằng API plugin này.

Brain cập nhật bản hybrid-hands 0.31.3 bằng công cụ cài đặt chính thức cho mọi repo đã dùng plugin, kiểm tra version/path được nạp. Cài lại addon từ checkout đã cập nhật bằng `paseo plugin install <đường dẫn tuyệt đối tới paseo-hh-tree>`, sau đó `paseo plugin reload hh-tree`. Tải lại app nếu phiên đang mở chưa nhận code mới; mở panel agent và nút Cây phiên để kiểm chứng. Các bước này chưa được executor chạy. Không archive phiên chính.

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
