# hybrid-hands — limit-watch (0.60.1)

Tóm tắt: `hand-ext limit-watch` chờ hạn mức bằng code, không gọi LLM trong các tick kiểm tra. LaunchAgent local chạy vào phút **0, 15, 30, 45** khi người dùng đã login và máy đang thức; không phát bù các lượt bị lỡ khi ngủ. Các tính năng khác xem [README chung](../../README.md).

## Bật và tắt

Chạy binary của bản plugin vừa cập nhật (hoặc đường tuyệt đối trong checkout):

```sh
hand-ext limit-watch on --persistent
hand-ext limit-watch on --persistent --target /ABS/target.json
hand-ext limit-watch status
hand-ext limit-watch tick
hand-ext limit-watch off
hand-ext limit-watch done --id brain
```

Lệnh đầu bật lịch rỗng, chờ đăng ký; không tự tìm hay tiếp tục mọi phiên. `--target` lặp lại được để đăng ký brain/Sol độc lập. Bỏ `--persistent` để one-shot: sau khi tất cả target đã có receipt được nhận hoặc đã xong, watcher tự tắt/gỡ job. Persistent trở về `armed` sau mỗi receipt, đợi sự kiện quota **mới** của chính phiên đó. `off` vô hiệu generation và gỡ LaunchAgent; không dừng các phiên đã tiếp tục, không xóa journal. `status` chỉ đọc state cục bộ, không gọi dịch vụ quota.

## Đăng ký tự điền metadata

Dùng skill [limit-watch](skills/limit-watch/SKILL.md) hoặc `/hybrid-hands:limit-watch [status|on|off|add-self <checkpoint>|add-side <name> <checkpoint>]`; không đối số xem status, off tắt toàn bộ và chỉ chạy khi gõ rõ.

```sh
hand-ext limit-watch add --self --checkpoint "Đã xong A, còn B" --next-step "Kiểm chứng B, ghi .done" --id brain --dry-run
hand-ext limit-watch add --side sol --checkpoint "Đã xong A, còn B" --dry-run
```

Bỏ `--dry-run` để ghi `~/.hybrid-hands/limit-watch/targets/<id>.json` và đăng ký. Tự lấy metadata public qua fetchAgent; thiếu agent/workspace/native/account home thì lỗi, không đoán. Dry-run chỉ in JSON, không ghi hoặc đăng ký. Add giữ persistent và generation hiện tại, không thay state target khác; trùng agent hoặc target đang dispatch_pending bị từ chối. `done --id ID` kết thúc riêng target, từ chối khi dispatch_pending; không dùng off để huỷ riêng target. Đăng ký lại cùng ID đã done đưa target về armed. JSON đăng ký có `work_pending=false` kết thúc target.

## Đăng ký đúng phiên

Brain ghi file JSON metadata/checkpoint công khai được, không chứa secret hay dữ liệu khách hàng. Điền giá trị thực từ metadata public của Paseo và cấu hình đã biết; không đọc credential, transcript hoặc log. Ví dụ dưới đây dùng ID/đường dẫn giả, **phải thay** trước khi dùng:

```json
{
  "id": "brain-v2",
  "adapter": "paseo",
  "provider": "claude",
  "account": "v2",
  "account_home": "/Users/USER/.claude-hand",
  "cwd": "/ABS/REPO",
  "native_id": "EXACT_NATIVE_SESSION_ID",
  "agent_id": "EXACT_PASEO_AGENT_ID",
  "workspace_id": "EXACT_WORKSPACE_ID",
  "paseo_provider": "claude-v2",
  "target": {"kind": "instance", "home": "/Users/USER/.paseo"},
  "target_key": "home:/Users/USER/.paseo",
  "work_pending": true,
  "checkpoint": "Đã làm phần A; chưa kiểm chứng phần B.",
  "next_step": "Hoàn tất phần B trong phạm vi đã duyệt."
}
```

