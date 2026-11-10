# Spec: kho dữ liệu chung hh-store và hiển thị live cho hh-ps

## Tóm tắt quyết định (1 trang)

- **Vấn đề:** `hh-ps --since 3h --json --ended --full` mất ~8,5 s/lần (0.37.3, đo 10/11/2026, n=3) vì mỗi lần đọc lại toàn bộ rollout Codex và transcript Claude; pane/panel phải poll 30–120 s và mỗi lần đốt CPU. Phần tự nóng còn lại: `native_source._records` 4,1 s self, `week._usd_since` 1,2 s, `codex._scan_rollouts` 0,8 s.
- **Mục tiêu:** dữ liệu đổi ở đâu thì kho chung cập nhật phần đó; `hh-ps` và UI chỉ đọc kho, hiện live.
- **Quyết định:**
  1. **Kho:** SQLite WAL bằng `sqlite3` stdlib tại `~/.hybrid-hands/state/hh-store.db`. File nguồn vẫn là nguồn sự thật; kho là chỉ mục dựng lại được (xoá kho → tự dựng lại, kết quả không đổi).
  2. **Lưu token thô**, tính USD~ lúc đọc theo `model-prices.json`; projection có cache USD phải gắn pricing fingerprint + parser_version.
  3. **Giai đoạn 1 — đọc tăng dần, không daemon:** mỗi lần `hh-ps` chạy, dưới khoá ghi, ingest phần mới của từng file JSONL append (cursor theo dev/inode/generation, chỉ commit tới newline cuối), file JSON nhỏ ghi đè thì đọc lại khi stat đổi. Các writer của plugin (run, managed execution, side-session) tăng `revision` sau khi ghi thành công. Không đổi output.
  4. **Giai đoạn 2 — live:** một indexer `hh-indexer` duy nhất mỗi máy (khoá `flock`), khởi theo nhu cầu, tự thoát khi không ai đọc 10 phút. Theo dõi bằng kqueue (thư mục + file đang hoạt động) kèm quét stat dự phòng 30 s; ingest ngay khi có thay đổi, ghi `revision` atomic. Hook Claude (SessionStart/Stop/SubagentStop/SessionEnd) gọi `hh-store touch` để khởi indexer và đánh dấu dirty. Pane dùng `watchPaths` + `FileChanged` trên file revision; server Paseo dùng `fs.watch` để huỷ cache, client hỏi revision rẻ mỗi 5 s.
  5. **Push thật chỉ cho dữ liệu của plugin**; Codex/Claude tự ghi file nên luôn qua indexer. Không gọi RPC/API daemon Codex.
  6. **Claude tách theo gói tài khoản:** v1 = Ultra (`~/.claude`), v2 = Pro (`~/.claude-hand`). USD~/token giống nhau (giá canonical), nhưng USD~ ứng với 1% tuần khác nhau: theo quan sát của người dùng 10/11/2026, ở Ultra khoảng gấp 10 lần Pro (chưa đo). Mọi bản ghi Claude (message, quota sample, hệ số hiệu chỉnh) mang khoá `account` + `plan`; hệ số USD~/1% tuần lưu riêng từng account; không dùng chung hay quy đổi hệ số giữa hai gói; account thiếu hệ số → `?`.
- **Chỉ số chấp nhận:** `hh-ps` ấm p50 ≤ 1 s ở giai đoạn 1, ≤ 300 ms ở giai đoạn 2 (n=5; người dùng hạ ngưỡng giai đoạn 1 ngày 10/11/2026); output JSON trùng bản 0.37.3 (golden test + so trực tiếp 770 trường, trừ trường tự đổi); thay đổi hiện trên pane ≤ 3 s; 3 phiên mở, máy rảnh: indexer + pane trung bình ≤ 2% CPU trong 10 phút.
- **Lane:** L2, người dùng duyệt spec/plan. Opus cắt 10 gói L1, gồm 1 spike (plan.md); mỗi giai đoạn phát hành riêng, lấy bản minor kế tiếp lúc gộp.
- **Người dùng cần làm:** duyệt hoặc sửa các quyết định 1–5 và chỉ số chấp nhận.

