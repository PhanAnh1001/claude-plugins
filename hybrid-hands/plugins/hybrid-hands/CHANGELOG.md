# Changelog

## 0.33.1 — 2026-11-09

- `ls` bỏ qua riêng phiên có agent đã xoá hoặc workspace lệch, vẫn reconcile các phiên hợp lệ khác.
- Phiên phụ Codex/Paseo vẫn archive workspace riêng khi done. Khi người dùng unarchive agent, `ls`/watch mở lại workspace nếu recovery có `action:"unarchive"`; `action:"restore"` không mutation.
- Guard `paseo_revived` giữ status `done`, ngăn `.done` cũ tự finish lại phiên vừa mở; lỗi giữ nguyên state để vòng sau retry.
- `ls` đọc archive state theo lô một lần, chỉ reconcile agent đổi archive state; snapshot lỗi/thiếu thì giữ state và warning một dòng. Watch giữ flow một phiên; rearchive chỉ tác động workspace riêng sau private check.

## 0.33.0 — 2026-11-09

- Thêm sổ tài khoản Claude `v1`/`v2`/`v…`, alias backend cũ và `hand-ext pick`; auto chọn theo order dsh → Codex low → Claude v1 low → Claude v2 low, giữ chặn ngày theo tài khoản.
- Phiên chính/phụ Claude chọn `--account` qua cùng loader tài khoản của hand-ext, nhận cả override backend canonical và legacy; không thêm nguồn cấu hình người dùng.
- Giữ model dsh `deepseek-v4.1-flash`, mặc định effort `off`; template ánh xạ `off: null` để tắt thinking, giữ low/high/max và nguồn giá canonical. User-Agent lấy version plugin 0.33.0.
- Đồng bộ policy Opus → Sol → hand theo tài khoản và order; rút hook mỗi prompt, giảm policy trùng và đưa phần tĩnh của brief lên đầu để dùng cache tiền tố.

## 0.32.2 — 2026-11-09

- Kiểm freshness quota theo thời điểm hoàn tất đọc nguồn, giữ timestamp quan sát gốc; không loại nhầm mẫu Paseo được tạo trong lúc lệnh đang chạy. Cho phép poll sớm một lần khi cache thành công đã hết hạn.
- Giữ baseline hiệu chỉnh cùng account/reset khi mốc reset chỉ jitter tối đa 2 giây; không nối các cửa sổ tuần khác nhau.

## 0.32.1 — 2026-11-09

- Sửa nguồn token/USD Claude ngoài khi chạy plugin từ bản cài đặt: cho phép tìm mã helper statusline qua cài đặt tài khoản chính nếu tài khoản ngoài chưa cài statusline, vẫn chỉ quét transcript `~/.claude-hand`. Giữ ưu tiên helper hiện có và override tường minh; helper thiếu/hỏng trả unknown.

## 0.32.0 — 2026-11-09

- Thêm hiệu chỉnh Claude ngoài (`~/.claude-hand`): ưu tiên live `rate_limit_event`/cache trực tiếp còn mới, dự phòng usage report Paseo khớp metadata auth Claude chính thức (kể cả Pi đăng nhập); chỉ lưu identity đã hash, không lưu email thô/credential, không cần đổi settings cho nguồn trực tiếp. USD~ chỉ từ token transcript Claude hand và giá canonical, tách input/output/cache đọc/cache ghi 5m/1h.
- USD~/1% tuần dùng chênh lệch USD và quota của hai quan sát hợp lệ cùng tài khoản/reset; quota số nguyên cần delta ≥2 điểm phần trăm, nguồn có phần lẻ thực cần delta dương; chưa đủ ngưỡng/mẫu, stale hoặc model thiếu giá thì `?`, không dựng baseline lịch sử. Lấy mẫu khoảng 120 giây, cache Paseo tối đa 5 phút. Panel/sidebar thêm quota 5h/tuần Claude ngoài, rate và các nhóm token tổng hợp transcript; USD~ lượt cũ thiếu cache split/session correlation vẫn unknown.
- Theo lựa chọn người dùng, dùng chung rate này để ước tính phần Claude riêng giữa các tài khoản khi rate sẵn sàng; đây là ước tính subscription, không phải hoá đơn hay đồng hồ riêng chính xác của từng tài khoản. Giữ độ chính xác nguồn, hiển thị % một chữ số lẻ không tăng độ chính xác của API.

