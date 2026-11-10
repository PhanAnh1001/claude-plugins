# Bổ sung brief ps-toggle-l0 (người dùng chốt 10/11/2026)

Thêm lệnh cấp plugin, gọi được ngay trong phiên Claude Code:

- Tạo `hybrid-hands/plugins/hybrid-hands/commands/parallel-subagents.md` theo cùng khuôn `commands/to-paseo.md`/`to-term.md` → `/hybrid-hands:parallel-subagents [on|off]`.
- Command chỉ là vỏ mỏng: chạy `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext parallel $ARGUMENTS` trong cwd repo hiện tại, in kết quả, nhắc mở phiên mới khi đã đổi. Không tự chạy `on` khi người dùng không gõ đối số; không chứa logic ghi config riêng (CLI vẫn là nguồn duy nhất).
- Câu AGENTS.md:31 và README nêu cả hai cách: `/hybrid-hands:parallel-subagents on|off` trong Claude Code, `hand-ext parallel on|off` ngoài terminal/Codex.
- PHẠM VI GHI thêm: `hybrid-hands/plugins/hybrid-hands/commands/parallel-subagents.md`.
- KIỂM CHỨNG thêm: `claude plugin validate` nhận command mới; không thêm test cho text command.
- Bàn giao ghi rõ đã kiểm chứng command nạp được hay chưa (phiên cần reload).

- Tên slash command chốt: `/hybrid-hands:parallel-subagents` (file `commands/parallel-subagents.md`) cho rõ nghĩa; CLI giữ `hand-ext parallel on|off`.
