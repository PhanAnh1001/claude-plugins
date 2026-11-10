# Giao việc phiên Sol `hpa-pilot`: live pilot hand agent Paseo ở claude-plugins

## Tóm tắt

- **Vai:** Sol lead tech/QA. Brain là phiên chính Opus v2. Mục tiêu: chứng minh live G7 (hpa-p3 bước 5–8) cho managed Paseo hand ở repo `/Users/anhtp/app/claude-plugins`, sửa lỗi nếu có trên nhánh riêng, ghi bàn giao.
- **Đã xong trước bạn (Opus v2, 09/11/2026):** `hand-ext provider setup --apply` (4 provider `hh-hand-codex|dsh|claude-v1|claude-v2`), `paseo daemon reload` (appliedPaths `agents.providers`, không restart-required), `.claude/hybrid-hands.json` repo đã có `ext_hand.mode=auto` + `ext_hand.paseo{package_root,target instance /Users/anhtp/.paseo}`; `hand-ext provider status --cwd /Users/anhtp/app/claude-plugins` = READY, missing rỗng.
- **Bắt buộc:** smoke backend `codex`. Tuỳ chọn nếu rẻ và pick/guard cho phép: một task nhỏ `dsh`, một task nhỏ `claude-v2`. **Không** smoke `claude-v1` (v1 đã dùng nhiều hôm nay).
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/hpa-pilot.md` (mở đầu bằng tóm tắt: pass/fail từng gate, lỗi, nhánh/commit sửa) rồi tạo file rỗng `docs/work-in-progress/handoffs/hpa-pilot.done`. Bị chặn cũng ghi rõ chỗ chặn rồi tạo `.done`.

## 1. Đọc trước

- `/Users/anhtp/app/claude-plugins/AGENTS.md` (luật repo).
- `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/hpa-p3.md` mục "Thứ tự live pilot" bước 5–8 và "Việc còn lại và giới hạn".
- `/Users/anhtp/app/claude-plugins/hybrid-hands/README.md` phần managed Paseo hand; `skills/ext-hand/SKILL.md`, `skills/paseo/SKILL.md` trong plugin.
- Spec/plan: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `...-plan.md`.

CLI: `H=/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin`.

## 2. Các gate pilot (theo thứ tự)

1. **Dispatch:** từ chính context của bạn (có `PASEO_AGENT_ID`), `$H/hand-ext pick --json` rồi `$H/hand-ext run --backend auto --mode paseo-required --brief /ABS/brief.md --cwd /Users/anhtp/app/claude-plugins --no-apply`. Brief hand do bạn viết, tự chứa, task disposable: tạo file mới `docs/work-in-progress/hpa-pilot-scratch.md` một dòng "pilot ok" trong workspace riêng của hand; không đọc/sửa gì khác. Chép nguyên văn luật dữ liệu ở mục 4 vào brief.
2. **Placement:** child có workspace/cwd riêng, cùng project claude-plugins, parent canonical là bạn, tab Subagents ở cha; model/account/effort đúng. Kiểm bằng `paseo ls --json`/`paseo inspect` và `$H/hh-ps --once` + `--json`: đúng **một** hand row, tokens/USD~/ended/elapsed đúng nguồn (thiếu thì `?`), không rollout root trùng.
3. **Stop:** dispatch task disposable thứ hai (dài hơn một chút) rồi stop/cancel nó qua đường chính thức; kiểm quiescence/settlement thật (process tree đã reap, reservation giải phóng), không dựa UI idle. Unknown thì giữ reservation, ghi lại, không blind retry.
4. **Lifecycle:** với task 1 đã done: đọc diff/report, `$H/hand-ext managed ls --cwd ...`, `review-approve --key K`, `archive --key K`; verify chỉ child archived, parent/workspace còn. Rồi `followup --key K --brief NEW` (brief tự chứa mới, sửa dòng thành "pilot ok 2"); verify reopen cùng agent/workspace, epoch 2, key/baseline/artifacts mới, epoch 1 còn, không áp patch hai lần. Không dọn worktree.
5. **Smoke tuỳ chọn:** `dsh` và `claude-v2` mỗi cái một task một dòng tương tự (`--backend dsh|claude-v2`). Guard/pick chặn thì ghi lý do, bỏ qua.
6. **Fallback:** chỉ kiểm bằng đọc code/test sẵn có (auto quay shell khi thiếu provider trước dispatch); **không** tắt provider/daemon để thử.

Mỗi gate ghi: lệnh, kết quả thật, pass/fail/unknown. Không claim phần chưa chạy. Gate 1 dùng `--backend auto` (order repo codex đứng đầu); pick ra backend khác codex thì ghi lại và vẫn chạy theo pick.

## 3. Lỗi tìm thấy

- Sửa trên worktree nhánh `side/hpa-pilot-fix` từ `main` (`/Users/anhtp/app/claude-plugins-wt/hpa-pilot-fix`). Giao code/test L0/L1 cho hand theo AGENTS (hand-ext run --backend auto, shell hoặc managed đều được), bạn review diff.
- Test hẹp phần sửa; full suite chỉ một lần cuối nếu có sửa code.
- Commit trên nhánh sau review, push nhánh. **Không merge main, không bump version/CHANGELOG, không cập nhật cài đặt plugin** — Opus làm release vì checkout chính đang có thay đổi chưa commit của phiên cấu hình global (0.35.0).
- Lỗi chặn gate sau thì sửa rồi chạy lại gate (dùng code từ worktree fix nếu cần, nêu rõ).

## 4. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## 5. Giới hạn

- PHẠM VI GHI: state/agent pilot do bạn tạo; worktree `side/hpa-pilot-fix`; `docs/work-in-progress/handoffs/hpa-pilot.md|.done`. Còn lại CHỈ ĐỌC.
- Không sửa `.claude/hybrid-hands.json`, `~/.paseo/config.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents.
- Không restart/reload daemon Paseo; không stop/archive agent nào không do bạn tạo trong pilot (đặc biệt agent tiktok và các phiên chính).
- Không đụng các file đang sửa dở trong checkout chính (`git status` ở `/Users/anhtp/app/claude-plugins`); không xoá/di chuyển `output/llm/`.
- Chỉ subscription; không API trả phí. Không vòng chờ vô hạn; mọi chờ có timeout hữu hạn; dừng tiến trình nền mình tạo trước khi bàn giao.
