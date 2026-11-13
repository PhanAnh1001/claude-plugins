# Nhiệt và Chrome headless

Tóm tắt: chọn khóa một slot, timeout hữu hạn, ưu tiên nền, reap fail-closed. Chưa đủ điều kiện phát hành: sandbox không cho đọc ps, chưa đo Chrome, chưa nối policy.

## Social listening

Nguồn xem ngày 13/11/2026: [Playwright MCP #1568](https://github.com/microsoft/playwright-mcp/issues/1568), [agent-browser #1437](https://github.com/vercel-labs/agent-browser/issues/1437), [Chrome flags](https://github.com/GoogleChrome/chrome-launcher/blob/main/docs/chrome-flags-for-tools.md). Các issue là báo cáo cộng đồng chưa kiểm chứng trên máy này: orphan có thể tiếp tục dùng CPU; Metal có thể đã là mặc định, bật unsafe-swiftshader không đồng nghĩa ép software. Vì vậy ưu tiên lifecycle, không áp cờ GPU trước số đo. Ngưỡng 60% và giới hạn hai luồng là lựa chọn vận hành theo brief, chưa chứng minh ngưỡng nhiệt. Không có nguồn xác nhận nên giữ luật test thường 90%.

## Thiết kế và giới hạn

Khóa flock toàn máy, timeout gồm chờ khóa/gate/lệnh. Không client CDP phải được lsof xác nhận; thiếu port, port 0, pipe hoặc lỗi đều chặn reap. Recheck identity trước TERM. Không hiện args để tránh lộ dữ liệu. Không suy nhiệt độ từ CPU; pmset chỉ là tín hiệu throttling. Cleanup group từ chối nếu không chứng minh browser an toàn; detached descendants chưa được quản lý đầy đủ. Slot cố định một, chưa có cấu hình tăng slot.

Policy thật ở lib/policy_rules.txt và scripts/session-start-policy.sh, nằm ngoài vị trí hooks/config mà brief cho phép; không sửa. Hai skill đã thêm luật, cần brain nối policy trong phạm vi mới.

## Đo CPU

| Cấu hình | Raw 3 lượt × 15s | Trung vị |
|---|---|---|
| swiftshader | chưa chạy | ? |
| metal | chưa chạy | ? |

`hh-heat status --json` và `hh-heat reap --dry-run` trả 2, PermissionError khi đọc tiến trình trong sandbox. Gate không chứng minh ok nên không mở benchmark/browser. Không tải three.js hay gọi dịch vụ. Brain cần đo trên máy thật bằng fixture công khai, kiểm renderer Metal thực trước kết luận. Không có số đo raw để báo cáo.

## Đo CPU 13/11/2026

Môi trường: MacBookPro17,1 (Apple M1, 8 CPU), macOS 26.6.2 (25G83), Chrome 157.0.8103.51; Chrome người dùng đang chạy bản .50 được giữ nguyên. Fixture WebGL three.js cục bộ: 200 hộp xoay, MeshStandardMaterial, ambient + directional light, antialias=true, canvas 1280×720, DPR=1. Chép three.module.js và phụ thuộc three.core.js có sẵn, không tải/cài gói. Toàn bộ benchmark và browser con chạy dưới `nice -n 19 taskpolicy -b`.

Phương pháp: n=3, thứ tự A,B,C,A,B,C,A,B,C; chỉ đổi chính sách render của trang. Mỗi lượt gate `--wait --timeout-min 10`, profile mới, remote-debugging-port=0 riêng (đọc DevToolsActivePort); chờ CDP/title sẵn sàng có hạn tối đa 60 lần, rồi warmup 5s; lấy 15 mẫu ps cách 1s; đọc title bằng curl `/json/list` (HTML-unescape trước parse JSON); TERM đúng browser/profile và cây con, đợi tối đa 5s rồi KILL chỉ cây còn lại nếu cần, nghỉ 10s. Tổng CPU cộng root đúng profile + descendants theo PPID, loại PID có trước; 100% tương đương một lõi, không chia 8. Đây là trung bình các chỉ báo `%CPU` của ps, không phải đo CPU-time delta chính xác cho từng giây. FPS là delta số lần gọi renderer.render / delta thời gian title trong cửa sổ đo, không phải presented FPS. C đã vẽ đúng 1 khung trước cửa sổ nên FPS trong cửa sổ = 0.

Có ba lần thử chuẩn bị không tính vào 9 lượt: title chưa sẵn sàng sau 5s; DevToolsActivePort chưa có sau 5s; title CDP escape `&quot;` khiến parse JSON lỗi (đã dừng runner và cleanup). Đã sửa parser/chờ sẵn sàng trong script tạm trước chuỗi đo hợp lệ. Vì phải chờ sẵn sàng, thời gian từ launch tới mẫu không cố định đúng 5s như brief ban đầu; cần giữ giới hạn này khi so sánh.

| Cấu hình | 3 lượt tổng %CPU trung bình | Trung vị %CPU | FPS từng lượt (trung vị) |
|---|---|---|---|
| A: rAF liên tục | 16.91 / 29.43 / 23.68 | 23.68 | 12.83 / 16.24 / 14.80 (14.80) |
| B: rAF bỏ khung, trần 10fps | 25.00 / 21.66 / 18.21 | 21.66 | 8.04 / 7.79 / 8.01 (8.01) |
| C: một khung rồi dừng | 28.17 / 19.93 / 23.05 | 23.05 | 0.00 / 0.00 / 0.00 (0.00) |

Renderer A: `ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)`.
Renderer B: `ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)`.
Renderer C: `ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)`.

### Raw: 15 mẫu tổng %CPU mỗi lượt

| Lượt | Cấu hình | 15 mẫu cách 1s |
|---|---|---|
| 1 | A | 13.8, 11.7, 27.7, 26.3, 30.3, 28.0, 26.3, 21.4, 6.6, 6.6, 18.3, 9.8, 9.0, 10.4, 7.5 |
| 2 | B | 97.3, 47.2, 46.2, 50.4, 30.0, 12.9, 10.7, 9.4, 13.6, 7.0, 9.1, 8.3, 18.0, 6.7, 8.2 |
| 3 | C | 192.2, 48.0, 52.9, 15.0, 23.4, 23.8, 29.0, 3.3, 5.7, 4.8, 5.6, 4.6, 2.7, 7.9, 3.7 |
| 4 | A | 122.8, 34.0, 20.8, 23.9, 31.7, 57.3, 48.2, 11.6, 10.2, 21.1, 14.5, 11.7, 10.0, 11.7, 11.9 |
| 5 | B | 21.8, 34.2, 39.2, 50.6, 72.8, 11.3, 10.1, 10.7, 8.8, 13.1, 8.3, 13.1, 8.2, 10.5, 12.2 |
| 6 | C | 109.6, 60.3, 42.2, 40.4, 4.7, 4.4, 4.7, 4.2, 5.7, 5.0, 3.2, 3.4, 3.3, 4.5, 3.3 |
| 7 | A | 25.1, 33.4, 19.5, 29.4, 52.0, 91.3, 11.7, 13.9, 11.4, 8.7, 13.1, 11.2, 13.2, 10.0, 11.3 |
| 8 | B | 24.5, 15.0, 14.9, 44.5, 38.3, 52.4, 9.6, 8.7, 10.7, 8.3, 14.0, 9.9, 7.6, 6.9, 7.8 |
| 9 | C | 100.0, 40.2, 21.5, 14.6, 57.5, 40.1, 17.0, 19.2, 8.6, 5.0, 5.2, 3.9, 4.5, 4.5, 4.0 |

CPU toàn máy (hh-heat, đã chia số lõi): trước chuẩn bị 10.76%; trước/sau chuỗi 9 lượt 33.75% / 33.95%; kiểm tra cuối 26.49%, state=ok, thermal_warning=false, cpu_speed_limit=null. Không có lần kiểm tra nào thấy hot; không suy rằng nhiệt độ vật lý thấp từ state=ok.

PID Chrome trước lần mở đầu đã được liệt kê bằng ps ở đầu phiên; snapshot PID bảo vệ trước chuỗi 9 lượt: `1275, 3846, 22264, 23934, 24425, 24429, 24437, 24444, 24521, 24526, 24561, 24562, 25571, 45203, 45370, 46089, 46107, 46112, 46113, 46118, 50724, 50725, 76275, 76552, 76556, 76661, 76837, 81243, 81266, 81267, 86379, 87154, 87155, 87157, 87176, 87181, 87183, 91529, 93432, 93451, 95152, 97220`. Không đóng browser g3-chrome/ga- hoặc browser ngoài profile benchmark.

### Kết luận và đề xuất cho luật

B giảm trung vị khoảng 8.5% so với A, C giảm khoảng 2.6%; khoảng dao động ba cấu hình chồng lấn mạnh. C vẫn có CPU burst đầu cửa sổ dù không render thêm; hoạt động khởi động Chrome và tải nền còn gây nhiễu. Không có bằng chứng đủ mạnh để áp luật bắt buộc 10fps, kết luận C ít CPU nhất, hoặc quy mức 275–400% GPU trước đó cho rAF. A chỉ đạt khoảng 13–16 render/s ở fixture chạy nền này, không phải vòng render đạt hàng trăm fps. Không so sánh GPU flags/SwiftShader trong phép đo này.

Đề xuất chỉ thêm hướng dẫn có điều kiện: cảnh chụp ảnh tĩnh có thể cung cấp chế độ render một khung rồi dừng animation để giữ khung xác định; cần chờ assets/shader và xác nhận frame trước capture. Đây là lựa chọn chức năng, chưa chứng minh ưu thế CPU ở tổng cửa sổ 15s trên máy này. Nếu cần luật tiết kiệm CPU định lượng, brain giao phép đo mới tách startup khỏi steady state và kiểm soát tải nền; không tự đổi protocol ở lượt này.

Social listening bổ sung, truy cập ngày 13/11/2026: [r/threejs: WebGL context loss](https://www.reddit.com/r/threejs/comments/1jifaf2/webgl_context_loss_for_mobile_works_in_firefox/) có báo cáo vòng render liên tục và kinh nghiệm giảm tần suất trên mobile; [r/webdev: CPU/GPU của website](https://www.reddit.com/r/webdev/comments/1wyp7zs/have_modern_websites_become_bad_in_performance_my/) thảo luận chi phí animation liên tục và khác biệt lớn giữa thiết bị. Đây là kinh nghiệm cộng đồng, không xác nhận ngưỡng 10fps hay kết quả headless M1. Tham khảo kỹ thuật bổ sung: [three.js render on demand](https://github.com/mrdoob/three.js/blob/dev/manual/pages/rendering-on-demand.html).

Kiểm chứng cuối: `hh-heat reap --dry-run` exit 0, không in đề xuất; `hh-heat status` exit 0, state=ok, headless=2, orphans=0. Kiểm tra ps theo exact prefix `--user-data-dir=/tmp/hh-cpu-T0dqn79o/` không còn Chrome benchmark; hai headless còn lại nằm ngoài phạm vi, giữ nguyên. Runner/server đã dừng. Artifacts công khai ở `/tmp/hh-cpu-T0dqn79o/` (fixture, bench.py, results.json chứa raw/renderer/FPS). Không thêm test hay code sản phẩm (0 dòng test / 0 dòng code sản phẩm); không commit, không đổi plugin/runtime.
