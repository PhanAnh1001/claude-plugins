## Tóm tắt
- Kết quả: xong. Đúng một managed hand Paseo đã chạy khoảng 133 giây, exit 0.
- Backend/model/effort: `codex / gpt-6.1-sol / low`, account `gpt`, provider `hh-hand-codex`.
- Child: `5cd5a742-9c5d-4cf9-84ef-8d7d70bbbcca`; workspace: `wks_218dffc04b5e999b`.
- Child và workspace đã tự archive trước khi Sol review-approve; không stop/archive thủ công/followup.
- File ngoài repo: `/Users/anhtp/app/claude-plugins-wt/demo-subagent-brief.md` — brief demo tự chứa, luật dữ liệu nguyên văn.
- File repo: `docs/work-in-progress/handoffs/demo-subagent.md` — bàn giao kết quả và bằng chứng.
- File repo: `docs/work-in-progress/handoffs/demo-subagent.done` — tín hiệu hoàn thành, tạo sau bàn giao.
- Kiểm chứng đạt: pick, managed ls, paseo inspect, hh-ps --once, report/patch/events, workspace recovery, review-approve.
- Scratch chỉ có trong worktree hand; --no-apply không áp vào repo gốc. Không sửa plugin/config, không commit/push.
- Còn lại: không có; chưa kiểm trực quan app/tab Subagents, đã kiểm parent binding bằng public metadata.

## Định danh và lệnh chạy
- Key: `12496cd9-1a8a-43d2-aabf-4bf0ec7b07ee:7d085d70-8205-4d00-93a0-0289c3c2ae4d:1`.
- Parent canonical session: `cd35dfdc-20cf-44cf-b9af-be8bf00d3143`.
- Parent Paseo agent (Sol demo-subagent này): `84b99b86-b1b4-4ada-8eb4-50dfce4976f3`.
- Child: `5cd5a742-9c5d-4cf9-84ef-8d7d70bbbcca`.
- Workspace: `wks_218dffc04b5e999b`; project: `prj_7a322b4848a466f5` (`claude-plugins`).
- Worktree giữ lại: `/Users/anhtp/.hybrid-hands/worktrees/claude-plugins-20261109-212536-439179-demo-subagent-codex`.
- `hand-ext pick --json`: exit 0; chọn codex/gpt-6.1-sol/low/gpt, skipped rỗng, native=true. Theo brief vẫn dùng managed Paseo.

```sh
/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --mode paseo-required --brief /Users/anhtp/app/claude-plugins-wt/demo-subagent-brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply --label demo-subagent --timeout-min 6
```

Lệnh được bọc subprocess timeout hữu hạn 480 giây; kết thúc exit 0, `hand-ext: codex ok`, không chạm timeout.

## Kiểm chứng chạy thật và review
1. `hand-ext managed ls --cwd /Users/anhtp/app/claude-plugins`: ghi exact key/child/workspace IDs khi state running. `paseo inspect CHILD --json` xác nhận running, Archived=false, ParentAgentId đúng Sol ở trên.
2. `hh-ps --once`: exit 0, đúng một dòng hand `codex gpt-6.1-sol/low ... demo-subagent` ngay dưới `phụ:demo-subage…`. Sol thuộc nhóm phiên phụ chưa rõ phiên cha; hand gắn đúng Sol, không rơi vào nhóm orphan hand.
3. Report và changes.patch chỉ có một file mới `docs/work-in-progress/demo-subagent-scratch.md`, một dòng `demo ok`; kiểm bytes worktree đúng `b'demo ok\n'`. Finalize: status=skipped, detail=managed policy: no_apply. Checkout gốc không có scratch.
4. Events chỉ của demo: đúng hai command completed (tạo scratch và `sleep 120`), cả hai exit 0; sleep chạy đúng một lần. Không có command hand-ext/side-session/subagent/ps/pgrep từ executor trong events demo. Không chạy suite vì chỉ demo runtime, không sửa plugin.
5. Backend bắt đầu 21:25:41.935, kết thúc 21:27:54.760 ngày 09/11/2026 (Asia/Ho_Chi_Minh), duration 132.825 giây. Outcome ok/exit 0, quiescence.confirmed=true, root_reaped=true, reservation=null.
6. Trước review-approve: execution đã archived, transport archiveConfirmed=true. `paseo inspect CHILD --json` trả Status=closed, Archived=true, ArchivedAt=2026-11-09T14:27:56.026Z (21:27:56 local).
7. `paseo workspace ls --background --json` không còn workspace demo. Kiểm riêng bằng public client của official CLI @getpaseo/cli 0.15.0: `inspectWorkspaceRecovery('wks_218dffc04b5e999b')` trả kind=recoverable, action=unarchive, xác nhận workspace archived. Chỉ đọc, không restore.
8. Sau khi Sol đọc report/patch/events: `hand-ext managed review-approve --cwd /Users/anhtp/app/claude-plugins --key 12496cd9-1a8a-43d2-aabf-4bf0ec7b07ee:7d085d70-8205-4d00-93a0-0289c3c2ae4d:1`: exit 0, ok=true, state=archived, review_approved=true theo output CLI. Không followup.

## Artifacts giữ lại
- Report: `/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261109-212536-439179-demo-subagent-codex/2265a8240302a71f5893974f24bb5c78eec1c6e9faa802a8af9ebc822564510b/report.md`.
- Patch: `/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261109-212536-439179-demo-subagent-codex/2265a8240302a71f5893974f24bb5c78eec1c6e9faa802a8af9ebc822564510b/changes.patch`.
- Events demo: `/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261109-212536-439179-demo-subagent-codex/2265a8240302a71f5893974f24bb5c78eec1c6e9faa802a8af9ebc822564510b/events.jsonl`.
- Execution state: `/Users/anhtp/.hybrid-hands/executions/2265a8240302a71f5893974f24bb5c78eec1c6e9faa802a8af9ebc822564510b.json`.
- Giữ nguyên worktree/history/report/patch/output. Không cleanup, không tác động agent khác, không restart/reload daemon. Không sửa settings/credential, không tự gọi API trả phí.
