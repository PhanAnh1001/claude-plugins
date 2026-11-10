# Spec: dọn worktree và chặn đầy ổ cho hybrid-hands

## Tóm tắt quyết định (1 trang)

- **Vấn đề:** plugin tạo worktree cho mỗi phiên phụ và lượt hand nhưng không bao giờ tự xoá. Ngày 10/11/2026, repo `live-tiktok-games` dồn tới 171 worktree, khoảng 30 GB, chỉ trong 6 ngày (worktree cũ nhất tạo 04/11). Ổ 228 GB chỉ còn 1,7 GB trống. Máy ảo Docker chết lúc 20:59 UTC ngày 09/11 với lỗi `no space left on device`.
- **Số đo trên máy, ngày 10/11/2026:**
  - Trong 135 worktree còn lại, 95 cái có bản ghi state của `side-session`, và **cả 95 đã kết thúc** (66 `stopped`, 28 `done`, 1 `dead`). 40 cái còn lại do brain tự chạy `git worktree add` (tên dạng `FIX-*`, `MAIN-*`, `PREVIEW-*`).
  - Mỗi worktree tạo từ `origin/main` chép ra khoảng 227 MB file git theo dõi. Trong đó 216 MB là bằng chứng review trong `docs/work-in-progress/handoffs/*-data/` và `*-shots/`.
  - Ngoài ra còn file git bỏ qua: `sessions/` và `output/` (tổng ~1,8 GB) và 21 thư mục `node_modules`.
  - `~/.hybrid-hands/worktrees` còn sót 54 worktree của hand-ext, tổng 535 MB.
- **Nguyên nhân trong plugin:**
  - `side-session stop` chỉ in ra lệnh xoá ("worktree kept; remove with …"). Trạng thái `done` cũng giữ nguyên worktree.
  - Không có lệnh dọn theo lô.
  - Không có cách loại thư mục nặng khi tạo worktree.
  - Không kiểm tra dung lượng trống trước khi tạo worktree mới.
  - hand-ext chỉ xoá worktree khi lượt chạy kết thúc bình thường; lượt bị crash để sót worktree.
- **Quyết định:**
  1. **`side-session gc`**: mặc định chỉ liệt kê (dry-run); thêm `--apply` mới xoá. Phân lớp worktree theo bảng ở mục 2.1. Chỉ xoá worktree thuộc plugin, đã kết thúc và sạch. **Luôn giữ nhánh**, nên commit không mất; khôi phục bằng `git worktree add <dir> <branch>`.
  2. **Tự dọn khi `side-session start`:** trước khi tạo worktree mới, tự dọn lớp A (đã merge). Cấu hình `side_session.worktree_gc.auto = "merged" | "off"`, mặc định `merged` (đã được người dùng duyệt ngày 10/11/2026).
  3. **Sparse checkout (P4 bị chặn, chưa phát hành):** thiết kế cấu hình theo repo `side_session.worktree_sparse_exclude`, mặc định `[]`, và cờ `--no-sparse`. Chỉ triển khai sau khi sửa baseline và S0 đạt.
  4. **Chặn đầy ổ:** trước khi tạo worktree (`side-session start`, `hand-ext run`), kiểm tra dung lượng trống. Dưới `disk_guard.warn_gb` (20) thì cảnh báo; dưới `disk_guard.block_gb` (5) thì từ chối và gợi ý `side-session gc`.
  5. **`hand-ext gc`**: xoá worktree hand sót lại khi lượt chạy tương ứng đã ở trạng thái kết thúc trong run registry. Lượt không rõ trạng thái thì giữ.
  6. **Worktree không thuộc plugin:** chỉ báo cáo, không bao giờ xoá; không suy quyền sở hữu từ tên thư mục.
- **Chỉ số chấp nhận:**
  - Dry-run trên `live-tiktok-games` không xoá gì và phân lớp đúng 135 worktree. Đối chiếu tay 10 mẫu, gồm ít nhất 2 mẫu mỗi lớp.
  - Sau `--apply` có người dùng duyệt: mọi nhánh còn nguyên (đếm `git branch` trước và sau bằng nhau); dung lượng thu hồi khớp con số dry-run dự kiến (lệch ≤ 5%).
  - Worktree mới có sparse chiếm ≤ 15 MB file theo dõi với pattern mặc định đề xuất cho `live-tiktok-games` (hiện ~227 MB).
