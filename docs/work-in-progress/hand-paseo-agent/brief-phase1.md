# Brief giai đoạn 1: hand thành agent Paseo — lane A gateway (G0, G1, G2, G6)

## Tóm tắt

- **Mục tiêu:** chốt quyết định vào spec/plan, chốt interface (G0), rồi làm xong G1 (identity/state/admission), G2 (adapter Paseo public client), G6a (ACP gateway), G6b (worker) của lane A theo `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md`, test hẹp xanh, commit trên nhánh.
- **Người dùng đã duyệt (09/11/2026):** Q1 = **A gateway ACP đủ 4 backend**; Q2 = mỗi hand một workspace riêng trong cùng project + Subagents track/tab ở cha; Q3 = **việc mới trước đây giao native Sol low chuyển sang hand agent Paseo** (native đang chạy giữ nguyên); Q4 = done giữ hiện, Sol archive đúng hand sau review, gửi tiếp tự mở lại; Q7 = **bật dần**: shell mặc định, opt-in pilot ở repo `claude-plugins` trước, thiếu daemon/capability thì quay về shell.
- **Opus chốt theo khuyến nghị spec (người dùng chưa phản đối):** Q5 = history Paseo + epoch/brief mới, chưa resume context CLI; Q6 = không tự dọn worktree trong MVP.
- **Không làm trong giai đoạn này:** G3 (tích hợp run_cmd/cli), G4 (hh-ps), G5 (policy/docs vận hành), G7, live pilot, release, đăng ký provider trên daemon. Opus giao các giai đoạn sau bằng phiên mới đọc bàn giao của bạn.

## MỤC TIÊU

G0 + G1 + G2 + G6a + G6b của lane A xong ở mức offline (fixture giả), interface đủ rõ để giai đoạn 2 tích hợp G3 mà không phải đổi lại.

## NGỮ CẢNH

- Spec/plan: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md` (đã có trong nhánh base `feat/hand-paseo-a`, commit `cee82cc`). Bàn giao nghiên cứu: `docs/work-in-progress/handoffs/sol-hand-paseo-spec.md` (repo chính).
- Base `feat/hand-paseo-a` = main `fd7d071` (gồm 0.33.1 revive workspace và order repo `codex gpt-6.1-sol low → dsh → claude-v1 → claude-v2`) + spec.
- Mẫu bridge: `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs`, `paseo.py` (chỉ tham chiếu, không sửa `lib/side_session/*`).
- Paseo CLI/server/client 0.15.0 tại `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`; DSH 0.2.1-rc.5.

## Việc cần làm

1. **G0:** cập nhật spec/plan theo quyết định trên (bỏ lane B/C khỏi phần thực thi, giữ một dòng lý do; tick gate G0; câu hỏi mở chỉ giữ cái thật sự còn mở). Viết mục interface trong spec: schema invocation/attempt/epoch, identity, completion/quiescence, usage provenance, ranh giới G1/G2/G6/G3. Chốt language/dependency/license cho gateway (không dựa `node_modules` tình cờ có trên máy của addon). Commit riêng.
2. **G1, G2** song song (khác file) theo plan mục 2, 3. Sau khi interface G1/G2 ổn, **G6a, G6b** song song theo plan mục 7. Owner file đúng như plan; G6b được sửa `runner.py`/backend/ledger nếu cần, không sửa `run_cmd.py`/`cli.py` (để G3).
3. Mỗi gói: brief hand tự chứa, phạm vi file, tối đa 3 ca test như plan. Review diff từng gói (không chỉ đếm test xanh), lỗi giao lại cùng backend một lần.
4. Commit từng gói trên nhánh của phiên. Cuối giai đoạn chạy **một lần** `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py'` và regression hẹp của phần sửa có sẵn (vd `parallel`, `runner`).

## Cách giao hand

Quyết định Q3 áp cho sản phẩm sau khi xong; để xây nó, dùng chế độ hiện hành: order repo đặt codex `gpt-6.1-sol` low đầu → theo Ngoại lệ A dùng subagent native Sol low (`fork_turns=none`, full brief, chép nguyên văn luật dữ liệu). Thiếu native/capability thì `hand-ext run --backend auto`. Tổng hand đang chạy ≤ `ext_hand.max_parallel` (4); cùng file/phụ thuộc tuần tự. Hand không recursion, không gọi hand-ext/side-session, không commit.

## PHẠM VI GHI

- `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `hybrid-hands/docs/2026-11-09-hand-paseo-agent-plan.md`
- Mới: `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/execution_state.py`, `execution_admission.py`, `execution_supervisor.py`, `paseo_transport.py`, `paseo_bridge.mjs`, `paseo_gateway.py` (hoặc `.mjs`), `execution_worker.py`; `hybrid-hands/plugins/hybrid-hands/bin/hand-paseo-acp`
- Sửa: `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/parallel.py` (chỉ G1), `runner.py` và backend/ledger liên quan (chỉ G6b, ghi lý do)
- Test mới: `hybrid-hands/tests/test_hand_paseo_admission.py`, `test_hand_paseo_transport.py`, `test_hand_paseo_gateway.py`, `test_hand_paseo_execution.py`, `hybrid-hands/tests/fixtures/hand_paseo/**`
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` + `.done` theo hợp đồng side-session.

## KHÔNG ĐƯỢC ĐỤNG

- `lib/side_session/*`, `lib/hh_ps/*`, `run_cmd.py`, `cli.py`, `config.py`, `run_registry.py`, `report.py`, skills/templates/README/OVERVIEW (giai đoạn sau). Không bump version, không CHANGELOG.
- Không tạo/send/stop/archive/restore agent, workspace, project Paseo thật; không đăng ký provider, không `paseo plugin install`, không sửa config daemon. Chỉ đọc source + fake client/fixture.
- Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents. Không xoá/di chuyển/dọn `output/llm/`.
- Không commit vào `main`, không merge/push. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Test hẹp từng gói như plan mục 2, 3, 7. Cuối giai đoạn một lần `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_paseo_*.py'` + regression hẹp phần sửa có sẵn. Mức test: tối thiểu.
- Xong khi: 4 gói + G0 commit trên nhánh, test xanh, Sol đã review từng diff; bàn giao ghi interface cho G3, lệnh/kết quả thật, phần chưa kiểm chứng.

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: commit theo gói, file mới/sửa, interface chốt cho G3/G4/G5, kết quả test, rủi ro/câu hỏi cần Opus hoặc người dùng chốt.
