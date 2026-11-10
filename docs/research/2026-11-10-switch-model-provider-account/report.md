# So sánh cách switch model, effort, provider, tài khoản: hybrid-hands + Paseo, cc-switch, OpenMausBot

## Tóm tắt

- **Câu hỏi:** nên switch ở tầng nào và dùng chung tài sản ra sao mà vẫn giữ cô lập tài khoản?
- **Kết luận chính:**
  1. Giữ hybrid-hands + Paseo cho brain/hand; đổi model/account bằng phiên mới theo luật repo (không có nguồn internet, nguồn nội bộ: `AGENTS.md`).
  2. cc-switch hỗ trợ cả per-session và ghi token vào default slot; không dùng chế độ ghi toàn cục song song với hybrid-hands (suy luận từ [note](notes/cc-switch.md)).
  3. OpenMausBot truyền model/effort theo lượt, có quota-switch cần người dùng trả lời; không đồng nghĩa mọi engine/account đổi nóng an toàn ([nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/quota-switch.ts#L2-L4), 11/2026).
  4. Khuyến nghị tách credential/state + overlay tài sản tĩnh; không học cách chia sẻ transcript/plugins nguyên thư mục (suy luận).
  5. Reconcile settings/plugin là thay đổi L2 cần người dùng chốt; nghiên cứu này không đổi runtime.
- **Số chính:** 3 hệ thống, 3 tầng brain/side/hand, 4 backend mặc định; roadmap 3 đợt (không có nguồn internet, nguồn nội bộ: [note](notes/hybrid-hands-paseo-switch.md)).
- **Người đọc phải làm:** chốt kiến trúc mục 3 và phạm vi L2 trước triển khai; giữ nguyên login, settings và sổ cài đặt hiện tại.

## 1. So sánh ba hệ thống

Nguồn chi tiết: [hybrid-hands + Paseo](notes/hybrid-hands-paseo-switch.md) (không có nguồn internet, nguồn nội bộ); [cc-switch](notes/cc-switch.md), [OpenMausBot](notes/openmausbot-switch.md) có link code gốc theo commit (11/2026). Các kết luận rủi ro là suy luận từ các note.

| Tiêu chí | hybrid-hands + Paseo | cc-switch (farion1231) | OpenMausBot |
|---|---|---|---|
| Model | Theo tầng brain/side/hand, repo | Ghi model/env live; proxy map model | ModelSelection theo bot/task, truyền theo lượt |
| Effort | Theo tầng/backend; launcher | Codex config; Claude proxy auto/off/passthrough, rectifier | Theo lượt; kiểm driver hỗ trợ |
| Provider | Backend code + Paseo provider | Provider config live + proxy | Instance gồm engine + cấu hình |
| Account | claude_accounts vN, Codex home riêng | Config dir riêng hoặc official default-slot swap | Nhiều instance/configDir, planDirectory |
| Phạm vi switch | Per-process | Toàn cục khi switch live; terminal per-session là nhánh riêng | Per-process/per-turn; không thấy ghi config toàn cục |
| Đổi giữa phiên | Luật repo: mở phiên mới | Live settings không chứng minh phiên đang chạy đổi ngay | Model/effort lượt sau (suy luận); engine cần answer |
| Failover | Auto + QUOTA/NOT_LOGGED_IN; preflight quota/guard | Có circuit breaker/failover, chưa đọc chi tiết | Quota-switch cần người dùng; fallback model |
| Đồng bộ plugin/skill/MCP/CLAUDE.md | Chưa tự sync giữa account | Symlink tài sản cả plugins/projects; mirror settings/MCP; @import | Claude mặc định project-only + MCP từng lượt; opt-in inherit; Codex symlink nhiều thư mục |
| Cô lập credential | CLAUDE_CONFIG_DIR/CODEX_HOME; v1 dùng login mặc định | Keychain theo dir; official mode ghi default slot | Claude configDir; Codex auth riêng, phần lớn home dùng chung |
| Rủi ro chính | Lệch cấu hình account, guard chưa phủ mọi account | Ghi token toàn cục, deeplink, proxy/API key | Full access, đọc token usage, chia sẻ transcript |

Ví dụ code gốc: cc-switch [shared.rs](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/shared.rs#L1-L12), OpenMausBot [Claude flags](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L1046-L1047), [Codex home](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex-shared-home.ts#L1-L11) (11/2026).

## 2. Thư mục chung hay tách

Chi tiết docs chính thức và quan sát cục bộ ở [note thư mục](notes/thu-muc-chung-vs-tach.md). Claude config dir bao gồm settings, plugins, chỉ dẫn và lịch sử; credential macOS dùng Keychain theo dir, fallback file 0600 ([directory](https://code.claude.com/docs/en/claude-directory), [authentication](https://code.claude.com/docs/en/authentication), 11/2026).

| Tiêu chí | A — chung thư mục, đổi credential | B — tách thư mục theo account |
|---|---|---|
| Song song/cô lập | Tranh slot login, usage dễ trộn | Per-process, state riêng |
| Plugin/skill/config | Một bản tự nhiên | Có thể lệch, cần overlay/reconcile |
| Rủi ro | Ghi dở hoặc đổi account ngoài ý muốn | Đồng bộ nhầm secret/state |
| Phù hợp hybrid-hands | Không khuyến nghị (suy luận) | Giữ nền tảng hiện có (suy luận) |

Quan sát cục bộ, không có nguồn internet (brain liệt kê tên mục 10/11/2026): v2 thiếu CLAUDE.md/agents/hooks; Codex hand thiếu AGENTS.md/agents/rules/hooks.json; sổ plugin tách. Không suy nội dung settings từ tên backup.

## 3. Phương án khuyến nghị (suy luận)

**Tách thư mục cho credential/state + lớp dùng chung (overlay) cho tài sản.** Học cc-switch shared.rs: symlink skills/plugins/commands/agents, mirror settings đã bỏ khoá nhạy cảm, chỉ chép mcpServers, CLAUDE.md một dòng @import; nhưng không bê nguyên danh sách chia sẻ. Học OpenMausBot codex-shared-home.ts về auth riêng: thực tế code còn giữ auth.lock/models_cache.json riêng, không chỉ auth.json ([cc-switch nguồn](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/shared.rs#L1-L12), [OMB nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex-shared-home.ts#L1-L11), 11/2026).

- **(a) Giữ riêng:** credential/Keychain, .claude.json state, projects/transcript, history, statusline cache; Codex sessions/archived_sessions. Usage/ledger cần theo account, không trộn phiên; native child vẫn đọc cố định `~/.codex-hand/sessions` (không có nguồn internet, nguồn nội bộ: `AGENTS.md`).
- **(b) Dùng chung:** CLAUDE.md qua dòng `@~/.claude/CLAUDE.md`; skills/agents/commands/hooks script qua symlink từng thư mục con; Codex AGENTS.md/rules/skills/agents qua symlink. Chỉ chia sẻ nội dung đã kiểm không chứa secret; MCP chỉ chiếu mcpServers đã lọc, không chép nguyên .claude.json. Hiệu lực Codex còn cần xác minh docs.
- **(c) Settings:** reconcile sinh từ base chung + override account; chỉ sửa khoá sở hữu (ownership floor), backup lần ghi đầu, dry-run mặc định. Không chép env bí mật hoặc model mặc định đè account.
- **(d) Plugins:** không symlink plugins/ hay installed_plugins.json: hai account có thể ghi đồng thời, luật repo cấm sửa thủ công sổ. Reconcile bằng `claude plugin install` chính thức lặp cho từng CLAUDE_CONFIG_DIR (v1 giữ tương thích biến unset), hoặc launcher chèn --plugin-dir/--settings/--mcp-config theo phiên. Scope install chưa xác minh. Managed-settings.json là kênh dùng chung mạnh nhất nhưng áp toàn máy, cần admin; chưa xác minh tự tải plugin ([CLI](https://code.claude.com/docs/en/cli-reference), [managed](https://code.claude.com/docs/en/managed-settings), 11/2026).
- **(e) Model/effort:** launcher truyền --model/--effort theo phiên, không ghi settings; phải xử lý env effort có ưu tiên cao hơn ([model-config](https://code.claude.com/docs/en/model-config), 11/2026).

**(c)(d) chạm luật hiện hành “không sửa settings/sổ cài đặt”: cần người dùng chốt L2 trước triển khai**, kể cả reconcile dùng công cụ chính thức. Nguồn luật: không có nguồn internet, nguồn nội bộ `AGENTS.md`; đây là đề xuất, không phải quyền ghi đã cấp.

## 4. Lộ trình nâng cấp hybrid-hands (suy luận)

1. **Đợt 1:** circuit breaker backend mở rộng ngoài QUOTA/NOT_LOGGED_IN; guard quota mọi account max_5h/week/day; doctor nhận diện account không đọc token, dựa metadata service Keychain theo sha256 thư mục và oauthAccount, không xuất định danh. Quy ước hash tham khảo [layout.rs](https://github.com/farion1231/cc-switch/blob/76e19b47cfb8e379f8944d3fe2ad6d4c369d438a/src-tauri/src/services/claude_account/layout.rs#L10-L11) (11/2026); khả năng truy cập metadata còn phải xác minh.
2. **Đợt 2:** registry backend khai bằng config; brain chuyển account có duyệt; `hand-ext accounts sync` overlay như mục 3, dry-run mặc định.
3. **Đợt 3:** Paseo provider sinh từ cùng config; browser guard cho server paseo-hh-tree nếu mở cổng.

**Không làm:** proxy takeover base_url toàn cục, import deep link, chuyển token vào default slot.

## 5. Giới hạn và câu hỏi mở

- Tổng hợp đọc tĩnh và dữ kiện brain đã xác minh; không chạy clone, không cài app, không đọc credential/transcript thật, không thử switch runtime.
- Chưa xác minh docs chính thức Codex về CODEX_HOME/profiles/effort/auth; [config-reference](https://developers.openai.com/codex/config-reference) là điểm cần đọc, không phải bằng chứng đã kiểm (11/2026).
- Chưa xác minh scope plugin install, managed có tự tải plugin, circuit breaker/failover cc-switch, và hành vi account/engine đổi giữa thread của mọi driver.
- Overlay cần giải quyết ownership, symlink bị thay thế, xung đột version và rollback; chưa chứng minh idempotent bằng thực thi.
- Nghiên cứu trước: [Bảo mật OpenMausBot](../2026-11-10-openmausbot-bao-mat/report.md). Khuyến nghị cách ly OMB vẫn giữ nguyên; bản này không phải kiểm toán bảo mật mới.
