# statusline

## Tóm tắt

- **Mục đích:** đóng gói thanh trạng thái (status line) 3–5 dòng, kèm các dòng skill nạp gần nhất của
  main và các subagent, của Claude Code thành plugin để
  máy nào cũng cài và cập nhật được bằng `claude plugin`.
- **Marketplace / plugin:** thư mục `statusline/` là marketplace `statusline-local`, chứa plugin
  `statusline` (bản 0.27.0). Dòng tách % hạn mức 7 ngày tính theo USD giá thật từng model, hiệu
  chỉnh $/1% trong khung giờ chỉ máy này chạy; đây là số ước tính, xem mục "Dòng tách hạn mức 7
  ngày theo máy".
- **Bản 0.27.0:** cuối dòng `Claude v1 ultra` có ô `Fable`: hạn mức tuần riêng của Fable 5.2 (payload
  status line không có), đọc từ `cachedUsageUtilization` mà CLI ghi vào `~/.claude.json` mỗi khi mở
  `/usage`; luôn có `~`, kèm giờ lấy số (`lấy dd/mm HH:MM`), qua giờ reset thì `?`.
- **Bản 0.26.1:** dòng `GPT` đọc rollout của cả `~/.codex` và `~/.codex-hand` (Codex hand của
  hybrid-hands, cùng tài khoản ChatGPT nên chung hạn mức).
- **Bản 0.26.0:** dọn code chết của khối dòng nhóm phiên: tóm tắt `.statusline-week-split.json`
  không còn `groups`/`go_week`, sổ USD không còn ghi tiêu đề phiên. Output không đổi.
- **Bản 0.25.0:** bỏ khối dòng nhóm phiên (`▶ <tên>  Claude …% | Go …%`) khỏi status line; xoá
  `session-lines.sh`. Các dòng khác giữ nguyên.
- **Bản 0.23.0:** dòng Claude đổi nhãn `Claude v1 ultra`; thêm dòng `Claude v2 pro` ngay dưới, cùng
  cột. Tài khoản của phiên đang vẽ lấy số live, tài khoản còn lại đọc cache statusline riêng của nó
  (`<home>/.statusline-cache.json`, có `~`, thiếu/qua reset hiện `?`); dòng v2 chỉ có số sau khi
  statusline đã chạy trong một phiên `~/.claude-hand`. Dòng GPT đọc rollout của `~/.codex` và `~/.codex-hand`; dòng
  `Go` vẫn căn cột với bảng nhưng in ở dòng cuối cùng của statusline.
- **Bản 0.19.1:** thêm dòng `GPT` dưới dòng `Go` (hoặc cuối bảng khi không có `Go`): % 5h/7d mới
  nhất và USD ước tính hôm nay của tài khoản `.codex-hand`, đọc từ sổ `codex_usage.jsonl` của
  hand-ext; chỉ hiện khi mẫu quota mới nhất kết thúc trong 24 giờ, không có thì ẩn cả dòng.
- **Bản 0.18.0:** khối hạn mức xếp thành bảng thẳng cột gồm bốn dòng `Claude`, `· máy này`,
  `· máy khác`, `Go`; USD/1% nằm trong ngoặc của ô 7d dòng Claude; đệm theo độ rộng hiển thị (bỏ
  mã ANSI) nên nhãn tiếng Việt vẫn thẳng cột; không dòng nào bắt đầu bằng khoảng trắng.
- **Bản 0.14.0:**
  - % 7 ngày của Claude và % Go (5h/wk/mo) in tới 0,1% khi có ước tính. **Số lẻ có `~` là số
    ước tính, không phải số gốc**: nguồn gốc chỉ cho số nguyên, và số ước tính luôn bị ép nằm trong
    khoảng của số nguyên đó. Xem mục "Số ước tính tới 0,1%".
  - 5h của Claude chỉ lấy từ payload hiện tại; không có thì in `5h:-` (không dùng số lưu cũ).
  - Khối dòng mới, mỗi nhóm phiên chính một dòng: % Claude và % Go của phiên chính cùng
    subagent/hand và các phiên phụ con cháu. Đoạn `phiên …` cũ ở dòng 3b đã bỏ.
