## Tóm tắt

- Kết quả: xong L1, hybrid-hands **0.37.0**; đã review, commit nhánh, push nhánh, merge và push `main`.
- Commit tính năng: `6e66b8a`; merge/main/origin-main: `39a9e4a8f6fef148d0f53c9ca6ce0d6c45fd1e6c`.
- Đã thêm mode `parallel_subagents.enabled` chỉ bật theo repo; helper chung hai hook, fallback luật thường khi config lỗi, giữ guard v1 và cap theo luật.
- Đã sửa tối thiểu AGENTS.md, README, changelog và manifest 0.37.0; danh sách từng file cùng lý do ở dưới.
- `uv run --offline --no-project --with pytest python3 -m pytest hybrid-hands/tests/test_policy_mode.py -q`: **3 passed**. `unittest`: **3/3 OK**.
- Đối chiếu trực tiếp byte output hook cũ/mới ở chế độ thường: khớp cả không AGENTS, khớp một phần và AGENTS cũ đầy đủ; JSON, shell syntax, diff check đạt; `claude plugin validate` passed.
- Đã update chính thức scope user ở Claude v1/v2; xác minh **14 repo × 2 tài khoản**, version/cache/source 0.37.0 khớp; danh sách và bằng chứng dưới đây.
- Không bật key ở repo nào; plugin parallel-subagents cũ vẫn tắt; giữ nguyên tài liệu untracked và output/llm hiện hữu.
- Chưa kiểm chứng native Agent chạy thật/worktree fallback thật; admission runtime ngoài L1. Phiên đang mở **cần reload/mở mới**. Không chạy full suite.

## Tiêu chí và giao hand

Sol viết tiêu chí chấp nhận và ba ca test trước khi giao tại `ps-mode-l1-hand-brief.md` trong thư mục bàn giao này. Chỉ giao một gói vì helper, hook và test phụ thuộc nhau. Brief hand có nguyên văn ba dòng luật dữ liệu; hand làm trực tiếp, không recursion, không commit hay cập nhật runtime.

`hand-ext pick --json` exit 0 chọn `codex`, model `gpt-6.1-sol`, effort `low`, account `gpt`, native eligible. Giao qua wrapper theo yêu cầu bắt buộc của brief:

```sh
hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --mode shell --brief /Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/ps-mode-l1-hand-brief.md --cwd /Users/anhtp/app/claude-plugins --label ps-mode-l1 --isolation none
```

Hand Codex hoàn tất exit **0**, status ok, 236.6 giây. Report: `output/llm/hand-ext/20261110-084351-629004-ps-mode-l1-codex/report.md`. Sol đọc diff và test; không có lỗi cần giao lại, không tự viết phần implementation.

Lỗi thao tác trước dispatch: lần tạo brief đầu bằng shell gặp lỗi encoding Python, khiến lần gọi hand-ext ngay sau đó exit **2** vì brief chưa tồn tại. Đã tạo brief bằng apply_patch và gọi lại thành công; lần exit 2 chưa tạo hand/writer. Không có lỗi backend, exit 7, exit 8 hay `PARENT_REQUIRED` trong lượt chạy thành công. Chủ động chọn `--mode shell` như đường hoạt động đã nêu trong brief, không thay config.

## File thay đổi và lý do

`H = hybrid-hands/plugins/hybrid-hands`.

| File | Lý do |
|---|---|
| `H/lib/shared_config.py` | Thêm default false; chuẩn hóa bool, chặn global true với warning không hiện giá trị; giữ provenance. |
| `H/lib/policy_mode.py` | Renderer chung hai hook; chọn cwd, kiểm provenance, fallback config lỗi, thay phần delegate/review khi bật. |
| `H/lib/policy_rules.txt` | Chuyển nguyên văn thân luật thường khỏi shell để renderer dùng chung, không nhân bản bộ luật. |
| `H/scripts/session-start-policy.sh` | Gọi helper, giữ envelope JSON jq và output mặc định theo byte. |
| `H/scripts/inject-policy.sh` | Gọi cùng helper để chọn đúng mode theo repo; giữ output thường. |
| `hybrid-hands/tests/test_policy_mode.py` | Ba ca hẹp: baseline, repo true/fallback, global true bị bỏ qua. |
| `hybrid-hands/README.md` | Mô tả key, JSON repo, guard, cap theo luật và cách migrate/mở phiên mới. |
| `H/CHANGELOG.md` | Ghi release 0.37.0 và phạm vi policy. |
| `H/.claude-plugin/plugin.json` | Tăng minor 0.36.1 → 0.37.0. |
| `AGENTS.md` | Thay hai câu cấm bằng luật plugin cũ luôn tắt, mode mới chỉ operator bật theo quyết định người dùng; thêm key cấu hình. |

Marketplace manifest không có version nên không sửa. Không sửa `parallel-subagents/`, `statusline/`, repo config, credential/settings hay installed registry bằng tay. Các thay đổi sổ cài đặt chỉ do CLI chính thức thực hiện.

## Review và kiểm chứng

