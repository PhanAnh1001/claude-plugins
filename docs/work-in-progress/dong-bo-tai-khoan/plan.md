# Plan: đồng bộ tài sản tài khoản

## Tóm tắt

- **Mục đích:** thực hiện [spec](spec.md) qua **5 pha, 10 task**, ưu tiên **CAO**, L2, ngày **10/11/2026**, trạng thái **chờ duyệt**.
- **Kết luận chính:** người dùng đã chốt hướng tách credential/state và overlay tài sản; phiên sau cần duyệt chi tiết trước code/apply. P0 chỉ đọc; P1 → P2 → P3 tuần tự theo phụ thuộc; P4 phát hành sau review.
- **Số chính:** tối đa 3 ca kiểm chứng quan trọng mỗi pha, chỉ fixtures thư mục tạm giả; không full suite. Lượt này không viết code/test hoặc đổi runtime.
- **Người đọc phải làm:** chốt mục 7 của spec và ngoại lệ AGENTS.md; brain giao brief có phạm vi ghi cụ thể cho từng task, review rồi phát hành. Hand không commit/cài runtime.

Không có nguồn internet, nguồn nội bộ: [AGENTS.md](../../../AGENTS.md), [nghiên cứu switch](../../research/2026-11-10-switch-model-provider-account/report.md), [thư mục](../../research/2026-11-10-switch-model-provider-account/notes/thu-muc-chung-vs-tach.md), [bảo mật](../../research/2026-11-10-openmausbot-bao-mat/report.md). Khuôn theo [hh-store spec](../hh-store/spec.md) và [plan](../hh-store/plan.md); không kế thừa quyền song song hay trạng thái hoàn thành của tài liệu mẫu.

## Quy ước thực hiện

Đường dẫn code dưới đây tương đối `hybrid-hands/plugins/hybrid-hands/`, test tương đối gốc repo. Tên module/test mới là dự kiến; brain điều chỉnh sau khi đọc code hiện tại, không mở rộng hành vi. Lệnh Python dưới chạy từ `/Users/anhtp/app/claude-plugins`, là lệnh dự kiến cho phiên triển khai, chưa chạy trong lượt tài liệu này.

Mỗi pha chỉ tối đa 3 ca nêu dưới; ưu tiên tham số hoá, không test getter/text. Dòng test thêm ≤ 1/2 dòng code thêm, tối đa 3 test mỗi thành phần. Đây là tính năng local, không mặc định mở rộng thành kiểm toán chống tấn công bên ngoài; nếu sau này thêm bề mặt nhận dữ liệu ngoài thì brain phải lập brief bảo mật riêng. Mọi fixture không chứa dữ liệu thật, không đọc home thật, subprocess CLI được giả lập. Không chạy model/API trả phí.

## P0 — manifest, status và dry-run chỉ đọc

- [ ] **P0.1 — chốt contract và schema:** file dự kiến `lib/hand_ext/config.py`, `constants.py`, module mới `lib/hand_ext/account_sync_manifest.py`, `hybrid-hands/tests/test_account_sync.py`. Xong khi cấu hình 4 tầng giữ provenance/merge, source/target/allowlist/exclude rõ ràng, denylist không thể bị manifest mở lại; câu hỏi scope/Codex có quyết định hoặc trạng thái blocked. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k manifest`.
- [ ] **P0.2 — planner và CLI:** file dự kiến `lib/hand_ext/cli.py`, module mới `lib/hand_ext/accounts_cmd.py`, `account_sync_plan.py`, test chung trên. Xong khi status/sync mặc định dry-run, selector và mã thoát theo spec, text/JSON chỉ tên/action, không tạo backup/lock/home, không gọi CLI ghi. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k dry_run`.

**Tối đa 3 ca P0:** (1) manifest 4 tầng + denylist trong cùng test tham số; (2) status/dry-run snapshot cây fixture trước/sau giống hệt và không có subprocess ghi; (3) selector lỗi/JSON không chứa sentinel giá trị env. Chưa apply lên home thật.

