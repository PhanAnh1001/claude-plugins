# Brief giai đoạn 2: G3 — tích hợp hand agent Paseo vào `hand-ext run` (lane A)

## Tóm tắt

- **Mục tiêu:** nối các thành phần giai đoạn 1 (state/admission/supervisor, transport, gateway, worker) vào `hand-ext run`, để một lượt hand có thể chạy thành agent Paseo thật qua gateway ACP, vẫn giữ worktree/patch/report/ledger/guard/exit 7/8; shell vẫn là mặc định.
- **Quyết định đã duyệt:** như giai đoạn 1 (lane A, Q2–Q7). Xem spec/plan đã chốt trên nhánh: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `...-plan.md` mục 4 (G3) và mục 7.
- **Interface đầu vào:** mục "Interface đã chốt cho G3" trong `docs/work-in-progress/handoffs/hpa-p1.md` (repo chính `/Users/anhtp/app/claude-plugins`).
- **Thêm vào G3:** lệnh thiết lập provider `hh-hand-*` trên daemon Paseo bằng cơ chế chính thức (custom provider `extends: acp` trỏ `bin/hand-paseo-acp`), có `--dry-run` in thay đổi và `--apply`. Giai đoạn này **chỉ viết và test bằng fixture**, không chạy `--apply` trên máy thật.

## MỤC TIÊU

G3 xong offline: chế độ `shell` (mặc định) / `auto` / `paseo-required` trong config `ext_hand`; `auto` chạy managed qua Paseo khi daemon + provider + capability đủ, thiếu thì shell cùng backend trước dispatch; sau dispatch không fallback trùng writer. Có lệnh setup provider. Gateway hết deny prompt khi được bind đúng worker/checker tin cậy.

## Việc cần làm

1. Theo plan mục 4: `paseo_controller.py`, `paseo_completion.py` mới; sửa `run_cmd.py`, `cli.py`, `config.py`, `run_registry.py`, `report.py`. Checker thật cho fresh pick/account/guard/quota/capacity; isolation prepare/finalize hiện có; settlement hooks finalize/report/ledger đúng một lần; awaiting_review; review archive exact child; follow-up epoch mới (Q5: không resume context CLI).
2. Gateway (`paseo_gateway.py`, `bin/hand-paseo-acp`): bind worker/checker/limits thật để nhận prompt khi env/flag binding hợp lệ; thiếu binding vẫn fail closed.
3. Lệnh setup provider (đặt trong `cli.py`, ví dụ `hand-ext paseo-provider setup [--dry-run|--apply]` và `status`): đọc source Paseo 0.15.0 đã cài để xác định cách đăng ký custom provider chính thức (file:line), sinh cấu hình cho 4 provider `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2`; `--apply` ghi bằng đường chính thức, giữ nguyên mọi khoá khác, backup trước khi ghi; `status` kiểm provider có mặt trong catalog daemon. Test bằng thư mục home giả.
4. Q3: thêm cờ/khả năng để Sol giao "việc native mới" thành managed hand (ví dụ `hand-ext run --mode paseo-required`), chưa đổi template/policy (G5 làm).
5. Test theo plan mục 4 (controller 3 nhóm, completion 3 nhóm) + 1 nhóm cho setup provider (dry-run không ghi; apply ghi đúng, giữ khoá khác). Regression hẹp phần hand-ext đã sửa (isolation/report/registry/capacity/cli).

## Cách giao hand

Order repo: codex `gpt-6.1-sol` low đầu → theo Ngoại lệ A dùng subagent native Sol low (`fork_turns=none`, full brief, chép nguyên văn luật dữ liệu); thiếu native thì `hand-ext run --backend auto`. Tổng hand ≤ 4; cùng file/phụ thuộc tuần tự (G3 sở hữu `run_cmd.py`, không giao hai writer). Hand không recursion, không commit.

## PHẠM VI GHI

- Mới: `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/paseo_controller.py`, `paseo_completion.py`, (nếu cần) `paseo_provider.py`; test `hybrid-hands/tests/test_hand_paseo_controller.py`, `test_hand_paseo_completion.py`, `test_hand_paseo_provider.py`, fixture dưới `hybrid-hands/tests/fixtures/hand_paseo/**`.
- Sửa: `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/{run_cmd,cli,config,run_registry,report,paseo_gateway,execution_worker,paseo_transport,execution_admission}.py`, `bin/hand-paseo-acp`, test hand-ext có sẵn bị ảnh hưởng.
- Spec/plan: tick G3, cập nhật interface nếu đổi.
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` + `.done`.

## KHÔNG ĐƯỢC ĐỤNG

- `lib/side_session/*`, `lib/hh_ps/*`, skills/templates/README/OVERVIEW, `paseo-hh-tree/*`, statusline (giai đoạn 3). Không bump version/CHANGELOG.
- Không chạy setup `--apply` thật, không sửa config daemon Paseo thật, không tạo/send/stop/archive agent/workspace/project thật, không `paseo plugin install`.
- Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents. Không xoá/di chuyển/dọn `output/llm/`.
- Không commit vào `main`, không merge/push. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Test hẹp từng file. Cuối giai đoạn chạy **một lần** `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_*.py'` (toàn bộ hand-ext + hand_paseo, vì G3 sửa run_cmd/cli/config). Mức test: tối thiểu.
- Xong khi: G3 + setup provider commit trên nhánh, test xanh, Sol review từng diff; bàn giao ghi lệnh setup provider (dry-run/apply/status), cấu hình bật `auto` cho một repo, interface cho G4/G5, phần chưa kiểm chứng.

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: commits, file, kết quả test thật, cách bật pilot (lệnh và khoá config chính xác), rủi ro còn lại.
