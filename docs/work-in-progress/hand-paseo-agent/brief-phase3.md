# Brief giai đoạn 3: G4 hh-ps + G5 policy/lệnh vận hành + G7 tích hợp offline (lane A)

## Tóm tắt

- **Mục tiêu:** hand agent Paseo hiện đúng trong hh-ps/cây phiên (không đếm trùng), Sol có lệnh CLI để review/archive/follow-up hand managed, policy/template chuyển việc native mới sang managed (Q3), tài liệu vận hành và tích hợp offline xanh; sau đó full suite một lần.
- **Quyết định đã duyệt:** lane A, Q2–Q7 như giai đoạn 1–2. Spec/plan trên nhánh: `hybrid-hands/docs/2026-11-09-hand-paseo-agent-spec.md`, `...-plan.md` (mục G4, G5, G7).
- **Interface đầu vào:** mục "Interface cho G4/G5" trong `docs/work-in-progress/handoffs/hpa-p2.md` (repo chính `/Users/anhtp/app/claude-plugins`). Base `feat/hand-paseo-a` = `f73f09a` (đã gồm giai đoạn 1 + 2).
- **Thêm một câu hỏi phải trả lời bằng source (không chạy thật):** daemon Paseo 0.15.0 có nạp lại `agents.providers` trong `<home>/config.json` khi đang chạy không (watch/reload/RPC), hay bắt buộc restart daemon. Ghi file:line. Phiên Opus đang chạy dưới daemon Paseo nên restart là việc rủi ro; Opus cần câu trả lời này để chạy pilot live.

## MỤC TIÊU

G4 + G5 + G7 xong offline, commit trên nhánh, full suite xanh một lần; bàn giao đủ để Opus chạy live pilot ở repo `claude-plugins` rồi release.

## Việc cần làm

1. **G4 hh-ps** (theo plan mục G4, mapping authoritative trong hpa-p2 "Interface cho G4/G5"): `lib/hh_ps/{models.py, registry_source.py, native_source.py, tree.py, usage_enrichment.py}`. Hand managed hiện là một hand trong cây dưới parent canonical, đủ backend/model/effort/status/exit_code/USD~/ended/elapsed theo contract 0.30.0 trong AGENTS.md; khử trùng giữa ExecutionRecord, RunRegistry meta và rollout native (một managed execution = một dòng, không cộng token hai lần); epoch follow-up là dòng/epoch riêng không đè epoch trước. Test mới `hybrid-hands/tests/test_hh_ps_paseo_hand.py`.
2. **G5 lệnh vận hành:** thêm lệnh CLI trên `PaseoController` có sẵn, ví dụ `hand-ext managed ls|review-approve|archive|followup --key <execution_key> [--brief F]` (tên tuỳ Sol, ghi trong bàn giao). Archive đúng child, follow-up mở epoch mới (Q4, Q5). Test hẹp trong `test_hand_paseo_controller.py` hoặc file test CLI mới.
3. **G5 policy/docs:** `skills/ext-hand/SKILL.md`, `skills/paseo/SKILL.md`, `templates/side-session-prompt-codex.md` (Q3: khi `ext_hand.mode` là `auto`/`paseo-required` và provider sẵn sàng, việc mới trước đây giao native Sol low thì giao `hand-ext run --mode paseo-required`; native đang chạy giữ nguyên; thiếu daemon/capability thì về đường cũ), `hybrid-hands/README.md`, `hybrid-hands/paseo-hh-tree/OVERVIEW.md`. Không sửa AGENTS.md (Opus làm).
4. **G7:** tích hợp offline end-to-end bằng fake transport/daemon (dispatch → worker → completion → hh-ps thấy một dòng → archive → follow-up epoch 2). Theo plan mục G7.
5. Trả lời câu hỏi reload provider ở phần Tóm tắt.
6. Commit từng gói trên nhánh phiên. Cuối giai đoạn chạy **một lần** full suite.

## Cách giao hand

Order repo: codex `gpt-6.1-sol` low đầu → theo Ngoại lệ A dùng subagent native Sol low (`fork_turns=none`, full brief, chép nguyên văn luật dữ liệu); thiếu native thì `hand-ext run --backend auto`. Tổng hand ≤ 4. G4 (hh_ps) và G5 docs khác file, chạy song song được; lệnh CLI G5 sửa `cli.py`, tuần tự với chỗ khác chạm `cli.py`. G7 sau cùng. Hand không recursion, không commit.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/*.py`, `lib/hand_ext/{cli,paseo_controller,paseo_completion,execution_state,run_registry,report}.py` (chỉ phần cần cho G4/G5/G7)
- `hybrid-hands/plugins/hybrid-hands/skills/{ext-hand,paseo}/SKILL.md`, `templates/side-session-prompt-codex.md`, `hybrid-hands/README.md`, `hybrid-hands/paseo-hh-tree/OVERVIEW.md`
- Test: `hybrid-hands/tests/test_hh_ps_paseo_hand.py`, `test_hand_paseo_*.py`, test hh_ps/hand-ext có sẵn bị ảnh hưởng, fixture `hybrid-hands/tests/fixtures/hand_paseo/**`
- Spec/plan: tick G4/G5/G7, cập nhật interface nếu đổi.
- Bàn giao: `docs/work-in-progress/handoffs/<tên phiên>.md` + `.done`.

## KHÔNG ĐƯỢC ĐỤNG

- `lib/side_session/*`, `paseo-hh-tree/src/**` (panel; chỉ sửa OVERVIEW.md), statusline, AGENTS.md. Không bump version/CHANGELOG (Opus làm ở release).
- Không chạy `hand-ext provider setup --apply` thật, không sửa config daemon Paseo thật, không restart daemon, không tạo/send/stop/archive agent/workspace/project thật, không `paseo plugin install`.
- Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings; không bật parallel-subagents. Không xoá/di chuyển/dọn `output/llm/`.
- Không commit vào `main`, không merge/push. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo.

## LUẬT BẮT BUỘC (chép nguyên văn)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Test hẹp từng file trong lúc làm. Ca test tối thiểu: (1) managed hand hiện đúng một dòng dưới parent, không cộng token trùng; (2) archive/follow-up qua CLI tạo epoch 2 không đè epoch 1; (3) G7 end-to-end fake. Mức test: tối thiểu.
- Cuối giai đoạn chạy **đúng một lần** full suite: `python3 -m unittest discover -s tests -p 'test_*.py'` với cwd `hybrid-hands` của worktree. Ghi số test và kết quả thật; test đỏ có sẵn từ trước (nếu có) thì đối chiếu với base `f73f09a` và ghi rõ.
- Xong khi: G4/G5/G7 commit trên nhánh, full suite xanh, Sol review từng diff.

## TRẢ VỀ

Bàn giao mở đầu bằng tóm tắt: commits, file, kết quả full suite, tên và cú pháp lệnh CLI managed, câu trả lời reload provider (file:line, có cần restart không), các bước live pilot Opus phải chạy theo thứ tự, rủi ro còn lại.
