# Giao việc phiên Sol `ws-archive`: xong việc thì archive agent + workspace, giao lại thì hiện lại

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain Opus v2 (agent Paseo `711ef386-2673-4c8b-8b1a-f24f1e56805e`; hỏi L1 bằng `paseo send --no-wait --behavior steer`).
- **Yêu cầu người dùng (09/11/2026, đã duyệt hành vi):** "phiên phụ hoặc hand và workspace chứa nó xong việc và báo cáo thì archived luôn; khi được giao lại thì cả hai được hiện lại". Thay quyết định cũ Q4 ("done giữ hiện, Sol archive sau review").
- **Release:** minor **0.36.0**. Phần managed hand đụng `paseo_*` đang bị phiên `hpa-pilot5` sửa — **chỉ làm phần đó sau khi có file `docs/work-in-progress/handoffs/hpa-pilot5.done`** và đã merge main mới nhất. Phần side-session làm ngay.
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/ws-archive.md` (mở đầu tóm tắt) rồi tạo file rỗng `docs/work-in-progress/handoffs/ws-archive.done`. Bị chặn cũng ghi chỗ chặn rồi tạo `.done`.

## 1. Bối cảnh đã xác minh (Opus, source Paseo 0.15.0)

- `paseo workspace archive <id>` = archive record + mọi agent/terminal của workspace; **chỉ xoá thư mục khi worktree do Paseo sở hữu** (dưới `~/.paseo/worktrees` hoặc có `<gitdir>/paseo/worktree.json` còn trong `git worktree list`) — `server/workspace-archive-service.js` `maybeRemoveDirectory`, `utils/worktree.js` `isPaseoOwnedWorktreeCwd`. Worktree của side-session (`~/app/*-wt/...`) và hand (`~/.hybrid-hands/worktrees/...`) không có marker, không nằm dưới root đó → thư mục giữ nguyên (Opus đã archive 25 workspace, cả 25 `removedDirectory` rỗng, thư mục còn).
- Khôi phục: session có `workspace.recovery.restore.request` (`server/session.js` ~2224, 2905) và `ensureWorkspaceRecordUnarchived`; gửi prompt cho agent archived có nhánh `unarchiveAgentState` (~3381–3395). Bạn xác minh API public đúng để restore workspace + unarchive agent, ưu tiên client public đã pin trong bridge.
- Workspace `local` (cwd checkout chính) dùng chung với phiên chính: **không bao giờ archive workspace local hoặc workspace còn agent khác chưa archived**.

## 2. Hợp đồng hành vi

1. **Phiên phụ (side-session, mọi provider qua Paseo):** khi thấy `<handoff_dir>/<tên>.done` và cleanup hiện có thành công (đã archive agent), archive thêm workspace của nó **nếu** workspace là `worktree` riêng và mọi agent trong đó đã archived/closed. Ghi `workspace_id` + `workspace_archived` vào state side-session. Lỗi archive workspace: cảnh báo, không chặn `done`, retry ở `ls/watch` sau (hữu hạn).
2. **Giao lại phiên phụ:** thêm đường giao lại chính thức (vd `side-session send --name <tên> --prompt-file F`, hoặc mở rộng `start --resume` cho mọi provider — bạn chọn, ghi lý do): restore workspace → unarchive agent → gửi prompt; state về `running`, xoá `.done` cũ theo cách an toàn (đổi tên giữ lịch sử, không xoá handoff), watchdog bật lại. Không tạo agent trùng.
3. **Hand managed:** khi execution settle xong report (state `awaiting_review`, đủ hook), tự archive exact child **và** workspace riêng của nó (workspace hand luôn riêng theo Q2). Không còn chờ review-approve mới archive; review-approve vẫn là điều kiện cho followup. `managed archive` giữ được (idempotent). Record/report/patch/worktree giữ nguyên.
4. **Giao lại hand (`managed followup`):** restore workspace → unarchive/reopen exact child → epoch mới như hiện có. Workspace bị xoá/thiếu cwd → blocked như contract cũ.
5. hh-ps/panel không đổi ý nghĩa trạng thái; dòng done vẫn hiện trong cây theo rule hiện có (archive chỉ ảnh hưởng sidebar Paseo).
6. Cập nhật README, skill side-session/ext-hand/paseo, template side-session prompt, AGENTS.md mục Q4 nếu có nhắc, CHANGELOG 0.36.0.

## 3. Quy trình

- Worktree mới `/Users/anhtp/app/claude-plugins-wt/ws-archive`, nhánh `side/ws-archive` từ main. Code/test qua hand (`hand-ext pick --json` trước; `run --backend auto --mode shell --cwd <worktree> --keep-worktree`; managed ở claude-plugins đang bị chặn bởi record kẹt nên dùng shell). Acceptance tối đa 3 nhóm: (a) side-session done → archive agent+workspace riêng, không đụng local/chung; giao lại → restore cả hai, không trùng; (b) hand awaiting_review → auto archive child+workspace; followup → restore cả hai, epoch mới; (c) lỗi archive/restore không làm mất trạng thái, không xoá thư mục. Fixture giả, không daemon thật trong test.
- Bạn review diff; lỗi → giao lại cùng backend một lần, rồi backend kế tiếp. Test hẹp + full suite một lần cuối; `claude plugin validate`; `node --check` bridge nếu đổi.
- Release 0.36.0 sau `hpa-pilot5.done`: merge main mới nhất, commit nhánh, push, merge main bằng `git -C /Users/anhtp/app/claude-plugins`, bump + CHANGELOG, validate, push main; `claude plugin update hybrid-hands@hybrid-hands-local --scope user` cho **cả** `CLAUDE_CONFIG_DIR=~/.claude` và `~/.claude-hand`; kiểm plugin list ở claude-plugins và live-tiktok-games cho cả hai account.
- Smoke live tối thiểu sau release: một side-session codex nhỏ tên `ws-archive-smoke` trong worktree riêng (task: ghi handoff một dòng + `.done`) → kiểm agent+workspace archived, thư mục còn → giao lại một prompt nhỏ → kiểm cả hai hiện lại → để nó xong lại. Hand managed chỉ smoke nếu record kẹt đã được hpa-pilot5 gỡ; nếu không, ghi "chưa smoke live".

## 4. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Thêm vào brief hand: chỉ đọc file trong worktree được giao; không chạy `ps`/`pgrep`/lệnh liệt kê tiến trình hay phiên khác của máy.

## 5. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/ws-archive`; merge + version/CHANGELOG/docs trên main (file plugin/docs của tính năng); side-session `ws-archive-smoke` và workspace của nó; `docs/work-in-progress/handoffs/ws-archive.md|.done`. Còn lại CHỈ ĐỌC.
- Không đụng nhánh `side/hpa-pilot-fix`, record/agent của hpa-pilot5, workspace `wks_95567480628a52bc`.
- Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents.
- Không restart/reload daemon; không archive/stop agent hay workspace không do bạn tạo (đặc biệt tiktok, phiên chính, workspace local).
- Không xoá/di chuyển `output/llm/`; không dọn worktree; không reset/stash thay đổi người khác.
- Chỉ subscription. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
