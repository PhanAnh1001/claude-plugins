# statusline

## Tóm tắt

- **Mục đích:** đóng gói thanh trạng thái (status line) 3 dòng, kèm các dòng skill nạp gần nhất của
  main và các subagent, của Claude Code thành plugin để
  máy nào cũng cài và cập nhật được bằng `claude plugin`.
- **Marketplace / plugin:** thư mục `statusline/` là marketplace `statusline-local`, chứa plugin
  `statusline` (bản 0.6.0).
- **Cài trên máy mới (3 bước):** `claude plugin marketplace add <thư-mục-repo>/statusline`,
  `claude plugin install statusline@statusline-local --scope user`, rồi chạy skill
  `statusline:setup` (hoặc `install.sh` của plugin).
- **Cập nhật:** chỉ cần `claude plugin marketplace update` và `claude plugin update`; không phải
  chạy lại setup, vì shim luôn chạy bản plugin đang cài.
- **Yêu cầu:** `jq`, `python3` >= 3.9, `bash`, `git`.

## Các dòng statusline

| Dòng | Nội dung | Ví dụ |
|---|---|---|
| 1 | `user@host`, tên thư mục hiện tại (`~` nếu là thư mục home), nhánh git màu xanh | `anh@mac dev-workflow (main)` |
| 2 | model (mức effort), tổng tokens của phiên, % context đang dùng | `Opus(high) \| tokens:6.5k \| ctx:55%` |
| 3 | rate limit 5 giờ và 7 ngày kèm giờ reset | `5h:12%(reset 09/10 15:53) \| 7d:85%(reset 15/10 10:46)` |
| 4+ | skill nạp gần nhất, mỗi dòng một agent (xem dưới); không có skill thì không có dòng nào | `🔧 dev-workflow:dev-triage (main)` |

- **Màu phần trăm:** xanh dưới 50%, vàng từ 50%, đỏ từ 80%.
- **Tokens** cộng mọi bản ghi `usage` trong transcript nên chỉ tăng, không giảm khi nén context.
- **Dòng skill** in sau dòng rate limit, không có dòng tiêu đề, ví dụ:

  ```text
  🔧 dev-workflow:measurement-evidence (main)
  🔧 dev-workflow:port-between-repos (hand: "Nạp skill để th")
  🔧 summary-first-docs:citing-sources (hand: "Nghiên cứu API")
  ```

  - **Dòng main** `🔧 <skill> (main)` là skill main nạp gần nhất, luôn đứng đầu. Main chưa nạp
    skill nào thì bỏ dòng này. Cả main lẫn subagent đều chưa nạp skill thì không in gì.
  - **Dòng subagent** `🔧 <skill> (<agent>: "<mô tả>")`: mỗi subagent có nạp skill được một dòng.
    Chỉ xét 5 transcript subagent sửa gần nhất (theo mtime) và in tối đa 3 dòng, skill nạp mới
    nhất ở trên.
  - **`<agent>`** là phần sau dấu `:` cuối của `agentType` trong `agent-<id>.meta.json` (ví dụ
    `parallel-subagents:hand` thành `hand`). Thiếu, hoặc file meta thiếu hay hỏng, thì ghi `subagent`.
  - **`<mô tả>`** là 15 ký tự đầu của trường `description` sau khi gộp khoảng trắng, bỏ ký tự
    không in được và đổi `"` thành `'`; không thêm `…`. Không có description thì chỉ in `(<agent>)`,
    ví dụ `(hand)`.
  - **Màu:** tên skill tô tím (magenta) giống tên model ở dòng 2; phần chú thích trong ngoặc,
    `(main)` và `(hand: "…")`, tô mờ (dim) giống `(high)` sau tên model; `🔧` giữ màu mặc định.
    Màu chỉ có khi statusline gọi
    `last-skill.sh --color`; chạy `last-skill.sh` không có cờ này thì ra văn bản trần.
  - **Cách tìm skill:** đọc ngược tối đa 4 MB cuối mỗi transcript, ưu tiên lời gọi tool `Skill`,
    dự phòng bằng thông điệp hook `🔧 Skill: <tên>`. Claude Code ghi lời gọi `Skill` của subagent
    vào transcript riêng `<session_id>/subagents/agent-<id>.jsonl` cạnh transcript chính, nên
    statusline đọc cả các file đó. Thứ tự các dòng subagent theo trường `timestamp`; bản ghi không
    có `timestamp` thì dùng mtime của file.
  - **Fail-open:** không có thư mục `subagents` hoặc đọc lỗi thì chỉ hiện những gì đọc được.
