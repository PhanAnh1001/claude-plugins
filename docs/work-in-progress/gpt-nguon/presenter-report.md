# Presenter hand report — 2026-11-08

## Phạm vi đã sửa

- `hybrid-hands/paseo-hh-tree/shared/tree.ts`: optional `week_pct_source`.
- `client/format.ts`, `client/compact.ts`: nhãn `riêng (đo)` chỉ khi `week_pct` hữu hạn và source chính xác `codex_rate_limits_delta`; thiếu số vẫn `riêng ? tuần`. Không đổi màu, layout, counts/pool.
- `client/compact.test.ts`: thêm assertion vào test có sẵn cho measured/unknown, không thêm test method.
- `statusline/.../scripts/shared_usage.py`: adapter import nguồn chung qua `shared_prices.plugin_candidates()`, deadline 0.75 giây cho mỗi shared read, chỉ trả số đã kiểm tra; không credential/network/settings. GPT dùng `load_codex(None, now)` và chỉ lấy sample rollout usable, age dưới 24h; ledger giữ parser/schema của statusline. Claude gọi `_five_hour("Claude", now)` để cache/live validation dùng chung.
- `gpt_usage.py`: giữ nguyên `collect(path, now)` ledger-only; main chọn quota mới nhất riêng từng cửa sổ giữa ledger hợp lệ và shared rollout. Không đổi USD hôm nay khỏi phạm vi ledger, không cộng rollout cost. Rollout weekly-only không có ledger vẫn có dòng GPT, 5h thiếu giữ thiếu.
- `statusline.sh`: thiếu payload Claude 5h dùng shared valid cache với dấu `~`, thiếu/expired vẫn `5h:-`. Giữ các phần khác.
- `hand_lines.py`: bổ sung phần riêng với cùng nhãn measured.
- statusline manifest/changelog lên `0.21.0`; header comments cập nhật cache/source.
- Hai test methods có sẵn ở statusline được mở rộng với fake rollout weekly-only, Claude cache fresh/expired; không tạo test method mới.

## Kiểm chứng thật

- `node --experimental-strip-types --test hybrid-hands/paseo-hh-tree/client/*.test.ts`: PASS 17/17. Lần đầu lỗi import extension của dòng mới, đã sửa dùng import `.ts` có sẵn và chạy lại PASS. Node có warning package module type hiện hữu.
- `npm run typecheck --prefix hybrid-hands/paseo-hh-tree`: PASS.
- `python3 -m unittest discover -s statusline/tests -p test_limit_table.py`: PASS 5/5, sau mở rộng weekly-only fixture.
- `python3 -m unittest discover -s statusline/tests -p test_statusline.py`: PASS 10/10, sau mở rộng cache fresh/expired fixture.
- Manual import-only fake assertions cho `hand_lines.row`: measured `GPT riêng (đo) 2.5% tuần`, unknown `GPT riêng ? tuần`: PASS.
- Manual monkeypatch shared source ngủ 2s: adapter fail-open trước 1.2s (deadline 0.75s): PASS.
- `bash -n statusline/.../scripts/statusline.sh`, `python3 -m py_compile` ba script Python: PASS.
- Manifest `json.loads`: PASS. `git diff --check -- statusline hybrid-hands/paseo-hh-tree`: PASS.

Không chạy full suite; không chạy real hh-ps, không đọc real cache/rollout/log/transcript, không network/API, không build/install/restart. Sol sẽ build bằng installed `compileDirectoryPlugin` sau review, theo steering đã nhận. Không có tiến trình nền còn chạy do hand tạo.

## Integration/giới hạn

- Core cung cấp `GptWindow.at/source/usable`, `load_codex(None, now).account`, `_five_hour`; adapter giữ statusline freshness 24h và phần trăm 0..100.
- Chọn per-window không lấy weekly thay 5h; shared loader tự đảm bảo đường dẫn cố định `.codex-hand` và lọc envelope usage.
- Delta đo được là chênh quota account trong cùng interval, có thể bao gồm phiên đồng thời; không phải phân bổ tuyệt đối riêng của một phiên. Nhãn ngắn theo brief, giải thích giữ ở report.
- Missing shared package/deadline/import/source validation fail-open, ledger statusline còn hoạt động.
- Không claim live UI/build/runtime thành công. Token/quota: ?.