## 1. Bối cảnh

### 1.1 Nguồn dữ liệu hh-ps (khảo sát `output/llm/hand-ext/20261110-100314-363718-store-survey-a-codex/report.md`)

Đường dẫn tương đối `hybrid-hands/plugins/hybrid-hands/`. `H` = Claude config home, `S` = `~/.hybrid-hands`.

| Nhóm | Nguồn | Kiểu cập nhật | Đọc hiện nay |
|---|---|---|---|
| Codex | `~/.codex-hand/sessions/**/rollout-*.jsonl`, `archived_sessions` | append, move sang archive | toàn file (`lib/hh_ps/codex.py:187`, `:368`, `lib/hh_ps/native_source.py:30`, `lib/hh_ps/machine_usage.py:64`) |
| Claude | `H/projects/*/*.jsonl`, `subagents/agent-*.jsonl` | append | toàn file (`lib/hh_ps/transcript_source.py:148`, `:229`) |
| Claude | `H/sessions/*.json` | ghi đè | toàn file (`lib/hh_ps/claude_source.py:64`) |
| Ledger | `S/codex_usage.jsonl`, `S/go_usage.jsonl` | append | toàn file (`lib/hh_ps/codex.py:265`, `lib/hh_ps/week.py:162`) |
| Plugin state | `S/runs/*.json`, `meta.json`, ledger JSON array, `S/executions/*.json`, side state `*.json`, marker `.done` | atomic replace | toàn file (`lib/hh_ps/registry_source.py:132`, `:189`, `:210`, `lib/hh_ps/paseo_source.py:26`) |
| Quota/cache | `H/.statusline-*.json`, `.hh-claude-rate-limit.json`, `S/claude-calibration.json` | replace | toàn JSON + stat (`lib/hh_ps/week.py:292`, `:363`, `lib/hh_ps/claude_calibration.py:69`) |
| Claude machine USD | helper `statusline/.../usage_ledger.py:289` | append | có cursor inode/size/newline sẵn (`usage_ledger.py:198`) |

### 1.2 Khả năng live (khảo sát `…store-survey-b-codex/report.md`)

- Mod Claude Code: SessionStart trả `watchPaths`, sự kiện `FileChanged {file_path, event}`; `$.fs.read/stat` không spawn (giới hạn 4 MiB). Chưa rõ watch ngoài cwd/đệ quy → cần spike.
- Paseo SDK: chỉ RPC request/response; server dùng được `node:fs` `watch`.
- Hook Claude: payload có `session_id`, `transcript_path`, `cwd`; plugin hiện chỉ dùng SessionStart/UserPromptSubmit.
- Python stdlib có `select.kqueue` (không đệ quy, 1 fd/vnode); không có FSEvents.

## 2. Thiết kế

### 2.1 Kho `hh-store`

Module mới `lib/hh_store/`. Schema (khởi từ đề xuất khảo sát, cắt tối thiểu):

- `meta(key PK, value)`: `schema_version`, `parser_version`, `revision` (số nguyên tăng), `last_read_at`.
- `files(file_id PK, path UNIQUE, scope, dev, inode, generation, offset, size, mtime_ns, parser_version, status)`; `scope` ∈ {codex_sessions, codex_archived, claude_transcript, claude_subagent, ledger_codex, ledger_go, state_json}.
- `codex_records(file_id, generation, byte_offset, thread_id, kind, observed_at, event_hash, payload_json, PK(file_id,generation,byte_offset))`: chỉ allowlist khoá hiện có ở `lib/hh_ps/native_source.py:24` (metadata/event), không chép nội dung chat.
- `claude_usage_lines(file_id, generation, byte_offset, account, …)` + `claude_file_info`: lưu từng dòng usage (id message/request, thời điểm, model, token, cwd/tiêu đề/effort/agentType/mốc kết thúc/context), không gộp theo message trong kho vì đường cũ lọc `since` trước rồi mới last-wins theo từng file (`lib/hh_ps/transcript_source.py:104`); last-wins giữ lúc đọc. `account` suy từ config home chứa file (v1 `~/.claude`, v2 `~/.claude-hand`, v… theo `claude_accounts`). Bảng `claude_messages` ban đầu không dùng.
- `claude_calibration(account PK, plan, usd_per_week_pct, samples, updated_at)`: hệ số riêng từng account (Ultra/Pro); P1.3 phát hiện trước đây chỉ có một hệ số lấy mẫu từ `~/.claude-hand` (v2) nhưng áp cho mọi dòng Claude kể cả v1 → đã tách; file hiệu chỉnh vẫn là nguồn chuẩn, file cũ không có account thuộc v2.
- `json_sources(path PK, stamp, payload_json)`: file JSON nhỏ ghi đè (state, quota, calibration) đã lọc allowlist trường hh-ps dùng.