## 0.31.6

- Sửa workspace phiên phụ vẫn hiện sau khi gom chung project: xác minh workspace ID đã lưu và không có agent dùng chung trước mutation; archive agent rồi workspace riêng, yêu cầu archivedAt hợp lệ. Lỗi cleanup retry, ls/watch đối soát done cũ; không archive project hoặc workspace phiên chính.

## 0.31.5

- Panel/Cây phiên chỉ hiện root đang chạy theo live/status; root đã kết thúc hoặc unknown ẩn cả cây, phiên phụ thiếu parent không thành root. Tổng usage toàn máy vẫn giữ nguyên.
- Tên phiên/hand ưu tiên description ngắn nếu snapshot cung cấp, rồi ai_title và tên/label có nghĩa; thiếu thì `?`, không lấy ID làm tên. Giữ giới hạn 6 phiên phụ, pool 4 và tóm tắt/màu trạng thái.

## 0.31.4

- Panel agent và màn hình Cây phiên mở tối đa 6 phiên phụ mỗi cây chính, ưu tiên đang chạy rồi mới nhất; phần dư giữ tóm tắt running/done/failed/unknown và màu trạng thái hiện có. Pool subagent/hand vẫn tối đa 4.

## 0.31.3

- Panel agent và màn hình Cây phiên dùng chung thứ tự forest: parent tường minh chứa phiên phụ dù input child đến trước; phiên phụ thiếu parent đứng sau mọi root, không đoán parent từ cwd.
- Tên subagent ưu tiên description ngắn thay type/id; native đọc description/title/agent_path/nickname từ metadata, không đọc prompt để đặt tên. Giữ mô tả gốc, pool 4, usage/status/counts.
- SDK Paseo 0.15.0 không có hook chỉnh hierarchy/order/label của danh sách sidebar native; nút sidebar chỉ mở Cây phiên. Không sửa bundle native hoặc archive/đổi tên agent runtime; brain cần cập nhật plugin và reload.

## 0.31.2

- hh-ps khám phá phiên Codex gốc chưa có side-session state từ metadata rollout cục bộ theo repo và thời gian quan sát; gắn native children theo parent thread, giữ alias pinned và không suy diễn status/model/usage. Không gọi RPC/API hay tạo state runtime.
- Rollout fork giữ identity/parent từ session_meta đầu, không để metadata cha kế thừa ghi đè; bỏ qua activity/model/token kế thừa trước mốc child và giữ quota riêng unknown khi chưa tách được sample kế thừa.

## 0.31.1

- Phiên chính Sol chỉ được archive bởi người dùng; gom phiên phụ theo project và dọn project legacy.
- Bổ sung luật sau sửa plugin: validate/test hẹp/review, tăng version và cập nhật qua công cụ chính thức cho mọi repo đang dùng; kiểm version/path nạp thực tế và báo reload khi cần.

## 0.31.0

- Thêm `side-session start --main` mở brain Sol Codex trên Paseo tại repo chính, prompt tùy chọn, effort mặc định high; không fallback screen, handoff/watchdog hay slot phiên phụ. State giữ role tương thích và stop archive lịch sử; bổ sung template và hướng dẫn phiên chính.

## 0.30.0

- GPT machine USD~ dùng token delta có timestamp quan sát được trong cửa sổ reset quota tuần hiện tại ở `~/.codex-hand/sessions` và `archived_sessions`, khử trùng thread/event, không cộng ledger trùng. Metadata-only thread không làm tổng observed thành unknown; không có event trong cửa sổ, event thiếu baseline/timestamp/giá hợp lệ hoặc file không đọc được thì `?`. Tổng chỉ phản ánh nguồn cục bộ đo được, không bảo đảm đủ mọi hoạt động tài khoản; USD~ là ước tính offline subscription, không phải hoá đơn.
- Phần riêng session pinned rollout/native child đo biến động quota tuần từ ít nhất hai sample `rate_limits` hợp lệ, không giảm trong cùng reset hiện tại. `Usage.week_pct_source` mặc định rỗng; nguồn known `codex_rate_limits_delta`, `week_pct_estimated=false`, nhãn `GPT riêng (đo) N% tuần`. Khoảng đo có thể gồm phiên đồng thời, không quy riêng độc quyền; thiếu nguồn/qua reset hiện `?`, không suy quota từ token/USD.
- GPT account có duration tường minh phân loại 5h bằng `window_minutes=300`, không đổi nhãn primary tuần `10080`; source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần. Phép đo GPT phần riêng mới bắt buộc duration tuần tường minh `window_minutes=10080`. Claude 5h kiểm freshness/reset numeric hoặc ISO của cache/live sẵn có; thiếu/hết hạn hiện `?`. Statusline dùng chung helper nguồn usage và bump phiên bản riêng.
- Giữ nguồn giá canonical duy nhất, không fallback model lạ; giữ colors/layout/counts/pool và unknown legacy.

