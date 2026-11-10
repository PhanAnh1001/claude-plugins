# Giao việc phiên Sol `hpa-pilot4`: chẩn đoán stop unresolved, recover, smoke dsh/claude-v2

## Tóm tắt

- **Vai:** Sol lead tech/QA; brain là phiên chính Opus v2 (agent Paseo `711ef386-2673-4c8b-8b1a-f24f1e56805e`; có câu hỏi L1 thì `paseo send --no-wait --behavior steer` tới agent đó, chờ trả lời, không mở phiên mới). Đọc đủ `docs/work-in-progress/handoffs/hpa-pilot3.md` trước.
- **Việc:** (1) chẩn đoán vì sao record stop `597c17ca-489d-40a3-8d26-d56519702bcc:e116170f-6287-4665-b45d-cf80b18b3709:1` thành sticky lost-authority/unknown dù tiến trình đã sạch, sửa, rồi recover để nhả reservation `c9d729cf…`; (2) smoke managed `dsh` và `claude-v2` (gate 5); (3) nếu rẻ, lặp gate 3 stop một lần trên bản mới để xác nhận certificate confirmed.
- **Opus đã duyệt trước (L1):**
  - Thêm metadata chẩn đoán an toàn vào evidence containment: stage, method, loại lỗi (vd `scan_eperm`, `signal_esrch`, `identity_mismatch`), pid/start của tiến trình liên quan; tuyệt đối không env/argv đầy đủ.
  - Sửa nguyên nhân gốc nếu chứng minh được là phân loại sai (lỗi vô hại như ESRCH sau khi tiến trình đã chết, hoặc EPERM trên tiến trình không thuộc cây/không cùng thời gian chạy) — giữ fail closed khi không chắc. Ghi rõ lý lẽ.
  - Lệnh **re-verify sau** (vd `managed recover` nhánh mới hoặc `managed reverify`, dry-run mặc định, `--apply` mới ghi) cho record cancelled-unresolved có worker_owner/process: chỉ xác nhận quiescence khi **mọi** identity đã track (pid + OS start) đã chết hoặc bị PID-reuse đã chứng minh, root reaped, quét marker cùng user sạch, worker owner không còn giữ execution sống (hoặc owner chủ động xác nhận), bound IDs khớp, dưới lock/revision fence. Evidence method `post_hoc_reverify`. Không đủ → từ chối, không mutation. Sau đó settlement/release theo đường chuẩn (hook settle), không nhả reservation tay.
  - Release: 0.35.5, thêm tối đa một vòng 0.35.6. Quy trình như hpa-pilot3 (hand làm code/test qua `hand-ext run --backend auto`, bạn review diff, narrow + full suite một lần mỗi release, validate, merge/push main bằng `git -C`, `CLAUDE_CONFIG_DIR=~/.claude claude plugin update … --scope user`, kiểm plugin list hai repo claude-plugins và live-tiktok-games).
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/hpa-pilot4.md` (mở đầu tóm tắt: nguyên nhân, commit/version, test, recover, kết quả smoke từng backend) rồi tạo file rỗng `docs/work-in-progress/handoffs/hpa-pilot4.done`. Bị chặn cũng ghi chỗ chặn rồi tạo `.done`.

## 1. Thứ tự

1. Chẩn đoán đọc code + metadata record (không đọc raw log/transcript/env). Nếu cần tái hiện, dùng fixture giả cục bộ.
2. Sửa + re-verify qua hand, review, release 0.35.5.
3. Recover record `597c17ca…` bằng CLI main (dry-run → `--apply` → lặp `--apply` ổn định); kiểm reservation đã nhả, `managed ls`/`hh-ps --once` đúng 1 row cancelled, không trùng. Sau đó review-approve/archive exact child nếu lifecycle cho phép.
4. Gate 5 (độc lập với 1–3, có thể chạy trước nếu slot đủ): `hand-ext pick --json`, rồi `hand-ext run --backend dsh --mode paseo-required --brief <scratch 1 dòng> --cwd /Users/anhtp/app/claude-plugins --no-apply` và tương tự `--backend claude-v2`. Kiểm placement/model/account/effort, hh-ps 1 row, review-approve/archive. Guard/quota chặn thì ghi lý do, không đổi config. **Không** claude-v1.
5. Nếu còn thời gian: lặp gate 3 (sleep setsid, `paseo stop` exact child) trên bản mới, mong đợi certificate confirmed + reservation nhả.

Mỗi bước ghi lệnh, kết quả thật, pass/fail/unknown; không claim phần chưa chạy.

## 2. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## 3. Giới hạn

- PHẠM VI GHI: worktree/nhánh `side/hpa-pilot-fix` (`/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`); merge + version/CHANGELOG trên main checkout chính (chỉ file plugin của bản vá); execution state/agent pilot do bạn tạo và record `597c17ca…` (chỉ qua lệnh CLI); `docs/work-in-progress/handoffs/hpa-pilot4.md|.done`. Còn lại CHỈ ĐỌC.
- Không stage/sửa `.claude/hybrid-hands.json`, `docs/work-in-progress/**` khác; không sửa `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents; không cài plugin cho account khác.
- Không restart/reload daemon Paseo; không stop/archive agent nào không do bạn tạo (đặc biệt agent tiktok và phiên chính). Gateway supervisor còn sống của record cũ: chỉ tác động qua đường chính thức đã chứng minh exact identity.
- Không xoá/di chuyển `output/llm/`; không dọn worktree; không reset/stash thay đổi người khác.
- Chỉ subscription; không API trả phí. Mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
