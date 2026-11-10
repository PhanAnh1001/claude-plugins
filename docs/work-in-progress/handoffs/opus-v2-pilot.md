# Kết quả phiên chính Opus v2: live pilot hand agent Paseo, archive workspace, báo tiktok

## Tóm tắt

- **Kết quả: xong.** hybrid-hands lên **0.36.1** (main `b7e2f92`, đã push). Pilot managed Paseo hand đạt mọi gate live, kể cả tab Subagents trên UI (người dùng xác nhận khi xem demo). Đã báo tiktok trạng thái cuối (`e9f97c57`, kèm tin ngắn cho `db52a99b`).
- **Runtime (người dùng cho phép):** `provider setup --apply` thêm 4 provider `hh-hand-*` vào `~/.paseo/config.json` (backup `config.json.backup-m6rk82gu`); `paseo daemon reload` nóng, không restart.
- **Cài đặt:** account v2 `~/.claude-hand` đã cài hybrid-hands bằng công cụ chính thức (người dùng đồng ý). Cả v1/v2 nạp 0.36.1 ở claude-plugins và live-tiktok-games.
- **Cấu hình repo:** `.claude/hybrid-hands.json` claude-plugins `mode=auto` đã commit `ec05d77` (người dùng duyệt).
- **Quyết định L2 người dùng duyệt (09/11):** recover xác nhận tay cho record cũ (`--legacy-attest`); hành vi archive agent + workspace khi xong, hiện lại khi giao lại (thay Q4); auto-compact phiên chính Claude 272000.
- **Demo subagent (yêu cầu người dùng):** Sol phụ `demo-subagent` tạo hand managed `5cd5a742`, chạy 133 s, tự archive child+workspace, rồi phiên phụ tự archive — đúng 0.36.0.
- **Còn mở:** không còn việc; phiên Claude đang mở cần mở mới để nạp 0.36.1 và nhận ngưỡng auto-compact 272k. Người dùng chuẩn bị clear phiên này.

## 1. Bản phát hành

| Version | Nội dung chính | Phiên Sol |
|---|---|---|
| 0.35.1 | Workspace ID `wks_…`; validate schema trước network; `managed recover`; gateway discovery unbound không thực thi | hpa-pilot, hpa-pilot2, hpa-pilot3 |
| 0.35.2 | Recover khi parent archived; metadata bound | hpa-pilot3 |
| 0.35.3 | Khớp envelope prompt ACP; marker từ chối ở gateway | hpa-pilot3 |
| 0.35.4 | Theo dõi tiến trình con và marker env khi stop | hpa-pilot3 |
| 0.35.5 | Sửa race EINVAL khi quét env macOS; `post_hoc_reverify` | hpa-pilot4 |
| 0.35.6 | `--legacy-attest`; intent bị từ chối admission → `not_admitted` | hpa-pilot5 |
| 0.36.1 | Tên dễ đọc trên sidebar: `<tên> · Sol phụ`, `<cha> › hand <backend> · <label>`; `side-session tidy --names` | ws-names |
| 0.36.0 | Archive agent + workspace khi xong, restore khi giao lại (`side-session send`, `managed followup`, `side-session tidy`); auto-compact main Claude 272000 | ws-archive, ws-archive-hand |

Full suite cuối 526 OK; `claude plugin validate` mặc định đạt (LICENSE/ICON thiếu từ trước).

## 2. Gate pilot

- Dispatch (codex, dsh, claude-v2), placement, hh-ps 1 dòng có token/USD~: **PASS**.
- Stop giữa chừng: **PASS** trên 0.35.6 (setsid descendant bị dọn, certificate confirmed, slot tự nhả).
- Review/archive/followup epoch 2: **PASS**.
- Tab Subagents UI: **PASS** (người dùng xác nhận khi xem demo `demo-subagent`).
- Record kẹt `597c17ca…` đã recover attested; hai intent cũ thành `not_admitted`.

## 3. Sidebar

Opus đã archive tay 33 workspace có mọi agent đã xong (xác định theo `workspaceId`, không theo cwd), cùng agent/workspace `ws-archive-hand` mà watcher cũ để sót. Thư mục giữ nguyên (Paseo chỉ xoá worktree do chính Paseo sở hữu). Còn 4 workspace local của phiên chính. Từ 0.36.0 việc này tự động.

## 4. Ghi chú

- Một lượt hand dsh (hpa-pilot4) tự chạy `pgrep -fl`, làm lộ command line các phiên khác; Sol không dùng dữ liệu đó, brief sau đã cấm.
- Giới hạn còn lại: macOS không có containment tuyệt đối (tiến trình vừa xoá marker env vừa thoát cây có thể sót).