- **Lane:** L2, người dùng duyệt spec và plan trước khi code. Plan cắt 1 spike và 6 gói L1 (xem [plan](plan.md)), phát hành một bản minor.
- **Trạng thái phê duyệt:** spec/plan đã được người dùng duyệt ngày 10/11/2026; chốt `auto = "merged"`, sparse mặc định `[]` và hai pattern ở mục 3.2. Cấu hình `live-tiktok-games` do Opus làm sau khi S0 đạt (hiện chưa đạt), ngoài phạm vi hand. P6 chỉ GC thật dry-run; không apply GC thật hoặc thử sparse trên repo thật.
- **Kết quả S0:** Git 2.55.0 đạt cô lập và commit/merge/rebase, nhưng helper `isolation.prepare` làm thiếu file bị loại trong baseline tree và ghi nhầm vào `dirty_files`. **S0 FAIL, chặn P4** đến khi sửa và kiểm chứng lại; xem [bằng chứng S0](spike-s0.md). Sol đã chạy lại và review FAIL; không tick S0/P4.

## 1. Bối cảnh

### 1.1 Code hiện tại (đường dẫn tương đối `hybrid-hands/plugins/hybrid-hands/`)

| Chỗ | Hành vi hiện tại |
|---|---|
| `lib/side_session/commands.py:34` `worktree_cmd` | `git worktree add <worktree_root>/<name> -b side/<name> <base>`, lấy đủ file |
| `lib/side_session/constants.py:48` | `worktree_root` mặc định `../{repo}-wt` |
| `lib/side_session/actions.py:614` `stop` | Giữ worktree, chỉ in lệnh xoá cho người dùng tự chạy |
| `lib/side_session/state.py` | Có `name`, `dir`, `status`, `handoff`, `worktree`, `role`; **không lưu `base`** |
| `lib/side_session/paseo.py:294` `tidy_workspace` | Archive workspace Paseo; theo contract 09/11 thì giữ thư mục local |
| `lib/hand_ext/isolation.py:144,394` | Worktree hand `<worktree_root>/<name>-<run_id>`; `_remove_worktree` chỉ chạy ở đường kết thúc bình thường |

### 1.2 Ngoài phạm vi

- Tối ưu Docker trong `ai-luxian` (`make test-db` thiếu `-v`) và trong `tcp-assistant` (vị trí `ARG GIT_SHA`). Hai việc này sửa ở repo riêng.
- Xoá các worktree hiện có trên máy. Việc này chỉ làm sau khi phát hành, bằng chính lệnh `gc` và có người dùng duyệt.
- Đổi quy trình brain tự chạy `git worktree add` trong `live-tiktok-games`. Plugin chỉ báo cáo các worktree này; muốn đổi quy trình thì sửa AGENTS của repo đó.

## 2. `side-session gc`

### 2.1 Phân lớp

Một worktree **thuộc plugin** khi có bản ghi state `side-session` với `worktree=true` và `dir` trỏ đúng thư mục (so đường dẫn đã resolve).

| Lớp | Điều kiện (đủ tất cả) | Hành vi |
|---|---|---|
| A: đã merge | Thuộc plugin; status kết thúc (`done`, `stopped`, `dead`, `capped`, `error`); không còn agent Paseo hay screen sống; sạch (không có file theo dõi bị sửa, không có file untracked chưa bị bỏ qua); nhánh có HEAD là tổ tiên của base, **hoặc** `git cherry <base> HEAD` không còn dòng `+` | `--apply` xoá worktree, kể cả file git bỏ qua; giữ nhánh |
| B: sạch, chưa merge | Như A nhưng còn commit chưa có trong base | Chỉ liệt kê, kèm số commit ahead; xoá khi có `--include-unmerged`; giữ nhánh |
| C: còn thay đổi | Có file theo dõi bị sửa, hoặc có file untracked chưa bị bỏ qua | Không bao giờ xoá |
| D: đang chạy hoặc chưa rõ | Status `running`, `idle`, `idle_no_done`, `unknown`; hoặc tra Paseo lỗi; hoặc workspace Paseo chưa archive | Không bao giờ xoá |
| E: không thuộc plugin | Nằm trong `worktree_root` (hoặc trong `git worktree list`) nhưng không có bản ghi state | Chỉ báo cáo |