`paseo_provider` phải là đúng provider metadata public trả về (có thể `claude` khi dùng env tài khoản riêng), không đoán từ nhãn. `account_home` phải là home thực của tài khoản chạy phiên; không chuyển tài khoản để né quota. Codex dùng `provider: "codex"`, `account: "gpt"`, home đúng `~/.codex-hand` hoặc `~/.codex`, `paseo_provider` đúng metadata (thường `codex`), và native thread ID. Bucket quota mặc định `codex`; chỉ đặt `limit_id` khác khi có bucket thực tương ứng. Claude hỗ trợ v1/v2; v1 luôn giữ trần day guard tối đa 8%/ngày, thiếu dữ liệu guard thì chờ.

Sol dùng `adapter: "side"` và thêm `side_name`, `side_uuid` lấy từ metadata side-session; giữ các ID Paseo/native/cwd ở trên. Tên không đủ để xác định phiên: UUID và các ID được kiểm lại trong send lock. Đường này tái dùng action của `side-session send`, gồm preflight, restore, marker history và watchdog; guard cấm role `main` giữ nguyên. Brain dùng adapter `paseo`, không gọi `side-session send` cho main.

Nên đăng ký trước khi quota hết: target ở `armed`, quota còn thì im lặng. Khi phiên báo lỗi quota trong metadata public, watcher ghi `blocked`. Nếu đăng ký **sau khi đã bị chặn**, thêm quan sát rõ ràng của chính phiên đó (Unix epoch giây thực, không dùng các số ví dụ dưới):

```json
{
  "blocked": {
    "observed_at": 1800000000,
    "windows": [
      {"id": "five_hour", "used_pct": 100, "reset_at": 1800001000, "observed_at": 1800000000},
      {"id": "seven_day", "used_pct": 100, "reset_at": 1800100000, "observed_at": 1800000000}
    ]
  }
}
```

Gộp khối `blocked` vào target JSON, ghi **tất cả** cửa sổ đang chặn. Codex dùng ID `codex:primary`/`codex:secondary` theo RPC thực, không suy cửa sổ 5h/tuần. Chỉ quota tài khoản đầy không đủ chứng minh một phiên đã bị chặn. Đăng ký lại cùng `id` cập nhật checkpoint và attestation; không được thay registration đang `dispatch_pending`. Không đăng ký trùng cùng endpoint/agent dưới hai tên.

## Quan sát và giao nhận

Máy trạng thái `armed → blocked → eligible → dispatch_pending → resumed`. Journal `~/.hybrid-hands/limit-watch/state.json` mode 0600, atomic write/fsync và flock xuyên suốt tick/send; `off` dùng cùng lock để không đổi generation giữa kiểm tra và gửi. Tick đang chạy thì tick kế tiếp bỏ qua. Journal được giữ khi tắt; không ghi hội thoại hay output CLI.