- **Cài trên máy mới (3 bước):** `claude plugin marketplace add <thư-mục-repo>/statusline`,
  `claude plugin install statusline@statusline-local --scope user`, rồi chạy skill
  `statusline:setup` (hoặc `install.sh` của plugin).
- **Cập nhật:** chỉ cần `claude plugin marketplace update` và `claude plugin update`; không phải
  chạy lại setup, vì shim luôn chạy bản plugin đang cài.
- **Yêu cầu:** `jq`, `curl` (phần Go thật), `python3` >= 3.9, `bash`, `git`.

## Hiệu chỉnh Claude ngoài — 0.22.0

Statusline đọc cache hiệu chỉnh Claude ngoài dùng chung với [hybrid-hands](../hybrid-hands/README.md#hiệu-chỉnh-claude-ngoài--0320); không gọi mạng để lấy calibration khi vẽ. Rate pin vẫn ưu tiên, sau đó là rate hiệu chỉnh hợp lệ; chưa sẵn sàng thì giữ nguyên fallback hiện có, kể cả prior, ở mục tách hạn mức theo máy bên dưới.

Nguồn là tài khoản `~/.claude-hand`: ưu tiên live `rate_limit_event`/cache trực tiếp còn mới, dự phòng usage report Paseo khớp email từ metadata auth Claude chính thức trong nội bộ (kể cả Pi đăng nhập). Chỉ lưu định danh tài khoản đã hash, không lưu email thô hay credential; nguồn trực tiếp không cần đổi settings. Mẫu được lấy khoảng mỗi 120 giây, cache Paseo tối đa 5 phút. USD~ chỉ tính token transcript Claude hand theo [giá canonical](../hybrid-hands/plugins/hybrid-hands/config/model-prices.json), gồm input/output/cache đọc/cache ghi 5m/1h. Rate USD~/1% tuần cần hai quan sát có USD và quota tăng hợp lệ trong cùng tài khoản/reset hiện tại; không dựng baseline lịch sử. Quota số nguyên cần delta ít nhất 2 điểm phần trăm để giảm sai số làm tròn; nguồn có phần lẻ thực chỉ cần delta dương, có thể nhỏ hơn. Rate chung giữ unknown đến khi đủ ngưỡng. Mẫu stale/thiếu, model thiếu giá hoặc không có delta hợp lệ thì cache chưa có rate dùng được.

Theo lựa chọn người dùng, rate được chia sẻ để ước tính phần Claude riêng giữa các tài khoản và chỉ thay ước tính hiện có khi rate mới sẵn sàng; đây là ước tính subscription, không phải hoá đơn hay phép đo chính xác riêng từng tài khoản. Phép tính giữ độ chính xác nguồn; % hiển thị một chữ số lẻ. Số nguyên API được viết `x.0%` không có nghĩa nguồn chính xác tới 0,1%. USD~ từng lượt ngoài vẫn unknown nếu registry cũ thiếu tách cache hoặc tương quan session; khối đầu panel tổng hợp từ transcript nguồn. Các mô tả hiệu chỉnh solo bên dưới là fallback khi không có pin hoặc rate hiệu chỉnh ngoài hợp lệ.

## Các dòng statusline

| Dòng | Nội dung | Ví dụ |
|---|---|---|
| 1 | `user@host`, tên thư mục hiện tại (`~` nếu là thư mục home), nhánh git màu xanh | `anh@mac dev-workflow (main)` |
| 2 | model (mức effort), tổng tokens của phiên, % context đang dùng | `Opus(high) \| tokens:6.5k \| ctx:55%` |
| 3 | dòng `Claude v1 ultra` của bảng hạn mức: rate limit 5 giờ và 7 ngày kèm giờ reset, USD/1% trong ngoặc ô 7d; 7d có thể là số ước tính tới 0,1%; ô cuối `Fable` là hạn mức tuần của Fable từ `~/.claude.json` (CLI cập nhật khi mở `/usage`, luôn `~`, kèm giờ lấy số; qua reset thì `?`, không có hạn mức Fable thì không có ô) | `Claude    5h:- \| 7d:~4.3% (reset 15/10 10:46 · $13.74/1%)` |
| 3a | dòng `Claude v2 pro` ngay dưới, cùng cột: 5h/7d của `~/.claude-hand`, live khi phiên chạy trên tài khoản đó, nếu không thì từ cache statusline riêng của nó (`~`, thiếu/qua reset thì `?`); dòng v1 theo quy tắc ngược lại | `Claude v2 pro    5h:2% \| 7d:20% (reset 14/11 07:00)` |
| 3b | hai dòng `· máy này` (từng thứ trong tuần) và `· máy khác` của cùng bảng, ô 5h để trống; ước tính, chưa có tóm tắt cho cửa sổ hiện tại thì không có hai dòng này | `· máy này   \| 7d:1.5% (T6 1.5%)`<br>`· máy khác  \| 7d:1.5%` |
| cuối | dòng `Go` của cùng bảng (căn cột theo bảng, in ở dòng cuối cùng): mức OpenCode Go thật (5h/tuần/tháng) kèm giờ reset, số lẻ có `~` khi có ước tính của hand-ext; hoặc ô `DS` (không có giờ reset) khi chưa có cache; không có cả hai thì không có dòng này | `Go        5h:~2.7% (reset 05/11 03:55) \| wk:~12.4% (reset 09/11 07:00) \| mo:~6.2% (reset 04/12 15:17)` |
| 5 | dòng `GPT` của cùng bảng: % 5h và 7d của mẫu quota mới nhất cùng USD ước tính hôm nay của tài khoản ChatGPT sau `~/.codex` và `~/.codex-hand` (rollout cục bộ); không có mẫu trong 24 giờ thì không có dòng này | `GPT        5h:? \| 7d:31% (reset 16/11 13:19) \| hôm nay ~$1.85` |
| sau đó | skill nạp gần nhất, mỗi dòng một agent (xem dưới); không có skill thì không có dòng nào | `🔧 dev-workflow:dev-triage (main)` |

- **Bảng hạn mức (dòng 3–5):** cột 1 là nhãn dòng (`Claude`, `· máy này`, `· máy khác`, `Go`,
  `GPT`), cột 2 là ô 5h (dòng tách máy để trống), cột 3 là ô 7d/wk, cột 4 `mo` chỉ dòng Go có còn
  dòng GPT dùng cột 4 cho `hôm nay ~$...`. Các ô đệm
  theo độ rộng hiển thị lớn nhất của cột (bỏ mã ANSI, đếm ký tự) nên dấu `|` thẳng hàng kể cả với
  nhãn tiếng Việt; thiếu dòng nào thì các dòng còn lại vẫn thẳng cột, chỉ còn dòng Claude thì in
  như bảng một dòng. Không dòng nào bắt đầu bằng khoảng trắng vì Claude Code cắt khoảng trắng đầu
  dòng, nên hai dòng tách máy mở đầu bằng `·`.
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
- **Rate limit** chỉ có sau phản hồi API đầu tiên của phiên. Trước đó phần 7d hiện giá trị lưu ở
  `.statusline-cache.json` trong thư mục cấu hình Claude, có dấu `~` phía trước; chưa có gì thì
  hiện `--`. Phần 5h không dùng giá trị lưu: payload không có `rate_limits.five_hour` thì in `5h:-`.
- **Mức OpenCode Go thật (`Go`)** là dòng trước GPT trong cùng bảng hạn mức, lấy từ API usage của OpenCode
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
  `~/.hybrid-hands/go_usage_summary.json` (`HYBRID_HANDS_STATE_DIR` chỉ dùng để test). Hai ô
  `DS 5h ~12.3%` và `tuần ~31.0%` (một chữ số lẻ) nằm ở cột 2 và cột 3 của dòng `Go`; dấu `~`
  xuất hiện khi bản tóm tắt đánh dấu `estimated` hoặc file cũ hơn
  5 giờ. Phần trăm dùng cùng ngưỡng màu với Claude (xanh dưới 50%, vàng từ 50%, đỏ từ 80%). Khi
  cache Go ở trạng thái `rejected`, segment DS thêm chữ mờ `(khoá Go bị từ chối)`. File thiếu hoặc
  JSON hỏng thì không in gì và statusline vẫn thoát 0; phần này chỉ đọc file bằng một lần `jq`,
  không gọi `hand-ext`, không gọi mạng. Có cache Go thật thì không in `DS` để tránh trùng.
- **GPT (`GPT`)** đọc rollout của `~/.codex` và `~/.codex-hand` (Codex hand của hybrid-hands; cùng
  một tài khoản ChatGPT nên chung hạn mức; thư mục không tồn tại bị bỏ qua) trong `sessions/`,
  `archived_sessions/`, chỉ file sửa trong 7 ngày. `STATUSLINE_CODEX_DIR` ghi đè danh sách, nhận một
  hoặc nhiều đường dẫn phân tách bằng `:`. Cùng thread id ở hai thư mục chỉ tính một lần. % 5h/7d là mẫu `rate_limits` mới nhất
  theo timestamp, nhãn theo `window_minutes` (300 = 5h, 10080 = 7d; thiếu thì primary = 5h,
  secondary = 7d); ô thiếu hoặc đã qua reset in `?`, ô có số kèm giờ reset. USD hôm nay (0h theo
  múi giờ máy) là token delta của từng thread × giá trong `model-prices.json`; model chưa có giá
  in `hôm nay ~$?`. Không có mẫu trong 24 giờ thì không có dòng GPT và statusline vẫn thoát 0.

## Dòng tách hạn mức 7 ngày theo máy

Ví dụ trong bảng hạn mức: `· máy này  | 7d:1.5% (T6 1.5%)` và `· máy khác  | 7d:1.5%`;
USD/1% nằm trong ngoặc ô 7d của dòng Claude, ví dụ `7d:~4.3% (reset 15/10 10:46 · $13.74/1%)`.
Ghim USD/1%: ghi một số dương vào `$CLAUDE_HOME/statusline-usd-per-pct.txt` (dòng `#` là chú thích);
số ghim thắng cả hiệu chỉnh lẫn mặc định 12, nhãn `pin`; xoá file để quay lại tự hiệu chỉnh.

- **Tóm tắt:**
  - Payload statusLine chỉ có % 7 ngày của cả tài khoản. Plugin quy chi phí API của máy này ra
    USD theo giá niêm yết từng model, rồi chia cho mức "USD cho 1% tuần" để ra % của máy này.
  - Mức $/1% được hiệu chỉnh trong các khung giờ chỉ máy này chạy; chưa đo được thì dùng mức
    mặc định $12/1% và gắn dấu `~`.
  - Đây là **ước tính**, không phải số Anthropic tách theo máy.
- **Cách tính USD:**
  - `week_split.py` chạy nền (khi tóm tắt thiếu hoặc cũ hơn 2 phút, có lock 5 phút) và gọi
    `usage_ledger.py` quét tăng dần `$CLAUDE_HOME/projects/**/*.jsonl`, kể cả transcript subagent.
  - Khử trùng theo cặp (`message.id`, `requestId`), giữ bản ghi **cuối**; bỏ model `<synthetic>`.
  - Đo một khung giờ bất kỳ (token và USD theo model/loại token, main/subagent, top phiên):
    `python3 scripts/usage_ledger.py --since 2026-11-06T20:00:00+07:00 [--until ISO] [--home DIR]`.
  - USD dùng giá riêng của input, output, cached, cache-write 5 phút/1 giờ trong nguồn chung;
    bản ghi không tách thời hạn cache ghi dùng loại 5 phút. Cache-read Opus 5.5 là 5% giá input.
  - Sổ `.statusline-local-usage.json` (version 4) lưu USD, thời điểm, phiên, tên và alias.
    Fingerprint bảng giá thay đổi hoặc sổ version cũ sẽ khiến quét lại để tính USD mới.
- **Một nguồn giá:** `hybrid-hands/plugins/hybrid-hands/config/model-prices.json`.
  Ledger tìm file theo thứ tự `HYBRID_HANDS_PRICING_FILE`, source sibling, rồi hybrid-hands
  installed mới nhất trong `$CLAUDE_HOME/plugins/cache/*/hybrid-hands/*`.
  Override hỏng không chuyển sang nguồn khác. Không có hybrid-hands hoặc giá/model chưa biết
  thì fail-open, đánh dấu `unpriced_models`, không đoán theo family và không dùng bảng fallback.
  Giá, ngày xác minh và URL nguồn nằm trong file chung; statusline không chép bảng giá riêng.
- **Hiệu chỉnh $/1%:**
  - Khung mặc định hằng ngày theo giờ máy: `12:00-13:30` và `21:00` hôm trước tới `07:00`.
  - File tuỳ chọn `$CLAUDE_HOME/statusline-solo-windows.txt`, mỗi dòng một khung:
    `daily HH:MM-HH:MM`, `daily -HH:MM-HH:MM` (bắt đầu từ hôm trước) hoặc
    `YYYY-MM-DD HH:MM-HH:MM` (khung riêng một ngày); bỏ qua dòng trống và dòng `#`. Có một dòng
    `daily` trở lên thì thay toàn bộ khung mặc định.
  - Xét 7 ngày gần nhất; bỏ khung chưa kết thúc và khung nằm trọn trong khung khác. Mỗi khung lấy
    mẫu đầu và mẫu cuối cùng giờ reset; mức tăng dưới 2% thì bỏ.
  - $/1% = tổng USD trong các khung ÷ tổng mức tăng. Không có khung nào thì dùng $12/1% (suy luận
    từ đo sơ bộ $9–15 cho 1% tuần).
- **Chia và phiên:**
  - Máy này = USD từ đầu cửa sổ 7 ngày ÷ $/1%; máy khác = % tài khoản − máy này (không âm). Phần
    trong ngoặc là % máy này theo từng thứ.
  - % theo phiên không còn hiện trên status line (bỏ từ 0.25.0).
- **Dấu `~`:** mức $/1% còn là mức mặc định (chưa hiệu chỉnh được) hoặc tóm tắt cũ hơn 30 phút.
- **Các file trạng thái** (trong `$CLAUDE_HOME`, mặc định `~/.claude`):
  `.statusline-week-samples.tsv` (mẫu % mỗi lần vẽ, 3 cột `epoch pct reset`; cột thừa của bản cũ
  được bỏ qua), `.statusline-local-usage.json`,
  `.statusline-week-split.json` (tóm tắt version 2), thư mục lock `.statusline-week-split.lock`,
  file cấu hình tuỳ chọn `statusline-solo-windows.txt`. Giữ dữ liệu 9 ngày.
- **Biến môi trường:** `STATUSLINE_WEEK_SPLIT=0` tắt hẳn (không ghi mẫu, không chạy nền, không in);
  `STATUSLINE_WEEK_SPLIT_SPAWN=0` chỉ tắt phần chạy nền.
- **Giới hạn:**
  - Nếu máy khác vẫn chạy trong khung "chỉ máy này", $/1% bị đo thấp và % máy này bị tính cao.
  - % trong payload là số nguyên, nên cần khung có mức tăng từ 2% trở lên.
  - Giá là giá API niêm yết; hạn mức gói Claude có thể không tỉ lệ đúng với giá này giữa các model.
  - Chỉ đếm transcript trong `$CLAUDE_HOME/projects`; tài khoản khác ở thư mục cấu hình khác
    (ví dụ `~/.claude-hand`) và phiên phụ provider khác `claude` không bị tính.
- **Nguồn port:** khử trùng từ `live-tiktok-games sessions/ops/runs/local-usage.sh`;
  hiệu chỉnh khung solo từ `calibrate.sh`; % máy = USD ÷ $/1% từ `day-budget.sh` (cùng thư mục).

## Số ước tính tới 0,1%

- **Quy ước:** số có một chữ số lẻ và dấu `~` là **ước tính**, không phải số gốc. Claude và API
  usage của OpenCode Go chỉ trả số nguyên; plugin chỉ thêm phần lẻ và luôn giữ nó trong khoảng của
  số nguyên gốc. Màu và trạng thái `rate-limited` vẫn theo số nguyên gốc.
- **Claude 7 ngày (dòng 3):**
  - Giả định Claude **cắt phần lẻ** (4,7% hiện là 4%). `week_split.py` lấy p = số nguyên của mẫu
    mới nhất, t0 = thời điểm sớm nhất của chuỗi mẫu cuối cùng còn cùng p và cùng giờ reset, rồi
    ước tính = p + USD máy này trong [t0, bây giờ) ÷ $/1%, ép vào [p, p + 0,9], làm tròn 1 chữ số.
  - Phần các máy khác dùng trong khoảng chưa nhảy số thì không biết được, nên số ước tính có thể
    **thấp** hơn thật.
  - Chỉ dùng khi tóm tắt đúng version, mới hơn 30 phút, phần nguyên khớp số đang hiện và giờ reset
    lệch không quá 1 giờ; không thì in số nguyên như cũ. Số lưu cache (đã có `~`) chỉ in một `~`.
  - 5 giờ của Claude không có ước tính (Claude Code không còn gửi dữ liệu 5 giờ).
- **OpenCode Go (dòng Go):**
  - Lấy `percent` ước tính trong sổ `go_usage_summary.json` của hand-ext, ghép rolling↔`5h`,
    weekly↔`7d`, monthly↔`30d` của model `deepseek*`.
  - Chỉ dùng khi sổ cập nhật trong 5 giờ và có `estimated: true`; số hiện = ước tính ép vào
    [max(0, API − 0,5), API + 0,4], tức vẫn làm tròn ra đúng số API. Không có ước tính thì in số
    nguyên như cũ; cửa sổ đã qua giờ reset vẫn in `~0%`.

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
│   ├── scripts/table.sh                  # đệm ô theo độ rộng hiển thị (source từ statusline.sh)
│   ├── scripts/go-segments.sh            # ô Go của bảng hạn mức (source từ statusline.sh)
│   ├── scripts/gpt_usage.py              # ô GPT: % quota và USD hôm nay từ rollout ~/.codex + ~/.codex-hand
│   ├── scripts/week-split.sh, week_split.py, usage_ledger.py   # dòng tách % 7 ngày theo máy (quét chạy nền)
│   ├── scripts/go_sessions.py            # lượt Go trong tuần, cộng dồn phiên phụ (cho trường sessions)
│   ├── scripts/go-usage-fetch.sh         # gọi API usage OpenCode Go, ghi cache (chạy nền)
│   ├── scripts/last-skill.sh, last_skill.py   # dòng skill gần nhất (port từ dev-workflow 0.3.0)
│   ├── scripts/subagent_skills.py        # tìm transcript subagent, nhãn agent + mô tả (cắt 30 ký tự)
│   ├── scripts/install.sh                # setup / --dry-run / --uninstall
│   ├── scripts/settings_json.py          # sửa JSON khi không có jq
│   ├── templates/statusline-shim.sh      # mẫu shim
│   └── skills/setup/SKILL.md             # skill statusline:setup
└── tests/                                # unittest (stdlib)
```


### Khối hand — bỏ từ 0.24.0

Statusline không còn vẽ cây phiên/subagent/hand-ext và không gọi `hh-ps` khi vẽ.
Xem cây đó bằng `hh-ps` hoặc pane hybrid-hands.

### Khối dòng phiên — bỏ từ 0.25.0

Statusline không còn vẽ mỗi nhóm phiên chính một dòng (% Claude và % Go của nhóm); `session-lines.sh`
đã xoá. Từ 0.26.0 tóm tắt `.statusline-week-split.json` cũng không còn ghi `groups`, `go_week`.