Khử trùng thread/event, baseline token trước tuần, delta cumulative, quota delta, alias canonical giữ nguyên logic hiện tại; chỉ thay **nguồn dòng** (đọc từ bảng thay vì file). USD tính lúc đọc.

### 2.2 Ingest tăng dần (giai đoạn 1)

- Khoá ghi `~/.hybrid-hands/state/ingest.lock` (`flock` LOCK_EX, chờ tối đa 5 s; quá thời gian thì đọc kho hiện có, ghi cảnh báo stderr).
- Với mỗi file JSONL: stat → so `(dev, inode)`; khác hoặc `size < offset` → `generation+1`, xoá bản ghi generation cũ của file, đọc lại từ đầu. Ngược lại đọc từ `offset`, chỉ xử lý dòng kết thúc `\n`, commit offset tới newline cuối trong cùng transaction với bản ghi.
- File chuyển `sessions` → `archived_sessions`: hai `file_id` khác nhau; khử trùng theo `(thread_id, event_hash)` như `lib/hh_ps/machine_usage.py:74` nên không cộng trùng; native child vẫn chỉ đọc scope `codex_sessions`.
- File JSON ghi đè: stat stamp khác → đọc lại, lọc allowlist, upsert `json_sources`.
- Dòng lỗi: giữ hành vi strict/unknown hiện có (`lib/hh_ps/native_source.py:41`, `lib/hh_ps/codex.py:195`) bằng cờ `status` của file; không biến thiếu dữ liệu thành 0.
- Đổi `parser_version` hoặc `schema_version` → dựng lại kho.
- Writer plugin (`lib/hand_ext/run_registry.py:146`, `lib/hand_ext/execution_state.py:170`, `lib/side_session/state.py:64`) gọi `hh_store.bump_revision()` sau ghi thành công; lỗi kho không làm hỏng writer (bắt và bỏ qua).

### 2.3 Indexer và live (giai đoạn 2)

- `bin/hh-indexer`: singleton bằng `flock` LOCK_EX|LOCK_NB trên `indexer.lock` giữ suốt đời; bên thua thoát 0.
- Theo dõi: kqueue trên thư mục gốc rollout, thư mục ngày hiện tại, thư mục project Claude của phiên đang sống (từ `H/sessions/*.json`) và file JSONL đang hoạt động (giới hạn fd theo `RLIMIT_NOFILE`, mặc định ≤ 256); sự kiện → đánh dấu dirty → debounce 300 ms → ingest như 2.2 → `revision+1` → ghi `~/.hybrid-hands/state/revision` (atomic replace, nội dung là số revision).
- Quét stat dự phòng 30 s để bù sự kiện mất hoặc file mới ngoài vùng watch. Watcher chỉ đánh dấu dirty, không cộng USD trực tiếp.
- Vòng đời: `hh-store touch` (hook) và `hh-ps` khởi indexer nền nếu chưa chạy; indexer thoát khi `last_read_at` quá 10 phút; SIGTERM đóng kqueue/DB sạch.
- Hook mới trong `hooks/hooks.json`: SessionStart, Stop, SubagentStop, SessionEnd → `hh-store touch --path <transcript_path>`; tổng ≤ 50 ms, luôn exit 0, không in gì.
- Pane `hh-tree-pane`: SessionStart trả `watchPaths: [<file revision>]`; `FileChanged` → debounce 1 s → chạy `hh-ps` (đã nhanh) → vẽ lại. Dự phòng: mỗi 30 s `$.fs.stat` file revision, đổi thì làm mới. Nếu spike cho thấy `watchPaths` không theo dõi được đường dẫn ngoài cwd → chỉ dùng dự phòng stat 2 s.
  - Kết luận S0 (tài liệu plugin-authoring 2.1.322, 10/11/2026): mod nhận được `classic.FileChanged` và tự trả `watchPaths` qua `classic.SessionStart` (`types/claude-code.d.ts:1284-1297`, `:1407`); `watchPaths` chỉ đăng ký lúc SessionStart, không đăng ký giữa phiên. Đường dẫn tuyệt đối ngoài cwd, file chưa tồn tại và debounce **chưa rõ** → P2.3 chạy thí nghiệm 9 dòng (toast khi `touch` file revision và file chưa có) trong phiên mới trước khi chốt. `$.fs.stat` không spawn, dùng được trong `$.clock.every` (reference.md:210-215) → dự phòng: stat `revision` mỗi 2 s, chỉ chạy `hh-ps` khi `mtimeMs` đổi. Không dùng `fswatch` (lệnh ngoài cần cài).
