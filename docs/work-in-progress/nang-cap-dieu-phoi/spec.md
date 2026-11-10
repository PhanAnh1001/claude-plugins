# Spec: nâng cấp điều phối và switch hybrid-hands + Paseo

## Tóm tắt

- **Mục đích:** giảm chọn nhầm backend lỗi/hết quota, thống nhất khai báo backend và giữ switch tài khoản có duyệt.
- **Quyết định chính:** người dùng đã chốt hướng 3 đợt; ưu tiên **THẤP**, làm sau `dong-bo-tai-khoan`. Đây là tài liệu L2, **chờ duyệt**, ngày **10/11/2026**; hướng đã chốt không đồng nghĩa chi tiết thiết kế được duyệt.
- **Phạm vi:** đợt 1 sửa phân loại auth, circuit breaker, guard mọi account, doctor; đợt 2 registry và bàn giao brain; đợt 3 provider Paseo cùng nguồn config, đánh giá browser guard.
- **Ngoài phạm vi:** code/runtime trong lượt tài liệu này; đồng bộ tài khoản; proxy takeover `base_url`, import deep link, chuyển token vào default slot, provider API-key, hot switch giữa phiên.
- **Số chính:** 3 đợt, 12 task trong [plan](plan.md); test tối thiểu tối đa 3 ca quan trọng/đợt, riêng chống tấn công từ ngoài kiểm kỹ nếu phát sinh.
- **Người đọc phải làm:** phiên sau duyệt spec/plan và các câu hỏi mở, xác nhận phụ thuộc xong rồi mới giao triển khai. Chưa chạy lệnh switch hay đổi config.

## 1. Nguồn và thứ tự triển khai

Không có nguồn internet, nguồn nội bộ: [nghiên cứu mục 4](../../research/2026-11-10-switch-model-provider-account/report.md), các note [thư mục](../../research/2026-11-10-switch-model-provider-account/notes/thu-muc-chung-vs-tach.md), [cc-switch](../../research/2026-11-10-switch-model-provider-account/notes/cc-switch.md), [OpenMausBot](../../research/2026-11-10-switch-model-provider-account/notes/openmausbot-switch.md), [hybrid-hands + Paseo](../../research/2026-11-10-switch-model-provider-account/notes/hybrid-hands-paseo-switch.md), [nghiên cứu bảo mật](../../research/2026-11-10-openmausbot-bao-mat/report.md) và [luật repo](../../../AGENTS.md).

Phụ thuộc tách riêng: [spec đồng bộ tài khoản](../dong-bo-tai-khoan/spec.md) (làm trước); không đưa sync/overlay/settings vào phạm vi này. Các thiết kế dưới là **suy luận/đề xuất**, chưa phải hành vi runtime đã kiểm chứng.

## 2. Thiết kế chung

Giữ cấu hình 4 tầng: mặc định plugin → global → repo → CLI; dict merge sâu, list/scalar thay nguyên, hiển thị provenance. Không sửa credential/settings/sổ cài đặt thủ công. Backend/account là khoá canonical; alias cũ vẫn được chuẩn hoá trước xét guard và cooldown. Không trộn usage giữa tài khoản, không suy quota từ token/USD~. Giá chỉ tham chiếu [model-prices.json](../../../hybrid-hands/plugins/hybrid-hands/config/model-prices.json), model lạ giữ unknown.

Luồng chọn: nạp/kiểm schema → canonical backend/account → guard nguồn quota → cooldown → capability/model/effort → admission pool hiện có → chạy → phân loại bằng tín hiệu CLI đáng tin → cập nhật state. `pick` chỉ đọc và trả lý do bỏ qua; `auto` giữ order. Backend explicit vẫn chịu guard/cooldown, không tự chuyển account. Exit 7 khi hết backend; exit 8 chờ slot, không đổi backend. Không đổi slots, parallel-subagents hoặc cấu hình model chưa được người dùng chốt.

## 3. Đợt 1 — chọn backend an toàn hơn

### 3.1 Sửa lỗi phân loại auth trước

Dữ kiện do brief cung cấp, không có nguồn internet, nguồn nội bộ: run `output/llm/hand-ext/20261110-162114-408406-switch-thu-muc-claude-v1/` đã ghi file nhưng wrapper báo `not_logged_in`, exit 7. **Giả thuyết, chưa xác nhận:** chuỗi “Not logged in” trong report bị coi là lỗi CLI. Không đọc transcript để tái hiện; tạo fixture công khai report có chuỗi đó + CLI exit 0 → `completed`.

