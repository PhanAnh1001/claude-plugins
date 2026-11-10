# Spec: đồng bộ tài sản giữa các thư mục tài khoản

## Tóm tắt

- **Mục đích:** giữ credential/state riêng từng tài khoản, giảm lệch chỉ dẫn, skill, agent, hook và plugin bằng overlay tài sản một chiều.
- **Quyết định chính:** người dùng đã chốt hướng tách phần riêng khỏi phần dùng chung; lệnh mặc định dry-run, không ghi đè mục thật, settings theo ownership floor, plugin/MCP qua CLI chính thức.
- **Phạm vi:** thiết kế L2, ưu tiên **CAO**, ngày **10/11/2026**, trạng thái **chờ duyệt**; 5 pha P0–P4 trong [plan](plan.md). Chi tiết quyền ghi vẫn cần duyệt trước triển khai.
- **Ngoài phạm vi:** code/runtime trong lượt này; chuyển login/token, chia sẻ transcript/state, sửa Codex config.toml, đổi model/account giữa phiên, cài OpenMausBot hay cc-switch.
- **Người đọc phải làm:** phiên sau duyệt spec/plan, chốt câu hỏi mục 7 và ngoại lệ luật mục 6, rồi mới chia việc triển khai. Tài liệu này không cấp quyền apply.

## 1. Cơ sở và trạng thái hiện tại

Nguồn thiết kế: [báo cáo switch](../../research/2026-11-10-switch-model-provider-account/report.md), [thư mục chung và tách](../../research/2026-11-10-switch-model-provider-account/notes/thu-muc-chung-vs-tach.md), [cc-switch](../../research/2026-11-10-switch-model-provider-account/notes/cc-switch.md), [OpenMausBot](../../research/2026-11-10-switch-model-provider-account/notes/openmausbot-switch.md), [hybrid-hands/Paseo](../../research/2026-11-10-switch-model-provider-account/notes/hybrid-hands-paseo-switch.md), [nghiên cứu bảo mật](../../research/2026-11-10-openmausbot-bao-mat/report.md).

Không có nguồn internet, nguồn nội bộ: [AGENTS.md](../../../AGENTS.md), [README](../../../hybrid-hands/README.md) và các nghiên cứu trên; quan sát tên mục do brain cung cấp ngày 10/11/2026, không đọc lại home tài khoản trong lượt viết spec:

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
- Nguồn mặc định: Claude v1 `~/.claude`; Codex `~/.codex`. Đích Claude lấy từ `claude_accounts` hiệu lực, trừ nguồn; Codex là `~/.codex-hand`. Không suy account mới bằng quét thư mục.
- Kết quả từng mục: `in_sync`, `missing`, `would_create`, `would_update`, `conflict`, `blocked`, `error`, `applied`; status dùng missing/drift thay cho hành động. JSON có schema_version, provider, alias tài khoản, loại tài sản, đường dẫn tài sản, action, reason, tên khoá; không có giá trị settings/env, account id đăng nhập hay payload MCP.
- Mã thoát đề xuất: 0 kiểm tra/apply hoàn tất không có conflict, 1 còn lệch ở status/dry-run hoặc conflict ở apply, 2 cấu hình/CLI/I/O lỗi. Không nuốt lỗi; apply có thể thành công từng mục, báo rõ phần còn lại, không tự retry khi kết quả CLI mơ hồ.
- Không xoá tài sản đích khi nguồn bị xoá. Apply lần hai với cùng nguồn không ghi lại file, backup hay cài lại plugin đã khớp.

### 2.2 Cấu hình 4 tầng

Đề xuất khoá `account_sync` gồm `sources`, `targets`, `items`, `exclude`, `settings.shared_keys`, `plugins`, `mcp`. Mỗi item khai provider, đường dẫn tương đối trong home, kiểu import/symlink/settings/official_cli. Cấu hình chỉ chứa tên/đường dẫn và chính sách, không chứa secret.

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
| Codex AGENTS.md | Symlink file sang nguồn | Mục thật hoặc link khác: conflict |
| Codex rules/, agents/, skills người dùng | Symlink từng mục con; bỏ qua `.system` ở cả nguồn/đích | Không ghi đè mục thật; không chạm `.system` |

