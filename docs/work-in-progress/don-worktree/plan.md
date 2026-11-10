# Plan: dọn worktree và chặn đầy ổ

## Tóm tắt

- **Thực hiện [spec](spec.md)** qua 1 spike (S0) và 6 gói cỡ L1, phát hành **một bản minor**: lấy số minor kế tiếp lúc gộp (main hiện ở 0.48.0).
- **Thứ tự:**
  - P1 → P2 → P3 phải tuần tự vì cùng sửa `lib/side_session/`.
  - S0 → P4 tuần tự.
  - P5 (`hand-ext gc`) chạy song song với P1–P4 vì khác thư mục.
  - P6 làm cuối: tài liệu, phát hành và kiểm chứng thật.
- **Ước lượng tổng:** khoảng 9–11 giờ việc của AI cộng 30 phút người dùng duyệt (spec, plan và lần `--apply` thật).
- **Trạng thái:** chờ người dùng duyệt spec và plan, chưa code.
- **Điều kiện bắt đầu:** người dùng chốt mặc định `worktree_gc.auto` và pattern sparse cho `live-tiktok-games` (spec mục 3.1, 3.2).

## Gói việc

| Gói | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|
| S0 | Spike sparse checkout trong worktree, git 2.55: cô lập giữa các worktree, an toàn khi commit/merge/rebase, hand-ext tạo worktree con từ worktree sparse | ghi kết quả vào `spike-s0.md` trong thư mục này | — |
| P1 | Phân lớp A–E, ghi `base` vào state, lệnh `side-session gc` dry-run (bảng và `--json`) | `lib/side_session/gc.py` (mới), `state.py`, `cli.py`, `actions.py`, test mới | — |
| P2 | `--apply`: khoá repo, kiểm tra lại trước khi xoá, `git worktree remove` không force, `--include-unmerged`, `--prune-branches`, nhật ký `worktree-gc.jsonl`, `worktree prune` | `lib/side_session/gc.py`, test | P1 |
| P3 | Tự dọn lớp A khi `start` (`worktree_gc.auto`), helper disk guard, chặn và cảnh báo ở `side-session start` | `lib/side_session/actions.py`, `paseo.py`, `config.py`, `constants.py`, helper disk | P2 |
| P4 | `worktree_sparse_exclude` và `--no-sparse` khi tạo worktree | `lib/side_session/commands.py`, `paseo.py`, `config.py`, `cli.py` | S0, P3 (cùng file `paseo.py`, `config.py`) |
| P5 | `hand-ext gc` (dry-run và `--apply`), disk guard ở `hand-ext run` | `lib/hand_ext/` (file gc mới, `cli.py`, `isolation.py`), test | — (dùng helper disk của P3: P5 viết trước nếu xong sớm, P3 dùng lại) |
| P6 | README, skill `side-session` và `ext-hand`, CHANGELOG, version; cài v1 và v2; dry-run thật trên `live-tiktok-games`; `--apply` sau khi người dùng duyệt; phiên thử có sparse | tài liệu, `plugin.json` | P1–P5 |

## Việc cần làm

- [ ] S0 spike sparse trong worktree — covers: spec 3.2 — estimate: 1 h
- [ ] P1 phân lớp A–E, `base` trong state, `side-session gc` dry-run, test fixture repo tạm năm lớp (gồm ca squash/cherry-pick) — covers: spec 2.1, 5.1 ca 1 — estimate: 2 h
- [ ] P2 `--apply` an toàn (khoá, kiểm tra lại, không force, giữ nhánh, nhật ký, cờ `--include-unmerged` và `--prune-branches`) — covers: spec 2.2, 2.3, 5.1 ca 2 — estimate: 2 h
- [ ] P3 tự dọn khi start và disk guard của side-session — covers: spec 3.1, 3.3, 5.1 ca 3 (disk) — estimate: 1,5 h
- [ ] P4 sparse exclude và `--no-sparse` — covers: spec 3.2, 5.1 ca 3 (sparse) — estimate: 1,5 h
- [ ] P5 `hand-ext gc` và disk guard ở `hand-ext run` — covers: spec 3.3, 4, 5.1 ca 3 (hand-ext) — estimate: 1,5 h
- [ ] P6 tài liệu, phát hành, cài, kiểm chứng thật (dry-run, `--apply` có duyệt, phiên thử sparse), ghi số đo vào plan — covers: spec 5.2, 5.3 — estimate: 1 h AI + 30 phút người dùng

## Kiểm chứng mỗi gói

- **Trong lúc làm:** chỉ chạy test hẹp của file test mới, ví dụ `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_gc.py' -q`.
- **Cuối P6:** test đầy đủ `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -q`, chạy đúng một lần.
- **Review:** brain review diff từng gói. Riêng P2 và P5 (hai chỗ xoá dữ liệu) phải đọc kỹ đường dẫn, cờ git và chỗ kiểm tra lại trước khi xoá.
- **Tick:** chỉ tick sau khi test hẹp xanh và brain đã review. Ghi số đo thật của P6 ngay dưới dòng tick.
