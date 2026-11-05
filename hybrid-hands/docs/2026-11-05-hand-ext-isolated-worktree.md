---
status: completed
lane: L2
approved: 2026-11-05
---

# hand-ext: worktree cách ly và luật dữ liệu cho hand ngoài

## Tóm tắt

- **Mục đích:** hand ngoài (dsh, opencode, codex, gemini) không chịu hook của Claude Code, nên không thể dựa vào hook để chặn đọc `.env` hay dữ liệu khách hàng. Cách chắc nhất là secret **không tồn tại** trong thư mục hand làm việc; đồng thời policy phải nói rõ loại dữ liệu nào không được giao ra dịch vụ ngoài.
- **Quyết định chính:**
  1. `hand-ext run` mặc định chạy trong git worktree tạm, detached tại `HEAD`, ngoài repo; chỉ chép thay đổi chưa commit của file tracked và file untracked không bị ignore. File bị ignore như `.env`, `*.demo.env` không bao giờ vào worktree.
  2. Cấu hình `ext_hand.isolation` (`worktree` mặc định khi cwd là git repo, hoặc `none`) và `ext_hand.worktree_root`; cờ `--isolation`, `--no-apply`, `--keep-worktree`.
  3. Sau run, diff của worktree được lưu vào `<runs_dir>/<run-id>/changes.patch` rồi áp về cwd gốc bằng `git apply --check` + `git apply`. Xung đột thì không ghi đè, report ghi rõ; worktree được dọn kể cả khi timeout/lỗi.
  4. Policy (SessionStart, UserPromptSubmit, skill `ext-hand`, preamble) thêm luật dữ liệu: secret và dữ liệu khách hàng dùng hand Claude; code, test, tài liệu kỹ thuật, tài liệu/dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được thì giao hand ngoài.
- **Việc người đọc cần làm:** không bắt buộc. Nếu repo có secret hoặc dữ liệu khách hàng, giữ `isolation=worktree` (mặc định) và không dùng `--isolation none`; chỉ đổi `worktree_root` khi cần đặt worktree ở ổ/thư mục khác. Xem mục 5 để kiểm chứng.

## 1. Vấn đề

Hand ngoài chạy bằng CLI subscription, không đi qua hook `PreToolUse` của Claude Code. Một brief chỉ nhắc "không đọc `.env`" là hàng rào mềm: hand vẫn có thể đọc nếu file tồn tại trong cwd, và mọi thứ hand đọc đều có thể đi lên dịch vụ ngoài. Câu hỏi đúng không phải "làm sao chặn đọc" mà "làm sao file bí mật không có ở đó".

Git worktree giải quyết phần secret: worktree mới checkout từ `HEAD` chỉ có file tracked. File bị `.gitignore` (`.env`, `*.demo.env`, thư mục credential...) không được checkout. Nếu muốn hand thấy đúng trạng thái làm việc, chỉ cần chép thêm thay đổi chưa commit của file tracked và file untracked **không bị ignore** — hai loại này không phải secret theo quy ước của repo.

Phần còn lại là phân loại dữ liệu: ngay cả khi workspace sạch, brief vẫn có thể yêu cầu hand đọc tài liệu khách hàng, log, nội dung DB rồi gửi lên dịch vụ ngoài. Vì vậy policy phải tách rõ việc được giao và việc phải dùng hand Claude.

## 2. Quyết định

### 2.1 Cấu hình và cờ

| Tên | Giá trị | Mặc định | Ý nghĩa |
|---|---|---|---|
| `ext_hand.isolation` | `worktree` \| `none` | `worktree` | `worktree` khi cwd là git repo; `none` chạy trực tiếp |
| `ext_hand.worktree_root` | đường dẫn | `~/.hybrid-hands/worktrees` (theo `HYBRID_HANDS_STATE_DIR` nếu đặt) | Nơi tạo `<repo>-<run-id>`; tương đối tính từ git toplevel |
| `--isolation` | `worktree` \| `none` | theo config | Ghi đè cho một lượt |
| `--no-apply` | cờ | tắt | Chỉ lưu `changes.patch`, không áp về cwd gốc |
| `--keep-worktree` | cờ | tắt | Không dọn worktree sau run |

Quy tắc fallback: cwd không phải git repo và isolation là mặc định → `none` kèm cảnh báo trong `report.md`. `worktree` được yêu cầu tường minh (config hoặc cờ) mà không tạo được worktree sạch → thoát 2, không chạy trong repo gốc. Lỗi git khi tạo worktree ở chế độ mặc định cũng thoát 2: chỉ fallback `none` cho trường hợp cwd không phải git repo, không fallback khi repo có nhưng worktree hỏng.

### 2.2 Luồng một lượt run

1. **Chọn cách ly:** `--isolation` > `ext_hand.isolation` > mặc định. Kiểm tra cwd có git repo không.
2. **Chuẩn bị worktree:** `git worktree add --detach <worktree_root>/<repo>-<run-id> HEAD`.
   - Áp `git diff HEAD --binary` của repo nguồn vào worktree (thay đổi chưa commit của file tracked).
   - Chép từng file từ `git ls-files --others --exclude-standard -z`, giữ symlink và mode; bỏ qua chính worktree và thư mục lượt chạy. Lớp chặn thứ hai: bỏ qua untracked có basename giống secret (`.env`, `*.env`, `*.pem`, `*.key`, `id_rsa*`, `.netrc`, `.npmrc`, `.pypirc`; trừ allowlist `.env.example`, `.env.sample`, `.env.template`, `*.env.example`) và symlink tuyệt đối, resolve ra ngoài repo hoặc trỏ tới file giống secret; tên bị bỏ (không đọc nội dung) được ghi vào report.
   - Chụp baseline bằng một `GIT_INDEX_FILE` riêng trong thư mục lượt chạy rồi `git write-tree`; không đụng index hay HEAD của repo người dùng.
