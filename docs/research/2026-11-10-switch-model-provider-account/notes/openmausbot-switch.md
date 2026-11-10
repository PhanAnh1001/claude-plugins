# OpenMausBot — cơ chế switch model, effort, provider, account

## Tóm tắt

- **Mục đích:** ghi lại cách OpenMausBot (app Electron, mỗi bot là một agent CLI dùng login sẵn có) chọn và đổi model/effort/provider/account, để so với hybrid-hands và cc-switch.
- **Kết luận chính:**
  1. Model + effort là `ModelSelection {instanceId, model, effort?, variant?}` lưu **theo bot**, task/thread được ghi đè riêng; truyền **mỗi lượt** (`--model`/`--effort` cho Claude, `effort` trong `turn/start` cho Codex) nên đổi giữa chừng được, lượt sau áp dụng.
  2. Provider = "instance" (engine + cấu hình); nhiều instance cùng loại → nhiều account. Claude tách account bằng `configDir` → `CLAUDE_CONFIG_DIR` riêng; Codex gói ChatGPT dùng `CODEX_HOME` riêng nhưng symlink phần lớn thư mục về home của người dùng.
  3. OpenMausBot **không ghi** `~/.claude/settings.json` hay `~/.codex/config.toml` toàn cục; Claude bot mặc định cô lập (`--strict-mcp-config`, `--setting-sources project`), MCP dựng theo lượt.
  4. Có cơ chế quota-switch: hết hạn mức thì hỏi người dùng chuyển engine (chỉ "answer" mới được đổi engine).
- **Mốc dữ liệu:** clone `milind-soni/OpenMausBot` HEAD `f55d45c6e0764ec78e5ba8b0427150656dc94c92` (11/2026). Link dạng `https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/<path>#L<n>`, viết tắt `[path:n]` bên dưới, đều trỏ commit này.
- **Người đọc phải làm:** dùng như nguồn so sánh; các điểm "không thấy" chưa được xác nhận là không có.

## 1. Model và effort

### 1.1 Lưu ở đâu
- Kiểu `ModelSelection` có `effort?: EffortLevel` ([server/contracts.ts:145](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/contracts.ts#L145)); `variant` là ID riêng của provider, loại trừ với effort ([server/contracts.ts:80](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/contracts.ts#L80), [server/new-bot-defaults.ts:19-20](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/new-bot-defaults.ts#L19-L20)) (11/2026).
- Theo bot, task (thread) có thể có `modelSelection` riêng; thiếu thì theo bot (`followsBotModel`) ([server/store.ts:96-100](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/store.ts#L96-L100)) (11/2026).
- API kiểm effort hợp lệ và engine có hỗ trợ ([server/index.ts:2597-2638](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/index.ts#L2597-L2638)); effort đã lưu mà driver không còn hỗ trợ thì bỏ, giữ model ([server/default-model-selection.ts:75-76](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/default-model-selection.ts#L75-L76)) (11/2026).

### 1.2 Truyền xuống CLI mỗi lượt
- Claude: `args.push("--model", …)` và `--effort` theo lượt ([server/drivers/claude.ts:1046-1047](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L1046-L1047)); mức `low…max` ([server/drivers/claude.ts:2041](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L2041)) (11/2026).
- Codex (app-server): `effort` gửi kèm turn; thread giữ mức cuối nếu không gửi ([server/drivers/codex.ts:1488-1490](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L1488-L1490)) (11/2026).
- Suy luận: vì truyền theo lượt nên đổi model/effort giữa thread có hiệu lực từ lượt kế tiếp, không cần mở phiên mới.
- Fallback model nhanh dùng lại `model/effort/variant` riêng ([server/quick-model-fallback.ts:163-167](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/quick-model-fallback.ts#L163-L167)) (11/2026).

## 2. Provider và account

### 2.1 Claude
- `configDir` theo instance → `CLAUDE_CONFIG_DIR`; mặc định `env.CLAUDE_CONFIG_DIR` rồi `~/.claude` ([server/drivers/claude.ts:90-96](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L90-L96), [:119-125](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L119-L125)); khi có configDir thì xoá biến OAuth của tiến trình cha ("Subscription OAuth always comes from this account's own login") (11/2026).
- Suy luận: nhiều account Claude = nhiều instance với `configDir` khác nhau (có `claude-accounts.test.ts` trong `server/drivers/`).
- Đọc hạn mức: token Claude từ `<configDir>/.credentials.json`, rồi Keychain macOS `security find-generic-password -s <service> -w`; service mặc định cho `~/.claude`, khác thì thêm hậu tố sha256(đường dẫn)[0:8] ([server/plan-usage.ts:736-790](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/plan-usage.ts#L736-L790)) (11/2026). Cùng quy ước hậu tố với cc-switch (xem note cc-switch.md).

### 2.2 Codex
- Gói ChatGPT: `CODEX_HOME = <planDirectory>/codex`; xoá `OPENAI_API_KEY` để không lật sang trả theo dùng ([server/drivers/codex.ts:344-355](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L344-L355)) (11/2026).
- Home riêng chỉ giữ `auth.json`, `auth.lock`, `models_cache.json`; `sessions`, `skills`, `plugins`, `sqlite`, `cache`… **symlink** về home của người dùng ([server/drivers/codex-shared-home.ts:1-11](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex-shared-home.ts#L1-L11)) (11/2026).
- Endpoint API trực tiếp / Company: `CODEX_HOME` cô lập hoàn toàn ([server/codex-endpoints.ts:55](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/codex-endpoints.ts#L55), [server/hosted-models.ts:91](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/hosted-models.ts#L91)) (11/2026).
- Model bị ChatGPT từ chối cho account thì ẩn và chuyển model dùng được đầu tiên ([server/drivers/codex.ts:387-392](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L387-L392), [:471-476](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L471-L476)) (11/2026).

### 2.3 Chuyển engine khi hết hạn mức
- `quota-switch.ts`: chỉ câu trả lời người dùng mới đổi engine, shell của bot không tự đổi ([server/quota-switch.ts:2-4](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/quota-switch.ts#L2-L4)) (11/2026).
- Router chọn bot theo nội dung: **không thấy** module router riêng ở `server/` (grep `router|routeTo|pickBot` chỉ ra file không liên quan).

## 3. Cấu hình CLI: dùng chung hay riêng

- Claude bot mặc định cô lập: `--strict-mcp-config`, `--setting-sources project`, `--add-dir <userSkillsDir>` ([server/drivers/claude.ts:1036-1041](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L1036-L1041)); MCP dựng theo lượt rồi ghi file tạm mode 0600 ([:1053-1138](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L1053-L1138), [:1305](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L1305)) (11/2026).
- Lối thoát `OMB_CLAUDE_INHERIT_USER_CONFIG=1`: bot nạp MCP/skills/hooks/CLAUDE.md của máy, có cảnh báo ([server/drivers/claude.ts:136-150](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L136-L150)) (11/2026).
- Settings riêng của bot: `<cwd|workspace>/.claude/settings.json` ([server/workspace.ts:99](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/workspace.ts#L99)) (11/2026).
- `~/.codex/config.toml` chỉ **đọc** để import thiết lập ([server/setup-import.ts:104-120](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/setup-import.ts#L104-L120)); ghi `~/.claude/settings.json` hay `config.toml` toàn cục: **không thấy** (11/2026).

## Chưa kiểm
- Không chạy app; chưa đọc UI đổi model, `claude-accounts.test.ts` và `acp/*` (grok/gemini/qwen).
