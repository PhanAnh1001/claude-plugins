# Bàn giao: hh-store giai đoạn 2 (10/11/2026)

## Tóm tắt

- **Trạng thái:** giai đoạn 2 (indexer + live) xong, phát hành **0.42.0**: commit `532a8ba`, merge `20e46a7` vào `main`, đã push (cả nhánh `feat/hh-store-p2-live`). Đã cài cho v1 (`~/.claude`) và v2 (`~/.claude-hand`); `paseo plugin reload hh-tree` chạy.
- **Số chính:** dữ liệu đổi → revision p50 0,39 s, max 2,33 s (ngưỡng ≤ 3 s đạt). CPU indexer 0,37–0,50% (ngưỡng ≤ 2% đạt). Test 140 OK cả bật/tắt kho; pane 6/6; Paseo 24/24; tsc 0.
- **Việc kế tiếp:** 7 việc mở ở mục 3; làm trước việc 1 (xác minh trường stdin hook bằng payload thật) và việc 2 (lần chạy lạnh hh-ps ~4,1 s).
- **Phiên brain mới:** bắt đầu từ file này + [plan](../hh-store/plan.md); chạy lệnh kiểm chứng nhanh ở mục 4 trước.

## 1. Đã xong

- P2.1 indexer + `hh-store` ✓.
- P2.2 hook SessionStart/Stop/SubagentStop/SessionEnd ✓.
- P2.3 pane: `watchPaths` + poll 1 s, debounce 300 ms ✓.
- P2.4 Paseo: revision 2 s, retry 60 s, safety 120 s ✓.
- Cài từ cache `plugins/cache/hybrid-hands-local/hybrid-hands/0.42.0`. Smoke: hook script của bản cài trả 0 và khởi indexer.
- Lỗi đã sửa trong lúc đo:
  - `Config` truyền positional sai thứ tự (rollout full mỗi 30 s).
  - Indexer decode `payload_json` không cần; thêm `codex_ingest.sync`/`claude_ingest.sync`.
  - So digest với chu kỳ trước để vẫn bump khi hh-ps tự ingest (từng trễ 28,8 s).
  - `_full_codex` bỏ qua rollout biến mất.
- Ngoài lề cùng phiên: đồng bộ cấu hình v1 → v2 (`~/.claude-hand/settings.json`, backup `settings.json.bak-20261110-sync`): hook env-guard, `CLAUDE_CODE_PLUGIN_DIRS` hh-tree-pane, plugin dev-workflow/jira-tools/summary-first-docs, cài đặt phụ, symlink 6 skill paseo-*.

## 2. Số đo thật (10/11/2026)

| Chỉ số | Kết quả | Ngưỡng |
|---|---|---|
| Dữ liệu đổi → revision | p50 0,39 s, max 2,33 s (n=9, có hh-ps mỗi 5 s) | ≤ 3 s, đạt |
| CPU indexer | 0,37% nhàn; 0,50% có hh-ps mỗi 5 s (trước khi sửa 2,2–2,7%) | ≤ 2%, đạt |
| Idle exit | 602 s sau lần chạm `last_read` | 600 s |
| Hook | trả về ~7 ms; `hh-store touch` ~90 ms chạy nền | — |
| hh-ps | p50 ~0,9 s khi indexer chạy (n=10); dao động 0,87–4,78 s cũng có khi tắt indexer → nhiễu máy | — |

## 3. Việc còn mở (theo ưu tiên)

1. Chưa xác minh tên trường stdin hook (`transcript_path`, `agent_transcript_path`) bằng payload thật. Kiểm bằng `hh-store status` sau khi mở phiên mới.
2. Lần chạy lạnh hh-ps ~4,1 s (calibration TTL 300 s + `claude auth status`) chưa xử lý.
3. Pane cần mở phiên Claude mới để nạp `watchPaths`; chưa xác nhận watchPaths với đường tuyệt đối ngoài cwd hoạt động (dự phòng poll 1 s vẫn đạt).
4. Mỗi Stop hook sinh một process python nền ~100 ms, có thể chồng nhau khi dồn dập.
5. Chưa có test Linux không kqueue (đường poll stat 2 s).
6. `hh-ps` chỉ tự khởi indexer khi chạy từ tty. Lệch có chủ ý: pane/Paseo/hook tự touch.
7. `_last_digest` không xoá trong `runtime._reset_for_tests` (vô hại hiện tại).

## 4. Lệnh kiểm chứng nhanh cho phiên mới

- `hh-store status` — trạng thái kho/indexer; sau khi mở phiên mới, xem hook đã ghi transcript chưa (việc 1).
- `pgrep -fl hh-indexer` — indexer có đang chạy (singleton, tự thoát sau ~600 s nhàn).
- Bộ test brain đã chạy thật 10/11 (đường tương đối tính từ gốc repo):
  - Python, cả kho bật và tắt → 140 OK mỗi lần:
    `cd hybrid-hands/tests && files=$(ls test_hh_*.py test_claude_calibration.py test_writer_revision.py | sed 's/\.py$//' | tr '\n' ' '); python3 -m unittest $(echo $files); HYBRID_HANDS_STORE=off python3 -m unittest $(echo $files)`
    Lưu ý: `discover -p 'test_hh_*.py'` bỏ sót calibration và writer.
  - Pane → 6 pass: `cd hybrid-hands/hh-tree-pane && node --test tests/*.ts`
  - Paseo → 24 pass, tsc 0: `cd hybrid-hands/paseo-hh-tree && node --test server/*.test.ts client/*.test.ts && npx tsc --noEmit -p .`
