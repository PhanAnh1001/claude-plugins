# GPT 6.2: thêm khả năng chọn, giữ nguyên default

## Tóm tắt

Core 0.67.2 nhận `gpt-6.2-sol` và `gpt-6.2-astra` khi người dùng chọn tường minh. Không thay profile, luật brain/hand, preset, account hoặc effort mặc định. Brain/code tiếp tục Sol6.1 high/low, collect tiếp tục Terra6.1 low theo bảng hiện hành.

## Thay đổi

- `MODEL_CAPABILITIES.codex` thêm hai model; không mở wildcard cho model lạ.
- Registry giá canonical thêm giá API chuẩn theo [OpenAI release](https://openai.com/index/introducing-gpt-6-2-astra-sol/) (đọc18/11/2026; không hiện ngày bài): Sol giữ giá6.1 Sol; Astra $8 input, $0.40 cached input, $40 output cho một triệu token. Giá API không đại diện chi phí hoặc quota subscription.
- Không sửa `profiles.py`, bảng preset trong `models_options.py`, các default backend hay cấu hình repo/global.
- Profile override / `models set` chỉ nhận model mới khi có yêu cầu chọn rõ. Adapter Codex nhận metadata nguyên vẹn từ core, không cần bảng model riêng.

## Kiểm chứng

`test_gpt62_compat.py` trước thay đổi:13 fail vì capability/price thiếu,2 pass cho default cũ và model lạ bị từ chối. Sau bổ sung capability/giá, các test mới đạt. Bộ kiểm hẹp gồm profile/model CLI/side-session, fixture Codex run và role pick; kết quả cuối:41 test đạt và12 subtest đạt, không chạy full suite.

Regression giữ nguyên: brain Sol6.1 high; code Sol6.1 low; collect B1/B2 Terra6.1 low; chrome Sonnet5.5 low/medium. Các preset cũ không tự chọn6.2. Có test truyền tường minh hai model xuống argv/ledger bằng backend giả, cấu hình không bị ghi lại. Không gọi model/API thật trong đợt sửa này.

## Social listening

Kế thừa nghiên cứu dự án3D đọc18/11/2026: [Low effort isn’t necessarily cheaper](https://www.reddit.com/r/codex/comments/1wefmx7/low_effort_isnt_necessarily_cheaper/) (trang ghi khoảng2 tháng trước, không rõ ngày) kể hiệu quả effort tùy task; đây là ý kiến cá nhân trên model cũ. Không dùng nó làm căn cứ tự nâng default. User chốt chỉ thêm khả năng chạy model mới, mọi luật chọn model cũ giữ nguyên.

## Phạm vi phát hành

Thay đổi runtime chỉ ở core; repo Codex adapter bổ sung kiểm thử metadata/agent/guard và tài liệu tương thích. Việc code/test đạt không chứng nhận native invocation, cài đặt hoặc hot reload; không đổi phiên đang chạy. Bảng giá chỉ là nguồn tính API estimate hiện có, không suy quota từ token/USD.
