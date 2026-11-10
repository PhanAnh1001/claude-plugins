# hybrid-hands + Paseo — switch model, effort, provider, tài khoản

## Tóm tắt

- **Mục đích:** mô tả cơ chế hiện có, tách khỏi đề xuất overlay trong [report](../report.md).
- **Kết luận chính:** ba tầng brain/side/hand cấu hình theo repo; tài khoản cô lập theo tiến trình; không đồng bộ MCP/skills giữa account.
- **Số chính:** 3 tầng, 4 backend mặc định; v1 guard 5%/ngày; exit 7 hết backend, exit 8 hết slot.
- **Người đọc phải làm:** mở phiên mới khi đổi model/account; không sửa settings toàn cục để switch.
- **Nguồn:** không có nguồn internet, nguồn nội bộ; các đường dẫn dưới tương đối gốc repo, dữ liệu 10/11/2026. Không đọc credential hoặc log thật.

## 1. Cấu hình và cô lập

- `hybrid-hands/README.md:192-201`, `hybrid-hands/plugins/hybrid-hands/commands/models.md`: `hand-ext models` xem/set/unset model và effort ba tầng theo repo; set chỉ khi người dùng chốt; áp phiên mới.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/config.py:246-260`: plugin → global `~/.hybrid-hands/config.json` → repo → CLI; dict merge sâu, list/scalar thay nguyên.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py:102-106`: order dsh → codex → claude-v1 → claude-v2; repo này ghi đè codex đầu (dữ kiện brief). v1=`~/.claude`, max_day_pct=5; v2=`~/.claude-hand`. `lib/hand_ext/config.py:175-195` cùng gốc plugin cho phép thêm vN bằng config.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/claude.py:32,76-78,228-238`: đặt CLAUDE_CONFIG_DIR per-process; v1 gỡ biến để dùng login mặc định `~/.claude.json`; chặn ANTHROPIC_BASE_URL/API_KEY/AUTH_TOKEN, OAuth env, Bedrock/Vertex.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/codex.py:125,143,183`: đặt CODEX_HOME riêng, chặn OPENAI_API_KEY/BASE_URL; không sửa settings toàn cục.
- `AGENTS.md`: đổi model/account phải mở phiên mới; không có bước tự đồng bộ MCP/skills giữa tài khoản.

## 2. Preflight và failover

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/run_cmd.py:69-102`, `lib/hand_ext/day_budget.py:96` cùng gốc plugin: auto bỏ qua backend theo quota_state, doctor và guard v1; thiếu nguồn guard không được suy là pass.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/run_cmd.py:528-541`: fallback backend kế tiếp chỉ khi `--backend auto` và QUOTA/NOT_LOGGED_IN; không phải circuit breaker mọi lỗi. Exit 7 khi hết backend; exit 8 phải chờ slot.
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py:58-61`: dsh 429 đợi 180 giây, tối đa 2 lần.
- Thêm provider mới cần backend code trong `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/`, giá ở `config/model-prices.json` và MODEL_CAPABILITIES (`lib/hand_ext/constants.py:183-184` cùng gốc plugin); chưa có registry backend hoàn toàn khai báo.

## 3. Paseo và cc-switch nội bộ

- `hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md:82,112-134`: provider tuỳ biến `codex-hand` extends codex, env CODEX_HOME trong `~/.paseo/config.json` (chỉ mô tả, không đọc file máy).
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_provider.py:25-26,90-111`: managed provider hh-hand-{codex,dsh,claude-v1,claude-v2}; setup dry-run mặc định.
- `hybrid-hands/plugins/hybrid-hands/lib/cc_switch/providers.py:13,48`: cc-switch nội bộ ánh xạ account → provider bằng paseo.claude_providers, mặc định {"v1":"claude"}; khác app farion1231 trong [note cc-switch](cc-switch.md).

## 4. Giới hạn

Đây là đọc tĩnh và tổng hợp dữ kiện brain đã xác minh; không chạy agent/provider, không thử switch login, không đo quota. Overlay/reconcile và registry backend là đề xuất, chưa được triển khai trong lượt này.
