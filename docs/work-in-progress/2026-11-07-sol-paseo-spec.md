# TÓM TẮT QUYẾT ĐỊNH 1 TRANG

L1, Sol tự quyết, Opus đọc bàn giao. Mục tiêu: Sol mới do Paseo sở hữu ngay khi start để điện thoại thấy hội thoại và gửi lệnh; không nhập lại thread đang có TUI writer.

| Phương án | Quyết định / lý do |
|---|---|
| TUI + import lúc đang chạy | Bỏ: active writer; import còn lọc cwd workspace. |
| `paseo run --provider codex-hand` đơn thuần | Thiếu providerOptions cho sandbox/writable roots; mode bypass mở rộng quyền quá mức. |
| Client đi kèm Paseo tạo workspace + agent | Chọn: cùng daemon/protocol với CLI/app, nhận providerOptions; không sửa server hay credentials. |

`start codex` thử kết nối daemon, tạo git worktree như cũ, đăng ký workspace directory chính thức cho cwd đó, tạo agent provider `codex-hand`, env CODEX_HOME đúng cfg.codex_home, model/effort từ override hoặc mặc định gpt-6.1-sol/high. Không kế thừa PASEO_AGENT_ID/PASEO_WORKSPACE_ID gây chạy nhầm workspace. Kết nối không được thì cảnh báo và screen cũ; lỗi tạo agent sau khi đã gửi request thì fail rõ, tuyệt đối không tạo writer thứ hai.

`ls`/max_parallel/watch dùng trạng thái agent khi transport=paseo, screen khi cũ; idle vẫn là phiên còn điều khiển được. Mất kết nối là unknown, không kết luận dead hay bỏ qua max_parallel. `attach` tên Paseo chỉ hướng dẫn mở agent trong app hoặc `paseo attach`; screen giữ nguyên. `handoff`/watch nhận `<handoff_dir>/<name>.done`, trạng thái done dừng watchdog, không xoá hội thoại. `stop` interrupt đúng agent + watchdog của nó, giữ worktree và agent để xem lại. State cũ vẫn đọc được, bổ sung transport/agent/workspace/thread id khi có.

Sandbox giữ workspace-write, approval never, network=true, writable roots dùng helper hiện có. Không dùng mode bypass. Paseo 0.15.0 schema providerOptions không nhận model_auto_compact_token_limit: đặt duy nhất khóa top-level này trong config.toml của CODEX_HOME hand bằng helper bảo toàn phần còn lại; không đọc auth, không đổi tài khoản, không API key. codex_profile khác rỗng không được âm thầm bỏ qua: báo chưa hỗ trợ trên đường Paseo.

Chốt sau review: helper compact dùng RPC native `config/value/write` trong app-server ngắn chỉ cấu hình, không tạo thread/turn, không tự sửa TOML bằng regex. Probe home tạm đã xác nhận giữ comment và chuỗi nhiều dòng. Giữ watchdog screen hiện có; chỉ bỏ Codex TUI screen, không thêm quản lý PID qua ps/kill. Lỗi tạo agent chưa rõ kết quả phải giữ chỗ max_parallel cho đến reconcile/stop.

Đếm token giữ tổng input−cached+output cho chi tiêu và last input+output cho context, native auto compact=272000; không cap Codex theo tổng chi. Giữ ghim rollout 4.11 một lần, ưu tiên thread id daemon nếu lấy được, không chọn rollout hand mới nhất. Không sửa hand_ext: sổ codex_usage 5.2 tiếp tục chỉ ghi lượt hand codex; phiên Sol lấy rollout ghim, không thêm dòng trùng sổ. Dự phòng 429 5.1 của `hand-ext --backend auto` giữ nguyên; lỗi provider/429 của agent Paseo không tự mở TUI.

Không sửa file sol-54 (statusline). sol-53 đã done nhưng đang có diff skill Paseo mục 4: chỉ sửa phần transport/import mới ở mục khác và ghi điểm ghép cho Opus. Không có AGENTS.md/CLAUDE.md tại repo/plugin hay ancestor áp dụng; hai file dev-workflow không áp dụng. Không sửa plan gốc hybrid-hands/docs ngoài phạm vi; spec này ghi nhóm 5 bổ sung.

## Tiêu chí chấp nhận và test tối thiểu (3 ca)

1. Daemon sẵn sàng: start Codex tạo workspace/agent codex-hand với cwd worktree, model/effort, sandbox/roots chính xác; state lưu agent id, không screen TUI, max_parallel tính agent sống.
2. Daemon vắng: screen cũ + cảnh báo. Daemon đã nhận create nhưng lỗi: fail rõ không screen để tránh writer trùng.
3. Watch/ls/attach/stop/handoff tuyến Paseo hoạt động; `.done` vẫn hoàn tất và ghim rollout không trôi sang hand khác.

Test hẹp trong lúc làm bằng unittest file mới; tối đa 3 test methods mới, tăng assert khi cần. Full `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -q` do Sol chạy ĐÚNG MỘT LẦN ở cuối sau live/review. dsh không chạy full. Kiểm thật do Sol: phiên thử ngắn qua code mới (được yêu cầu riêng, không mở thêm phiên công việc), ghi .done, ls/logs/send qua daemon, xác nhận workspace/cwd, cleanup chỉ tài nguyên thử; không restart daemon. App trên điện thoại chưa thể quan sát trực tiếp: phân biệt bằng chứng daemon/workspace và xác nhận UI còn cần người dùng.
