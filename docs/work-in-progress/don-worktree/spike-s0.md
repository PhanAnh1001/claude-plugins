# S0 sparse worktree — 10/11/2026

**Kết luận: FAIL, chặn P4.** Git 2.55.0 đạt 2 ca Git thuần; ca helper tạo child thành công nhưng baseline sai. Chưa Sol review, không tick plan. Không sửa code plugin hay config/runtime.

## Chạy lại và fixture

Chạy tại gốc checkout repo:

```sh
git --version
python3 docs/work-in-progress/don-worktree/spike_s0.py
```

Lệnh cuối exit **1**, assertion đúng nguyên nhân: `CASE 3 FAIL: excluded tracked files incorrectly reported as baseline deletions`. Script có đúng 3 ca spike, timeout 30 giây mỗi lệnh Git, chỉ dùng file giả. Không launch model, không dùng auth/API. Git config global/system được bỏ qua cho fixture; identity giả chỉ truyền qua env cho subprocess.

Fixture lần chạy bản lưu: `/tmp/don-s0-veycr571` (Git resolve thành `/private/tmp/...`). Main, sibling, sparse và child đều nằm dưới đường dẫn này. Các lần thăm dò trước dùng `/tmp/don-s0-3_zqnxmt`, `/tmp/don-s0-irz65p_j`, `/tmp/don-s0-0k9n0x64`; đều đã dọn.

## Ba ca và bằng chứng

1. **PASS — cô lập sparse.** Tạo main và sibling đầy đủ, sparse bằng chuỗi lệnh dưới. Hai file `demo-data/item.txt`, `demo-shots/item.txt` vắng trong sparse nhưng còn trên main/sibling; hai checkout đó sạch. `core.sparseCheckout=true` ở worktree sparse; không có key này trong local config dùng chung.

   ```sh
   git worktree add --no-checkout <sparse> -b sparse
   git -C <sparse> sparse-checkout set --no-cone '/*' '!docs/work-in-progress/handoffs/*-data/' '!docs/work-in-progress/handoffs/*-shots/'
   git -C <sparse> checkout
   ```

2. **PASS — commit/merge/rebase.** Sửa `src/app.txt` rồi `git add -A`, commit trong sparse; main thêm `src/merged.txt`, sparse merge main; main thêm `src/rebased.txt`, sparse rebase main. Sau từng thao tác, `git rev-parse HEAD:<excluded-file>` giữ nguyên blob ID của cả hai file bị loại. Sau rebase, sparse sạch và hai file vẫn không materialize. Đây là luồng không conflict, không chứng minh các luồng conflict hoặc sửa nội dung file bị loại.

3. **FAIL — helper child từ sparse.** Gọi thật `isolation.prepare(cfg, sparse, 's0', run_dir, IsolationChoice('worktree'))` với mọi đường dẫn cfg trỏ vào fixture. Parent có một tracked edit và một file untracked giả. Child tạo được, nhận đủ hai thay đổi và giữ đúng blob ID trong HEAD; cả hai file bị loại không materialize. Nhưng `git cat-file -e <baseline_tree>:<excluded-file>` trả khác 0 cho cả hai. `ctx.dirty_files` thực tế:

   ```text
   docs/work-in-progress/handoffs/demo-data/item.txt
   docs/work-in-progress/handoffs/demo-shots/item.txt
   src/app.txt
   src/untracked.txt
   ```

   Hai dòng đầu không phải thay đổi người dùng. `_snapshot_tree` dùng index riêng khởi đầu rỗng rồi `git add -A` trong sparse, nên baseline thiếu các tracked file không checkout. Chưa kết luận patch cuối sẽ xoá file ở parent: S0 chỉ gọi prepare, không finalize/apply. Sol cần xử lý tương thích baseline trước P4 rồi chạy lại đúng ca này.

## Dọn fixture

Script khôi phục tracked edit giả bằng `git restore`, unlink đúng file untracked mình tạo, kiểm `git status --porcelain` rỗng, rồi `git worktree remove <child/sparse/sibling>` **không force**. Không gọi `isolation.cleanup` vì implementation hiện dùng `--force`. Sau remove, `worktree list --porcelain` chỉ còn main giả; cuối cùng dọn thư mục fixture. Lần chạy cuối in `FIXTURE REMOVED /tmp/don-s0-veycr571` trước assertion exit 1. Không xoá worktree/nhánh thật, không đọc dữ liệu thật hoặc `output/llm/`.

## Quyết định đã duyệt và JSON bàn giao

Spec/plan đã duyệt ngày 10/11/2026: auto=`merged`; sparse mặc định `[]`; hai pattern bên dưới đã được duyệt. Đây là **JSON đề nghị**, không phải config đã ghi. Opus cấu hình `live-tiktok-games` sau bàn giao và sau khi xử lý chặn S0; hand không ghi config hay thử sparse trên repo thật. P6 GC thật chỉ dry-run, không apply thật.

```json
{
  "side_session": {
    "worktree_gc": {"auto": "merged"},
    "worktree_sparse_exclude": [
      "docs/work-in-progress/handoffs/*-data/",
      "docs/work-in-progress/handoffs/*-shots/"
    ]
  }
}
```

## Phạm vi kiểm chứng

Không thêm unit test/plugin code; thêm một script spike 3 ca (67 dòng), không có code sản phẩm thêm để tính tỷ lệ test/code. Chỉ chạy script mới, không full suite. Hai lượt thăm dò đầu chưa có assertion baseline nên exit 0 không được dùng để kết luận ca 3 đạt; hai lượt sau có assertion tái hiện lỗi đều exit 1. Không kiểm chứng dung lượng 15 MB, GC thật, runtime, conflict merge/rebase hoặc finalize/apply; không có tiến trình nền.