## P1 — CLAUDE.md và symlink tài sản

Phụ thuộc P0; phần Codex chờ xác minh tài liệu chính thức trong câu hỏi 4 của spec. Không có bằng chứng thì blocked riêng Codex, không nhận xét rằng link tạo được đồng nghĩa CLI nạp được.

- [ ] **P1.1 — overlay Claude:** file dự kiến module mới `lib/hand_ext/account_sync_assets.py`, `accounts_cmd.py`, test chung. Xong khi CLAUDE.md mới chỉ có một dòng import tuyệt đối; skills/agents/commands/hooks symlink từng mục con, giữ link paseo đúng nguồn, mục thật/sai link thành conflict; không sửa script. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k assets`.
- [ ] **P1.2 — overlay Codex và ranh giới:** file dự kiến `account_sync_manifest.py`, `account_sync_assets.py`, test chung. Xong khi AGENTS.md symlink file và rules/agents/skills symlink con theo cơ chế đã xác minh; bỏ qua .system, config.toml, state; kiểm đường dẫn lại lúc ghi, nguồn thiếu blocked; không tự copy hooks.json. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k assets`.

**Tối đa 3 ca P1:** (1) apply Claude/Codex bằng fixture tham số rồi apply lần hai không đổi; (2) mục thật/sai link conflict không ghi đè; (3) cây giữ riêng + .system/config.toml có sentinel không bị đọc hoặc sửa, đường dẫn thoát vùng bị chặn. Gộp assert vào cùng ca, không thêm test cho mỗi tên file.

## P2 — settings ownership floor và backup

Phụ thuộc P1 và duyệt allowlist/ngoại lệ luật. Không áp settings thật trong hand ngoài; kiểm chứng thật nếu cần do brain/runtime tin cậy thực hiện theo quyền đã duyệt.

- [ ] **P2.1 — reconcile chọn khoá:** file dự kiến module mới `lib/hand_ext/account_sync_settings.py`, `account_sync_manifest.py`, test chung. Xong khi chỉ khoá được duyệt thay đổi; env/model/effort/auth/unknown nguyên vẹn; nguồn thiếu không xoá đích; enabledPlugins chưa cài không được bật; output chỉ tên khoá. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k settings`.
- [ ] **P2.2 — ghi an toàn:** file dự kiến `account_sync_settings.py`, `accounts_cmd.py`, test chung. Xong khi backup đầu theo hash đường dẫn, thư mục 0700/backup 0600, atomic replace giữ mode, khoá và fingerprint chặn concurrent edit, symlink/JSON lỗi blocked; backup lỗi thì đích nguyên vẹn; apply lại không ghi thêm. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k settings`.

**Tối đa 3 ca P2:** (1) floor + backup + mode + idempotence; (2) JSON lỗi/symlink/concurrent edit không ghi; (3) lỗi backup/replace giữ file cũ và output không lộ sentinel. Tham số hoá các lỗi trong cùng ca.

## P3 — plugin và MCP qua CLI chính thức

