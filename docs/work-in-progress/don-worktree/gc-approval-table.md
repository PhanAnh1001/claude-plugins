# Bảng GC thật để duyệt

Chỉ dry-run; chưa xoá worktree, chưa prune nhánh thật. Số byte là kích thước metadata file (không phải số block filesystem, không hứa thu hồi thực tế). Sẽ đo lại bằng plugin đã cài trước bàn giao.

| Công cụ/lớp | Repo | Tên | Nhánh/HEAD | Tracked byte | Ignored byte | Tổng byte | Quyết định |
|---|---|---|---|---:|---:|---:|---|
| side-session B | live-tiktok-games | RV-13 | review/wp-13 | 31487809 | 45171624 | 76659433 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session B | live-tiktok-games | RV-14 | review/wp-14 | 28994601 | 45171624 | 74166225 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session B | live-tiktok-games | SOL-RV62 | side/SOL-RV62 | 238412819 | 0 | 238412819 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session B | live-tiktok-games | SOL-WP68 | side/SOL-WP68 | 239061255 | 0 | 239061255 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session B | live-tiktok-games | SOL-WP70 | side/SOL-WP70 | 238326892 | 962213 | 239289105 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session B | live-tiktok-games | SOL-WP73 | test/wp73-localhost-privacy | 238515612 | 0 | 238515612 | Giữ; chỉ đề xuất nếu duyệt include-unmerged |
| side-session A | live-tiktok-games | WP-11 | side/WP-11 | 20009928 | 45171624 | 65181552 | Chờ duyệt apply |
| hand-ext finished | claude-plugins | fix-stale-claim-20261110-175627-040964-fsc-probe-brief-codex | detached a30265772cae | — | — | 6437025 | Chờ duyệt apply; HEAD khớp base_commit registry |

Lớp C/D/E và hand unknown/dirty không được đề xuất xoá. GC mặc định giữ nhánh. Dữ liệu ignored sẽ bị xoá cùng worktree nếu người dùng duyệt apply; không đọc nội dung trong lần kiểm chứng này.

Đối chiếu 10 mẫu ở `gc-manual-samples.json`: 1 A, 2 B, 2 C, 2 D, 3 E. Chỉ có một A thật; chưa đạt điều kiện ít nhất hai A. Không dựng dữ liệu thật giả để đủ mẫu.