## 0.29.0

- hh-ps đọc metadata native Codex child từ rollout cục bộ trong đường dẫn cố định ~/.codex-hand/sessions (không dùng override CODEX_HOME để giữ cô lập tài khoản), không gọi daemon RPC/API; đối chiếu parent thread qua pinned Sol rollout về sid canonical và xuất trong Session.subagents với provider codex, agent_type native-codex.
- JSON giữ status/provider/parent canonical của native cùng exit_code nullable cho subagent và hand; field mới có default cuối dataclass để giữ tương thích. Không suy completed từ mtime hoặc im lặng.
- Native chung pool tối đa 4 và số đếm X✓ Y✗ trong panel: completed → ✓; failed/errored/cancelled hoặc exit_code khác 0 → ✗, unknown → ?. Lỗi có precedence.
- Token chỉ từ nguồn native, USD~ theo giá canonical; thiếu nguồn hiện ?, không bịa quota hay tạo run/meta/report/token ledger hand-ext.

Panel agent/sidebar Paseo: running/busy dùng theme accent nếu accent là xanh dương, nếu không dùng màu xanh dương dự phòng bảo đảm tương phản ở giao diện sáng/tối; done dùng statusSuccess (xanh lá); failed/exit khác 0/timeout/killed dùng statusDanger (đỏ); idle/silent dùng statusWarning (vàng); lost/unknown dùng foregroundMuted (xám). Số đếm ✓ xanh lá, ✗ đỏ. Dòng đã kết thúc hiện giờ local HH:MM, thêm dd/mm nếu khác ngày; running không hiện giờ kết thúc. Không hiện giờ bắt đầu. Mỗi dòng hiện USD~ riêng, provider Claude/GPT và usage.week_pct riêng trong tuần; thiếu hiện ?. Không thay phần riêng bằng phần trăm tài khoản hoặc suy quota GPT.

Khối riêng ở đầu panel/sidebar hiện tổng USD~ toàn máy trong tuần của Claude/GPT và phần trăm tài khoản 5h/tuần, thay quota ở dòng root. JSON tree.machine_usage:[{plan,window:"tuần",usd,source}] cung cấp tổng toàn máy, không cộng các dòng cây đang hiển thị. Claude dùng phép tổng hợp tuần cục bộ hiện có. GPT đọc rollout trong đường dẫn cố định ~/.codex-hand/sessions và ~/.codex-hand/archived_sessions, khử trùng theo thread, chỉ cộng token delta được chứa trong cửa sổ tuần hiện tại; thiếu cửa sổ/giá/nguồn giữ unknown. Không cộng trùng ledger và rollout. Riêng gắn native child vào cây vẫn chỉ đọc sessions.

Giữ tối đa 4 phiên phụ, pool chung 4 agent, lựa chọn phiên gần nhất, số đếm phần ẩn và loại nhóm orphan. Addon này chỉ áp dụng panel/sidebar Paseo; hh-tree-pane giữ bố cục, chỉ nhận sửa tương thích native status/exit/unknown ban đầu.

## 0.28.0