Phụ thuộc P2 và xác minh scope install/cách truyền MCP an toàn. Tài liệu tham chiếu cần kiểm lại: [Claude CLI](https://code.claude.com/docs/en/cli-reference), [MCP](https://code.claude.com/docs/en/mcp) (11/2026); hiện chỉ kế thừa câu hỏi mở từ nghiên cứu, chưa xác minh mới.

- [ ] **P3.1 — reconcile plugin:** file dự kiến module mới `lib/hand_ext/account_sync_official.py`, `accounts_cmd.py`, test chung. Xong khi marketplace add/install chỉ cho nguồn tin cậy đã duyệt và plugin bật ở nguồn nhưng thiếu ở đích, account env đúng (v1 unset tương thích), scope tường minh đã xác minh; khác version/tắt ở đích báo drift, không sửa sổ hoặc symlink plugins/; lỗi/ACK mơ hồ không retry mù. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k official`.
- [ ] **P3.2 — MCP và phương án theo phiên:** file dự kiến `account_sync_official.py`, `accounts_cmd.py`; nếu dự phòng được duyệt thêm `lib/hand_ext/backends/claude.py` và `lib/side_session/` (chỉ launcher xác định sau khảo sát), test chung. Xong khi MCP chỉ báo tên; add-json yêu cầu duyệt server cụ thể, payload không qua argv/log lộ secret; không đọc .claude.json thủ công; dự phòng --plugin-dir/--settings/--mcp-config không tự bật và không sửa model/effort toàn cục. Kiểm chứng: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q -k official`.

**Tối đa 3 ca P3:** (1) plugin thiếu chạy đúng CLI/scope/env rồi lần hai no-op; (2) CLI lỗi trả partial/error không ghi sổ trực tiếp; (3) MCP chưa duyệt không gọi CLI, đã duyệt truyền an toàn với fixture giả và không lộ sentinel. Nếu truyền an toàn chưa có thì đánh dấu blocked, không cài thử trên account thật.

## P4 — tài liệu, review và phát hành

Phụ thuộc P0–P3; bước phát hành do Opus/Sol điều phối theo luật repo. Không chọn version trước khi đối chiếu main lúc phát hành.

- [ ] **P4.1 — hướng dẫn và luật:** file dự kiến `hybrid-hands/README.md`, `AGENTS.md`, `commands/` và `skills/ext-hand/` nếu cần mục lệnh mới, hai tài liệu spec/plan này. Xong khi người dùng duyệt câu bổ sung luật, có dry-run/apply/conflict/backup/khôi phục, phạm vi account/repo, cảnh báo symlink/hook; ghi rõ Codex hooks.json và config.toml ngoài phạm vi. Kiểm chứng: `git diff --check`; dùng `python3 -I` kiểm mọi link nội bộ tương đối trong các Markdown đã sửa tồn tại, không test text tài liệu.
- [ ] **P4.2 — review, version và cập nhật cài đặt:** file dự kiến `.claude-plugin/plugin.json`, `CHANGELOG.md`, `hybrid-hands/README.md` nếu cần release note. Xong khi brain review diff và test hẹp xanh, tăng version thích hợp + changelog; validate plugin bằng CLI chính thức đã xác minh; cập nhật qua công cụ chính thức cho repo hiện tại và mọi repo/account đang dùng plugin, không tự bật repo mới, không sửa sổ/settings thủ công. Xác minh version và đường dẫn plugin thực nạp theo từng cặp repo/account, báo phiên cần reload; brain xử lý commit/push/merge theo AGENTS.md, hand không làm. Kiểm chứng hẹp cuối: `python3 -I -m pytest hybrid-hands/tests/test_account_sync.py -q`; thêm `git diff --check`, kiểm JSON manifest bằng `python3 -I`. Lệnh update/validate cụ thể phải lấy từ CLI chính thức và hướng dẫn cài tại thời điểm phát hành, ghi vào bàn giao; không đoán scope hoặc chạy installer trong lượt tài liệu này.

**Tối đa 3 kiểm tra P4:** (1) test file account_sync cuối đúng một lượt, nếu đỏ chỉ chạy lại test hỏng; (2) diff/JSON/link hợp lệ; (3) brain xác minh bảng repo × account × version × đường dẫn nạp, ghi cần reload khi có. Không full suite, không tuyên bố đã cập nhật khi chưa quan sát runtime.

## Bàn giao cần có

Báo cáo task đã xong/chặn, câu hỏi người dùng còn phải chốt, file chạm, lệnh/kết quả thật và version/path theo repo/account. Không in credential, account id đăng nhập, settings/env hoặc payload MCP; không đưa backup thật vào artifacts. Lượt viết tài liệu hiện tại chỉ hoàn thành khi spec và plan tồn tại, link tương đối được kiểm bằng `python3 -I`; mọi checkbox triển khai tiếp tục để trống.
