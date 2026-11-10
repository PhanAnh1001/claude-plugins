# Brief: nghiên cứu và viết spec/plan chạy hand/subagent thành agent Paseo

## Tóm tắt

- **Mục tiêu:** viết bản nháp spec và plan (L2, người dùng duyệt) để mỗi lượt hand/subagent chạy thành agent Paseo thật. Agent đó hiện dưới phiên cha trên sidebar Paseo và dừng/archive/mở lại được như phiên. Thiết kế dựa trên cách làm của tính năng agent orchestration của Paseo.
- **Người dùng chốt (09/11/2026):** chọn hướng "hand thành agent Paseo" (Ngoại lệ B trong AGENTS.md, trước đây chưa triển khai), tham khảo agent orchestration của Paseo.
- **Việc này chỉ nghiên cứu và viết tài liệu:** không sửa code plugin, không tạo agent/workspace Paseo thật, không đổi config.

## MỤC TIÊU

Có spec + plan đủ để người dùng duyệt và Sol triển khai: hand-ext (dsh/codex/claude-v1/claude-v2) và subagent native của Sol chạy qua daemon Paseo theo mô hình orchestration của Paseo, mà vẫn giữ đủ bảo đảm hiện có của hand-ext.

## NGỮ CẢNH (Opus đã biết)

- Daemon Paseo (Paseo CLI 0.15.0, gốc package `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`) chạy agent bằng CLI thật: provider `claude` → `claude --output-format stream-json --input-format …`; provider `codex-hand` → `codex app-server` với `CODEX_HOME=~/.codex-hand`.
- Đã xác minh ở `docs/work-in-progress/handoffs/sol-ws-chung.md`: `createAgent` nhận `cwd`, `workspaceId`, `callerAgentId` (`node_modules/@getpaseo/client/dist/daemon-client.d.ts:194-202`); có workspaceId tường minh thì cwd bị ép về cwd workspace (`node_modules/@getpaseo/server/dist/server/server/session.js:3325-3346`); `agent/create-agent/intent.js:18-26` dùng workspace/cwd của caller khi không chỉ định; đường MCP nội bộ `agent/create-agent/create.js:139-163` giữ cwd đã resolve. `inspectWorkspaceRecovery`/`restoreWorkspace` hoạt động (Opus đã dùng mở lại 6 workspace ngày 09/11).
- `paseo inspect` có `ParentAgentId`. `hybrid-hands/paseo-hh-tree/OVERVIEW.md` ghi API plugin không đổi được dòng sidebar gốc, nên hand chỉ hiện trên sidebar nếu là agent Paseo thật.
- Side-session đã tạo Sol qua bridge `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs` và `paseo.py` (workspace riêng mỗi worktree, gắn projectId, archive khi done). Đây là mẫu sẵn có trong repo.
- Hand-ext hiện tại: `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/` (worktree cô lập, `changes.patch` áp về repo, run/meta/report, sổ token/ledger, slot `max_parallel`, exit 7/8, timeout, `hand-ext pick`), order mặc định `dsh → codex → claude-v1 → claude-v2` (0.33.0). Subagent native của Sol theo Ngoại lệ A: `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt-codex.md`, `skills/paseo/SKILL.md`.
- `paseo-hh-tree/node_modules/@agentclientprotocol` có mặt: Paseo có thể hỗ trợ provider ACP; cần xác minh có chạy dsh qua đó được không.
- Phiên `sol-ws-hoi` đang sửa `lib/side_session/{paseo.py,paseo_bridge.mjs,actions.py,state.py}` (tự mở lại workspace). Không sửa các file đó; spec chỉ tham chiếu.

## Câu hỏi spec phải trả lời (có bằng chứng file:line hoặc URL công khai kèm ngày)

