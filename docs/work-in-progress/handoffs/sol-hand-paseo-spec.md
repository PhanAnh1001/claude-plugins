## Tóm tắt

- **Kết quả: xong phần nghiên cứu/spec/plan L2, chờ người dùng duyệt triển khai.**
- **Khuyến nghị:** Paseo quản lý agent con thật qua ACP gateway mới bọc runner hand-ext; workspace local riêng tại worktree cô lập, parent bằng callerAgentId. Gateway giữ admission/CLI/patch/report/usage; không dùng agent quan sát với shell writer độc lập.
- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`: kiến trúc, mapping backend, bằng chứng E1–E21, bảo đảm và 7 quyết định cần duyệt.
- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md`: gói theo file/phụ thuộc, test tối thiểu, full suite một lần cuối và release/install gates.
- Kiểm chứng thật: 3 nhóm probe pure source/fixture PASS (Node exit 0), 8 link nội bộ hợp lệ, 41 qualified file:line tồn tại; `git diff --cached --check` xanh.
- **Giới hạn:** chưa chứng minh sidebar native lồng; native đang chạy không chuyển thành agent riêng; gateway chưa tồn tại, full backend context resume chưa trong MVP.
- Đã cập nhật order repo **codex gpt-6.1-sol low → dsh → claude-v1 → claude-v2** theo người dùng/commit main `6d3e9c7`; không sửa config worktree cũ.
- **Commit:** `723d193` trên `side/sol-hand-paseo-spec`; chỉ hai docs, không push/merge/main.
- Không sửa plugin/test/config/side_session, không bump/install/reload, không chạy test plugin hay mutation Paseo thật; không tạo tiến trình nền/script tạm.
- Còn lại: Opus đọc spec/plan, trình 7 câu hỏi bên dưới; triển khai/live pilot/release chỉ sau duyệt. Usage hand token/USD/quota: `?` (không gọi hand).

## Backend → provider Paseo

Các provider `hh-hand-*` là đề xuất phải viết/cài mới, không phải provider đang có trên daemon. Native-intent mới đổi thành managed execution phải được duyệt; legacy native không tạo run/meta/report/ledger giả.

| Backend | Provider trực tiếp đã tìm được đường source | MVP khuyến nghị | Làm được / chưa làm được |
|---|---|---|---|
| codex | `codex-hand` kế thừa codex, CODEX_HOME `~/.codex-hand`, low (alias thực tế từ brief, không mở config để kiểm live) | `hh-hand-codex` ACP → runner codex hiện có | Có đường source; chưa live parity. Thiếu gateway/capability thì shell |
| claude-v1 | `claude` + per-launch CLAUDE_CONFIG_DIR `~/.claude`, low | `hh-hand-claude-v1` ACP → runner + guard 5%/ngày | Có đường env/account; direct chưa giữ đủ scrub/admission. Thiếu gateway thì shell |
| claude-v2 | `claude` + CLAUDE_CONFIG_DIR `~/.claude-hand`, low | `hh-hand-claude-v2` | Có đường source, chưa live; thiếu thì shell |
| dsh | Paseo generic custom ACP + DSH `--profile acp` thật có sẵn | `hh-hand-dsh` ACP → headless runner hiện có | ACP protocol khả thi nhưng shipped route khác Go, usage chỉ context. Giữ shell hiện tại tới khi gateway parity; không chỉ đổi command |

## Bảo đảm mất hoặc phải làm lại

Nếu dùng direct provider chỉ bằng createAgent, mất phần runner đang sở hữu tiến trình: timeout/token cap/exit classifier/report/ledger không tự đi theo; scrub env frontend cũng không scrub env daemon. Đặc biệt hook agent.turn.before là notification nên không chặn UI gửi tiếp vượt slot/quota. Khuyến nghị gateway gate mọi ACP session/prompt, giữ backend CLI/parser hiện có.

