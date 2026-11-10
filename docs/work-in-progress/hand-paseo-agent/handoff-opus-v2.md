# Bàn giao cho phiên chính Opus v2: pilot live hand agent Paseo rồi báo tiktok

## Tóm tắt

- **Bạn là phiên chính Opus v2** (người dùng chuyển phiên chính từ Claude v1 sang v2 ngày 09/11/2026 vì v1 đã dùng nhiều trong ngày). Mục tiêu người dùng (/goal): *tự động xong hết task rồi báo repo tiktok (`/Users/anhtp/app/live-tiktok-games`) để áp dụng luôn*.
- **Đã xong:** lane A (hand chạy thành agent Paseo, opt-in, shell vẫn mặc định) đã merge vào `main` và push. Bản phát hành 0.34.0 (commit `3071628`). Full suite trên main: 497 test OK. Plugin nạp từ checkout nên mọi repo đã dùng code mới. Phiên cấu hình global (nhánh `side/cfg-goi-*`) đang chuẩn bị 0.35.0 trên nền đó; thay đổi chưa commit của họ trong checkout chính (`AGENTS.md`, `README.md`, CHANGELOG 0.35.0, …), **không đụng**.
- **Người dùng đã cho phép phiên Opus v2 chạy** bước ghi `~/.paseo/config.json` + `paseo daemon reload` (bộ lọc auto mode chặn Opus v1). Nếu bộ lọc vẫn chặn, dừng và hỏi người dùng tự chạy bằng `!`.
- **Việc còn lại theo thứ tự:** (1) đăng ký provider + reload; (2) bật `mode=auto` chỉ cho repo claude-plugins; (3) chạy một task pilot nhỏ, kiểm cây/stop/review/archive/follow-up; (4) ghi kết quả, sửa lỗi nếu có (giao Sol, bản vá 0.35.x/… tuỳ version main lúc đó); (5) báo phiên brain tiktok áp dụng.

## 0. Trạng thái phiên Opus v1 lúc bàn giao

- Không còn phiên Sol/hand nào chạy cho lane A (hpa-p1, hpa-p2, hpa-p3 đã xong và merge). Phiên Opus v1 dừng, không chờ thêm.
- Việc chờ người dùng: không có, ngoài trường hợp bộ lọc auto mode chặn bước provider setup/reload (khi đó hỏi người dùng tự chạy bằng `!`).
- Khi xong, ghi kết quả vào `docs/work-in-progress/handoffs/opus-v2-pilot.md` (mở đầu bằng Tóm tắt) và tạo `opus-v2-pilot.done`.

## 1. Bối cảnh đã chốt

- Spec/plan: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `...-plan.md`. Quyết định người dùng: Q1 lane A đủ 4 backend; Q2 mỗi hand một workspace riêng cùng project + Subagents tab ở cha; Q3 việc mới trước đây giao native Sol low chuyển sang hand agent Paseo; Q4 done giữ hiện, Sol archive sau review, gửi tiếp tự mở lại; Q5 epoch/brief mới, không resume context CLI; Q6 không tự dọn worktree; Q7 bật dần, pilot ở claude-plugins trước.
- Bàn giao kỹ thuật: `docs/work-in-progress/handoffs/hpa-p2.md` (setup provider, cấu hình), `hpa-p3.md` (CLI managed, bằng chứng reload nóng, thứ tự pilot 8 bước, rủi ro). Đọc mục "Thứ tự live pilot" của `hpa-p3.md`.
- Daemon đã xác minh: home `/Users/anhtp/.paseo`, version 0.15.0, listen `127.0.0.1:6767`, không desktop-managed; provider hiện có `claude`, `codex`, `codex-hand`. Dry-run setup chỉ có 4 mục `create` (`hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`), command trỏ `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-paseo-acp`.

## 2. Các bước pilot

1. Đăng ký và reload (source Paseo: reload nóng, không restart, không đóng agent đang chạy; xem `hpa-p3.md`):
   ```sh
   H=/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext
   $H provider setup --home /Users/anhtp/.paseo --package-root /Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli --apply
   paseo daemon reload --home /Users/anhtp/.paseo --json
   ```
   Kiểm `appliedPaths`/`restartRequiredPaths`; có restart-required thì dừng pilot, báo người dùng, không tự restart.
2. Gộp vào `ext_hand` của `/Users/anhtp/app/claude-plugins/.claude/hybrid-hands.json` (giữ `order` hiện có): `"mode": "auto"`, `"paseo": {"package_root": "<package như trên>", "target": {"kind": "instance", "home": "/Users/anhtp/.paseo"}}`. Lưu ý: nếu 0.35.0 (cấu hình global) đã đổi cách nạp config thì đọc README mới trước. Chạy `$H provider status --cwd /Users/anhtp/app/claude-plugins`, phải thấy 4 provider khả dụng.
3. Giao một phiên Sol (`side-session start --name hpa-pilot --provider codex`) chạy pilot từ context có `PASEO_AGENT_ID`: task disposable nhỏ (vd sửa một câu trong file docs tạm, `--no-apply`), `hand-ext run --backend auto --mode paseo-required --brief ... --cwd /Users/anhtp/app/claude-plugins --no-apply`; kiểm sidebar (workspace riêng, tab Subagents ở cha), `hh-ps --once` đúng một dòng, stop thử, rồi `hand-ext managed ls|review-approve|archive|followup`. Smoke tối thiểu backend codex; backend khác nếu rẻ. Chỉ dùng subscription, không API trả phí.
4. Lỗi thì Sol sửa trên nhánh, test hẹp, Opus đọc bàn giao, release bản vá theo luật AGENTS.md (bump + CHANGELOG + validate + merge main + push + kiểm `claude plugin list` ở cả claude-plugins và tiktok).

## 3. Báo repo tiktok

Sau pilot (hoặc nếu pilot bị chặn thì báo trạng thái "đã cập nhật, chưa bật"): gửi phiên brain tiktok bằng `paseo send --no-wait <agent>` (các agent Opus tiktok trước đây: `e9f97c57`, `6d8cc829`; kiểm bằng `paseo ls` còn sống). Nội dung: hybrid-hands 0.34.0+ đã nạp (plugin đọc từ checkout); muốn hand chạy thành agent Paseo thì gộp `mode`/`paseo` như bước 2 vào `.claude/hybrid-hands.json` của tiktok (giữ `order: ["codex"]`), chạy `provider status`, Sol giao việc mới bằng `--mode paseo-required` và review/archive bằng `hand-ext managed …`. Nêu rõ phần live nào đã/ chưa kiểm chứng.

## 4. Luật giữ nguyên

Theo AGENTS.md repo. Không sửa `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents; không xoá/di chuyển `output/llm/`; không restart daemon Paseo; không chạy lệnh phá hoại; không đụng thay đổi chưa commit của phiên cấu hình global.
