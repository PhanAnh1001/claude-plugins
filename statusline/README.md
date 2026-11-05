# statusline

## Tóm tắt

- **Mục đích:** đóng gói thanh trạng thái (status line) 3–4 dòng, kèm các dòng skill nạp gần nhất của
  main và các subagent, của Claude Code thành plugin để
  máy nào cũng cài và cập nhật được bằng `claude plugin`.
- **Marketplace / plugin:** thư mục `statusline/` là marketplace `statusline-local`, chứa plugin
  `statusline` (bản 0.11.0).
- **Cài trên máy mới (3 bước):** `claude plugin marketplace add <thư-mục-repo>/statusline`,
  `claude plugin install statusline@statusline-local --scope user`, rồi chạy skill
  `statusline:setup` (hoặc `install.sh` của plugin).
- **Cập nhật:** chỉ cần `claude plugin marketplace update` và `claude plugin update`; không phải
  chạy lại setup, vì shim luôn chạy bản plugin đang cài.
- **Yêu cầu:** `jq`, `curl` (phần Go thật), `python3` >= 3.9, `bash`, `git`.

## Các dòng statusline

| Dòng | Nội dung | Ví dụ |
|---|---|---|
| 1 | `user@host`, tên thư mục hiện tại (`~` nếu là thư mục home), nhánh git màu xanh | `anh@mac dev-workflow (main)` |
| 2 | model (mức effort), tổng tokens của phiên, % context đang dùng | `Opus(high) \| tokens:6.5k \| ctx:55%` |
| 3 | rate limit 5 giờ và 7 ngày của Claude kèm giờ reset | `5h:12%(reset 09/10 15:53) \| 7d:85%(reset 15/10 10:46)` |
| 4 | mức OpenCode Go thật (5h/tuần/tháng) kèm giờ reset, hoặc số ước tính `DS` (không có giờ reset) khi chưa có cache; không có cả hai thì không có dòng này | `Go 5h:0%(reset 05/11 03:55) \| wk:1%(reset 09/11 07:00) \| mo:0%(reset 04/12 15:17)` |
| sau đó | skill nạp gần nhất, mỗi dòng một agent (xem dưới); không có skill thì không có dòng nào | `🔧 dev-workflow:dev-triage (main)` |

- **Màu phần trăm:** xanh dưới 50%, vàng từ 50%, đỏ từ 80%.
- **Tokens** cộng mọi bản ghi `usage` trong transcript nên chỉ tăng, không giảm khi nén context.
- **Dòng skill** in sau dòng rate limit, không có dòng tiêu đề, ví dụ:

  ```text
  🔧 dev-workflow:measurement-evidence (main)
  🔧 dev-workflow:port-between-repos (hand: "Nạp skill để thử statusline")
  🔧 summary-first-docs:citing-sources (hand: "Nghiên cứu API của EasyHRM")
  🔧 dev-workflow:bug-investigation (hand: "Điều tra lỗi statusline không...")
  ```

  - **Dòng main** `🔧 <skill> (main)` là skill main nạp gần nhất, luôn đứng đầu. Main chưa nạp
    skill nào thì bỏ dòng này. Cả main lẫn subagent đều chưa nạp skill thì không in gì.
  - **Dòng subagent** `🔧 <skill> (<agent>: "<mô tả>")`: mỗi subagent có nạp skill được một dòng.
    Chỉ xét 5 transcript subagent sửa gần nhất (theo mtime) và in tối đa 3 dòng, skill nạp mới
    nhất ở trên.
  - **`<agent>`** là phần sau dấu `:` cuối của `agentType` trong `agent-<id>.meta.json` (ví dụ
    `parallel-subagents:hand` thành `hand`). Thiếu, hoặc file meta thiếu hay hỏng, thì ghi `subagent`.
  - **`<mô tả>`** là trường `description` sau khi gộp khoảng trắng, bỏ ký tự không in được và đổi
    `"` thành `'`. Dài quá 30 ký tự (đếm theo ký tự, không theo byte) thì lấy 30 ký tự đầu, bỏ
    khoảng trắng cuối rồi nối `...` (3 dấu chấm ASCII); từ 30 ký tự trở xuống thì in nguyên.
    Không có description thì chỉ in `(<agent>)`,
    ví dụ `(hand)`.
  - **Màu:** tên skill tô cùng màu Claude Code dùng cho inline code (màu `permission` của theme
    dark, rgb(177,185,249), mã truecolor `\033[38;2;177;185;249m`). Phần chú thích trong ngoặc,
    `(main)` và `(hand: "…")`, tô mờ (dim) giống `(high)` sau tên model; `🔧` giữ màu mặc định.
    Màu chỉ có khi statusline gọi `last-skill.sh --color`; chạy `last-skill.sh` không có cờ này
    thì ra văn bản trần.
  - **Cách tìm skill:** đọc ngược tối đa 4 MB cuối mỗi transcript, ưu tiên lời gọi tool `Skill`,
    dự phòng bằng thông điệp hook `🔧 Skill: <tên>`. Claude Code ghi lời gọi `Skill` của subagent
    vào transcript riêng `<session_id>/subagents/agent-<id>.jsonl` cạnh transcript chính, nên
    statusline đọc cả các file đó. Thứ tự các dòng subagent theo trường `timestamp`; bản ghi không
    có `timestamp` thì dùng mtime của file.
  - **Fail-open:** không có thư mục `subagents` hoặc đọc lỗi thì chỉ hiện những gì đọc được.
