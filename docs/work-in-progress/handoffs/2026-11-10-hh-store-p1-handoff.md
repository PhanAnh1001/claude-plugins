# Bàn giao: hh-store giai đoạn 1 (10/11/2026)

## Tóm tắt

- **Trạng thái:** P1.1–P1.4 xong, brain đã review; chưa commit. Đo thật: `hh-ps --since 3h --json --ended --full` kho tắt p50 9,18 s → kho bật p50 3,48 s (~2,6×), output tương đương (chỉ khác `duration_seconds`, `generated_at`). Chưa đạt ngưỡng giai đoạn 1, người dùng đã hạ còn p50 ≤ 1 s (≤ 300 ms dời sang giai đoạn 2).
- **Việc kế tiếp:** P1.6 tối ưu 4 điểm nóng (xem [plan](../hh-store/plan.md) mục P1.6), rồi P1.7 đo lại + phát hành bản minor kế tiếp (main đang 0.39.0; một phiên khác đang làm 0.40.0 nhãn tài khoản trên cùng working tree).
- **Phiên brain mới:** repo đã đặt `parallel_subagents.backend = claude-v2`, `main_session.claude_account = v2` (10:39, chưa commit, không phải do phiên này). Mở brain v2: `side-session start --main --provider claude --account v2` (qua Paseo) hoặc trực tiếp CLI `CLAUDE_CONFIG_DIR=$HOME/.claude-hand claude` tại gốc repo, bắt đầu từ file này + plan.

## 1. File thuộc gói hh-store (chỉ commit đúng các file này)

- Mới: `hybrid-hands/plugins/hybrid-hands/lib/hh_store/` (`__init__`, `paths`, `db`, `ingest`, `runtime`, `codex_ingest`, `claude_ingest`), `hybrid-hands/tests/test_hh_store.py`, `test_hh_store_codex.py`, `test_hh_store_claude.py`, `test_writer_revision.py`.
- Sửa: `lib/hh_ps/{native_source,codex,machine_usage,transcript_source,claude_calibration}.py` (`claude_source.py` nếu có diff), `lib/hand_ext/{run_registry,execution_state}.py`, `lib/side_session/state.py`; test cách ly kho: `test_hh_ps{,_gpt_nguon,_native,_codex,_pricing_cache,_ended,_side,_multirepo,_usage}.py`, `test_claude_calibration.py`, `test_hand_usage_running.py`, `fixtures/hh_ps/fixture.py`, 13 file `test_hand_ext_*/test_hand_paseo_*/test_side_session_*` (setUpModule `HYBRID_HANDS_STATE_DIR`), `test_hand_paseo_execution.py`.
- Của phiên khác (KHÔNG commit chung): `account_label.py`, `compact.py`, `render.py`, `models.py`, `usage_enrichment.py`, `hand_ext/{cli,config,constants,parallel_cmd}.py`, `shared_config.py`, README, CHANGELOG, plugin.json, `test_account_label.py`, `test_hand_parallel_cmd.py`, `policy_mode.py`, `.claude/hybrid-hands.json`. Trước khi commit, đối chiếu `git diff` từng file sửa chung để không lẫn hunk.

## 2. Kết quả đã kiểm chứng

- `test_hh_*.py` 105 OK (bật kho, cách ly thư mục tạm). Suite đầy đủ 549 test: 3 lỗi policy (`test_policy_mode`, `test_hand_ext_isolation.PolicyTextTest`, `test_policy_brain_context`) thuộc WIP phiên khác.
- Tách hệ số Claude USD~/1% tuần theo account: trước đây một hệ số lấy mẫu từ `~/.claude-hand` (v2) áp cho mọi phiên kể cả v1; nay mỗi account riêng, file cũ thuộc v2, v1 `?` tới khi có mẫu.
- Kho thật `~/.hybrid-hands/state/hh-store.sqlite3` (~35 MB) đã xoá và dựng lại sạch lúc 10:45 trước khi đo.

## 3. Rủi ro còn mở

- Phiên khác từng gom WIP người khác vào commit (`521ade8`); file hh-store chưa commit có thể bị gom tiếp.
- Ghi đè tại chỗ cùng inode, không ngắn đi: Codex phát hiện bằng fingerprint trong `meta`; Claude chưa (transcript chỉ append).
- Claude chưa `forget_missing` (bản ghi file đã xoá không được đọc, chỉ chiếm chỗ).
- Lấy mẫu hiệu chỉnh v1 mới thêm `claude auth status` mỗi 120 s.
- Lỗi `cc-switch term --agent <id>` với agent tài khoản v2 (10/11): lệnh sinh `claude --resume <sid> --model claude-opus-5-5` không kèm `CLAUDE_CONFIG_DIR` của account agent, nên tìm transcript trong `~/.claude` → "No conversation found" (transcript nằm ở `~/.claude-hand/projects/…`). `lib/cc_switch/providers.py:34` chỉ đọc `CLAUDE_CONFIG_DIR` của shell gọi. Cần sửa: suy account từ provider Paseo của agent (`paseo.claude_providers`) rồi đặt `CLAUDE_CONFIG_DIR` tương ứng khi mở terminal.