- **Rate limit** chỉ có sau phản hồi API đầu tiên của phiên. Trước đó dòng 3 hiện giá trị lưu ở
  `.statusline-cache.json` trong thư mục cấu hình Claude, có dấu `~` phía trước; chưa có gì thì
  hiện `--`.

## Cài đặt

Thay `<thư-mục-repo>` bằng nơi clone repo `claude-plugins`:

```sh
git clone https://github.com/PhanAnh1001/claude-plugins.git <thư-mục-repo>
claude plugin marketplace add <thư-mục-repo>/statusline
claude plugin install statusline@statusline-local --scope user
```

Sau đó, trong Claude Code, gọi skill `statusline:setup`. Hoặc chạy tay từ thư mục plugin đã cài,
xem `installPath` trong `installed_plugins.json` hoặc dùng thẳng thư mục repo:

```sh
bash <thư-mục-repo>/statusline/plugins/statusline/scripts/install.sh --dry-run
bash <thư-mục-repo>/statusline/plugins/statusline/scripts/install.sh
```

`install.sh` làm ba việc và chạy lại nhiều lần vẫn an toàn:

1. Sao lưu `statusline-command.sh` đang có trong thư mục cấu hình Claude thành
   `statusline-command.sh.bak-<YYYYmmddHHMMSS>`, trừ khi file đó đã là shim.
2. Ghi shim `statusline-command.sh`. Mỗi lần vẽ, shim tìm `installPath` của
   `statusline@statusline-local` (hoặc `statusline@` bất kỳ) trong
   `plugins/installed_plugins.json` rồi chạy `scripts/statusline.sh` của bản đó.
3. Đặt khoá `statusLine` trong `settings.json` thành
   `{"type": "command", "command": "bash \"$HOME/.claude/statusline-command.sh\""}`, giữ nguyên
   mọi khoá khác. File được ghi nguyên tử (file tạm rồi đổi tên); đã đúng thì không ghi.

Biến `CLAUDE_HOME` đổi thư mục cấu hình (mặc định `$HOME/.claude`). JSON được sửa bằng `jq`, không
có `jq` thì dùng `python3`.

## Cập nhật

```sh
claude plugin validate <thư-mục-repo>/statusline
claude plugin validate <thư-mục-repo>/statusline/plugins/statusline
claude plugin marketplace update statusline-local
claude plugin update statusline@statusline-local
```

Luôn tăng `version` trong `plugins/statusline/.claude-plugin/plugin.json` trước khi cập nhật để
bản cache được làm mới. Không phải chạy lại setup.

## Gỡ

```sh
bash <thư-mục-plugin>/scripts/install.sh --uninstall --dry-run
bash <thư-mục-plugin>/scripts/install.sh --uninstall
claude plugin uninstall statusline@statusline-local
```

`--uninstall` khôi phục bản sao lưu `.bak-<YYYYmmddHHMMSS>` mới nhất về `statusline-command.sh`
(khoá `statusLine` giữ nguyên vì vẫn trỏ đúng file). Không có bản sao lưu thì xoá shim và bỏ khoá
`statusLine` nếu nó trỏ tới shim. Gỡ plugin trước mà chưa chạy `--uninstall` thì shim chỉ in một
dòng nhắc, không lỗi.

## Kiểm thử

```sh
python3 -m unittest discover -s <thư-mục-repo>/statusline/tests
```

Test chỉ dùng thư mục tạm làm `CLAUDE_HOME` và `HOME`, không đụng cấu hình Claude thật.

## Cấu trúc

```text
statusline/                               # gốc marketplace (đưa cho marketplace add)
├── .claude-plugin/marketplace.json       # statusline-local -> ./plugins/statusline
├── README.md
├── plugins/statusline/
│   ├── .claude-plugin/plugin.json
│   ├── scripts/statusline.sh             # vẽ 3 dòng + các dòng skill
│   ├── scripts/last-skill.sh, last_skill.py   # dòng skill gần nhất (port từ dev-workflow 0.3.0)
│   ├── scripts/subagent_skills.py        # tìm transcript subagent, nhãn agent + đầu mô tả
│   ├── scripts/install.sh                # setup / --dry-run / --uninstall
│   ├── scripts/settings_json.py          # sửa JSON khi không có jq
│   ├── templates/statusline-shim.sh      # mẫu shim
│   └── skills/setup/SKILL.md             # skill statusline:setup
└── tests/                                # unittest (stdlib)
```