- Shared loader chuẩn hóa trước merge, nên cả effective config và sections tái sử dụng đều không mang global true hiệu lực; giữ nguồn global để thấy provenance của giá trị bị từ chối. Chỉ bool JSON thật hợp lệ.
- Helper chỉ nhận true có nguồn repo, dùng path loader đã resolve, giữ fallback config main worktree hiện có; cap lấy `ext_hand.max_parallel` đã được loader kiểm 1..4.
- Variant thay phần phân vai/delegate/review, giữ nguyên thân dữ liệu, khuôn brief, tiếp việc, test tối thiểu và ngữ cảnh brain. Không dùng lệnh run làm preflight giả rồi spawn writer thứ hai. Native v1 vẫn cần kết quả pick đúng account/model/effort và đủ capability; guard chặn/thiếu nguồn không spawn.
- `policy_rules.txt` được đối chiếu bằng script với literal RULES của hook tại baseline: **giống nguyên văn**.
- Chạy hook cũ bằng `git show` và hook mới trên fixture tạm: so sánh stdout bytes cả hai hook khi không AGENTS, AGENTS có một đoạn trùng, và toàn bộ AGENTS baseline; **đều khớp**.
- `python3 -m pytest hybrid-hands/tests/test_policy_mode.py -q`: exit **1**, Python mặc định thiếu module pytest. Không tải package; dùng pytest đã có trong cache qua uv offline.
- `uv run --offline --no-project --with pytest python3 -m pytest hybrid-hands/tests/test_policy_mode.py -q`: exit **0**, **3 passed in 1.65s**.
- `python3 -m unittest discover -s hybrid-hands/tests -p test_policy_mode.py -v`: exit **0**, **3 tests OK**.
- `bash -n` hai hook: exit **0**. Parse JSON plugin/marketplace manifests: đạt. `git diff --check` và staged diff check: exit **0**.
- `claude plugin validate hybrid-hands/plugins/hybrid-hands`: exit **0**, **Validation passed**. CLI còn nêu thiếu LICENSE và icon cho profile đăng catalog; đây không phải lỗi validation runtime và không thuộc thay đổi này.
- Không thêm link tài liệu nội bộ mới; các đường dẫn runtime trong tài liệu tương ứng file hiện hữu. Không chạy full suite hay kiểm thử nội dung tài liệu.

## Commit / merge

Nhánh `feat/hybrid-hands-repo-parallel-mode` được push trước merge. Commit tính năng `6e66b8a`; merge `--no-ff` vào main thành `39a9e4a8f6fef148d0f53c9ca6ce0d6c45fd1e6c`; đã push main. `git rev-parse HEAD origin/main` cho cùng SHA. Working tree tracked sạch; các thư mục docs/work-in-progress untracked của người khác vẫn nguyên.

## Cập nhật plugin và xác minh runtime

Chạy cho cả default Claude v1 (`/Users/anhtp/.claude`) và v2 (`CLAUDE_CONFIG_DIR=/Users/anhtp/.claude-hand`):

```sh
claude plugin marketplace update hybrid-hands-local
claude plugin update hybrid-hands@hybrid-hands-local --scope user --json
```

Cả hai update exit **0**, JSON trả `oldVersion=0.36.1`, `newVersion=0.37.0`, scope user, restart required. Không install/enable ở repo mới.

`claude plugin list --json` được chạy lại từ từng repo dưới đây trên cả hai account: tất cả enabled user scope, version/folderVersion 0.37.0; plugin parallel-subagents cũ disabled. Vì đây là cài đặt user dùng chung, hai update trên bao phủ các repo cùng account; không cần ghi config từng repo.

- `/Users/anhtp/app/claude-plugins`
- `/Users/anhtp/app/tcp-assistant-main`
- `/Users/anhtp/app/tcp-assistant`
- `/Users/anhtp/app/live-tiktok-games`
- `/Users/anhtp/app/live-tiktok-games-preview-publish`
- `/Users/anhtp/app/slt-ocr-pro`
- `/Users/anhtp/app/hrm-open-sources`
- `/Users/anhtp/app/ai-luxian`
- `/Users/anhtp/app/common-modules`
- `/Users/anhtp/app/skill-key`
- `/Users/anhtp/app/ai-practice-english`
- `/Users/anhtp/app/codex-plugins`
- `/Users/anhtp/app/team-ai-gitops`
- `/Users/anhtp/app/ai-comic-video`

Đường dẫn CLI báo nạp nguồn cho cả hai account: `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`.

Cache v1: `/Users/anhtp/.claude/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.0`; cache v2: `/Users/anhtp/.claude-hand/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.0`. Manifest cache xác nhận 0.37.0; năm file runtime sửa/thêm trong mỗi cache được so byte với nguồn và đều khớp.

Bằng chứng metadata 28 tổ hợp: `docs/work-in-progress/handoffs/ps-mode-l1-runtime-verification.json`.

## Còn lại / giới hạn

Không có phần L1 còn mở. Chưa chạy native Agent thật ở mode bật, chưa thử fallback bằng worktree thật, không suy rằng phiên đang mở đã hot load. Cần reload/mở phiên mới để dùng policy mới. Không bật `parallel_subagents.enabled` trong bất kỳ repo nào; việc bật vẫn cần quyết định người dùng cho repo cụ thể. Cưỡng chế admission/slot native thực thuộc L2, bản này chỉ nhắc trong luật.

Tất cả lệnh nền/PTY do phiên này tạo đã kết thúc trước ghi `.done`; không tạo side-session mới hay gửi tin cho brain. Sau khi report này hoàn tất sẽ tạo `ps-mode-l1.done` để watcher side-session xử lý lifecycle.
