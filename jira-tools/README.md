# jira-tools

Marketplace Claude Code tự host (`jira-tools-local`) chứa plugin **jira-tools**: CLI Jira Server
(REST v2, xác thực PAT Bearer) dùng chung cho nhiều dự án trên cùng một host. Chỉ dùng thư viện
chuẩn Python, chạy bằng mọi `python3` ≥ 3.9.

## Bố cục

```
.claude-plugin/marketplace.json
plugins/jira-tools/
  .claude-plugin/plugin.json
  bin/jira-cli                 điểm vào CLI
  lib/jira_tools/              mã nguồn
  config/jira.example.json     mẫu hư cấu; bản thật config/jira.json bị gitignore
  config/secrets.example.json  mẫu PAT; bản thật config/secrets.json bị gitignore
  certs/                       CA bundle (*.pem bị gitignore)
  scripts/build-ca-bundle.sh   dựng lại CA bundle
  scripts/session-start.sh     SessionStart hook
  hooks/hooks.json
  skills/jira/SKILL.md         hướng dẫn dùng cho Claude
tests/                         pytest
```

## Cài đặt

```sh
claude plugin marketplace add <đường-dẫn-repo>/jira-tools
claude plugin install jira-tools@jira-tools-local
```

Với marketplace kiểu thư mục, `claude plugin list` báo plugin được đọc thẳng từ thư mục
`plugins/jira-tools` của repo này: sửa `config/jira.json` ở repo có hiệu lực từ phiên kế tiếp
(hoặc `/reload-plugins`), không cần cài lại. Lúc cài, Claude Code vẫn chép một bản vào
`~/.claude/plugins/cache/jira-tools-local/jira-tools/<version>`.

## Cấu hình

- `config/jira.json` (bị gitignore, vì chứa host, mã dự án, tên repo và id customfield của tổ
  chức): `profiles` (host), `default_profile`, `projects` (mỗi dự án có `profile`, `repos`,
  `create_defaults`, `fields`). Tạo từ mẫu hư cấu rồi sửa giá trị:

  ```sh
  cp plugins/jira-tools/config/jira.example.json plugins/jira-tools/config/jira.json
  ```

  Thiếu file này thì CLI thoát 2 kèm hướng dẫn trên; SessionStart hook chỉ in một dòng nhắc,
  không chặn phiên. Muốn để config ngoài plugin: đặt `JIRA_TOOLS_CONFIG_DIR` trỏ tới thư mục chứa
  `jira.json` (và `secrets.json` nếu dùng). Chi tiết và thứ tự ưu tiên env: `skills/jira/SKILL.md`.
- PAT: `JIRA_PAT` > `config/secrets.json` > macOS Keychain (`keychain_service` của profile).
- CA: nếu host Jira chỉ gửi leaf cert (thiếu CA trung gian), dựng bundle riêng bằng
  `plugins/jira-tools/scripts/build-ca-bundle.sh [URL_CA_TRUNG_GIAN]` (hoặc biến
  `JIRA_CA_INTERMEDIATE_URL`; mặc định GlobalSign AlphaSSL CA 2025). Script lấy certifi qua
  `python3 -m certifi`, `uv` hoặc `pip --user`. Không bao giờ tắt verify.

## File bị gitignore

`config/jira.json`, `config/secrets.json` và `certs/*.pem` không vào Git, nhưng **vẫn được
chép** vào bản cache khi cài từ marketplace kiểu thư mục (đã kiểm: bước cài không áp
`.gitignore`). Một máy mới clone repo sẽ không có các file này: tạo `config/jira.json` từ mẫu,
chạy `scripts/build-ca-bundle.sh` nếu cần và lưu PAT vào Keychain trước khi dùng; sau đó tăng
`version` và `claude plugin update` để bản cache nhận file.

## Kiểm thử

```sh
uvx pytest -q tests
uvx ruff check .
```
