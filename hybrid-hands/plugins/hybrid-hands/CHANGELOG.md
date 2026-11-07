# Changelog

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
