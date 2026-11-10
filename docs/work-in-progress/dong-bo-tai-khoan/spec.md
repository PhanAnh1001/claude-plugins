# Spec: đồng bộ tài sản giữa các thư mục tài khoản

## Tóm tắt

- **Mục đích:** giữ credential/state riêng từng tài khoản, giảm lệch chỉ dẫn, skill, agent, hook và plugin bằng overlay tài sản một chiều.
- **Quyết định chính:** người dùng đã chốt hướng tách phần riêng khỏi phần dùng chung; lệnh mặc định dry-run, không ghi đè mục thật, settings theo ownership floor, plugin/MCP qua CLI chính thức.
- **Phạm vi:** thiết kế L2, ưu tiên **CAO**, ngày **10/11/2026**, trạng thái **đã duyệt hướng triển khai 10/11/2026**; 5 pha P0–P4 trong [plan](plan.md). Manifest và ownership floor cụ thể vẫn cần duyệt trước apply thật.
- **Ngoài phạm vi:** runtime/apply home thật trong lượt P4.1 (chỉ sửa QA hẹp P0 theo brief); chuyển login/token, chia sẻ transcript/state, sửa Codex config.toml, đổi model/account giữa phiên, cài OpenMausBot hay cc-switch.
- **Người đọc phải làm:** theo quyết định mục 6/7 và duyệt manifest cụ thể trước apply. Tài liệu này không cấp quyền apply.

## 1. Cơ sở và trạng thái hiện tại

Nguồn thiết kế: [báo cáo switch](../../research/2026-11-10-switch-model-provider-account/report.md), [thư mục chung và tách](../../research/2026-11-10-switch-model-provider-account/notes/thu-muc-chung-vs-tach.md), [cc-switch](../../research/2026-11-10-switch-model-provider-account/notes/cc-switch.md), [OpenMausBot](../../research/2026-11-10-switch-model-provider-account/notes/openmausbot-switch.md), [hybrid-hands/Paseo](../../research/2026-11-10-switch-model-provider-account/notes/hybrid-hands-paseo-switch.md), [nghiên cứu bảo mật](../../research/2026-11-10-openmausbot-bao-mat/report.md).

Nguồn nội bộ: [AGENTS.md](../../../AGENTS.md), [README](../../../hybrid-hands/README.md) và các nghiên cứu trên; quan sát tên mục do brain cung cấp ngày 10/11/2026, không đọc lại home tài khoản trong lượt viết spec:

- Claude v2 thiếu CLAUDE.md, agents/, hooks/; skills/paseo đã có symlink sang v1; sổ plugin riêng.
- Codex hand thiếu AGENTS.md, agents/, rules/, hooks.json. Việc thiếu hooks.json không có nghĩa được phép tự sao chép nó.
- Suy luận: overlay cần quản lý từng tài sản; chia sẻ nguyên home hoặc nguyên plugins/ sẽ phá ranh giới state.