Phân loại phải phân biệt text kết quả của hand với stderr, exit code và sự kiện lỗi có cấu trúc của CLI. Không dùng regex trên toàn report để quyết định auth/quota/circuit breaker; exit 0 không tự xoá lỗi auth có cấu trúc hợp lệ. Không đổi lỗi thật thành thành công chỉ vì có file đầu ra.

### 3.2 Circuit breaker theo backend

Mở rộng [quota_state.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/quota_state.py) bằng trường có default tương thích: số lỗi hạ tầng liên tiếp, loại lỗi, lần lỗi cuối và `cooldown_until`. Giữ riêng trạng thái quota/auth hiện có. Chỉ TIMEOUT/FAILED có bằng chứng CLI về 5xx/429/mạng mới cộng lỗi; lỗi code/test/brief và cancel không được retry hay kích breaker. TIMEOUT không đủ bằng chứng giữ lỗi thường.

Đề xuất cần duyệt: 3 lỗi liên tiếp trong 10 phút → cooldown 5 phút, tối đa 15 phút nếu tái diễn; dùng hằng cấu hình có giới hạn, không magic number. Hết hạn cho phép một lần thăm dò trong lượt run thực, không chạy nền; khoá atomic để tránh nhiều probe đồng thời. Thành công xoá chuỗi lỗi, lỗi hạ tầng tiếp tục cooldown; process chết phải hết lease có hạn. `pick/auto` báo loại lỗi và hạn cooldown, không in stderr thô. Tôn trọng retry có hạn của dsh, chỉ tính outcome cuối, không nhân retry giữa hai tầng. Không tự chạy lại brief có thể đã ghi file; trạng thái hoàn tất mơ hồ phải reconcile trước fallback.

Tham khảo cần đọc tĩnh thêm: [cc-switch circuit_breaker.rs](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/proxy/circuit_breaker.rs) (11/2026). Nghiên cứu cũ chưa đọc chi tiết file này; không coi ngưỡng trên là ngưỡng của cc-switch.

### 3.3 Guard quota mọi account

Mỗi `claude_accounts.vN` và codex có `max_5h_pct`, `max_week_pct`, `max_day_pct`. Giữ guard v1 5%/ngày hiện có; ngưỡng mới của account khác cần duyệt, không tự áp 5% cho tất cả. Ngưỡng bật: đạt hoặc vượt ngưỡng thì chặn; thiếu nguồn, sai account, sample cũ hoặc reset hết hạn thì chặn kèm lý do unknown. Ngưỡng không cấu hình không tự suy là 0 hay 100; schema phân biệt disabled với thiếu dữ liệu của ngưỡng đang bật.

Dùng cache/sample `rate_limits` sẵn có, không thêm API/key. GPT phân loại 5h bằng 300 phút, tuần bằng 10080 phút; legacy account sample giữ contract hiện có. Ngày dùng helper `day_budget.py` nếu đủ nguồn hợp lệ theo account; không có nguồn thì chặn ngưỡng ngày đang bật, không quy đổi token/USD thành quota. Native và terminal dùng cùng admission guard; pick trả native/native_reason nhưng caller vẫn kiểm capability. Nguồn nội bộ, không có nguồn internet: [day_budget.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/day_budget.py), [constants.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py), AGENTS.md.

### 3.4 Doctor nhận diện không đọc token

Chỉ kiểm tồn tại mục Keychain bằng truy vấn metadata, tuyệt đối không `-w/-g` hay lấy password. Nhãn plan lấy từ allowlist `oauthAccount` qua helper an toàn; không dump JSON. Đối chiếu định danh trong bộ nhớ để báo `v1/v2: trùng`, không in/lưu định danh, email, hash định danh hoặc account id. Không đủ metadata tin cậy → `không xác định`, không suy khác account từ hai thư mục khác nhau. Sự tồn tại Keychain không chứng minh login còn hiệu lực.

Quy ước service sha256 thư mục là điểm cần kiểm, nhất là v1 unset `CLAUDE_CONFIG_DIR`; tham khảo [layout.rs](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L10-L11) (11/2026). Nếu metadata không đủ phát hiện trùng mà không đọc secret, giữ unknown và báo người duyệt; không mở rộng quyền đọc credential.

