# Ghi chú nguồn: hybrid-hands và Paseo

## Tóm tắt

- **Mục đích:** ghi các sự kiện về hybrid-hands + Paseo dùng để so sánh với OpenMausBot.
- **Nguồn:** không có nguồn internet, nguồn nội bộ (tài liệu trong repo này, 11/2026).
- **Chưa xác minh:** schedule/heartbeat của Paseo không có trong tài liệu hybrid-hands.

## hybrid-hands

- Mô hình brain/hand/phiên phụ; backend theo thứ tự dsh → codex → claude-v1 → claude-v2; guard v1 5%/ngày. Không có nguồn internet, nguồn nội bộ: [hybrid-hands/README.md](../../../../hybrid-hands/README.md) (dòng 108-117, 290) (11/2026)
- Cô lập tài khoản ~/.codex-hand và ~/.claude-hand, worktree, không API key (dsh dùng go.key quyền 600), luật dữ liệu, ledger USD~/quota, hh-ps/hh-tree-pane. Không có nguồn internet, nguồn nội bộ: [hybrid-hands/README.md](../../../../hybrid-hands/README.md) (dòng 317-341, 375-421) (11/2026)

## Paseo

- Daemon 127.0.0.1:6767, relay E2E tắt mặc định, ghép điện thoại do người dùng tự làm, không tự khởi động khi login. Không có nguồn internet, nguồn nội bộ: [skills/paseo/SKILL.md](../../../../hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md) (dòng 79-108) (11/2026)