- **Base:** state chưa lưu base. Từ bản này, `start` ghi `base` vào state. Bản ghi cũ thiếu base thì dùng `side_session.default_base`.
  - So với cả `<base>` cục bộ và `origin/<base>` (nếu có ref); merge vào một trong hai là đủ.
  - Không tự `git fetch`; muốn fetch thì thêm cờ `--fetch`.
- **Báo cáo dry-run:** mỗi dòng gồm lớp, tên, nhánh, số commit ahead, dung lượng chia theo phần theo dõi và phần bị bỏ qua, lý do bị chặn. Cuối bảng là tổng dung lượng thu hồi được của lớp A (và của B khi có `--include-unmerged`). Có thêm `--json`.

### 2.2 Áp dụng

- **Khoá:** mỗi repo một khoá (dùng lại helper khoá của state). Hai lệnh `gc` chạy cùng lúc thì lệnh sau đợi hoặc báo bận.
- **Kiểm tra lại trước khi xoá:** ngay trước khi xoá từng worktree, phân lớp lại một lần nữa. Lớp đổi thì bỏ qua và ghi lý do.
- **Lệnh xoá:** `git worktree remove <dir>`, **không** `--force`. Git chỉ coi file theo dõi bị sửa hoặc file untracked chưa bị bỏ qua là "bẩn", nên file bị bỏ qua (`sessions/`, `output/`) bị xoá cùng worktree. Thử thật ngày 10/11/2026: xoá thành công 37 worktree, có cái mang 80 MB `sessions/`.
- **Nhánh:** mặc định giữ. Cờ `--prune-branches` chạy `git branch -d` (chữ `d` thường, git tự từ chối xoá nhánh chưa merge), chỉ áp cho lớp A.
- **Nhật ký:** thêm một dòng vào `<state_dir>/worktree-gc.jsonl` cho mỗi worktree đã xoá: thời điểm, tên, nhánh, SHA của HEAD, số byte thu hồi, lớp. Nhờ đó khôi phục được bằng `git worktree add <dir> <branch>`.
- Cuối cùng chạy `git worktree prune`.

### 2.3 Dữ liệu

- `gc` chỉ đọc metadata: trạng thái git, kích thước, state. Không đọc nội dung file.
- Dữ liệu trong thư mục bị bỏ qua có thể chứa dữ liệu người thật (ví dụ `sessions/` của `live-tiktok-games`). Xoá đi là giảm rủi ro lộ dữ liệu, nhưng báo cáo dry-run phải ghi rõ dung lượng phần này để người dùng thấy trước khi xoá.

## 3. Ngăn worktree phình

### 3.1 Tự dọn khi start

- `side_session.worktree_gc.auto`: `"merged"` (mặc định đã duyệt) hoặc `"off"`.
- Khi là `merged`, `start --worktree` chạy gc lớp A của repo trước `git worktree add`, không tính `--include-unmerged`. Lỗi gc chỉ cảnh báo, không chặn start.

### 3.2 Sparse checkout — thiết kế đã duyệt, P4 blocked

S0 đã được Sol chạy lại/review FAIL ở baseline `isolation.prepare`; các cấu hình/cờ dưới đây chưa có trong release P1–P3/P5. Không ghi config hoặc thử trên live-tiktok-games.

- `side_session.worktree_sparse_exclude`: danh sách pattern theo cú pháp gitignore, mặc định `[]`.
- Khi danh sách khác rỗng, `start` làm lần lượt: `git worktree add --no-checkout …` → `git -C <wt> sparse-checkout set --no-cone '/*' '!<pattern>'…` → `git -C <wt> checkout`.
- Cờ `--no-sparse` bỏ qua cấu hình này.
- Pattern cho `live-tiktok-games` đã được người dùng duyệt ngày 10/11/2026; Opus chỉ đặt trong `.claude/hybrid-hands.json` sau khi S0 đạt (hiện không đạt), ngoài task này: `docs/work-in-progress/handoffs/*-data/` và `docs/work-in-progress/handoffs/*-shots/`. Hai pattern này bỏ được 216 MB trên tổng 227 MB.
- Spike S0 cần xác nhận với git 2.55:
  1. sparse của worktree không ảnh hưởng checkout chính hay worktree khác;
  2. commit, merge và rebase trong worktree sparse không xoá nhầm file đã bị loại khỏi checkout;
  3. `hand-ext` khi tạo worktree con từ worktree sparse vẫn chạy đúng.