## 4. Đợt 2 — registry và bàn giao brain

Registry khai báo backend id, adapter subscription được phép, mẫu argv dạng mảng (không shell eval), env allowlist, home dir, danh sách model/effort/capability và khoá giá canonical. Schema từ chối API-key/base_url override/auth env, không chỉ che giá trị. Adapter code vẫn chịu trách nhiệm parse CLI/error; config không phải quyền nạp code hoặc command tuỳ ý từ nguồn ngoài. Các backend cũ được biểu diễn thành default tương đương; không tự thêm provider API.

Hook chỉ gợi ý bàn giao và in `side-session start --main --account vN` cho Claude, kèm model/effort được duyệt nếu cần. Người dùng duyệt đích rồi brain mở phiên mới từ bàn giao; không tự đổi account/model/effort, không `/model` giữa phiên, không sửa default login. Học nguyên tắc người dùng trả lời trước đổi engine của [quota-switch.ts](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/quota-switch.ts#L2-L4) (11/2026), không sao chép cơ chế đọc token của OMB.

## 5. Đợt 3 — Paseo và bề mặt trình duyệt

Sinh `hh-hand-*` từ registry hiệu lực chung thay danh sách cứng trong [paseo_provider.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_provider.py). Dry-run mặc định, apply qua công cụ chính thức, chỉ cập nhật provider plugin sở hữu; giữ provider người dùng, so diff và rollback phần sở hữu. Không sửa `~/.paseo` thủ công trong hand; brain thực hiện runtime sau duyệt.

Đọc tĩnh hiện tại: [index.server.ts](../../../hybrid-hands/paseo-hh-tree/index.server.ts) chỉ đăng ký RPC qua PluginServerContext; chưa thấy listener tại entrypoint, **chưa chứng minh toàn bộ transport không nghe cổng**. Đầu pha phải kiểm đường gọi/transport và listener thực bằng brain, chỉ metadata cổng/process, không log thật. Nếu không có listener plugin sở hữu, ghi N/A và ranh giới host Paseo; không thêm HTTP server để có chỗ gắn guard.

Nếu có listener: kiểm Host allowlist, Origin đúng origin được cấu hình (gồm port/scheme), từ chối origin null/khác và Host lạ nhằm chống DNS rebinding; không dùng CORS làm xác thực hay tin proxy header mặc định. Quy tắc request thiếu Origin/non-browser và WebSocket phải duyệt theo transport thực. Đây là bảo mật chống tấn công ngoài: kiểm kỹ nhánh/biên, SAST, dependency scan và DAST staging qua luồng thật trước phát hành, không dùng dữ liệu khách hàng.

## 6. Rủi ro, chấp nhận và câu hỏi mở

Chấp nhận: fixture report chứa “Not logged in” + exit 0 hoàn tất; lỗi code không breaker/retry; cooldown hết hạn phục hồi có giới hạn; guard không bỏ lọt unknown; doctor không lộ định danh; registry/Paseo không drift, switch chỉ qua phiên mới có duyệt. Không claim đã kiểm runtime trong lượt viết tài liệu.

Rủi ro: 429 dễ lẫn quota/hạ tầng; cache nhầm account gây chặn sai; fallback sau timeout tạo writer trùng; registry argv/env mở đường vượt policy; metadata Keychain không đủ chứng minh trùng; guard ở sai tầng RPC không bảo vệ listener host. Mọi lỗi thiếu bằng chứng giữ unknown, không tự hạ guard.

Câu hỏi mở cần duyệt:
1. Có chấp thuận ngưỡng breaker 3 lỗi/10 phút, cooldown 5–15 phút và TTL lease probe cụ thể nào?
2. Ngưỡng 5h/tuần/ngày từng vN và codex, freshness sample và cửa sổ ngày theo helper hiện có là gì? Ngưỡng nào được tắt tường minh?
3. Metadata oauthAccount nào đủ đối chiếu trùng an toàn; nếu không đủ có chấp nhận doctor unknown?
4. Registry cho phép những executable/placeholder nào; hook gợi ý bàn giao tích hợp sự kiện nào mà không gây spam?
5. Listener thuộc plugin hay host Paseo; ai sở hữu bản vá transport và quy tắc thiếu Origin nếu cần?
