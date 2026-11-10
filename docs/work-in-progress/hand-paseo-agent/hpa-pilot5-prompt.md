# Giao việc phiên Sol `hpa-pilot5`: legacy-attest recover, rồi smoke dsh/claude-v2 và gate stop

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain Opus v2 (agent Paseo `711ef386-2673-4c8b-8b1a-f24f1e56805e`; hỏi L1 bằng `paseo send --no-wait --behavior steer`). Đọc đủ `docs/work-in-progress/handoffs/hpa-pilot4.md` trước.
- **Người dùng đã duyệt (L2, 09/11/2026):** thêm đường recover xác nhận tay cho record cũ thiếu inventory: `hand-ext managed recover --legacy-attest` (tên cờ có thể điều chỉnh, giữ nghĩa). Mục tiêu: nhả reservation `c9d729cf…` của record `597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1`, đang chặn mọi hand managed ở claude-plugins (exit 8).
- **Opus duyệt thêm (L1):** intent bị từ chối ở admission (AdmissionConflict/AdmissionFull, chưa có reservation/process/agent) phải thành terminal `not_admitted`, không treo `unknown` trong hh-ps; recover hai intent `9d939fbb-61ba-46b7-bcc0-93af0dd5477b:9c960316-9a77-477e-b6fb-b7f127bd72ca:1` (dsh) và `b6a7f87a-a8e7-444a-b984-79a3dc2f9587:9a9858bf-886c-4a88-906b-e21a22055e74:1` (claude-v2) cùng đường đó. CLI exit 8 in lý do ngắn (loại conflict, key đang giữ claim), không lộ dữ liệu nhạy cảm.
- **Release:** 0.35.6, thêm tối đa một vòng 0.35.7. Quy trình như hpa-pilot4 (hand code/test, bạn review, narrow + full suite một lần mỗi release, validate, merge/push main bằng `git -C`, `claude plugin update` cho **cả** `CLAUDE_CONFIG_DIR=~/.claude` và `~/.claude-hand`, kiểm plugin list hai repo × hai account).
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/hpa-pilot5.md` (mở đầu tóm tắt) rồi tạo file rỗng `docs/work-in-progress/handoffs/hpa-pilot5.done`. Bị chặn cũng ghi chỗ chặn rồi tạo `.done`.

## 1. Hợp đồng `--legacy-attest`

Dry-run mặc định; `--apply` mới ghi. Bắt buộc **đủ tất cả**:

1. Record cancelled/unresolved, latest exact epoch, có worker_owner/process nhưng **thiếu** inventory/reap proof (tức là record tạo trước 0.35.5); record có inventory đầy đủ phải đi đường `post_hoc_reverify`, không dùng cờ này.
2. Bound IDs (invocation/attempt/request/placement/cwd/reservation) khớp durable receipt; thao tác dưới lock và revision fence strict.
3. Worker owner (gateway supervisor, record ghi pid 37655) **đã chết**, có chứng minh bằng OS identity (pid + OS start) hoặc PID reuse đã chứng minh. Nếu còn sống: CLI từ chối và in hướng dẫn đóng exact child qua đường Paseo chính thức. Ở bước live, bạn được phép đóng/archive **đúng** child `6690365c-6cc5-4778-a502-622a3705827a` qua Paseo public để gateway exit; xác minh exact identity trước; không đụng agent khác.
4. Root pid/PGID ghi trong record không còn sống (pid absent hoặc OS start khác).
5. Quét marker cùng user ngay lúc apply: 0 process mang marker của invocation này, **0 lỗi quét không vô hại** (EPERM/không chắc → từ chối).
6. Cờ operator tường minh và chuỗi lý do do operator truyền (vd `--reason "người dùng duyệt 09/11/2026"`), lưu vào record.

Kết quả: outcome `cancelled`, quiescence **không** đánh `confirmed: true` giả mà ghi `attested: true`, `method: operator_legacy_attest`, kèm evidence 3–5; settlement qua năm hook chuẩn và admission release đúng một lần; `--apply` lặp ổn định (byte-identical). hh-ps hiện row cancelled/✗ hoặc nhãn attested — không phải ✓. README/CHANGELOG: nêu rõ đây là ngoại lệ có người xác nhận, chỉ cho record trước 0.35.5, rủi ro còn lại (process vừa xoá marker vừa thoát cây).

## 2. Thứ tự

1. Code + test qua hand (`hand-ext pick --json` trước; `run --backend auto --mode shell --cwd <worktree> --keep-worktree`; worktree `/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`, merge main trước). Acceptance tối đa 3 nhóm: (a) legacy-attest đủ điều kiện → release một lần, lặp ổn định; thiếu bất kỳ điều kiện nào → từ chối không mutation; (b) admission reject → `not_admitted` terminal, hh-ps không unknown, exit 8 có lý do; recover intent cũ; (c) không rò env/argv/secret.
2. Review, release 0.35.6.
3. Live: đóng exact child `6690365c…` qua Paseo public (nếu gateway còn sống) → `managed recover --legacy-attest` dry-run → `--apply --reason …` → lặp `--apply`. Kiểm reservation `c9d729cf…` đã nhả, `managed ls`/`hh-ps --once` đúng 1 row cancelled/attested. Recover hai intent cũ.
4. Gate 5: smoke managed `dsh` và `claude-v2` (`--mode paseo-required --no-apply`, scratch 1 dòng, cap token đủ, timeout hữu hạn), kiểm placement/model/account/effort, hh-ps 1 row mỗi cái, review-approve/archive. Guard/quota chặn thì ghi lý do. **Không** claude-v1.
5. Gate 3 trên 0.35.6: task sleep setsid, `paseo stop` exact child; mong đợi certificate confirmed (method `root_group+tracked_tree+env_marker`) và reservation nhả tự động. Kiểm `ps` + quét marker sau stop.
6. Lỗi mới: sửa thành 0.35.7 (một vòng), rồi chạy lại bước lỗi. Mỗi bước ghi lệnh, kết quả thật, pass/fail/unknown.

## 3. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Thêm vào brief hand: chỉ đọc file trong worktree được giao; không chạy `ps`/`pgrep`/lệnh liệt kê tiến trình hay phiên khác của máy (lượt hpa-pilot4 hand dsh đã chạy `pgrep -fl` lộ command line phiên khác — không lặp lại).

## 4. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/hpa-pilot-fix`; merge + version/CHANGELOG trên main (chỉ file plugin của bản vá); execution state/agent pilot do bạn tạo, record `597c17ca…`, hai intent nêu trên (chỉ qua CLI); đóng/archive đúng child `6690365c…`; `docs/work-in-progress/handoffs/hpa-pilot5.md|.done`. Còn lại CHỈ ĐỌC.
- Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents; không cài plugin cho account khác.
- Không restart/reload daemon Paseo; không stop/archive agent nào khác (đặc biệt agent tiktok, phiên chính, parent pilot cũ).
- Không xoá/di chuyển `output/llm/`; không dọn worktree; không reset/stash thay đổi người khác; không sửa record/reservation bằng tay.
- Chỉ subscription; không API trả phí. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