1. Agent orchestration của Paseo: tạo agent con bằng gì (CLI `paseo run`, MCP tool, `callerAgentId`, biến `PASEO_AGENT_ID`), quan hệ cha/con lưu ở đâu, sidebar hiện con thế nào, `send`/`wait`/`stop`/`archive` với con, con có cwd/worktree riêng được không, con xong thì sao. Đọc source đã cài, skill/tài liệu Paseo kèm package, và tài liệu công khai của Paseo nếu có.
2. Mỗi backend của hand-ext ánh xạ sang provider Paseo nào: codex (`codex-hand`, effort low), claude-v1/v2 (provider `claude` với config dir riêng của từng tài khoản?), dsh (ACP/provider tùy biến hay không làm được). Backend nào không có cách thì giữ đường shell hiện tại và nói rõ.
3. Giữ được những bảo đảm nào của hand-ext khi chạy qua Paseo: worktree cô lập + patch, slot `max_parallel` chung với native, exit code 7/8, timeout, quota/chặn ngày, token ledger/USD~, report. Cái nào mất hoặc phải làm lại.
4. Subagent native của Sol: có trở thành agent Paseo riêng (dừng riêng được) hay vẫn nằm trong tiến trình `codex app-server` của Sol. Nếu không đổi được thì ghi rõ giới hạn.
5. Subagent Claude Code (`hybrid-hands:hand`): có đưa lên Paseo được không; nếu không thì ghi ngoài phạm vi.
6. Vòng đời trên sidebar: tên dòng, cha, archive khi xong, tự mở lại (khớp với việc của `sol-ws-hoi`), dọn workspace, không đụng phiên chính.
7. Fallback khi daemon Paseo không chạy hoặc thiếu capability: quay về đường shell hiện tại, không tạo writer trùng.
8. Ảnh hưởng tới `hh-ps`, Cây phiên, statusline (nguồn token/trạng thái mới, không đếm trùng).

## Sản phẩm

- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`: mở đầu bằng tóm tắt (mục tiêu, quyết định chính, giới hạn, việc người dùng cần duyệt), rồi trình bày từ nhóm lớn tới nhánh. Mỗi phương án có lựa chọn khuyến nghị. Câu hỏi mở cần người dùng chốt đặt thành danh sách riêng.
- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md`: tóm tắt đầu file, chia gói theo file độc lập để chạy song song, mỗi task là checkbox, ghi test hẹp cho từng gói, mức test tối thiểu, lệnh full suite chạy một lần cuối, bước release (bump, CHANGELOG, validate, cập nhật cài đặt).
- Bàn giao theo hợp đồng side-session.

## PHẠM VI GHI

- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md` (tạo mới)
- Script probe tạm chỉ đọc trong thư mục tạm riêng, xoá trước khi báo cáo.
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` và `.done`.

## KHÔNG ĐƯỢC ĐỤNG

- Không sửa code/test/config plugin, không bump version. Không sửa `lib/side_session/*` (phiên `sol-ws-hoi` đang làm).
- Không tạo/send/stop/archive/delete agent, workspace hay project Paseo thật; chỉ đọc metadata (`paseo ls`, `inspect`, `workspace ls`, `project ls`, đọc source). Probe hàm bằng fixture giả như bàn giao `sol-ws-chung` đã làm.
- Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents. Không xoá/di chuyển/dọn `output/llm/`.
- Không commit vào `main`, không merge/push. Được commit tài liệu trên nhánh phiên của mình.
- Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol là lead tech: phần đọc source và viết spec/plan Sol tự làm (việc thiết kế, không phải code L0/L1). Nếu cần hand tra cứu song song thì giao qua `hand-ext run --backend auto` theo `ext_hand.order`, chép nguyên văn luật dữ liệu vào brief hand, và review kết quả.

## KIỂM CHỨNG

- Tài liệu: link nội bộ trỏ đúng file tồn tại; mỗi kết luận về Paseo có file:line source đã cài hoặc URL công khai kèm ngày; phân biệt rõ cái đã probe với cái suy luận.
- Không chạy test plugin (không đổi code).
- Xong khi: hai file spec/plan đã commit trên nhánh, bàn giao liệt kê câu hỏi mở cần người dùng chốt.

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: khuyến nghị kiến trúc trong một đoạn, bảng ánh xạ backend → provider Paseo (làm được / không), bảo đảm nào mất, câu hỏi mở, commit.
