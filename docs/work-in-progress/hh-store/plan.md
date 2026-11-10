# Plan: hh-store (giai đoạn 1 + 2)

## Tóm tắt

- **Thực hiện [spec](spec.md)** qua 10 gói cỡ L1 (gồm 1 spike S0), hai đợt phát hành, mỗi đợt lấy bản minor kế tiếp lúc gộp (10/11: main đã 0.39.0, một phiên khác đang làm 0.40.0 nhãn tài khoản trên cùng repo).
- **Song song tối đa 4 hand** (chế độ parallel_subagents bật cho repo này); cùng file/phụ thuộc chạy tuần tự. Brain viết tiêu chí, review diff, đo trên dữ liệu thật, phát hành.
- **Trạng thái:** giai đoạn 1 phát hành 0.41.0 (p50 0,70 s); giai đoạn 2 xong, phát hành **0.42.0** (commit `532a8ba`, merge `20e46a7` vào main, đã push; cài v1 + v2, `paseo plugin reload hh-tree` chạy). Đo thật: dữ liệu đổi → revision p50 0,39 s, max 2,33 s (≤ 3 s đạt); CPU indexer 0,37–0,50% (≤ 2% đạt). Còn 7 việc mở (mục cuối giai đoạn 2). Bàn giao: `docs/work-in-progress/handoffs/2026-11-10-hh-store-p2-handoff.md` (giai đoạn 1: `2026-11-10-hh-store-p1-handoff.md`).

## Giai đoạn 1 — kho + ingest tăng dần

| Gói | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|
| P1.1 | `lib/hh_store/`: schema, mở/khoá, cursor/generation, bump_revision, dựng lại khi đổi version, quyền 0600 | `lib/hh_store/*`, test mới | — |
| P1.2 | Codex: ingest rollout vào `codex_records`; `codex.py`, `native_source.py`, `machine_usage.py` đọc từ kho, giữ phép dẫn xuất | `lib/hh_ps/codex.py`, `native_source.py`, `machine_usage.py` | P1.1 |
| P1.3 | Claude transcript/subagent + JSON ghi đè + ledger JSONL vào kho | `lib/hh_ps/transcript_source.py`, `claude_source.py`, `registry_source.py`, `week.py` (phần ledger) | P1.1; song song P1.2 |
| P1.4 | Writer bump revision: run, managed execution, side-session state | `lib/hand_ext/run_registry.py`, `execution_state.py`, `lib/side_session/state.py` | P1.1; song song P1.2/P1.3 |
| P1.5 | `tree.py` gọi ingest trước build; brain đo, so tương đương, phát hành | `lib/hh_ps/tree.py`, CHANGELOG, plugin.json | P1.2–P1.4 |

- [x] P1.1 kho + test (cursor append, truncate → generation mới, kho hỏng → dựng lại); brain review đạt 10/11
- [x] P1.1b `runtime.connection()` (giữ khoá suốt tiến trình, lỗi/hết giờ → None → đường đọc file cũ, env `HYBRID_HANDS_STORE=off`) + `read_tail` (dòng cuối không newline đọc tạm, không lưu, giữ tương đương)
- [x] P1.2 Codex từ kho; golden `test_hh_ps_gpt_nguon.py`, `test_hh_ps_native.py` xanh cả bật/tắt kho; brain review đạt 10/11 (còn: cách ly state dir trong test, đo số transaction ghi mỗi lần chạy ở P1.5)
- [x] P1.3 transcript Claude + subagent từ kho (ledger/state nhỏ giữ đường cũ); hệ số USD~/1% tuần tách theo account, file cũ thuộc v2; test cách ly kho; brain review đạt 10/11
- [x] P1.4 bump revision trong ba writer (`run_registry._write`, `execution_state.atomic_json`, `side_session/state.save`); lỗi kho không làm hỏng writer; brain review đạt 10/11
- [x] P1.5a đo 10/11 (dữ liệu thật, xen kẽ n=3): kho tắt 7,94/9,18/9,67 s; kho bật 3,50/3,48/3,27 s (p50 3,48 s, nhanh ~2,6×). Tương đương: 1377 trường, chỉ khác `duration_seconds` (5) và `generated_at` (1), giống hệt độ lệch giữa hai lần chạy kho tắt. Chưa đạt ngưỡng (người dùng hạ ngưỡng giai đoạn 1 còn ≤ 1 s, ≤ 300 ms dời sang giai đoạn 2); `tree.py` không cần sửa (reader tự ingest).
- [x] P1.6 tối ưu (10/11, profile kho bật đo lại: warm 1,95 s, lạnh 5,4 s; điểm nóng chính đã thành `machine_usage._gpt_usd` 1,24 s), 4 hand v2 song song, brain review đạt: (a) `codex_ingest` file không đổi stat (dev/inode/size/mtime_ns + parser + scope) thì không ghi kho, không đọc lại; (b) `machine_usage` cache tổng GPT theo thread trong kho (bảng `gpt_usd_files`, `gpt_usd_threads`; khoá gồm stamp file, start, options, bảng giá; chỉ dùng lại khi max stamp ≤ now), memo giá theo model; không bỏ được khoá khử trùng `json.dumps` cho thread một file vì phản ví dụ A,B,A cùng stamp; (c) `paseo_source`/`claude_source` gộp các lần resolve; (d) `week.window_messages` parse mỗi transcript một lần cho mọi khoảng (chép logic statusline, thiếu helper thì gọi bản gốc), `claude auth status` cache theo account TTL = POLL 120 s, chỉ lưu digest.
- [x] P1.7 đo 10/11 (dữ liệu thật, n=5 sau một lượt khởi động): 0,682/0,675/0,698/0,758/0,709 s → **p50 0,70 s, đạt ≤ 1 s**. Tương đương: kho bật vs kho tắt 0 khác; kho tắt code mới vs bản chụp trước P1.6 0 khác (bỏ qua `duration_seconds`/`generated_at`). Test `test_hh_*` + calibration + writer: 134 OK cả bật/tắt kho. Version 0.41.0, CHANGELOG, README mục 6. Đã commit `30c1dd7`, merge `5868b69` vào main và push; cài 0.41.0 cho v1 (`~/.claude`) và v2 (`~/.claude-hand`), validate đạt. Còn mở: lần lạnh vẫn ~4,1 s (đo bằng bản đã cài, lượt đầu sau ~5 phút), cache hiệu chỉnh TTL 300 s gọi lại `claude auth status` và lấy mẫu; nên profile riêng lần lạnh ở đầu giai đoạn 2 (indexer chạy nền sẽ gánh phần này).

