# Giao việc phiên Sol `hpa-pilot3`: sửa ACP discovery, release 0.35.1, chạy lại live pilot

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain là phiên chính Opus v2. Đọc đủ `docs/work-in-progress/handoffs/hpa-pilot2.md` (và `hpa-pilot.md`) trước.
- **Opus đã duyệt (L1), giữ bất biến "không thực thi khi chưa bound":**
  - (E) Gateway `hand-paseo-acp` khởi động **unbound** được (thiếu state-root/invocation-id): chỉ trả lời `initialize` và `session/new` (+ các method metadata thuần mà catalog Paseo 0.15.0 gọi, xác định từ source `acp-agent.js`), trả catalog model/mode tĩnh theo provider; **mọi `session/prompt` và method có side effect bị từ chối** bằng JSON-RPC error cố định, không spawn backend, không ghi state/ledger, không đọc auth. Bound giữ nguyên hành vi cũ. Binding thiếu/hỏng một phần (chỉ có một biến) vẫn fail như cũ.
  - (F) `managed recover` mở rộng cho pending=`create`: chỉ khi `workspaceConfirmed`, chưa createConfirmed/sendConfirmed/writer/process/outcome, và **daemon xác nhận chắc chắn** creation của đúng `[agentId, agentKey]` thất bại (`phase=failed`, `outcomeUnknown=false`, `inFlight=null`) **và** inspect agent trả không tồn tại. Ưu tiên API public lifecycle creation nếu Paseo 0.15.0 có (server báo `creationLifecycle=true`); chỉ dùng receipt file daemon nếu không có API, đọc metadata tối thiểu, không echo raw error/env. Mọi trường hợp khác từ chối, không mutation.
- **Lần này bạn làm cả release** (theo AGENTS.md: Sol được điều phối commit/merge main): vì provider command trỏ checkout chính, fix phải lên `main` mới chạy live được.
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/hpa-pilot3.md` (mở đầu tóm tắt: commit/version, test, pass/fail từng gate) rồi tạo file rỗng `docs/work-in-progress/handoffs/hpa-pilot3.done`. Bị chặn cũng ghi chỗ chặn rồi tạo `.done`.

## 1. Việc làm (tuần tự)

1. Trên worktree `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix` (nhánh `side/hpa-pilot-fix`, HEAD `d6f922f`): merge `main` mới nhất nếu main đã đi tiếp.
2. Giao code/test (E)(F) cho hand theo AGENTS (`hand-ext pick --json` trước; `run --backend auto --mode shell --cwd <worktree> --keep-worktree`, `--max-tokens` đủ lớn như lượt trước). Acceptance tối đa 3 nhóm: (1) unbound: initialize/session/new trả catalog, prompt bị từ chối, không spawn/ghi; bound không đổi; (2) recover create: đủ điều kiện → failed + nhả reservation đúng một lần, lặp an toàn; thiếu/không chắc → từ chối không đổi record; (3) entry gateway với binding một phần vẫn fail. Bạn review toàn bộ diff; lỗi → giao lại cùng backend đúng một lần.
3. Test hẹp (gateway/ACP, controller, CLI, transport), `node --check` bridge, `claude plugin validate`, full suite đúng một lần cuối.
4. **Probe offline trước release:** chạy binary worktree unbound với env giống catalog (`NO_BROWSER=true`, không binding): initialize + session/new phải có result; gửi `session/prompt` phải bị từ chối; không tiến trình backend nào được spawn. Ghi bằng chứng.
5. **Release 0.35.1:** commit trên nhánh, push nhánh; merge vào `main` ở checkout `/Users/anhtp/app/claude-plugins` bằng `git -C` (không đụng file dirty có sẵn như `.claude/hybrid-hands.json` và `docs/work-in-progress/**`; xung đột thì dừng, ghi lại); bump `plugin.json` 0.35.1 + mục CHANGELOG 0.35.1 (workspace ID schema, pre-network schema validation, managed recover, unbound ACP discovery), validate, commit, push `main`. Kiểm `CLAUDE_CONFIG_DIR=~/.claude claude plugin list` ở cwd claude-plugins và `/Users/anhtp/app/live-tiktok-games` thấy 0.35.1 read from checkout. Không cài plugin cho account khác.
6. **Recover live** key kẹt `68bcf6da-5503-4ff5-b366-1c040c97303c:96b77fc4-c729-4a40-b519-98d2602a4752:1` bằng CLI main (dry-run rồi `--apply`); kiểm reservation `95f1251c…` đã nhả, `managed ls`/`hh-ps --once` hiện failed, không row trùng.
7. **Live gates** bằng CLI checkout chính (`/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin`), `--cwd /Users/anhtp/app/claude-plugins`, `--no-apply`, timeout hữu hạn, đúng thứ tự gate 1–5 của `docs/work-in-progress/hand-paseo-agent/hpa-pilot-prompt.md` (dispatch qua `--backend auto` → placement/hh-ps/tab Subagents → stop task thứ hai + quiescence/reap thật → review-approve/archive/followup epoch 2 → smoke tuỳ chọn dsh/claude-v2; không claude-v1). Daemon có cache catalog/provider snapshot: nếu vẫn thấy lỗi probe cũ, kiểm xem Paseo có cơ chế refresh provider public không phải restart; **không** restart/reload daemon — ghi lại để Opus quyết.
8. Lỗi mới: sửa cùng quy trình thành 0.35.2, tối đa hai vòng; còn lỗi thì ghi và bàn giao. Mỗi gate ghi lệnh, kết quả thật, pass/fail/unknown; không claim phần chưa chạy.

## 2. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## 3. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/hpa-pilot-fix`; merge + version/CHANGELOG trên `main` checkout chính (chỉ các file plugin của bản vá); execution state/agent pilot do bạn tạo hoặc key kẹt nêu trên (chỉ qua `managed recover`); `docs/work-in-progress/handoffs/hpa-pilot3.md|.done`. Còn lại CHỈ ĐỌC.
- Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents.
- Không restart/reload daemon Paseo; không stop/archive agent nào không do bạn tạo (đặc biệt agent tiktok và phiên chính).
- Không xoá/di chuyển `output/llm/`; không dọn worktree; không reset/stash thay đổi của người khác.
- Chỉ subscription; không API trả phí. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
