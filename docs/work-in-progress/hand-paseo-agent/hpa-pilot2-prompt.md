# Giao việc phiên Sol `hpa-pilot2`: gỡ record kẹt, chạy lại live pilot managed Paseo hand

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain là phiên chính Opus v2. Tiếp nối bàn giao `docs/work-in-progress/handoffs/hpa-pilot.md` (đọc đủ trước).
- **Opus đã duyệt (L1):** (A) tích hợp fix `d8361b6` lên `main` hiện tại (`c9e356a`, 0.35.0); (B) bridge/transport kiểm request bằng schema chính thức **trước network** — fail thì là từ chối chắc chắn, không side effect: attempt chuyển failed trước dispatch và nhả reservation, không để unresolved; (C) lệnh recover hẹp cho record kẹt; (D) chạy lại live gates 1–5 của hpa-pilot.
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/hpa-pilot2.md` (mở đầu tóm tắt: pass/fail từng gate, commit, test) rồi tạo file rỗng `docs/work-in-progress/handoffs/hpa-pilot2.done`. Bị chặn cũng ghi rõ chỗ chặn rồi tạo `.done`.

## 1. Bối cảnh

- Provider `hh-hand-*` đã đăng ký + reload; `.claude/hybrid-hands.json` repo có `ext_hand.mode=auto` + `paseo`; `provider status` READY.
- Worktree fix: `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`, nhánh `side/hpa-pilot-fix` (commit `d8361b6` trên base 0.34.0). `.pilot/` trong đó là bằng chứng phiên trước, giữ nguyên, không commit.
- Record kẹt: state root `/Users/anhtp/.hybrid-hands/executions`, key `825cfecb-c073-4674-aa62-5ee980fab4c0:dfb1d6f7-0074-4a85-8071-65a127203805:1`, state `admitted`, transport.pending `workspace`, workspaceId UUID `15633291-…` (không khớp `^wks_[a-f0-9]{16}$` của `WorkspaceCreateRequestSchema` Paseo 0.15.0), không agentKey/createConfirmed/writer/process; reservation `6b0ae39c…` còn giữ.

## 2. Việc làm (tuần tự)

1. **(A) Tích hợp:** merge `main` vào `side/hpa-pilot-fix` (không rebase lịch sử đã push), giải xung đột nếu có, test hẹp transport.
2. **(B) Kiểm schema trước network:** trong `paseo_bridge.mjs` (hoặc lớp transport tương ứng), validate payload mutation workspace/create/send bằng schema chính thức trong package Paseo đã pin (`@getpaseo/protocol`) **trước khi gửi**. Fail → trả mã riêng (vd `REQUEST_SCHEMA_REJECTED`, kèm path/code issue, không echo payload nhạy cảm) có cờ chứng minh "chưa gửi". Transport/controller xử lý mã này là failed trước dispatch: xoá pending, attempt/execution terminal failed, nhả reservation đúng một lần, giữ isolated cwd; không shell fallback với `paseo-required`; `auto` chỉ được fallback nếu đúng contract "trước dispatch" hiện có — ghi rõ lựa chọn. Lỗi khác (network/ACK mất/timeout/lỗi server) **giữ nguyên** unresolved như cũ.
3. **(C) Recover hẹp:** subcommand `hand-ext managed recover --cwd REPO --key K` (dry-run mặc định, `--apply` mới ghi). Chỉ chấp nhận đúng điều kiện: pending=`workspace`, chưa `workspaceConfirmed`, không agentKey/createConfirmed/sendConfirmed/writer/process/outcome, **và** workspaceId bound bị schema chính thức từ chối (chứng minh không thể tồn tại trên daemon). Đủ điều kiện → terminal failed với lý do `invalid_bound_workspace_id`, nhả reservation một lần, ghi bằng chứng vào record. Mọi trường hợp khác từ chối, không mutation. Không sửa immutable IDs, không xoá file state/lock bằng tay.
4. Giao code/test (B)(C) cho hand theo AGENTS (`hand-ext pick --json` trước; `run --backend auto`, shell mode trong worktree fix, đặt `--max-tokens` đủ — lượt trước cap 40000 bị capped, nên ≥150000). Bạn review diff. Test hẹp: transport, controller, CLI managed, bridge (`node --check`). Full suite một lần cuối sau khi xong code.
5. Commit trên nhánh sau review, push nhánh. **Không merge main, không bump version/CHANGELOG, không update plugin** — Opus release.
6. **Recover live:** chạy `managed recover` từ code worktree fix (dry-run rồi `--apply`) cho key kẹt; kiểm reservation đã nhả, record terminal, `managed ls`/`hh-ps --once` hiện failed (✗), không row trùng.
7. **(D) Chạy lại live gates** bằng CLI của worktree fix (`/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix/hybrid-hands/plugins/hybrid-hands/bin`, `--cwd /Users/anhtp/app/claude-plugins`, `--no-apply`, `--max-tokens` ≥150000, timeout hữu hạn), đúng thứ tự gate 1–5 của prompt cũ `docs/work-in-progress/hand-paseo-agent/hpa-pilot-prompt.md` (dispatch codex qua `--backend auto` → placement/hh-ps → stop task thứ hai + quiescence/reap → review-approve/archive/followup epoch 2 → smoke tuỳ chọn dsh/claude-v2; không claude-v1). Lưu ý provider command trỏ checkout chính (`/Users/anhtp/app/claude-plugins/.../bin/hand-paseo-acp`) — nếu code ACP phía child cần fix mới mà checkout chính chưa có, ghi rõ và dừng gate đó thay vì sửa config provider.
8. Lỗi mới: sửa trên cùng nhánh theo cùng quy trình, chạy lại gate. Tối đa hai vòng sửa; còn lỗi thì ghi và bàn giao.

Mỗi gate ghi lệnh, kết quả thật, pass/fail/unknown. Không claim phần chưa chạy.

## 3. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## 4. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/hpa-pilot-fix`; execution state/agent pilot do bạn tạo hoặc key kẹt nêu trên (chỉ qua lệnh recover); `docs/work-in-progress/handoffs/hpa-pilot2.md|.done`. Còn lại CHỈ ĐỌC.
- Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents.
- Không restart/reload daemon Paseo; không stop/archive agent nào không do bạn tạo (đặc biệt agent tiktok và phiên chính).
- Không đụng checkout chính `/Users/anhtp/app/claude-plugins` ngoài file bàn giao; không xoá/di chuyển `output/llm/`; không dọn worktree.
- Chỉ subscription; không API trả phí. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