Gateway vẫn cần xây mới durable control state, shared supervisor/pool, crash/ACK reconciliation, cancel quiescent và finalize/ledger đúng một lần. Khóa kernel hiện tại tự nhả khi frontend thoát là chưa đủ nếu daemon còn writer. Native legacy ngoài dispatcher chỉ quan sát được, không thể cưỡng chế cap trước spawn; release phải định tuyến task mới qua dispatcher và reconcile unknown trước admission.

Không thể hứa native Codex/Claude child đang chạy được lift giữ nguyên hội thoại. Task mới native-intent đi gateway là managed hand mới, có record/ledger thật; đây là thay semantics Ngoại lệ A, không phải native runtime tự có Paseo agent ID. Gateway MVP có lịch sử Paseo, gửi tiếp là task brief mới tự chứa; không hứa resume context backend CLI. Không tự cleanup worktree vì workspace local mất directory thì recovery unavailable.

## Câu hỏi mở để Opus trình người dùng

1. Gateway bảo toàn runner hay provider trực tiếp phải xây lại parity? **Khuyến nghị gateway.**
2. Track cha + tab child + Cây phiên có đủ MVP, hay sidebar native phải lồng ngay? **Khuyến nghị track/tab MVP**, literal sidebar cần gói upstream app riêng.
3. Có đổi native-intent mới sang managed gateway/Ngoại lệ B? **Khuyến nghị opt-in cho lượt mới**, legacy giữ nguyên, không migrate đang chạy.
4. Archive khi nào? **Khuyến nghị giữ active sau done tới review**, archive exact child theo thao tác rõ ràng; không archive parent.
5. Reopen có cần full backend context ngay? **Khuyến nghị history Paseo + epoch/task mới**, full resume backend để gói sau.
6. Worktree retention bao lâu? **Khuyến nghị không cleanup tự động MVP**, policy disk/history-only riêng sau duyệt.
7. Rollout/fallback? **Khuyến nghị shell default, auto pilot được duyệt, paseo-required cho yêu cầu cứng**, cài provider bằng setup chính thức, không tạo key mới.

## Bằng chứng và kiểm chứng đã chạy

