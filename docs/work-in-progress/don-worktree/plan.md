# Plan: dọn worktree và chặn đầy ổ

## Tóm tắt

- **Thực hiện [spec](spec.md)** qua 1 spike (S0) và 6 gói cỡ L1, phát hành **một bản minor**: đã phát hành 0.50.0 sau account sync 0.49.0 (merge c210946); merge release e85b80d, đã push main.
- **Thứ tự:**
  - P1 → P2 → P3 phải tuần tự vì cùng sửa `lib/side_session/`.
  - S0 → P4 tuần tự.
  - P5 (`hand-ext gc`) chạy song song với P1–P4 vì khác thư mục.
  - P6 làm cuối: tài liệu, phát hành và kiểm chứng thật.
- **Ước lượng tổng:** khoảng 9–11 giờ việc của AI cộng 30 phút người dùng duyệt (spec, plan và lần `--apply` thật).
- **Trạng thái:** spec/plan đã được người dùng duyệt ngày 10/11/2026. S0 lần đầu FAIL ở baseline của helper hand-ext; sau khi sửa `isolation._snapshot_tree`, chạy lại PASS ngày 10/11/2026. P4 xong trong 0.51.0. Config sparse cho `live-tiktok-games` chưa ghi. Xem [bằng chứng](spike-s0.md).
- **Quyết định đã duyệt:** `worktree_gc.auto = "merged"`; sparse mặc định `[]`; hai pattern `docs/work-in-progress/handoffs/*-data/` và `docs/work-in-progress/handoffs/*-shots/`. Config repo thật do Opus làm (S0 đã đạt, config chưa ghi), ngoài phạm vi hand; không thử sparse trên repo thật. P6 GC thật chỉ dry-run, không apply thật.

## Gói việc

| Gói | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|
| S0 | Spike sparse checkout trong worktree, git 2.55: cô lập giữa các worktree, an toàn khi commit/merge/rebase, hand-ext tạo worktree con từ worktree sparse | ghi kết quả vào `spike-s0.md` trong thư mục này | — |
| P1 | Phân lớp A–E, ghi `base` vào state, lệnh `side-session gc` dry-run (bảng và `--json`) | `lib/side_session/gc.py` (mới), `state.py`, `cli.py`, `actions.py`, test mới | — |
| P2 | `--apply`: khoá repo, kiểm tra lại trước khi xoá, `git worktree remove` không force, `--include-unmerged`, `--prune-branches`, nhật ký `worktree-gc.jsonl`, `worktree prune` | `lib/side_session/gc.py`, test | P1 |
| P3 | Tự dọn lớp A khi `start` (`worktree_gc.auto`), helper disk guard, chặn và cảnh báo ở `side-session start` | `lib/side_session/actions.py`, `paseo.py`, `config.py`, `constants.py`, helper disk | P2 |
| P4 | Đã xong trong 0.51.0: `worktree_sparse_exclude` và `--no-sparse` khi tạo worktree | `lib/side_session/commands.py`, `paseo.py`, `config.py`, `cli.py` | S0, P3 (cùng file `paseo.py`, `config.py`) |
| P5 | `hand-ext gc` (dry-run và `--apply`), disk guard ở `hand-ext run` | `lib/hand_ext/` (file gc mới, `cli.py`, `isolation.py`), test | — (dùng helper disk của P3: P5 viết trước nếu xong sớm, P3 dùng lại) |
| P6 | README, skill `side-session` và `ext-hand`, CHANGELOG, version; cài v1 và v2; dry-run thật trên `live-tiktok-games`; không apply GC thật, không thử sparse trên repo thật | tài liệu, `plugin.json` | P1–P3/P5 (P4 phát hành riêng 0.51.0) |

## Việc cần làm

- [x] S0 spike sparse trong worktree — covers: spec 3.2 — estimate: 1 h
- [x] P1 phân lớp A–E, `base` trong state, `side-session gc` dry-run, test fixture repo tạm năm lớp (gồm ca squash/cherry-pick) — covers: spec 2.1, 5.1 ca 1 — estimate: 2 h
- [x] P2 `--apply` an toàn (khoá, kiểm tra lại, không force, giữ nhánh, nhật ký, cờ `--include-unmerged` và `--prune-branches`) — covers: spec 2.2, 2.3, 5.1 ca 2 — estimate: 2 h
- [x] P3 tự dọn khi start và disk guard của side-session — covers: spec 3.1, 3.3, 5.1 ca 3 (disk) — estimate: 1,5 h
- [x] P4 sparse exclude và `--no-sparse` — covers: spec 3.2, 5.1 ca 3 (sparse) — estimate: 1,5 h
- [x] P5 `hand-ext gc` và disk guard ở `hand-ext run` — covers: spec 3.3, 4, 5.1 ca 3 (hand-ext) — estimate: 1,5 h
- [x] P6 tài liệu, phát hành, cài, kiểm chứng GC thật chỉ dry-run (không apply thật, không thử sparse trên repo thật), ghi số đo vào plan — covers: spec 5.2, 5.3 — estimate: 1 h AI + 30 phút người dùng
  - **Số đo thật P6 (0.50.0 đã cài, 10/11/2026 19:48–19:49 +07):** side-session GC live: 137 worktree, A1/B6/C20/D69/E41, eligible 65.181.552 byte, 37,12s, nhánh 252→252; hand-ext GC claude-plugins: finished1/dirty18/unknown75, 6.437.025 byte, 13,27s, nhánh 86→86; hand-ext GC live: unknown94/eligible0, 2,72s, nhánh 252→252. Cả ba exit0, không apply thật.
  - **Cài/kiểm:** official marketplace/plugin update v1/v2 exit0; 32 kiểm tra cài đặt exit0, version/folderVersion 0.50.0, cache code khớp source merge; cần reload. Validate plugin exit0/success=true, manifest 0 lỗi/0 cảnh báo; directory advisory LICENSE_MISSING/ICON_MISSING còn nguyên. 22 relative file links hợp lệ.
  - **Giới hạn:** full suite chạy đúng một lần: 575 tests, failures2/errors3, exit1; hai errors mới đã sửa + test hẹp3 OK, không chạy lại full suite. Còn pytest thiếu và hai assert policy có trên main. Đối chiếu tay 10 mẫu có 1A/2B/2C/2D/3E, chưa đủ 2A vì thực tế chỉ có 1A. Không kiểm số byte thu hồi thật hoặc sparse <=15MB. Xem gc-approval-table.md, các *-measurement.json và full-suite-result.json.

