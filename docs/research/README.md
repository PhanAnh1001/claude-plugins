# Nghiên cứu

## Tóm tắt

- **Mục đích:** lưu các nghiên cứu nhiều nguồn của repo, có dẫn nguồn và ngày dữ liệu.
- **Số nghiên cứu:** 3.
- **Thêm mới:** tạo `docs/research/<YYYY-MM-DD>-<slug>/report.md` + `notes/<topic>.md` theo skill summary-first-docs:saving-research, rồi thêm mục ở đầu danh sách dưới (mới nhất trước).

## Danh mục

- [2026-11-13 — Nhiệt và Chrome headless](2026-11-13-headless-heat/report.md): khóa trình duyệt, cleanup bảo thủ; chưa có benchmark.

### 2026-11-11 - So sánh Paperclip và hybrid-hands

- **Câu hỏi:** Paperclip điều phối agent khác hybrid-hands thế nào, ưu điểm nào áp dụng được?
- **Kết luận:**
  - Paperclip là control plane MIT với ticket + execution lock, budget có auto pause, audit log và config rollback ([nguồn](https://github.com/paperclipai/paperclip), 11/2026).
  - Nên áp dụng ưu tiên Cao: audit log JSONL, budget USD~ cứng, khoá claim theo brief (suy luận).
  - Ưu tiên Vừa: revision cấu hình + rollback, goal ancestry trong brief (suy luận).
  - Không học heartbeat tự trị, org chart nhiều cấp, server/DB riêng (suy luận).
- **Liên kết:** [report](2026-11-11-so-sanh-paperclip/report.md), [notes](2026-11-11-so-sanh-paperclip/notes/paperclip.md)

### 2026-11-10 - Switch model, effort, provider, tài khoản

- **Câu hỏi:** hybrid-hands + Paseo, cc-switch và OpenMausBot switch khác nhau thế nào; dùng chung hay tách thư mục account?
- **Kết luận:**
  - Giữ tách credential/state, overlay tài sản tĩnh (suy luận).
  - hybrid-hands đổi model/account bằng phiên mới, cô lập per-process (không có nguồn internet, nguồn nội bộ: `AGENTS.md`).
  - cc-switch có cả per-session và default-slot swap; không dùng swap toàn cục song song (suy luận từ [note](2026-11-10-switch-model-provider-account/notes/cc-switch.md), có nguồn gốc 11/2026).
  - OpenMausBot truyền model/effort theo lượt, nhưng chia sẻ nhiều thư mục Codex ([nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex-shared-home.ts#L1-L11), 11/2026).
  - Reconcile settings/plugin cần chốt L2; chưa triển khai.
- **Liên kết:** [report](2026-11-10-switch-model-provider-account/report.md), [notes](2026-11-10-switch-model-provider-account/notes/)

### 2026-11-10 - Bảo mật OpenMausBot và so sánh với hybrid-hands + Paseo

- **Câu hỏi:** có nên cài OpenMausBot lên user macOS đang chạy hybrid-hands + Paseo?
- **Kết luận:**
  - Không cài lên máy chính; giữ hybrid-hands + Paseo cho điều phối agent code (suy luận từ các nguồn dưới).
  - Chế độ full bỏ sandbox và duyệt [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L163-L168) (11/2026).
  - Có lỗ đã biết chưa vá cho phép lách thẻ duyệt Full-access [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md#L24-L27) (11/2026).
  - Đọc token OAuth Claude từ Keychain [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/plan-usage.ts#L736-L790) (11/2026).
  - Nếu cần, chỉ chạy trong VM/user riêng với tài khoản phụ.
- **Liên kết:** [report](2026-11-10-openmausbot-bao-mat/report.md), [notes](2026-11-10-openmausbot-bao-mat/notes/)