- Source đã cài: Paseo CLI/server/client 0.15.0, DSH 0.2.1-rc.5; repo base `a76826aa1e3ef0ae2ed10aa9b42d066c70c9a070`. Spec bảng E1–E21 ghi path prefixes đầy đủ và file:line. Đọc skill/reference Paseo như tài liệu nghiên cứu, không chạy workflow tạo agent của skill.
- Public đọc ngày 09/11/2026: [Orchestration](https://paseo.sh/docs/orchestration), [workflows](https://paseo.sh/docs/orchestration-workflows), [MCP](https://paseo.sh/docs/mcp), [CLI](https://paseo.sh/docs/cli), [custom providers](https://paseo.sh/docs/custom-providers), [hooks](https://paseo.sh/docs/plugins/hooks), [lifecycle upstream](https://github.com/getpaseo/paseo/blob/main/docs/agent-lifecycle.md). Ưu tiên source version cài khi tài liệu upstream khác.
- `node --input-type=module` qua stdin, import/extract pure source + fixture giả, exit **0**:
  - P1: public resolveSessionCreateAgentIntent + resolveCreateAgentIntent: child workspace giữ isolated cwd và parent; workspace cha hoặc omit workspace ép cwd về cha, 3 fixture PASS.
  - P2: helper createExternalProcessEnv với synthetic base giữ FAKE_API_KEY fixture-only khi overlay account dir; type turn.before là event, không waiting request, PASS. Không đọc/in env thật.
  - P3: DSH ACP usageUpdate với fake input/output/context chỉ phát used/size context, không billable token split, PASS.
- Python inline link checker: **8 internal Markdown links resolve**, evidence entries E1–E21 đủ; full-suite command trong plan xuất hiện đúng một lần và repo order mới có mặt, exit 0.
- Python inline citation checker: **41 qualified file:line** trỏ source tồn tại, dòng đầu có thật; link còn hợp lệ sau review, exit 0. Một số citation viết rút gọn cùng thư mục theo entry E đã đọc thủ công.
- `git diff --check`, rồi `git diff --cached --check`: exit **0**. Commit chỉ hai tài liệu (387 dòng thêm).
- `git show 6d3e9c7 -- .claude/hybrid-hands.json`: xác minh commit order mới đúng codex trước; chỉ đọc, không sửa config.
- Không test plugin/full suite/validate/install/reload, không create/send/cancel/archive/restore agent/workspace/project; không model/API calls, không đọc .env/auth/credential/transcript/log thật. Không probe runtime gateway/ACP handshake/live account/stop/reopen/sidebar app; các mục đó đã ghi gate rõ trong plan.
- Probe dùng stdin, không script/file tạm, không background process. Không hand/subagent được mở vì brief giao Sol tự nghiên cứu thiết kế L2; cập nhật native Sol-low được giữ cho các gói L0/L1 sau duyệt, không có writer trùng.

## Phạm vi và trạng thái bàn giao

- Worktree: `/Users/anhtp/app/claude-plugins-wt/sol-hand-paseo-spec`; branch `side/sol-hand-paseo-spec`.
- Spec: `/Users/anhtp/app/claude-plugins-wt/sol-hand-paseo-spec/hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`.
- Plan: `/Users/anhtp/app/claude-plugins-wt/sol-hand-paseo-spec/hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md`.
- Không sửa `lib/side_session/*`; sol-ws-hoi giữ ownership. Plan chỉ tham chiếu recovery contract, yêu cầu reconcile main mới trước implementation.
- Sau khi ghi/kiểm bàn giao, tạo `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/sol-hand-paseo-spec.done` làm tín hiệu xong. Không gửi tin cho brain bằng tool.


## Vòng 2

### Tóm tắt

- **Kết quả: xong vòng 2 nghiên cứu/spec/plan; Q1 kiến trúc vẫn chờ người dùng duyệt.** Mục này thay các khuyến nghị/câu hỏi vòng 1 ở trên; không coi B là quyết định đã duyệt.
- **Khuyến nghị:** pilot B chỉ Codex gpt-6.1-sol low qua adapter public client dựa bridge side-session, workspace/worktree riêng cùng project, callerAgentId=Sol, handoff .done và token pinned rollout. Nếu cần đủ bảo đảm bốn backend/guard mọi UI ngay bản đầu, chọn A gateway ACP; C plugin có sẵn chỉ nên học mẫu.
- Spec: thêm khảo sát 10 plugin, builtin/skills/registry, source pin/license/date, so sánh A/B/C và ma trận bảo đảm giảm của B.
- Plan: tách lane B/A/C, gói độc lập file, test hẹp, full suite một lần cuối và release/install gates.
- **Q2 đã chốt:** workspace riêng mỗi hand trong cùng project + Subagents track/tab cha là đủ, không cần sidebar lồng.
- **Q4 đã chốt:** done giữ hiện; Sol archive đúng hand sau review; follow-up tự revive cùng IDs, marker epoch mới.
- **Commit:** `a6db4bf` trên `side/sol-hand-paseo-spec`, chỉ hai docs; commit vòng 1 `723d193` giữ nguyên.
- Kiểm thật: 9 link nội bộ, 22 link source plugin pin, 52 file:dòng hợp lệ; A/B/C/Q2/Q4 và một full-suite command nhất quán; git diff/cached --check xanh.
- Chưa có plugin khảo sát nào thay trọn guards/pool/patch/ledger hand-ext; không install/reload, không test plugin, không code/config/Paseo mutation hay model call.
- Còn mở Q1/Q3/Q5/Q6/Q7 bên dưới; token/USD/quota hand nghiên cứu `?` (không giao hand). Cache source public tạm đã xóa, không tiến trình nền còn lại.

### Backend → provider theo ba lựa chọn

Nhãn hiện hành: **A gateway ACP, B Codex bridge MVP, C dựa plugin**; thay nhãn A/B/C ở vòng 1. Không provider hh-hand-* nào được đăng ký trong nhiệm vụ này.

| Backend | B pilot khuyến nghị có điều kiện | A gateway nếu chọn parity | Trạng thái |
|---|---|---|---|
| codex gpt-6.1-sol low | Paseo `codex-hand`, own workspace/worktree, caller Sol; adapter mới | hh-hand-codex → CLI runner | Có đường source, chưa live; adapter/admission/patch còn phải viết |
| dsh | Shell hand-ext hiện tại | hh-hand-dsh → runner Go/NDJSON hiện có | ACP shipped không tương đương route/usage; không bật direct |
| claude-v1 low | Shell hand-ext, guard 5%/ngày/account hiện tại | hh-hand-claude-v1 | Claude per-launch account env khả thi theo source nhưng chưa direct parity |
| claude-v2 low | Shell hand-ext đúng account | hh-hand-claude-v2 | Cùng giới hạn direct; không tự đổi config/account |

### Khảo sát plugin và kết luận

Nguồn public đọc **09/11/2026**: [directory Paseo](https://paseo.sh/plugins), [orchestration](https://paseo.sh/plugins/category/orchestration?window=all), [registry repo pin c64d118](https://github.com/getpaseo/plugins/tree/c64d1181b85d1dcdce552d50496ad1a88d749f9e), [registry protocol](https://github.com/getpaseo/plugins/blob/c64d1181b85d1dcdce552d50496ad1a88d749f9e/PROTOCOL.md), [workflows](https://paseo.sh/docs/orchestration-workflows), source package Paseo 0.15.0. Spec mục 3.5 giữ URL source/license từng plugin ở pin đã đọc.

- **Firstmate** gần nhất mỗi worker workspace/worktree, dùng MCP; charter không cap concurrency/cùng-file như repo. MIT, có thể học placement/board, không thay routing/guards chỉ bằng prompt.
- **Playbooks** có YAML DAG/parent manager/timeout/state nhưng step chung run workspace; package khai MIT, không có LICENSE riêng ở pin đã đọc, cần làm rõ notice trước vendor.
- **SLP** có real agent placement, caller mapping, assignment/evidence, MIT; whole plugin có role pool/setup riêng, tích hợp lớn và không cần thêm manager cạnh Sol.
- **gyuha Agent Team** orchestration CLI/MCP và shared workspace, chưa thấy LICENSE hoặc package license: không chọn copy/fork code khi chưa rõ điều khoản.
- **ssime-git Agent Teams** MIT, persistent roles/idempotency, nhưng object create khảo sát không đặt parent Sol và chung workflow workspace.
- **Agent Crew**, **Agent Tree**, **Workflow Progress** (MIT): UI/tree/progress, không biến shell/native thành daemon agent có lifecycle riêng. Hai plugin native cần đọc nội dung journal/transcript; phiên nghiên cứu chỉ đọc source, không dữ liệu thật.
- **Session Janitor** MIT: archive/retention, không create child; không bật auto archive vì Q4 sau Sol review. **Parent Wake** MIT: gửi thông báo parent, không executor/guard; không bật/install/gửi tin trong nhiệm vụ này.
- Skills chính thức `paseo`, `paseo-handoff`, advisor/committee và workflows là recipe create/workspace/wait/track; builtin là provider/usage/worktree-include, chưa thấy hand runner orchestrator trong builtin list. Code Paseo upstream Apache-2.0, third-party license riêng.
- Direct HTTP index `https://plugins.paseo.sh/index.json` trả **403**; thay bằng directory + 10 record registry Git pin + source pin. Khảo sát có chọn lọc, không audit toàn registry; npm source commit theo record, chưa tải/đối chiếu byte artifact hay test runtime.

### Bảo đảm B thiếu và khoảng trống bridge cần Opus kiểm

B giữ upfront pick/guard, isolation+patch nếu nối controller, shared reservation+timeout nếu viết supervisor; DSH/Claude shell giữ đường cũ. B **không có OS exit CLI Codex** từ wait/.done (backend_exit_code=null), không tự giữ max-turn/token cap/sandbox flags như runner, không cưỡng chế quota/slot cho người dùng gửi trực tiếp UI. Strict option không hỗ trợ phải fallback shell trước dispatch hoặc trả unsupported ở required. Rollout là nguồn token Codex; không tạo ledger hand-ext giả, không cộng rollout/projection/ledger. Unknown writer vẫn giữ slot, không apply/fallback.

Snapshot sol-ws-hoi đọc ở **2eae0b877a226705cd0209cb012861a4fd6d9100**: revive chỉ unarchive workspace khi agent đã active và cwd còn nguyên; không tự unarchive agent. `.done → _finish_codex → paseo.finish` đang archive ngay, trái Q4. Vì vậy adapter hand riêng phải thêm caller, awaiting_review, archive sau Sol review, mở agent cùng ID rồi revive workspace và admission epoch mới; không copy nguyên start/finish, không sửa lib/side_session của owner. refreshAgent source có unarchive/reload **và có thể interrupt**, phải precheck exact archived/quiescent child, cấm refresh parent/active polling. Cần live verify IDs/thread sau khi được phép; thiếu đường an toàn thì blocked, không tạo writer mới thay thế.

B pilot 3–5 ngày công là ước lượng thiết kế, không gồm parity mọi UI; A 8–15 ngày công; C fork nhỏ 5–10 nhưng parity toàn bộ C chưa đủ dữ liệu ước lượng. Không dùng ước lượng này làm cam kết lịch.

### Câu hỏi mở còn lại để trình người dùng

1. **Q1:** chọn B pilot với giới hạn trên, A gateway parity, hay C cần spike plugin cụ thể? Khuyến nghị B có điều kiện; không chấp nhận giảm bảo đảm thì A.
2. **Q3:** task mới trước đây native có route thành managed Codex qua B/A không? Legacy native giữ nguyên, không promote/migrate đang chạy; Claude native conversion ngoài phạm vi.
3. **Q5:** nếu chọn A có cần full backend context resume ngay không? B có đường Codex persistence nhưng cần live verify cùng thread; A mặc định history + brief epoch mới.
4. **Q6:** retention worktree? Khuyến nghị không cleanup tự động MVP để giữ reopen; cleanup history-only gói riêng.
5. **Q7:** rollout/fallback? Khuyến nghị shell mặc định, opt-in Codex pilot, required báo thiếu capability; không tự install plugin/provider/config trước duyệt.

**Q2/Q4 không còn là câu hỏi mở.**

### Kiểm chứng thật và phạm vi cuối vòng 2

- Python inline kiểm hai docs: **9 internal Markdown links** tồn tại; **22 pinned plugin source/license links** khớp file snapshot đã tải và line anchor trong bounds; **52 qualified file:line** tồn tại/dòng đầu hợp lệ. Snapshot branch E23 được đọc bằng git show tại hash cụ thể, không sửa nhánh đó.
- Kiểm bảng Markdown số cột nhất quán, đủ 10 candidates; nhãn A/B/C và Q2/Q4 không còn quyết định cũ; full Python suite command trong plan xuất hiện đúng một lần. Đây là lint tài liệu, không plugin test.
- `git diff --check` và `git diff --cached --check` exit 0; commit `a6db4bf` chỉ hai file docs (202 insertions, 141 deletions). Không push/merge/main.
- Không chạy thêm probe runtime, không plugin/full test/validate/install/reload/version bump; không tạo/send/stop/archive/restore agent/workspace/project thật, không thay settings hay đọc .env/auth/credential/transcript/log thật.
- Source public tải vào `/tmp/hand-paseo-spec-r2.XBAqVN` đã xóa và kiểm không còn trước commit/bàn giao. Mọi subprocess đã thoát; không background agent/hand/side-session được mở.
- Sau ghi/kiểm mục Vòng 2, tạo `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/sol-hand-paseo-spec-r2.done`. Bản tài liệu cuối: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md` và `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md` trên nhánh phiên.
