---
name: jira
description: Dùng CLI Jira Server (REST v2, PAT Bearer) của plugin jira-tools để xem, tạo, sửa, comment, chuyển trạng thái hay tìm issue Jira; dự án tự chọn theo repo git hiện tại. Dùng khi người dùng nhắc tới Jira, issue key (ví dụ PROJ-123), task, worklog hay trạng thái issue.
---

# CLI Jira (plugin jira-tools)

## Khi nào dùng

Mọi thao tác với Jira Server đã khai trong `config/jira.json`: đọc issue, tạo task, sửa field, comment, chuyển trạng
thái, tìm bằng JQL. Không dùng `curl` kiểu Atlassian Cloud: Jira Server dùng REST **v2**,
`description` là chuỗi text/wiki-markup (không phải ADF), xác thực bằng PAT qua header Bearer.

## Cách gọi

Gọi bằng đường dẫn tuyệt đối mà SessionStart hook đã báo trong ngữ cảnh, tức
`${CLAUDE_PLUGIN_ROOT}/bin/jira-cli`. Chạy được từ mọi thư mục, chỉ cần `python3`.

| Lệnh | Việc |
|---|---|
| `whoami` | tài khoản của PAT |
| `meta [--project K] [--type T]` | issue type + field bắt buộc |
| `create --summary S [--type T] [--description D] [--label L] [--assignee U] [--priority P] [--parent K] [--field K=V]` | tạo issue |
| `update KEY [--summary ...] [--field K=V]` | sửa issue (chỉ gửi field được truyền) |
| `comment KEY --body B` | thêm comment |
| `transitions KEY` | transition đang mở |
| `transition KEY --to TÊN [--comment C]` | chuyển trạng thái (tên transition hoặc trạng thái đích) |
| `worklog KEY --time 1h30m [--started ISO] [--comment C] [--remaining 0m]` | log thời gian; có `--remaining` thì đặt remaining rồi đọc lại |
| `get KEY` | tóm tắt issue, có mô tả |
| `search --jql Q [--limit N]` | tìm issue |

- `--json` in nguyên response; `--dry-run` (create/update/comment/transition/worklog) in method, URL,
  payload rồi thoát 0, không gọi mạng và không cần PAT.
- `--field KEY=VALUE`: giá trị parse được thành JSON thì gửi JSON, không thì gửi chuỗi. Id các
  custom field của từng dự án nằm ở khoá `fields` trong `config/jira.json`.
- Mã thoát: `0` ổn, `1` lỗi từ Jira/mạng, `2` lỗi cấu hình (thiếu PAT, không khớp dự án, tham
  số sai), `3` tên transition không khớp.
- Không bao giờ in PAT ra output.

## Log work khi chuyển Done

Log thời gian **thật**, ghi theo ngày làm việc thật, đặt remaining về 0, rồi mới chuyển trạng thái:

```bash
jira-cli worklog PROJ-123 --time 1h30m --started 2026-09-25T09:00+07:00 \
  --comment 'Sửa, test và nghiệm thu' --remaining 0m
jira-cli transition PROJ-123 --to Done
```

- `--time`/`--remaining` theo định dạng Jira (`w`/`d`/`h`/`m`, ví dụ `30m`, `2h`, `1h30m`); sai
  định dạng thì thoát 2. `--started` bỏ trống thì lấy giờ hiện tại theo timezone máy.
- Có `--remaining`: gửi `adjustEstimate=new&newEstimate=...`, sau đó đọc lại `timetracking`, lệch
  thì thoát 1. Không có `--remaining`: `adjustEstimate=auto`, Jira tự trừ.
- Không gửi worklog qua `update.worklog` của transition, vì transition không có screen sẽ bị Jira
  bỏ qua lặng lẽ.

## Thứ tự ưu tiên

- Dự án: `--project` > `JIRA_PROJECT` > dự án có `repos` chứa tên repo git. Tên thử theo thứ
  tự: basename của `git rev-parse --show-toplevel`, rồi tên repo chính (thư mục cha của
  `--git-common-dir`) — nhờ vậy cwd trong một git worktree vẫn khớp dự án của repo chính.
  Lệnh `create`/`meta` không khớp dự án nào thì thoát 2, không
  tự rơi về dự án khác. Lệnh khác dùng `default_profile` để chọn host.
- Host: `JIRA_BASE_URL` > profile của dự án > `default_profile`.
- PAT: `JIRA_PAT` > `config/secrets.json` (gitignore, dạng như `secrets.example.json`) > macOS
  Keychain theo `keychain_service` của profile.
- CA: `SSL_CERT_FILE` nếu đã đặt, không thì `ca_bundle` của profile nếu file tồn tại.
- Thư mục config: `JIRA_TOOLS_CONFIG_DIR` > `${CLAUDE_PLUGIN_ROOT}/config`.

## Thêm dự án hoặc host mới

Sửa `config/jira.json` (bị gitignore; chưa có thì chép từ mẫu hư cấu `config/jira.example.json`;
đường dẫn tương đối tính theo thư mục plugin):

```json
{
  "profiles": {
    "<tên-host>": {"base_url": "https://jira.example.com", "api_prefix": "/rest/api/2",
                   "keychain_service": "<service>", "ca_bundle": "certs/<file>.pem"}
  },
  "projects": {
    "<KEY>": {"profile": "<tên-host>", "repos": ["<tên-repo-git>"],
              "create_defaults": {}, "fields": {"<tên dễ đọc>": "customfield_..."}}
  }
}
```

`create_defaults` được đặt vào payload create trước các cờ (cờ luôn thắng). Ví dụ dự án mẫu PROJ khai
`{"assignee": null}` để issue mới chưa giao cho ai thay vì rơi về project lead.
Lưu PAT: `security add-generic-password -a "$USER" -s <service> -w '<PAT>' -U`.