Codex mở official CLI app-server bằng `CODEX_HOME` đã ghim, thực hiện handshake và chỉ `account/rateLimits/read`, timeout hữu hạn và thu hồi process sau đọc. Không mở thread, không gọi `turn/start` trong collector, không dùng API key. Theo [OpenAI App Server](https://learn.chatgpt.com/docs/app-server) (đối chiếu 12/11/2026), kết quả có các bucket/cửa sổ và trạng thái chặn từ server; thiếu bucket/cửa sổ cần thiết thì chờ.

Claude ưu tiên `.hh-claude-rate-limit.json`, sau đó `.statusline-cache.json`, rồi `paseo usage --json` khớp tài khoản qua official `claude auth status --json` (chỉ so sánh nội bộ, không in danh tính/auth). Quan sát mới phải không ở tương lai, dưới 30 phút, reset còn hiện tại. Cache statusline hiện thường thiếu `five_observed_at`/`week_observed_at`, nên mtime mới không làm số liệu cũ trở thành mới. Các cửa sổ chặn được giữ lại khi nguồn mất/thiếu dữ liệu.

Ưu tiên chờ nguồn mới. Nếu Claude chỉ có dữ liệu cũ, sau **max(reset mọi cửa sổ chặn) + 120 giây**, thử một continuation có nhãn **“reset dự kiến”**. Thiếu bất kỳ reset nào thì chờ. Quota mới còn chặn hoặc guard v1 chưa cho phép thì không gửi. Một lần thử dự kiến đã dùng thì không tự thử lại do cùng block. Collector không tự bật extra usage, mua credits, đổi account hay tắt guard.

Ngay trước gửi phải xác minh agent/workspace/endpoint/native/cwd/provider, trạng thái idle hoặc lỗi quota, không active turn và không quyền đang chờ. Phiên đã xong, bị dừng, mất identity hoặc mất cwd không nhận continuation. Brain Paseo idle/finished giữa lượt vẫn được theo dõi; chỉ kết thúc khi `done --id ID`, archive/đóng/mất identity đã xác minh hoặc đăng ký `work_pending=false`. Brain tự về armed sau resumed kể cả khi watcher không bật persistent, chỉ gửi lại sau block mới. Side có `.done`/stopped vẫn kết thúc target. Prompt chỉ gồm “làm tiếp”, checkpoint và bước kế tiếp đã đăng ký.

`resumed` nghĩa là daemon đã xác nhận **nhận** continuation, không khẳng định công việc đã hoàn tất hay chắc chắn inference thành công. Không dùng riêng exit 0 của một lệnh shell làm bằng chứng. Timeout/queued/ACK mơ hồ giữ `dispatch_pending`, không tự gửi lần hai. Sau crash giữa reserve và send cũng giữ pending: hiện chưa có receipt tương quan để tự reconcile qua public API nên cần operator kiểm đúng phiên trước khi thay journal; không hứa exactly-once. Không tự xóa pending bằng `off/on` hay đổi ID để thử lại.

Tmux và Codex CLI ngoài Paseo chưa có adapter chứng minh ô nhập/ownership đủ chắc nên registration bị từ chối; không bơm phím mù vào shell/menu. Chưa kiểm thử gửi continuation vào phiên thật để tránh gọi LLM. Plugin trong phiên đang mở có thể cần reload sau operator cập nhật bản cài qua CLI chính thức. Tài liệu `dev-workflow/resume-work` nằm ngoài phạm vi việc này, chưa sửa.

## Social listening

Kế thừa nghiên cứu đã duyệt, nguồn được người nghiên cứu mở ngày **12/11/2026**; đây là báo cáo cộng đồng, chưa phải lỗi tái hiện tại máy này:

- [Claude #92004](https://github.com/anthropics/claude-code/issues/92004), **04/09/2026**: nhiều phiên cùng account có hành vi auto-continue khác nhau → đăng ký và kiểm từng target.
- [Codex #8310](https://github.com/openai/codex/issues/8310), **19/12/2025**: resume có thể lặp ý định cũ → gửi checkpoint cùng bước tiếp theo.
- [Claude #35744](https://github.com/anthropics/claude-code/issues/35744), **18/03/2026**, bình luận **28/05/2026**: cần kiểm runtime trước resume → chặn running/quyền/identity chưa rõ.
- [unsnooze](https://github.com/saaranshM/unsnooze), không rõ ngày xuất bản, **đọc 12/11/2026**: ghim session/reset và quyền pane → state bền, fail closed cho tmux.
- [claude-auto](https://github.com/Darkblader24/claude-auto), không rõ ngày xuất bản, **đọc 12/11/2026**: banner cũ/reset nhiều cửa sổ → không dùng text lịch sử, đợi reset chặn muộn nhất và retry hữu hạn.

## Kiểm chứng

Ba ca chính với fixtures giả, không gọi quota/LLM thật:

```sh
python3 -m unittest discover -s hybrid-hands/plugins/hybrid-hands/tests -p test_limit_watch.py -v
```

Bao gồm: quota còn thì im lặng; blocked → quota mới → một receipt/one-shot, persistent đợi block mới, ACK/crash không gửi trùng; stale Claude → max reset+buffer → chỉ một lần thử, guard/partial window không bị bỏ qua. RPC/bridge chạy với binary/client giả.

### Social listening — đóng gói skill và command

Đã xem ngày **13/11/2026**: [Claude Code #41842](https://github.com/anthropics/claude-code/issues/41842) phản ánh skill plugin không hiện thành slash command; [r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1qkyjqi/bug_adding_fields_to_pluginjson_silently_breaks/) phản ánh thêm trường manifest có thể làm hỏng discovery. Đây là phản ánh cộng đồng, chưa tái hiện tại máy này. Ảnh hưởng: cung cấp cả skills/limit-watch/SKILL.md và commands/limit-watch.md, giữ manifest tối giản và chạy plugin validate. Ý kiến cá nhân chưa kiểm chứng: hai entrypoint giúp người dùng dễ tìm workflow hơn.

## hh-heat — điều phối nhiệt (0.60.0)

Tóm tắt: quan sát CPU/load và tín hiệu giảm xung macOS; đây không phải số đo nhiệt độ. Một khóa `~/.hybrid-hands/locks/browser.lock` dùng chung toàn máy, mặc định một slot; `--slots N` ưu tiên hơn `HH_HEAT_BROWSER_SLOTS` (số nguyên dương). Policy vận hành giữ tối đa 1 trình duyệt toàn máy. CPU từ ps chia số CPU logic, không suy trực tiếp ra nhiệt độ.

```sh
hh-heat status --json
hh-heat gate --max-cpu 60 --wait --timeout-min 20
hh-heat browser --slots 1 --timeout-min 10 -- <lệnh>
hh-heat reap --dry-run --min-age-min 10
hh-heat reap --min-age-min 10
```

Gate trả 0 khi ok, 1 khi busy/hot hoặc hết chờ, 2 khi không quan sát được; lỗi quyền sandbox trả 3 và yêu cầu chạy ngoài sandbox. Timeout browser trả 124, ngắt trả 130. Timeout gồm cả chờ khóa và gate. Browser chạy nice 19/taskpolicy background; cleanup chỉ nhóm của lệnh khi chứng minh Chrome headless/profile tạm/không client CDP. Không chứng minh được thì giữ tiến trình và báo cảnh báo. Sau lệnh/timeout, so PID trước/sau và gửi TERM cho Chrome headless mới, detached ppid 1, profile tạm, không client CDP; giữ Chrome có trước. reap chỉ chọn root ppid 1, tuổi đủ, profile tạm và lsof xác nhận không kết nối CDP; pipe/port 0/thiếu dữ liệu giữ nguyên. Reap không có dry-run sẽ gửi TERM, không xoá profile. Không in command line hay đường dẫn profile. Nền tảng khác có thể trả unavailable (2).

Policy SessionStart đã có luật trình duyệt và chặn mở thêm phiên khi busy/hot. Chưa đo Metal so với SwiftShader; xem [nghiên cứu](../../../docs/research/2026-11-13-headless-heat/report.md).

### Social listening — hh-heat

Tóm tắt: ngày 13/11/2026 xem [issue Playwright về Chrome mồ côi](https://github.com/microsoft/playwright-cli/issues/312) và [thảo luận Puppeteer khi reload](https://www.reddit.com/r/nextjs/comments/1g6sdsk). Cộng đồng ghi nhận tiến trình trình duyệt còn sống sau controller; issue đề xuất dò theo user-data-dir. Thiết kế bổ sung so PID trước/sau ngoài process group, kiểm lại profile tạm, orphan và CDP trước TERM; không dọn Chrome có trước. Đây là báo cáo cộng đồng, chưa kiểm chứng độc lập; kiểm chứng triển khai dùng fixtures giả, không chạy Chrome thật.