### 3.3 Chặn đầy ổ

- Helper chung đọc dung lượng trống bằng `shutil.disk_usage` trên ổ chứa `worktree_root`.
- Dưới `disk_guard.warn_gb` (mặc định 20): in cảnh báo kèm gợi ý `side-session gc`.
- Dưới `disk_guard.block_gb` (mặc định 5): `side-session start --worktree` và `hand-ext run` dừng với mã thoát 9, không tạo worktree. Cờ `--ignore-disk-guard` để vượt chặn khi người dùng chủ động.

## 4. `hand-ext gc`

- Duyệt `<ext_hand.worktree_root>/*`. Tách `run_id` từ tên `<name>-<run_id>` rồi tra run registry.
- Chỉ xoá worktree sạch có ownership registry chính xác, run đã kết thúc và completion evidence (`changes.patch`, report hoặc exit code). Managed execution phải settled; detached HEAD khác base ghi nhận thì giữ. Apply khoá repo, recheck rồi dùng `isolation._remove_worktree` không force.
- Không tìm thấy run, hoặc run còn chạy: giữ nguyên và liệt kê là `unknown`.
- Mặc định dry-run, `--apply` mới xoá, cuối cùng `git worktree prune` trên repo nguồn. Mỗi lượt xoá ghi một dòng nhật ký như mục 2.2.

## 5. Tiêu chí chấp nhận và test

### 5.1 Test (mức tối thiểu theo AGENTS repo; fixture là repo git tạm, không dùng dữ liệu thật)

1. **Phân lớp:** một repo tạm có đủ năm lớp A–E, gồm cả ca nhánh đã squash hoặc cherry-pick (`git cherry` không còn `+`). Dry-run không xoá gì và JSON đúng lớp.
2. **Áp dụng an toàn:**
   - `--apply` chỉ xoá lớp A, và lớp B khi có cờ;
   - nhánh còn nguyên, nhật ký đủ trường;
   - worktree bị sửa giữa lúc liệt kê và lúc xoá thì bị bỏ qua.
3. **Ngăn phình:**
   - sparse loại đúng pattern và checkout chính không đổi;
   - disk guard cảnh báo và chặn đúng ngưỡng (giả lập `disk_usage`);
   - `hand-ext gc` xoá run đã kết thúc, giữ run không rõ.

Test đầy đủ của plugin chạy đúng một lần ở cuối.

### 5.2 Kiểm chứng thật

- Cài bản mới, chạy `side-session gc` (dry-run) trên `live-tiktok-games`, so với số đo ở mục tóm tắt.
- P6 hiện chỉ được chạy GC thật dry-run; không chạy `--apply` thật trong phạm vi đã duyệt này.
- Không thử sparse trên `live-tiktok-games`; S0 chỉ dùng repo giả `/tmp`. Cấu hình hai pattern đã duyệt do Opus thực hiện sau khi S0 đạt (hiện chưa đạt).

### 5.3 Tài liệu

Cập nhật trong cùng bản phát hành:
- README của plugin;
- skill `side-session` (Sol dry-run rồi `side-session gc --name <gói> --apply` sau merge khi brief/session cho phép; cấm apply/cần duyệt thì dừng ở dry-run);
- skill `ext-hand`;
- CHANGELOG và tăng version minor.

### 5.4 Trạng thái phát hành

Đã phát hành 0.50.0 sau account sync 0.49.0, merge `e85b80d` và push main. P1/P2/P3/P5 đã review và test hẹp đạt; P6 đã validate/cài v1/v2 và đo GC thật chỉ dry-run. Full suite chạy đúng một lần (575 tests, failures=2/errors=3); hai errors auto-GC được sửa và test hẹp xanh lại, ba lỗi ngoài phạm vi còn lại không sửa, không chạy lại full suite. Xem số đo thật và giới hạn ở [plan](plan.md). P4 blocked do S0 FAIL. Không có GC apply thật, không có đo sparse <=15 MB, không ghi config live-tiktok-games.
