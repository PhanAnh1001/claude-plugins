# Giao việc phiên Sol `ws-archive-hand`: hand managed xong thì archive child + workspace, followup thì hiện lại

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain Opus v2 (agent Paseo `711ef386-2673-4c8b-8b1a-f24f1e56805e`). Chạy **song song** với phiên Sol `ws-archive` (agent `fd39b959-86ff-429e-a04f-4784a1ab6801`), phiên đó là lead tích hợp và release 0.36.0; bạn chỉ làm phần hand managed, **không release**.
- **Yêu cầu người dùng (đã duyệt hành vi):** hand xong việc và báo cáo thì archive child và workspace chứa nó; khi được giao lại (`managed followup`) thì cả hai hiện lại.
- **Kết thúc:** commit + push nhánh `side/ws-archive-hand`, ghi `docs/work-in-progress/handoffs/ws-archive-hand.md` (tóm tắt: commit, file, test, điểm tích hợp với ws-archive) rồi tạo file rỗng `docs/work-in-progress/handoffs/ws-archive-hand.done`; gửi một tin ngắn `paseo send --no-wait --behavior steer fd39b959-86ff-429e-a04f-4784a1ab6801 '<commit + đường dẫn handoff>'` để ws-archive merge.

## 1. Hợp đồng

1. Execution settle xong report (`awaiting_review`, đủ hook) → tự archive exact child **và** workspace của nó (workspace hand luôn riêng theo Q2; xác định thành viên theo `workspaceId`, không theo cwd; chỉ archive workspace khi mọi agent trong đó đã archived). Không chờ review-approve; review-approve vẫn là điều kiện cho followup. `managed archive` giữ, idempotent, archive cả workspace.
2. `managed followup`: restore workspace (API public Paseo, vd `workspace.recovery.restore`/unarchive record — xác minh trong source `server/session.js` ~2224/2905 và client đã pin) → unarchive/reopen exact child → epoch mới như hiện có. Workspace/cwd mất → blocked như contract cũ, không recreate.
3. Lỗi archive/restore: không mất trạng thái record, ghi receipt, retry hữu hạn ở lần gọi sau; không xoá thư mục (archive workspace chỉ xoá worktree Paseo-owned — worktree hand ở `~/.hybrid-hands/worktrees` không phải; vẫn kiểm bằng fixture).
4. hh-ps không đổi ý nghĩa trạng thái.

## 2. Quy trình

- Worktree `/Users/anhtp/app/claude-plugins-wt/ws-archive-hand`, nhánh `side/ws-archive-hand` từ main mới nhất (0.35.6 `055336a` trở lên). Phạm vi file: `lib/hand_ext/paseo_*.py`, `paseo_bridge.mjs`, tests `test_hand_paseo_*` và fixture tương ứng. **Không** sửa `lib/side_session/*`, README, skills, templates, AGENTS.md, manifest, CHANGELOG (ws-archive làm); ghi đoạn docs đề xuất trong handoff.
- Code/test qua hand, chạy **song song tối đa** `ext_hand.max_parallel` khi file tách biệt (vd bridge/transport một hand, controller/CLI một hand, tests một hand); cùng file thì tuần tự. `hand-ext pick --json` trước; `run --backend auto --mode shell --cwd <worktree> --keep-worktree`, cap token đủ lớn. Review diff; lỗi → giao lại cùng backend một lần, rồi backend kế tiếp.
- Test hẹp `test_hand_paseo_*` + `node --check` bridge; full suite một lần cuối trên nhánh. Không smoke live (ws-archive smoke sau khi merge).

## 3. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Thêm vào brief hand: chỉ đọc file trong worktree được giao; không chạy `ps`/`pgrep`/lệnh liệt kê tiến trình hay phiên khác của máy.

## 4. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/ws-archive-hand`; `docs/work-in-progress/handoffs/ws-archive-hand.md|.done`. Không merge main, không bump, không update plugin. Còn lại CHỈ ĐỌC.
- Không sửa config/settings/credential/`installed_plugins.json`; không bật parallel-subagents; không restart/reload daemon; không archive/stop agent/workspace thật nào.
- Không xoá/di chuyển `output/llm/`; không dọn worktree. Chỉ subscription. Mọi chờ có timeout hữu hạn.