## Kiểm chứng mỗi gói

- **Trong lúc làm:** chỉ chạy test hẹp của file test mới, ví dụ `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_gc.py' -q`.
- **Cuối P6:** test đầy đủ `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -q`, chạy đúng một lần.
- **Review:** brain review diff từng gói. Riêng P2 và P5 (hai chỗ xoá dữ liệu) phải đọc kỹ đường dẫn, cờ git và chỗ kiểm tra lại trước khi xoá.
- **Tick:** chỉ tick sau khi test hẹp xanh và brain đã review. Ghi số đo thật của P6 ngay dưới dòng tick.

### Review thực hiện

- P1: Sol review diff đạt; `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_gc.py' -q`: 3 tests OK (Sol chạy lại 10/11/2026).
- S0: lần đầu Sol chạy lại `python3 docs/work-in-progress/don-worktree/spike_s0.py`: exit 1, CASE3 baseline FAIL. Sau khi sửa `_snapshot_tree` seed index tạm từ index thật, chạy lại exit 0 (PASS) ngày 10/11/2026, output ở `spike-s0-rerun.txt`; test `test_hand_ext_isolation_sparse.py` 1 OK.
- P4: `test_side_session_sparse.py` 3 OK; `test_side_session_c*.py` 17 OK; `test_side_session_gc*.py` 6 OK. Phát hành 0.51.0; chưa kiểm chứng start end-to-end thật, lỗi giữa chừng trên git thật, ≤15 MB trên repo thật.

- P2: Sol review đường dẫn/common-dir/inode/HEAD, flock repo, recheck, remove không force và journal đạt; test hẹp `test_side_session_gc.py`: 3 tests OK (Sol chạy lại). Apply chỉ fixture giả, không repo thật.

- P1 mở lại review: dry-run metadata thật phát hiện macOS screen -ls trả 1 cùng danh sách socket hợp lệ; current parser giữ nhầm terminal screen ở D. Đã giao Codex sửa cùng backend lượt 1, chưa tick lại. Đo ban đầu chỉ chẩn đoán, chưa dùng làm bảng duyệt xoá cuối.

- P1 rework screen (cùng backend Codex lượt 1): Sol review parser snapshot đầy đủ với return0/1, alive exact và unknown fail-closed đạt; test hẹp `test_side_session_gc.py`: 3 tests OK. Đã tick lại P1 sau rework.

- P5: Sol review ownership/common-dir/registry, lock + fresh recheck, remove không force, journal, read-only Git/index và latest epoch đạt. `test_hand_ext_gc.py`: 1 test OK; `test_disk_guard.py`: 2 tests OK (Sol chạy lại). Chỉ apply fixture giả. Test budget tính cả gói P5, không theo delta từng rework.

- P3: Sol review central start gate trước tạo handoff/state/worktree, auto chỉ A và gc lỗi không bỏ disk check đạt. `test_side_session_gc_start.py`: 3 tests OK (Sol chạy lại); không auto-GC trong dry-run/resume/non-worktree.

### P6 — hoàn tất phạm vi dry-run và phát hành, toàn gói xong một phần

Đã review tài liệu, phát hành 0.50.0 (e85b80d) và cập nhật plugin v1/v2 chính thức; P6 tick sau kiểm tra hẹp/review và số đo trên. Full suite không xanh, các giới hạn được giữ nguyên trong bàn giao. S0 PASS sau sửa baseline, P4 xong trong 0.51.0; chưa cấu hình sparse cho repo thật, không apply GC thật. JSON patterns đã duyệt bàn giao cho Opus ghi.

- P5 mở lại review cuối: cần giữ candidate chứa registry run_dir (artifacts) hoặc machine_state_dir (registry/journal), đã giao lại Claude-v2 lượt 1; chưa tick lại.

- P5 rework artifacts: Sol review containment paths của run_dir và machine_state_dir đạt; `test_hand_ext_gc.py`: 1 test OK (Sol chạy lại). Wrapper followup có report/patch áp thành công nhưng lifecycle unresolved, recover chính thức exit 1 StateConflict; giữ state/reservation để Opus xử lý, không sửa module ngoài phạm vi.

- Full suite cuối đã chạy đúng một lần: `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -q` — 575 tests/94.874s, exit 1, failures=2/errors=3. Hai errors mới do auto-GC không nuốt TypeError/AttributeError đã được Sol sửa hẹp thành cảnh báo (ngoại lệ tool lỗi: managed recover exit 1 StateConflict), giữ disk guard độc lập; test mới `test_side_session_gc_start.py` chạy lại 3 OK. Không chạy lại full suite. Ba lỗi ngoài phạm vi: test_account_sync import pytest thiếu; hai assert policy cũ. Hai implementation policy và test của chúng trùng byte với origin/main c210946, không sửa. Không claim full suite xanh.