- **Rate limit** chỉ có sau phản hồi API đầu tiên của phiên. Trước đó dòng 3 hiện giá trị lưu ở
  `.statusline-cache.json` trong thư mục cấu hình Claude, có dấu `~` phía trước; chưa có gì thì
  hiện `--`.
- **Mức OpenCode Go thật (`Go`)** nằm ở dòng riêng ngay dưới dòng hạn mức Claude, lấy từ API usage của OpenCode
  (`GET https://opencode.ai/zen/go/v1/usage`), cùng nguồn với plugin `opencode-go-usage-source`
  của Paseo. `go-usage-fetch.sh` đọc khoá `opencode-go` trong
  `${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json` (chỉ đọc, không in, không ghi khoá đi
  đâu; header Authorization đi qua stdin của `curl` nên không nằm trong argv), gọi API rồi ghi
  nguyên tử cache `$CLAUDE_HOME/.statusline-go-usage.json` (mặc định `~/.claude`, quyền 600).
  Statusline chỉ đọc cache bằng một lần `jq`, không chờ mạng: cache thiếu hoặc cũ hơn 5 phút thì
  khởi fetch tách hẳn ở nền (có lock 60 giây), lần vẽ hiện tại vẫn dùng số đang có. Nhãn
  `Go 5h`, `wk`, `mo`; cửa sổ `rate-limited` tô đỏ; cache cũ hơn 15 phút thêm `~`; cửa sổ đã qua
  giờ reset in `~0%` và bỏ giờ reset. Lỗi tạm thời (mạng, HTTP 5xx, JSON hỏng) giữ số của lần fetch
  ok gần nhất tối đa 6 giờ kèm `~` thay vì tụt về `DS`; lỗi khoá (`rejected`) hoặc thiếu khoá
  (`no_key`) thì bỏ số cũ. Đặt `STATUSLINE_GO_LIVE=0` để tắt hẳn phần gọi mạng.
- **Dự phòng (`DS`)** khi chưa có cache Go thật (kể cả `no_key`, `rejected`, hoặc `error` đã quá
  6 giờ): đọc đúng một file JSON do `hand-ext` ghi,
  `$HYBRID_HANDS_STATE_DIR/go_usage_summary.json`, mặc định
  `~/.hybrid-hands/go_usage_summary.json` (`HYBRID_HANDS_STATE_DIR` chỉ dùng để test). Định dạng
  `DS 5h ~12% · tuần ~31%`; dấu `~` xuất hiện khi bản tóm tắt đánh dấu `estimated` hoặc file cũ hơn
  5 giờ. Phần trăm dùng cùng ngưỡng màu với Claude (xanh dưới 50%, vàng từ 50%, đỏ từ 80%). Khi
  cache Go ở trạng thái `rejected`, segment DS thêm chữ mờ `(khoá Go bị từ chối)`. File thiếu hoặc
  JSON hỏng thì không in gì và statusline vẫn thoát 0; phần này chỉ đọc file bằng một lần `jq`,
  không gọi `hand-ext`, không gọi mạng. Có cache Go thật thì không in `DS` để tránh trùng.

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

Test chỉ dùng thư mục tạm làm `CLAUDE_HOME`, `HOME` và `XDG_DATA_HOME`, khoá Go giả, cùng một
`curl` giả đặt đầu `PATH`; không đọc `auth.json` thật và không gọi API thật.

## Cấu trúc

```text
statusline/                               # gốc marketplace (đưa cho marketplace add)
├── .claude-plugin/marketplace.json       # statusline-local -> ./plugins/statusline
├── README.md
├── plugins/statusline/
│   ├── .claude-plugin/plugin.json
│   ├── scripts/statusline.sh             # vẽ 3 dòng + các dòng skill
│   ├── scripts/go-usage-fetch.sh         # gọi API usage OpenCode Go, ghi cache (chạy nền)
│   ├── scripts/last-skill.sh, last_skill.py   # dòng skill gần nhất (port từ dev-workflow 0.3.0)
│   ├── scripts/subagent_skills.py        # tìm transcript subagent, nhãn agent + mô tả (cắt 30 ký tự)
│   ├── scripts/install.sh                # setup / --dry-run / --uninstall
│   ├── scripts/settings_json.py          # sửa JSON khi không có jq
│   ├── templates/statusline-shim.sh      # mẫu shim
│   └── skills/setup/SKILL.md             # skill statusline:setup
└── tests/                                # unittest (stdlib)
```