Nguồn thiếu thì blocked, không tạo link đứt. Chỉ tài sản được brain xác nhận không chứa secret mới đưa vào manifest; symlink cho phép mọi account sửa cùng nội dung nguồn, cần cảnh báo trong dry-run. Không tự sửa hook hoặc đường dẫn trong script. Hook dùng home tuyệt đối v1 hoặc ghi theo CLAUDE_CONFIG_DIR phải được kiểm tra trước khi cho vào allowlist.

## 4. Reconcile phần có trạng thái cấu hình

### 4.1 Settings ownership floor

Chỉ áp dụng settings.json của Claude. Danh sách ứng viên dùng chung: `statusLine`, `hooks`; `enabledPlugins`, `extraKnownMarketplaces` phải phối hợp P3, không bật plugin chưa cài. `permissions` là câu hỏi mở, mặc định không đồng bộ. Allowlist cuối cùng phải được duyệt; trước đó P2 bị chặn.

- Giữ nguyên `env` toàn bộ (kể cả ANTHROPIC_*), `model`, `apiKeyHelper`, `effortLevel`, `modelSettings`, các khoá định tuyến/xác thực và mọi khoá không được duyệt. Manifest không được vượt denylist này.
- Với khoá được sở hữu, chép giá trị từ nguồn; không merge list mù. Khoá nguồn thiếu giữ đích và báo lệch, không tự xoá. Chỉ diff tên khoá/action, không in giá trị ngay cả ở JSON, lỗi parser hoặc subprocess stderr.
- Settings JSON lỗi hoặc settings đích là symlink: blocked, không ghi. Đọc và sửa có chọn lọc trong runtime tin cậy; không giao file thật chứa secret cho hand ngoài.
- Trước lần ghi đầu: backup nguyên file đích tại `~/.hybrid-hands/backups/<sha256 đường dẫn tuyệt đối>/`; thư mục 0700, backup 0600, tạo độc quyền, không ghi đè backup gốc. Backup có thể chứa secret: không in/đọc bằng hand, không đưa vào repo. File mới có marker trạng thái trước là absent, không giả backup rỗng.
- Ghi file tạm cùng thư mục, fsync rồi atomic replace; giữ mode file đích (file mới 0600). Khoá theo đích và kiểm fingerprint ngay trước replace; file thay đổi từ lúc lập kế hoạch → conflict. Lỗi backup thì không ghi settings. Không log nội dung.
- Khôi phục là thao tác riêng do brain duyệt, không tự rollback cả batch hoặc ghi đè thay đổi mới của người dùng. Report chỉ ghi đường dẫn backup và tên khoá đã đổi.

### 4.2 Plugin và MCP

- Plugin: không symlink plugins/; lấy danh sách plugin bật và marketplace qua metadata/CLI an toàn, không đọc credential. Chỉ xử lý marketplace đã được duyệt, nguồn URL có credential bị chặn và không in. Chạy `claude plugin marketplace add` rồi `claude plugin install` cho plugin nguồn bật mà đích thiếu, với CLAUDE_CONFIG_DIR của đích; v1 giữ cách unset biến tương thích launcher hiện có.
- Phải xác minh scope user/project/local trước P3; không suy scope từ enabledPlugins. Không tự bật plugin ở repo trước đó chưa dùng. Khác version hoặc plugin bị tắt ở đích báo drift/conflict, không tự nâng/hạ/bật lại. Lỗi một CLI được báo theo mục, không sửa sổ để chữa.
- MCP: mặc định chỉ báo tên server lệch; không đọc/in env hay giá trị từ `.claude.json`. Đồng bộ chỉ khi người dùng duyệt server cụ thể qua `claude mcp add-json`, dữ liệu do brain/runtime tin cậy cung cấp; không hiện JSON/argv chứa secret trong log. Nếu CLI không hỗ trợ truyền payload an toàn thì chặn, không gọi bằng argv lộ secret. CLI chính thức tự cập nhật state; sync không parse/sửa `.claude.json` thủ công.
- Dự phòng cần duyệt riêng: launcher chèn `--plugin-dir`, `--settings`, `--mcp-config` theo phiên; chỉ có hiệu lực với phiên do launcher mở, không âm thầm thay cho cài đặt thất bại. Không dùng dự phòng để vượt duyệt MCP.