- Panel Paseo: server `fs.watch` file revision → huỷ cache; RPC mới `hh-tree.revision` trả số revision; client hỏi revision mỗi 5 s, chỉ gọi `hh-tree.get` khi số đổi.

### 2.4 Bất biến bắt buộc (AGENTS.md)

- Rollout Codex chỉ ở `~/.codex-hand/sessions` và `archived_sessions` (không theo `CODEX_HOME`); native child chỉ `sessions`; không gọi RPC/API daemon.
- Không suy completed từ mtime/im lặng; unknown giữ `?`/null; không cộng trùng ledger và rollout; giá duy nhất từ file canonical, model lạ không fallback.
- Kho chỉ chứa metadata/số tổng hợp theo allowlist; không chép nội dung transcript, prompt, report hay credential. Quyền file kho `0600`, thư mục `0700`.
- Contract hiển thị (màu, đếm, pool, không giờ bắt đầu, orphan) không đổi.
- Quota/hiệu chỉnh Claude không trộn giữa account: Ultra và Pro có tỉ lệ USD~/1% tuần khác nhau (~10×); một account không mượn hệ số của account khác.

## 3. Chỉ số và cách đo

| Chỉ số | Ngưỡng | Cách đo |
|---|---|---|
| Thời gian `hh-ps` ấm | p50 ≤ 1 s (giai đoạn 1), ≤ 300 ms (giai đoạn 2), n=5 | `/usr/bin/time` lệnh pane, sau một lần ingest |
| Lần dựng kho đầu | ≤ thời gian 0.37.3 (~8,5 s) | xoá kho, chạy một lần |
| Tương đương output | 0 khác ngoài trường tự đổi | golden test (`tests/test_hh_ps_gpt_nguon.py:39`, `:82`, `:100`; `tests/test_hh_ps_native.py:43`, `:121`, `:134`; `tests/test_hh_ps_pricing_cache.py:10`) + so cũ/mới xen kẽ n=3 |
| Độ trễ live | ≤ 3 s | ghi một dòng token_count giả vào rollout fixture/thư mục tạm, đo tới khi revision đổi và pane vẽ |
| CPU nền | ≤ 2% trung bình 10 phút, 3 phiên mở | `ps` lấy mẫu mỗi 5 s |

## 4. Rủi ro

- `watchPaths` có thể không hỗ trợ ngoài cwd → spike trước gói P2.3, có dự phòng stat.
- kqueue mất sự kiện khi file rename/xoá → quét dự phòng 30 s + generation.
- Hai bản hh-ps cũ/mới cùng chạy khi một số phiên chưa reload → kho tách theo `schema_version`, bản cũ không đọc kho.
- Kho hỏng → xoá và dựng lại tự động (kiểm `PRAGMA quick_check` khi mở lỗi).
- Helper Claude của statusline là plugin riêng: không sửa; giai đoạn 1 đo riêng `week._usd_since`, chỉ đưa vào kho nếu vẫn vượt ngưỡng.
