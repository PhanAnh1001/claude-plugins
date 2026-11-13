# So sánh điều phối agent: Paperclip và hybrid-hands

## Tóm tắt

- **Mục đích:** xem Paperclip ([README](https://github.com/paperclipai/paperclip), 11/2026) có ưu điểm nào nên áp dụng cho hybrid-hands.
- **Kết luận:** hybrid-hands đã mạnh ở đa backend rẻ, guard quota và cây giám sát. Paperclip hơn ở 4 điểm: khoá claim việc bền, budget cứng có pause, audit log + revision config, gắn mục tiêu (goal) vào brief.
- **Đề xuất ưu tiên Cao (suy luận):** (1) audit log append-only cho lệnh mutating của hand-ext/side-session; (2) budget cứng USD~ theo tuần/brief, pause khi vượt; (3) khoá claim theo brief ID chống writer trùng.
- **Không nên học:** chạy agent tự trị theo heartbeat không người duyệt, org chart nhiều cấp, server/DB riêng.
- **Nguồn:** ghi chú fact ở [notes/paperclip.md](notes/paperclip.md); thông tin hybrid-hands từ `AGENTS.md` và `hybrid-hands/README.md` (nguồn nội bộ, không có link internet). Mọi đề xuất là suy luận, chưa đo.

## 1. Paperclip là gì

Control plane open-source (MIT), self-hosted, coi tập agent như một công ty: org chart, ticket, budget, heartbeat, duyệt của board, dashboard, audit log, adapter cho nhiều loại agent ([nguồn](https://github.com/paperclipai/paperclip), 11/2026). Chi tiết: [notes/paperclip.md](notes/paperclip.md).

## 2. Bảng so sánh

| Trục | Paperclip ([nguồn](https://github.com/paperclipai/paperclip), 11/2026) | hybrid-hands (nội bộ) |
|---|---|---|
| Tổ chức/vai trò | Org chart, role, reporting line, permission | 3 tầng cố định: brain Opus → Sol lead → hand executor |
| Giao việc & chống trùng | Ticket, 1 assignee, execution lock, blocker dependency | Brief file theo khuôn; max_parallel 4; "unknown sau spawn reconcile, không duplicate writer"; cùng file thì tuần tự (do người điều phối giữ) |
| Ngân sách | Budget company/agent/project, cảnh báo, auto pause | USD~ ước tính offline, guard v1 8%/ngày, quota 5h/tuần hiển thị; không có trần USD cứng |
| Heartbeat & trạng thái | Agent thức theo việc/lịch, ticket giữ trạng thái | Chạy theo lệnh; trạng thái qua file .done, report, meta hand-ext |
| Governance | Approval gate việc và hire; pause/reassign/stop | L2/L3 người dùng duyệt; Sol review; giao lại 1 lần rồi đổi backend |
| Giám sát/UI | Dashboard web + mobile | hh-ps, panel/sidebar Paseo (có app điện thoại), statusline |
| Audit & rollback | Activity log bền; config revision + rollback | Git cho code; `hand-ext config --json` hiện nguồn key; accounts sync có backup; không có audit log tập trung |
| Đa backend | Adapter Claude Code, Codex, Cursor, Gemini CLI, HTTP... | dsh → codex → claude-v1 → claude-v2, native khi đủ điều kiện; tối ưu chi phí subscription |
| Gắn mục tiêu | Goal ancestry task → project → goal | Brief có MỤC TIÊU; plan/spec ở docs; không có liên kết máy đọc |

## 3. Ưu điểm có thể áp dụng (suy luận)

1. **Audit log append-only** — Cao. Ghi mỗi `hand-ext run/pick`, `side-session start/stop/tidy --apply`, `accounts sync --apply`, `models set`, `parallel-subagents on|off` thành 1 dòng JSONL (thời điểm, lệnh, backend, run id, exit code, không giá trị secret) vào thư mục state hybrid-hands. Lợi: truy vết vì sao chọn backend/ai bật mode. Chi phí: thấp; rủi ro lộ dữ liệu nếu log cả argv, cần lọc.
2. **Budget cứng có pause** — Cao. Thêm `ext_hand.budget.{week_usd,brief_usd}`; `hand-ext pick` trả `skip_reason=budget` khi tổng USD~ tuần (đã có trong `machine_usage`) vượt, panel hiện cảnh báo ở 80%. Lợi: chặn tiêu vượt như guard v1 nhưng tổng quát. Rủi ro: USD~ là ước tính, có thể `?` → phải định nghĩa unknown = không chặn hay chặn.
3. **Khoá claim theo brief** — Cao. `hand-ext run` tạo lock theo hash brief/PHẠM VI GHI; run thứ hai trùng phạm vi bị exit riêng. Lợi: biến luật "cùng file tuần tự" thành cơ chế. Rủi ro: lock mồ côi khi chết → cần TTL + kiểm PID (giống fix stale claim).
4. **Revision cấu hình + rollback** — Vừa. `hand-ext models`/`config` ghi bản trước vào `.history/`, thêm `hand-ext config rollback`. Lợi: lùi nhanh khi đổi order/model sai. Rủi ro: không áp cho settings/credential (cấm sửa).
5. **Goal ancestry trong brief** — Vừa. Thêm trường `MỤC TIÊU GỐC: <plan/spec path#mục>` vào template brief (`templates/`), hh-ps hiện nhãn plan. Lợi: hand hiểu "vì sao", brain tra lại plan. Chi phí: thấp.
6. **Blocker dependency giữa side-session** — Thấp. `side-session start --after NAME` chờ .done. Lợi: chuỗi việc tuần tự tự động. Rủi ro: tăng độ phức tạp, dễ treo nếu .done không tới.
7. **Pause/reassign từ panel** — Thấp. Nút pause/đổi backend trên panel Paseo. Lợi: điều khiển từ điện thoại. Rủi ro: thao tác nhầm, cần xác nhận.

## 4. Không nên học

- **Heartbeat tự trị / "zero-human company":** trái luật L2/L3 người dùng duyệt và không vòng chờ vô hạn; tốn quota subscription.
- **Org chart nhiều cấp, "hire" agent:** mô hình 3 tầng đủ cho 1 người dùng, thêm cấp tăng token điều phối.
- **Server + DB + dashboard web riêng:** đã có Paseo + hh-ps; thêm hạ tầng là thêm bề mặt tấn công và bảo trì.
- **Adapter HTTP/agent tuỳ biến tràn lan:** hybrid-hands cố ý giới hạn backend subscription, không API key trả phí.
