# Giao việc phiên Sol `ws-names`: tên dễ hiểu cho phiên phụ, hand và workspace trên sidebar Paseo

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain Opus v2 (agent Paseo `711ef386-2673-4c8b-8b1a-f24f1e56805e`; hỏi L1 bằng `paseo send --no-wait --behavior steer`).
- **Phản hồi người dùng (09/11/2026):** tên phiên phụ và subagent chưa dễ hiểu; nhìn sidebar không biết subagent nào thuộc phiên phụ nào. Hiện trạng: workspace local của phiên phụ tên `main`; agent hand không có tên (`-`); workspace hand tên run id dài `claude-plugins-20261109-212536-439179-demo-subagent-codex`.
- **Opus đã chốt quy ước (L1):**
  - Phiên phụ — tên agent **và** title workspace: `<tên> · <loại> phụ`, loại = `Sol` | `Opus v1` | `Opus v2` | `dsh` (theo provider/account). Ví dụ `demo-subagent · Sol phụ`.
  - Hand managed — tên agent **và** title workspace: `<tên phiên cha> › hand <backend> · <label>`. Ví dụ `demo-subagent › hand codex · demo-subagent`. Cha là phiên chính: `chính › hand <backend> · <label>`. Cha không xác định: `? › hand …`.
  - Bắt đầu bằng tên phiên cha để hand nằm cạnh phiên phụ của nó; tối đa 60 ký tự (cắt phần label, giữ tiền tố cha + backend); không chứa đường dẫn, secret hay nội dung brief.
  - Phiên chính và workspace dùng chung: **không** đổi tên (giữ title người dùng đặt).
- **Release:** 0.36.1. **Kết thúc:** ghi `docs/work-in-progress/handoffs/ws-names.md` (mở đầu tóm tắt) rồi tạo file rỗng `docs/work-in-progress/handoffs/ws-names.done`.

## 1. Việc làm

1. Đặt tên khi tạo: side-session start/send (mọi provider qua Paseo) đặt tên agent + title workspace riêng theo quy ước; hand managed (dispatch/followup) đặt tên child + title workspace. Dùng API public (create option title/name nếu có; nếu không thì `agent update --name` / `workspace rename` tương đương qua client đã pin) — xác minh trong source Paseo 0.15.0.
2. Tên cha của hand: lấy từ parent canonical (state side-session → `<tên>`; phiên chính → `chính`). Không đoán từ cwd.
3. Lỗi đặt tên chỉ cảnh báo, không chặn dispatch/done; retry hữu hạn ở lần ls/watch sau; idempotent.
4. Lệnh tay `side-session tidy --names` (hoặc tương đương; dry-run mặc định, `--apply` mới ghi) để đổi tên các agent/workspace **do plugin tạo** đang hiện theo quy ước mới; không đụng phiên chính/workspace chung/thành viên lạ.
5. hh-ps / panel `paseo-hh-tree`: nếu đang hiện tên agent Paseo thì dùng tên mới; không đổi cấu trúc cây.
6. README, skill side-session/ext-hand/paseo, CHANGELOG 0.36.1.

## 2. Quy trình

- Worktree `/Users/anhtp/app/claude-plugins-wt/ws-names`, nhánh `side/ws-names` từ main mới nhất (0.36.0 `4e38c39` trở lên). Code/test qua hand, **song song tối đa** `ext_hand.max_parallel` khi file tách biệt (side_session lib / hand_ext paseo_* / docs), cùng file thì tuần tự. `hand-ext pick --json` trước; `run --backend auto --mode shell --cwd <worktree> --keep-worktree`. Acceptance tối đa 3 nhóm: (a) quy ước tên đúng cho phiên phụ mọi loại + hand có cha phụ/chính/không rõ, cắt 60 ký tự; (b) đặt tên khi tạo/giao lại, lỗi không chặn, idempotent; (c) tidy --names chỉ đổi đối tượng plugin sở hữu, dry-run không ghi.
- Review diff; lỗi → giao lại cùng backend một lần, rồi backend kế tiếp. Test hẹp + full suite một lần cuối; validate; `node --check` bridge nếu đổi.
- Release 0.36.1: commit nhánh, push, merge main bằng `git -C /Users/anhtp/app/claude-plugins`, bump + CHANGELOG, validate, push main; `claude plugin update hybrid-hands@hybrid-hands-local --scope user` cho **cả** `CLAUDE_CONFIG_DIR=~/.claude` và `~/.claude-hand`; kiểm plugin list ở claude-plugins và live-tiktok-games cho cả hai account.
- Smoke live: chạy `tidy --names` dry-run rồi `--apply` trên các mục plugin đang hiện; mở một hand managed nhỏ (`--mode paseo-required --no-apply`, scratch 1 dòng) từ chính phiên bạn, kiểm tên child + workspace là `ws-names › hand <backend> · <label>`, workspace phiên bạn là `ws-names · Sol phụ`. Ghi kết quả.

## 3. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Thêm vào brief hand: chỉ đọc file trong worktree được giao; không chạy `ps`/`pgrep`/lệnh liệt kê tiến trình hay phiên khác của máy.

## 4. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/ws-names`; merge + version/CHANGELOG/docs trên main (file của tính năng); đổi tên agent/workspace do plugin tạo (qua lệnh plugin); hand smoke do bạn tạo; `docs/work-in-progress/handoffs/ws-names.md|.done`. Còn lại CHỈ ĐỌC.
- Không đổi tên/archive phiên chính, workspace chung, agent tiktok không do plugin tạo. Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, settings/credential/`installed_plugins.json`; không restart/reload daemon; không bật parallel-subagents.
- Không xoá/di chuyển `output/llm/`; không dọn worktree. Chỉ subscription. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