## Giai đoạn 2 — indexer + live

| Gói | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|
| S0 | Spike: `watchPaths` với đường dẫn ngoài cwd có phát `FileChanged` không (mod nhỏ thử nghiệm, không phát hành) | thư mục tạm | — (làm song song giai đoạn 1) |
| P2.1 | `bin/hh-indexer`: singleton flock, kqueue + quét 30 s, debounce, idle exit 10 phút, SIGTERM sạch; `hh-store touch` | `bin/hh-indexer`, `bin/hh-store`, `lib/hh_store/indexer.py` | giai đoạn 1 đã phát hành |
| P2.2 | Hook SessionStart/Stop/SubagentStop/SessionEnd gọi `hh-store touch` (≤ 50 ms, exit 0) | `hooks/hooks.json`, script hook mới | P2.1 |
| P2.3 | Pane: `watchPaths` + `FileChanged` debounce 1 s, dự phòng stat theo kết quả S0 | `hybrid-hands/hh-tree-pane/hooks/*` | S0, P2.1 |
| P2.4 | Paseo: server `fs.watch` revision huỷ cache, RPC `hh-tree.revision`, client hỏi revision 5 s | `hybrid-hands/paseo-hh-tree/*` | P2.1; song song P2.3 |

- [x] S0 spike watchPaths (tài liệu), kết luận ở spec mục 2.3; thí nghiệm runtime dời vào đầu P2.3
- [x] P2.1 indexer + `hh-store`; test singleton, idle exit, truncate/rename. Idle exit đo được 602 s sau lần chạm `last_read` (ngưỡng 600 s).
- [x] P2.2 hook SessionStart/Stop/SubagentStop/SessionEnd; hook trả về ~7 ms, `hh-store touch` ~90 ms chạy nền.
- [x] P2.3 pane live: `watchPaths` + poll 1 s, debounce 300 ms; test pane 6/6.
- [x] P2.4 Paseo live: revision 2 s, retry 60 s, safety 120 s; test Paseo 24/24, tsc 0.
- [x] Đo 10/11/2026 trên dữ liệu thật: dữ liệu đổi → revision p50 0,39 s, max 2,33 s (n=9, có hh-ps mỗi 5 s; ≤ 3 s đạt). CPU indexer 0,37% nhàn, 0,50% có hh-ps mỗi 5 s (≤ 2% đạt; trước khi sửa 2,2–2,7%). hh-ps p50 ~0,9 s khi indexer chạy (n=10); dao động 0,87–4,78 s cũng có khi tắt indexer → nhiễu máy. Test 140 OK cả bật/tắt kho. Phát hành 0.42.0 (`532a8ba`, merge `20e46a7`, đã push cả `feat/hh-store-p2-live`); cài v1 (`~/.claude`) và v2 (`~/.claude-hand`) từ cache `plugins/cache/hybrid-hands-local/hybrid-hands/0.42.0`; `paseo plugin reload hh-tree` running; smoke hook bản cài trả 0 và khởi indexer.
- Lỗi đã sửa trong lúc đo: `Config` truyền positional sai thứ tự (rollout full mỗi 30 s); indexer decode `payload_json` không cần (thêm `codex_ingest.sync`/`claude_ingest.sync`); so digest với chu kỳ trước để vẫn bump khi hh-ps tự ingest (từng trễ 28,8 s); `_full_codex` bỏ qua rollout biến mất.

### Việc còn mở sau 0.42.0 (theo ưu tiên)

1. [ ] Xác minh tên trường stdin hook (`transcript_path`, `agent_transcript_path`) bằng payload thật: mở phiên mới rồi xem `hh-store status`.
2. [ ] Lần chạy lạnh hh-ps ~4,1 s (calibration TTL 300 s + `claude auth status`) chưa xử lý.
3. [ ] Pane cần mở phiên Claude mới để nạp `watchPaths`; chưa xác nhận watchPaths với đường tuyệt đối ngoài cwd (dự phòng poll 1 s vẫn đạt).
4. [ ] Mỗi Stop hook sinh một process python nền ~100 ms, có thể chồng nhau khi dồn dập.
5. [ ] Chưa có test Linux không kqueue (đường poll stat 2 s).
6. [ ] `hh-ps` chỉ tự khởi indexer khi chạy từ tty (lệch có chủ ý: pane/Paseo/hook tự touch) — ghi nhận, chỉ đổi nếu cần.
7. [ ] `_last_digest` không xoá trong `runtime._reset_for_tests` (vô hại hiện tại).

## Luật áp cho mọi gói

- Hand chỉ dùng fixture giả, không đọc `~/.codex-hand`, `~/.claude*`, `~/.hybrid-hands` thật; brain tự đo trên dữ liệu thật.
- Mức test tối thiểu; golden test sẵn có là chuẩn tương đương.
- Không sửa `statusline/`, `parallel-subagents/`, settings/credential; không xoá `output/llm/`.