Tham khảo ngoài dự án: cc-switch có @import và mirror tài sản tại [shared.rs](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/shared.rs#L1-L12) (11/2026); OpenMausBot chia sẻ nhiều thư mục Codex tại [codex-shared-home.ts](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex-shared-home.ts#L1-L11) (11/2026). Đây là nguồn của nghiên cứu đã có, không phải xác minh mới; suy luận: chỉ học cơ chế, không sao chép danh sách state dùng chung.

## 2. Contract lệnh và manifest

### 2.1 Giao diện

```text
hand-ext accounts status [--account vN|--all] [--json]
hand-ext accounts sync [--account vN|--all] [--apply] [--json]
```

- `status` chỉ đọc; `sync` không có `--apply` chỉ lập kế hoạch, không tạo home, backup, lock file hay gọi CLI có tác dụng ghi.
- `--account vN` chỉ một Claude account đã khai báo; `--all` gồm các Claude đích và Codex hand. Không truyền selector tương đương `--all`; hai selector loại trừ nhau. Nguồn chuẩn không là đích.
- Nguồn mặc định: Claude v1 `~/.claude`; Codex `~/.codex`. Đích Claude lấy từ `claude_accounts` hiệu lực, trừ nguồn; Codex hand chỉ xuất các mục blocked, chưa tạo overlay. Không suy account mới bằng quét thư mục.
- Kết quả từng mục: `in_sync`, `missing`, `would_create`, `would_update`, `conflict`, `blocked`, `error`, `applied`; status dùng missing/drift thay cho hành động. JSON có schema_version, provider, alias tài khoản, loại tài sản, đường dẫn tài sản, action, reason, tên khoá; không có giá trị settings/env, account id đăng nhập hay payload MCP.
- Mã thoát hiện tại: 0 khi mọi mục in_sync/applied; 1 khi còn missing/drift/would_create/would_update/conflict/blocked; 2 khi có error hoặc lỗi cấu hình/selector/I/O. Không nuốt lỗi; apply có thể thành công từng mục, báo rõ phần còn lại, không tự retry khi kết quả CLI mơ hồ.
- Không xoá tài sản đích khi nguồn bị xoá. Apply lần hai với cùng nguồn không ghi lại file, backup hay cài lại plugin đã khớp.

### 2.2 Cấu hình 4 tầng

Khoá `account_sync` (alias tương thích của `ext_hand.account_sync`) gồm `sources`, `items`, `exclude`, `settings`, `plugins`, `mcp` và `source_override_approved`. Mỗi item khai provider, đường dẫn tương đối trong home và `type: import|symlink` (mặc định `symlink`); settings và plugin/MCP được khai ở section riêng, không phải item type. `settings` gồm `shared_keys`, `approved_keys`, `ownership`. `targets` chưa hỗ trợ: giá trị không rỗng bị từ chối (`targets_not_supported`); đích lấy từ tài khoản hiệu lực và selector. Override manifest tầng CLI hiện chỉ là tham số nội bộ `manifest_from(..., overrides=...)`, chưa có cờ CLI công khai để truyền manifest override. Cấu hình chỉ chứa tên/đường dẫn và chính sách, không chứa secret.

Không có nguồn internet, nguồn nội bộ: [config.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/config.py), [constants.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py). Giữ thứ tự mặc định plugin → global `~/.hybrid-hands/config.json` (hoặc HYBRID_HANDS_CONFIG) → repo → CLI; dict merge sâu, list/scalar thay nguyên; hiển thị provenance đã lọc. Global lỗi phải báo đường dẫn, không âm thầm dùng mặc định.

Danh sách cấm mục 3.1 là hàng rào code, không thể mở lại bằng manifest hoặc cờ CLI. Exclude của người dùng chỉ thu hẹp thêm. Đường dẫn nguồn/đích phải khác nhau, đích không trùng nhau, không tạo vòng symlink; từ chối đường dẫn tương đối thoát home, symlink cha dẫn sang vùng giữ riêng và item không thuộc allowlist. Không chạy script từ manifest.

## 3. Phân loại tài sản

### 3.1 Giữ riêng tuyệt đối

Không đọc nội dung, chép, liên kết, sửa hoặc backup credential/Keychain, `.credentials.json`, `auth.json`, `auth.lock`, `.claude.json` state (kể cả `~/.claude.json` ngoài home), `projects/`/transcript, `history.jsonl`, statusline/rate-limit cache, Codex `sessions/`, `archived_sessions/`, sqlite state, `models_cache`/`models_cache.json`. Không chia sẻ ledger/quota giữa account. Không duyệt đệ quy những cây này để tìm tài sản.

`plugins/` và `installed_plugins.json` không được symlink hoặc sửa thủ công; chỉ CLI chính thức có thể cập nhật sổ cài đặt. `config.toml`, Codex `skills/.system`, hooks.json và các mục chưa phân loại nằm ngoài allowlist. File lạ mặc định blocked.

### 3.2 Dùng chung có chọn lọc

| Provider / tài sản | Hành vi | Xung đột |
|---|---|---|
| Claude CLAUDE.md | Tạo file một dòng `@<đường dẫn tuyệt đối nguồn>/CLAUDE.md` kèm newline khi thiếu | Nội dung khác, symlink khác hoặc loại file khác: conflict, không ghi đè |
| Claude skills/, agents/, commands/, hooks/ script | Tạo thư mục chứa nếu thiếu; symlink từng mục con sang nguồn; không link cả thư mục gốc | Mục thật, symlink sai/đứt: conflict; giữ symlink paseo hiện có nếu đúng nguồn |
| Codex AGENTS.md | Blocked: chưa đủ bằng chứng symlink/discovery | Không apply |
| Codex rules/, agents/, skills người dùng | Blocked riêng từng overlay; xem verification | Không chạm `.system` |

Nguồn thiếu thì blocked, không tạo link đứt. Chỉ tài sản được brain xác nhận không chứa secret mới đưa vào manifest; symlink cho phép mọi account sửa cùng nội dung nguồn, cần cảnh báo trong dry-run. Không tự sửa hook hoặc đường dẫn trong script. Hook dùng home tuyệt đối v1 hoặc ghi theo CLAUDE_CONFIG_DIR phải được kiểm tra trước khi cho vào allowlist.

## 4. Reconcile phần có trạng thái cấu hình

### 4.1 Settings ownership floor

Chỉ áp dụng settings.json của Claude. Allowlist đã duyệt về thiết kế: `statusLine`, `hooks`; `enabledPlugins`, `extraKnownMarketplaces` phải phối hợp P3, không bật plugin chưa cài. `permissions` giữ riêng. Mỗi giá trị command/hook cần ownership approved + verified + sha256 khớp; duyệt tên khoá không đủ.

- Giữ nguyên `env` toàn bộ (kể cả ANTHROPIC_*), `model`, `apiKeyHelper`, `effortLevel`, `modelSettings`, các khoá định tuyến/xác thực và mọi khoá không được duyệt. Manifest không được vượt denylist này.
- Với khoá được sở hữu, chép giá trị từ nguồn; không merge list mù. Khoá nguồn thiếu giữ đích và báo lệch, không tự xoá. Chỉ diff tên khoá/action, không in giá trị ngay cả ở JSON, lỗi parser hoặc subprocess stderr.
- Settings JSON lỗi hoặc settings đích là symlink: blocked, không ghi. Đọc và sửa có chọn lọc trong runtime tin cậy; không giao file thật chứa secret cho hand ngoài.
- Trước lần ghi đầu: backup nguyên file đích tại `~/.hybrid-hands/backups/<sha256 đường dẫn tuyệt đối>/`; thư mục 0700, backup 0600, tạo độc quyền, không ghi đè backup gốc. Backup có thể chứa secret: không in/đọc bằng hand, không đưa vào repo. File mới có marker trạng thái trước là absent, không giả backup rỗng.
- Ghi file tạm cùng thư mục, fsync rồi atomic replace; giữ mode file đích (file mới 0600). Khoá theo đích và kiểm fingerprint ngay trước replace; file thay đổi từ lúc lập kế hoạch → conflict. Lỗi backup thì không ghi settings. Không log nội dung.
- Khôi phục là thao tác riêng do brain duyệt, không tự rollback cả batch hoặc ghi đè thay đổi mới của người dùng. Report chỉ ghi đường dẫn backup và tên khoá đã đổi.

### 4.2 Plugin và MCP

- Plugin: không symlink plugins/; lấy danh sách plugin bật và marketplace qua metadata/CLI an toàn, không đọc credential. Chỉ xử lý marketplace đã được duyệt, nguồn URL có credential bị chặn và không in. Chạy `claude plugin marketplace add` rồi `claude plugin install` cho plugin nguồn bật mà đích thiếu, với CLAUDE_CONFIG_DIR của đích; v1 giữ cách unset biến tương thích launcher hiện có.
- Scope user/project/local đã xác minh tại [verification](verification.md), ngày 2026-11-10; không suy scope từ enabledPlugins. Không tự bật plugin ở repo trước đó chưa dùng. Khác version hoặc plugin bị tắt ở đích báo drift/conflict, không tự nâng/hạ/bật lại. Lỗi một CLI được báo theo mục, không sửa sổ để chữa.
- MCP: mặc định chỉ báo tên server lệch; không đọc/in env hay giá trị từ `.claude.json`. Đồng bộ chỉ khi người dùng duyệt server cụ thể qua `claude mcp add-json`, dữ liệu do brain/runtime tin cậy cung cấp; không hiện JSON/argv chứa secret trong log. Nếu CLI không hỗ trợ truyền payload an toàn thì chặn, không gọi bằng argv lộ secret. CLI chính thức tự cập nhật state; sync không parse/sửa `.claude.json` thủ công.
- Dự phòng cần duyệt riêng: launcher chèn `--plugin-dir`, `--settings`, `--mcp-config` theo phiên; chỉ có hiệu lực với phiên do launcher mở, không âm thầm thay cho cài đặt thất bại. Không dùng dự phòng để vượt duyệt MCP.

Tài liệu Claude được nghiên cứu trước trích dẫn: [CLI](https://code.claude.com/docs/en/cli-reference), [MCP](https://code.claude.com/docs/en/mcp), [model/effort](https://code.claude.com/docs/en/model-config) (11/2026). Scope install và giới hạn metadata đã đối chiếu tại [verification](verification.md). Launcher tiếp tục truyền `--model`/`--effort` theo phiên; `CLAUDE_CODE_EFFORT_LEVEL` có ưu tiên cao hơn, cần xử lý theo chính sách launcher đã duyệt, không sao chép effort qua settings.

## 5. Chấp nhận và rủi ro

- Dry-run/status không đổi bất kỳ file nào; output chỉ metadata đã lọc. Apply lần hai không đổi kết quả trên fixtures giả.
- Conflict mục thật không bị ghi đè; mọi mục giữ riêng còn nguyên byte/mode/link; Codex .system và config.toml không đổi.
- Lỗi giữa batch giữ các mục thành công, trả trạng thái từng mục; không tuyên bố toàn bộ đồng bộ. Thay đổi nguồn sau khi tạo symlink có hiệu lực ngay: đây là rủi ro chia sẻ chủ động, không phải snapshot.
- Suy luận: symlink/path race có thể vượt ranh giới ghi; cần kiểm tra lại đường dẫn lúc apply, khoá và từ chối bất định. Phạm vi hiện tại là công cụ local, không thêm dịch vụ mạng hoặc cơ chế nhận manifest từ xa.
- Plugin mới/hook mới có thể chạy mã: danh sách nguồn tin cậy phải được duyệt, không tự tải hay cài trong bước status. Không dùng tài khoản thật hoặc API trả phí cho test.

## 6. Luật đã duyệt ngày 10/11/2026

Câu bổ sung dưới đây đã được duyệt và thêm nguyên văn vào [AGENTS.md](../../../AGENTS.md). Quyền apply vẫn phụ thuộc manifest và ownership floor cụ thể; không cấp quyền apply home thật cho gói này.

> Sau khi người dùng duyệt manifest và ownership floor cụ thể, cho phép `hand-ext accounts sync --apply` tạo overlay và reconcile đúng khoá settings đã duyệt bằng backup + atomic write; tuyệt đối không sửa credential, state hay sổ cài đặt thủ công. Plugin/MCP chỉ qua CLI chính thức với phạm vi đã duyệt. Luật cập nhật plugin áp dụng cho mọi thư mục tài khoản đang dùng plugin ở repo hiện tại và các repo khác; không tự bật nơi chưa dùng. Phải kiểm version và đường dẫn nạp thực tế theo từng repo/account, báo cần reload nếu phiên đang mở chưa nhận bản mới.

## 7. Quyết định và phần blocked

1. Nguồn Claude mặc định v1; override phải explicit `source_override_approved: true`, được người dùng duyệt và acyclic. Homes trùng/lồng nhau bị từ chối; không tự suy nguồn/đích.
2. Settings chỉ `statusLine`/`hooks`, permissions giữ riêng. `enabledPlugins`/`extraKnownMarketplaces` thuộc CLI P3, không chép raw settings. Approval từng giá trị theo ownership floor và hash, từng asset theo manifest.
3. Từng hook chưa duyệt vẫn blocked. Research 2026-11-10 xác nhận hook có quyền user và CLAUDE_CONFIG_DIR không chứng minh rewrite đường dẫn/đích ghi. Adapter hiện chặn hook script kể cả approved; không tự bật sau khi duyệt tên.
4. Codex overlay blocked riêng AGENTS.md/rules/agents/skills: CODEX_HOME chọn home không chứng minh symlink discovery; skills được tài liệu hóa tại `$HOME/.agents/skills`, không chứng minh overlay custom home trong thiết kế. `hooks.json`, `config.toml`, `.system` ngoài phạm vi. Không có xác nhận hook Codex đủ điều kiện triển khai.
5. Plugin dùng scope user/project/local tường minh, marketplace tin cậy đã duyệt và official CLI; không autoenable/upgrade. MCP chưa server nào approved; dù approved vẫn blocked vì chưa xác minh transport payload an toàn. Không phát minh stdin/file option hay dùng argv chứa secret.
6. Nguồn kết luận nghiên cứu và URL chính thức, ngày 2026-11-10: [verification.md](verification.md). Đây là nghiên cứu tài liệu, không chứng minh binary/runtime đã nạp hay test thật.
7. Thử slot mới: claim normal running chờ 3 phút, tối đa 20 lần/mỗi gói; unresolved/pending không tiến triển 30 phút mới dừng. Quy tắc này ghi ở spec/plan, không thêm vào AGENTS.md.

Không còn chờ duyệt spec tổng. Chưa apply home thật; Sol chỉ chạy status/sync DRY-RUN để người dùng duyệt manifest + ownership floor. Restore, từng hook, từng MCP server và Codex overlay giữ gate riêng.