Tài liệu Claude được nghiên cứu trước trích dẫn: [CLI](https://code.claude.com/docs/en/cli-reference), [MCP](https://code.claude.com/docs/en/mcp), [model/effort](https://code.claude.com/docs/en/model-config) (11/2026). Scope install còn chưa xác minh. Launcher tiếp tục truyền `--model`/`--effort` theo phiên; `CLAUDE_CODE_EFFORT_LEVEL` có ưu tiên cao hơn, cần xử lý theo chính sách launcher đã duyệt, không sao chép effort qua settings.

## 5. Chấp nhận và rủi ro

- Dry-run/status không đổi bất kỳ file nào; output chỉ metadata đã lọc. Apply lần hai không đổi kết quả trên fixtures giả.
- Conflict mục thật không bị ghi đè; mọi mục giữ riêng còn nguyên byte/mode/link; Codex .system và config.toml không đổi.
- Lỗi giữa batch giữ các mục thành công, trả trạng thái từng mục; không tuyên bố toàn bộ đồng bộ. Thay đổi nguồn sau khi tạo symlink có hiệu lực ngay: đây là rủi ro chia sẻ chủ động, không phải snapshot.
- Suy luận: symlink/path race có thể vượt ranh giới ghi; cần kiểm tra lại đường dẫn lúc apply, khoá và từ chối bất định. Phạm vi hiện tại là công cụ local, không thêm dịch vụ mạng hoặc cơ chế nhận manifest từ xa.
- Plugin mới/hook mới có thể chạy mã: danh sách nguồn tin cậy phải được duyệt, không tự tải hay cài trong bước status. Không dùng tài khoản thật hoặc API trả phí cho test.

## 6. Thay đổi luật cần người dùng duyệt

Không có nguồn internet, nguồn nội bộ: [AGENTS.md](../../../AGENTS.md). Đề xuất bổ sung, chưa có hiệu lực:

> Sau khi người dùng duyệt manifest và ownership floor cụ thể, cho phép `hand-ext accounts sync --apply` tạo overlay và reconcile đúng khoá settings đã duyệt bằng backup + atomic write; tuyệt đối không sửa credential, state hay sổ cài đặt thủ công. Plugin/MCP chỉ qua CLI chính thức với phạm vi đã duyệt. Luật cập nhật plugin áp dụng cho mọi thư mục tài khoản đang dùng plugin ở repo hiện tại và các repo khác; không tự bật nơi chưa dùng. Phải kiểm version và đường dẫn nạp thực tế theo từng repo/account, báo cần reload nếu phiên đang mở chưa nhận bản mới.

## 7. Câu hỏi mở trước triển khai

1. Nguồn Claude luôn v1 hay cho cấu hình nguồn khác? Đề xuất mặc định v1, override chỉ khi người dùng chốt nguồn và không tạo chu trình.
2. Chốt allowlist settings: statusLine/hooks; enabledPlugins/extraKnownMarketplaces thuộc bước CLI nào; có chia sẻ permissions không? Đề xuất permissions giữ riêng.
3. Hooks chung có an toàn khi ghi theo CLAUDE_CONFIG_DIR hoặc đường dẫn v1 tuyệt đối? Ai xác nhận từng hook đủ điều kiện?
4. Xác minh chính thức Codex: CODEX_HOME, AGENTS.md toàn cục, rules/, agents/, skills và hành vi symlink. [Config reference](https://developers.openai.com/codex/config-reference) là điểm cần kiểm, chưa phải bằng chứng đã xác minh (11/2026). P1 Codex chỉ bật sau khi xác minh.
5. Xác minh scope `claude plugin install`, cơ chế liệt kê metadata không lộ secret và cách truyền payload `claude mcp add-json` an toàn; chốt duyệt MCP riêng từng server.
6. Duyệt câu bổ sung AGENTS.md mục 6; chi tiết chưa duyệt thì chỉ triển khai P0 theo brief chỉ đọc riêng.