3. **Chạy backend:** `RunSpec.cwd` = worktree (hoặc thư mục con tương ứng nếu `--cwd` là thư mục con); dsh nhận worktree qua `HAND_EXT_DSH_WORKSPACE`. Ledger và registry vẫn ghi cwd gốc để `hh-ps`/báo cáo không trỏ vào worktree đã xoá.
4. **Lấy patch:** chụp tree cuối, `git diff --binary <baseline> <final>`, ghi `changes.patch`, lấy danh sách file bằng `git diff --name-only -z`. File bị ignore không bao giờ vào patch vì snapshot dùng `git add -A` (tôn trọng `.gitignore`).
5. **Áp về gốc:** `git apply --check` trước; đạt thì `git apply`. Không đạt thì ghi `xung đột — không ghi đè` kèm file; không chạy `--3way` để tránh để lại conflict marker trong file người dùng. Patch vẫn nằm trong thư mục lượt chạy.
6. **Dọn:** `git worktree remove --force` + `git worktree prune`, kể cả khi backend timeout/lỗi; `--keep-worktree` giữ lại. Nếu dọn lỗi, report ghi cảnh báo.

Sandbox `read-only` vẫn chạy trong worktree; nếu hand không ghi được gì thì patch rỗng và bước áp bị bỏ qua.

### 2.3 Mã thoát

Giữ nguyên bảng cũ (0 ok, 1 failed, 2 usage, 4 capped, 6 timeout, 7 mọi backend hết hạn mức/chưa đăng nhập). Mã 2 bao gồm lỗi chuẩn bị worktree khi `isolation=worktree` được yêu cầu hoặc khi repo có git nhưng không tạo được worktree. `--no-apply` và xung đột patch không đổi mã thoát của lượt chạy; kết quả áp nằm trong report và khối tóm tắt.

## 3. Hợp đồng dữ liệu

- `<runs_dir>/<run-id>/changes.patch`: diff nhị phân từ trạng thái ban đầu của worktree đến trạng thái sau run; có thể rỗng. Luôn được ghi khi chế độ worktree chụp được tree cuối.
- `<runs_dir>/<run-id>/report.md`: report của hand (nếu có) + khối `## Cách ly worktree` do wrapper thêm, gồm chế độ, nguồn, worktree, patch, kết quả áp (`ok` / `xung đột` / `bỏ qua` / `lỗi`), danh sách file, dòng `Bỏ qua file nghi bí mật` (nếu có), trạng thái dọn.
- Ledger `output/llm/hand_usage.json` ghi `cwd` là cwd gốc, không phải worktree.
- Khối tóm tắt cuối lệnh có thêm dòng `cách ly: ...; áp patch: ...; worktree: đã dọn|giữ lại|dọn lỗi` để brain thấy ngay mà không phải mở report.

## 4. Luật dữ liệu (policy)

Văn bản được thêm vào `scripts/session-start-policy.sh` (mục LUẬT CHỌN HAND, item 1), bản ngắn `scripts/inject-policy.sh`, `skills/ext-hand/SKILL.md`, `templates/ext-hand-preamble.md` và mục Tóm tắt của README:

> Không giao hand ngoài (dsh, opencode, codex, gemini — gửi dữ liệu lên dịch vụ ngoài) việc phải đọc hoặc gửi: secret (`.env`, token, mật khẩu, URL DB có mật khẩu), dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân). Những việc đó dùng hand Claude. Được giao hand ngoài: code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.

Worktree là lớp phòng thủ bổ sung, không thay thế luật này: worktree không chứa file bị ignore, nhưng dữ liệu khách hàng vẫn có thể nằm trong file tracked hoặc trong prompt. Vì vậy brief vẫn phải chép luật cấm và PHẠM VI GHI hẹp.

## 5. Kiểm chứng

- Test mới `tests/test_hand_ext_isolation.py` phủ: `.env`/file ignored không có trong worktree; thay đổi chưa commit và untracked không ignore có trong worktree; patch áp về gốc đúng (thêm/sửa/xoá file); xung đột không ghi đè và report nêu xung đột; `--no-apply`; dọn worktree khi lỗi/timeout; cwd không phải git repo → `none` + cảnh báo; `--isolation worktree` tường minh trên non-git → thoát 2.
- Chạy toàn bộ test: `python3 -m pytest ~/app/claude-plugins-wt/hand-ext-isolate/hybrid-hands/tests -q` (hoặc `python3 -m unittest discover -s hybrid-hands/tests -q`).
- `bash -n` hai script policy; `claude plugin validate hybrid-hands`; ruff nếu môi trường có.

## 6. Việc còn lại và rủi ro

- Không chạy `hand-ext run` thật trong quá trình làm (tốn hạn mức); backend được thay bằng stub trong test.
- `.gitignore` vẫn là lớp đầu; lớp lọc theo basename là lớp thứ hai, không nhận diện được secret tên lạ (ví dụ `credentials.txt`) hay secret nằm trong file tracked. File `.env` nếu repo lỡ track vẫn giữ hành vi cũ (đi theo diff/checkout như file tracked khác). Repo vẫn cần ignore secret đúng cách và không `git add` secret.
- Patch xung đột không được tự merge; brain/hand phải xử lý bằng một lượt mới hoặc apply thủ công từ `changes.patch`.
- `--keep-worktree` để lại thư mục ngoài repo; dọn bằng `git -C <repo> worktree remove --force <path>` và `git -C <repo> worktree prune`.