- User-Agent của hand-ext dsh lấy phiên bản từ manifest plugin, tránh lệch phiên bản khi release.
- Sửa cc-switch --self báo nhầm PID TUI đã được reap còn sống khi tiến trình kết thúc giữa liveness probe và ps; kiểm tra lại PID khi ps không còn state.
- Panel agent/sidebar Paseo gọn: icon, tên, model·effort, elapsed, USD~; quota tài khoản mỗi account plan chỉ ở root, bỏ header/footer và nhãn lặp.
- Mỗi cây hiện tối đa 4 phiên phụ, chỉ phiên hoạt động gần nhất mở tối đa 4 subagent/hand có cha; phần cũ gộp done/error/running/unknown, không mất số đếm phiên ẩn. Running ưu tiên, tie giữ thứ tự duyệt cây/agent đầu vào; lỗi có precedence trên trạng thái running cũ.
- Native Codex child còn phụ thuộc nguồn JSON hh-ps; không tự suy dữ liệu hoặc quota. Không đổi hh-ps, hh-tree-pane hay statusline.

## 0.27.0

- Quyết định A: ưu tiên tab native cho Sol trên Paseo khi backend thực theo order là codex `gpt-6.1-sol` low và tools hỗ trợ model/effort riêng; `fork_turns=none`, full brief/luật dữ liệu, executor không recursion. Tổng native + hand-ext không vượt `ext_hand.max_parallel` (1..4), cùng file tuần tự; không đổi code/slots hand-ext, config hay policy Opus/Claude/dsh.
- Đã kiểm chứng local: Codex CLI 0.166.0 + Paseo CLI 0.15.0, child completed đúng parent và timeline 3 dòng assistant. Tab/history native được giữ; không archive top-level/parent. B chưa triển khai vì A đạt.
- Bridge read-only `subagents`/`subagent-timeline` và Python wrappers xác minh child thuộc đúng parent và đọc history; kiểm endpoint bằng `expectedTargetKey`, không tạo hay archive agent.
- Phân biệt báo cáo/usage native/Paseo với run/meta/report/token ledger hand-ext; thiếu hiện `?`, không bịa quota. Thiếu capability trước spawn dùng auto như cũ; unknown sau spawn không tạo duplicate writer.

## 0.26.0

- Usage panel cho session/subagent/hand/side provider: model, effort, USD~ offline, quota tài khoản 5h/tuần, ended hoặc đang chạy và elapsed; thiếu nguồn hiện `?`, không suy token thành quota GPT. Phần riêng hand tuần có nhãn riêng khi có nguồn.
- Giá canonical [`config/model-prices.json`](config/model-prices.json), override `HYBRID_HANDS_PRICING_FILE`, lưu date/source xác minh ngày 2026-11-07; cache Claude theo cấu hình, model lạ không fallback. USD~ subscription là ước tính, không phải hoá đơn.
- `hh-ps --once`; mặc định đủ việc chạy/vừa xong theo since, không gấp 3 hay ẩn cây đã xong. Text/JSON giữ orphan hand-ext; cả hai giao diện cây bỏ nhóm này.
- Gắn cha từ `CODEX_THREAD_ID`/`PASEO_AGENT_ID` về sid canonical; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời. Áp dụng mọi loại agent/backend, gồm Sol Codex/Claude/dsh.
- Sổ usage statusline version 4 có fingerprint; USD~ Claude là ước tính, không phải chi phí chính xác hay hoá đơn.
- UI bỏ giờ bắt đầu; JSON/meta giữ started và metadata parent canonical, ended, status, exit_code, tokens, effort, duration. Legacy unknown không bịa giá trị.

## 0.25.3

- Giữ phiên có dòng `user` khi chọn phiên gần nhất để chuyển terminal/Paseo.

- Mặc định 4 Sol; mỗi Sol tối đa 4 hand nền độc lập, cùng file tuần tự, đợi đủ rồi Sol review. Scope uuid riêng qua screen/Paseo; exit 8 chờ slot, exit 7 doctor trước dự phòng. Giới hạn cấu hình số nguyên 1..4.

- Doctor Codex không chặn khi model, effort hoặc sandbox trong config thiếu/lệch: CLI override mỗi lượt, dùng chung home với Sol và không ghi config. Cài đặt, đăng nhập gói và service_tier legacy vẫn bắt buộc.
- Prompt Sol bắt buộc giao code/test/tài liệu L0/L1 qua auto theo ext_hand.order; chỉ tự viết khi hand-ext lỗi (ghi lý do/mã thoát) hoặc cần secret. Exit 7 phải doctor trước dự phòng, chỉ dùng ví dụ codex medium khi xác nhận dsh hết quota.
