## Tóm tắt
- Kết quả: xong code trong worktree `sol-paseo`, live daemon đạt; chưa ghép vào plugin chính và chưa quan sát trực tiếp UI điện thoại.
- Quyết định: Codex mới do daemon Paseo tạo, tự đăng ký workspace worktree; daemon không kết nối được thì cảnh báo và dùng screen cũ.
- `lib/side_session/{paseo.py,paseo_bridge.mjs,actions.py,attach.py,cli.py,state.py,constants.py}`: thêm transport Paseo và giữ lifecycle/max_parallel/handoff.
- `codex_trust.py`, `tokens.py`: compact native 272000, ghim đúng thread/rollout; giữ cách đếm token.
- Hai skill `side-session`, `paseo`: mô tả đường mới và giới hạn import; không sửa mục 4 Paseo của sol-53 hay statusline sol-54.
- Manifest + `hand_ext/backends/dsh.py`: đồng bộ phiên bản 0.25.0; ba file test và spec mới ghi hợp đồng/kiểm chứng.
- Test hẹp cuối: 3 ca Paseo + 1 ca version đều PASS; nhóm side-session trước đó 82/82 PASS.
- Full suite chạy ĐÚNG MỘT LẦN: 397 test, 1 lỗi version; đã sửa đúng một dòng và test riêng PASS, không chạy lại full.
- Live: agent codex-hand xuất hiện trong `paseo ls`, workspace hợp lệ; gửi tin tiếp nhận phản hồi/file chứng minh, log xem được, watch/handoff nhận `.done`; đã dọn tài nguyên thử.
- Opus cần ghép patch bằng ba chiều; điện thoại mở workspace Sol mới trên daemon đã pair, không cần import. UI điện thoại cần người dùng xác nhận.
- Patch, log và đường ghép ở dưới; đã tạo `sol-paseo.done`. Không commit/push, không restart daemon, không đọc/in secret.

## TÓM TẮT QUYẾT ĐỊNH 1 TRANG

L1 có lựa chọn giải pháp, Sol tự quyết theo giao việc, không chờ duyệt. Spec trước khi giao dsh: [2026-11-07-sol-paseo-spec.md](/Users/anhtp/app/claude-plugins-wt/sol-paseo/docs/work-in-progress/2026-11-07-sol-paseo-spec.md).

| Phương án | Quyết định |
|---|---|
| Codex TUI trong screen rồi import | Bỏ: TUI giữ active writer; import còn lọc cwd của workspace, nên worktree anh em không hiện. |
| Chỉ gọi `paseo run` | CLI đã cài thiếu đường truyền providerOptions cho sandbox/writable roots cần giữ. Không dùng preset bypass quyền. |
| Client đi kèm Paseo tạo workspace + agent | Chọn: daemon giữ writer ngay từ đầu, dùng cùng protocol với CLI/app, truyền được sandbox và cấu hình model/effort. |

`start --provider codex` probe daemon trước khi tạo worktree; khi sẵn sàng tạo workspace source directory chính thức cho đúng cwd, agent `codex-hand`, `CODEX_HOME` từ cấu hình (mặc định `~/.codex-hand`), model/effort từ override hoặc mặc định `gpt-6.1-sol`/`high`. Không kế thừa agent/workspace của phiên gọi. Mất daemon trước create thì cảnh báo + screen; lỗi sau khi đã gửi create không mở writer thứ hai. Kết quả chưa rõ giữ trạng thái `unknown`, giữ tên và slot `max_parallel` tới khi reconcile/stop.

`ls`/watch truy vấn agent; idle vẫn chiếm slot và nhận tin. `.done` giữ nguyên hợp đồng, kết thúc watchdog; không xoá hội thoại. `attach` tên Paseo hướng dẫn app/`paseo attach ID`; session screen cũ giữ hành vi cũ. `stop` interrupt đúng agent rồi dừng watchdog của nó, giữ worktree và hội thoại. Watchdog vẫn là screen riêng; Codex không còn chạy TUI trong screen trên đường Paseo. State cũ mặc định transport screen.

Sandbox giữ `workspace-write`, approval `never`, network bật và danh sách writable roots của helper hiện có. Không mode bypass. ProviderOptions Paseo 0.15.0 không có `model_auto_compact_token_limit`: helper gọi native `codex app-server` chỉ để RPC `config/value/write`, đặt top-level 272000 trong home hand, giữ comment/multiline; không tạo thread/turn. `codex_profile` không rỗng + daemon ready báo chưa hỗ trợ (exit 2), không âm thầm bỏ profile; daemon vắng vẫn chạy screen profile.

Giữ 4.11: chỉ ghim rollout đúng native thread, kiểm cả `session_meta.id` và cwd; thiếu thread thì token chưa biết, không chọn rollout hand theo cwd. Tổng chi = input−cached+output; context = last input+output, không dừng Codex theo tổng chi. 5.2: không sửa sổ `codex_usage`, hand Codex tiếp tục qua hand-ext hiện có; Sol dùng rollout ghim, không ghi chi tiêu trùng. 5.1: không đổi dự phòng 429 của hand-ext auto; agent lỗi không tự mở screen mới.

## File đã đổi và phạm vi

Tất cả đường dưới đây tương đối với `/Users/anhtp/app/claude-plugins-wt/sol-paseo`:

| File | Lý do |
|---|---|
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py` (mới) | Probe, tạo/refresh/interrupt agent, quản lý unknown và target fingerprint an toàn. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs` (mới) | Adapter Node dùng client/daemon-target của CLI đã cài, workspace + agent chính thống. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py` | Route start, max_parallel, live/watch/stop/daystop, `.done`, ghim thread muộn. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/attach.py` | Tra tên Paseo trong repo, hướng dẫn mở agent; giữ menu screen bên ngoài repo. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/cli.py` | Dispatch attach tương thích transport. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/state.py` | Lưu transport, agent/workspace/target/thread; đọc state cũ. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/constants.py` | Hằng transport, timeout, status, native config RPC. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/codex_trust.py` | Helper native ghi riêng compact key; cleanup/reap đúng process con. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/tokens.py` | Matcher rollout chính xác theo thread và cwd, giữ công thức token. |
| `hybrid-hands/plugins/hybrid-hands/skills/side-session/SKILL.md` | Hướng dẫn start/attach/watch/stop/fallback và compact. |
| `hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md` | Transport daemon, workspace, active writer và lọc cwd khi import; không đổi mục 4. |
| `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` | Bump 0.24.0 → 0.25.0 cho tính năng mới. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py` | Chỉ đổi USER_AGENT 0.24.0 → 0.25.0 theo test/quy ước version. |
| `hybrid-hands/tests/test_side_session_paseo.py` (mới) | Đúng 3 test methods cho daemon ready, fallback/lỗi create, lifecycle/done. |
| `hybrid-hands/tests/test_side_session.py` | Fixture screen tắt tự probe daemon thật. |
| `hybrid-hands/tests/test_side_session_codex.py` | Fixture Codex screen không gọi daemon thật. |
| `docs/work-in-progress/2026-11-07-sol-paseo-spec.md` (mới) | Quyết định L1, tiêu chí nhận và nhóm 5 Paseo bổ sung trong phạm vi cho phép. |

Không có AGENTS.md/CLAUDE.md áp dụng tại repo/plugin/ancestor lúc kiểm tra; bản ở dev-workflow không thuộc scope. Đã đọc bàn giao/state của sol-53/54 trước khi làm; tránh hh_ps, mục 4 Paseo và statusline. Plan lịch sử ở `hybrid-hands/docs/...` nằm ngoài phạm vi `docs/work-in-progress/` được giao nên không sửa. Brief chép nguyên văn các luật cấm đọc `.env`/credential, không API key, không commit/push, không xoá `output/llm/`.

## Giao hand, review và dự phòng

Brief và toàn bộ output được giữ dưới `output/llm/` trong worktree, không xoá.

| Run trong `output/llm/hand-ext/` | Kết quả thật / Sol review |
|---|---|
| `20261107-153216-351341-sol-paseo-implement-dsh` | `--backend auto` chọn dsh; timeout 3300.5s, exit 6; runner vẫn áp patch 15 file. Sol đọc diff, tìm 11 vấn đề, giao sửa. |
| `20261107-162758-369930-sol-paseo-review-fix-dsh` | auto/dsh exit 0, 1083.5s, patch 9 file; 82 test side-session PASS. Sol review lại, tìm thêm phân loại lỗi create, hướng dẫn stop và cleanup native child. |
| `20261107-164652-720836-sol-paseo-final-fix-codex-codex` | auto trước đó exit 7, không backend chạy được; dự phòng Codex medium đúng luật. Exit 0, patch 4 file, 3 test PASS. |
| `20261107-164931-061112-sol-paseo-pending-watch-codex` | Codex medium exit 0, patch 2 file; unknown chưa có ID vẫn giữ slot qua watch, 3 test PASS. |
| `20261107-165606-311127-sol-paseo-version-fix-codex-codex` | auto lại exit 7; Codex medium exit 0, chỉ một dòng version, 1 test PASS. Sol review patch và chạy test hẹp cuối trên worktree nguồn. |

Các lần auto exit 7 báo: doctor Codex chưa đạt; không backend nào chạy được (hết hạn mức hoặc chưa đăng nhập). Không suy đoán nguyên nhân riêng của dsh, không tạo key, không gọi API trả phí trực tiếp. Backend Codex dùng tài khoản ChatGPT hand có sẵn.

Sol review mọi patch: bỏ quản lý watchdog PID có race; dùng lại watchdog screen, lưu state trước khi watcher chạy; không resurrect done/stopped; disconnect/idle/unknown không giải phóng slot; generic AGENT_CREATE_FAILED giữ unknown vì có thể mất reply; interrupt thất bại không đánh dấu đã stop; exact rollout thread/cwd; done-first và native thread xuất hiện muộn vẫn pin; loại regex sửa TOML, dùng writer native và thu hồi process con. Sol chỉ sửa trực tiếp câu tài liệu về active writer cho chính xác ngoài spec/brief/bàn giao.

## Kiểm chứng và giới hạn kết luận

1. Test hẹp khi phát triển: file Paseo đúng 3 methods; nhóm side-session 82 tests PASS sau dsh review-fix. Các vòng test hẹp khi có sửa fixture/finding được giữ trong log hand; không chạy full trong hand. Audit lần hand đầu: `output/llm/sol-paseo-hand1-test-audit.json`.
2. Probe native config ở home tạm, không inference: `sol-paseo-config-probe.json`, `sol-paseo-native-helper-probe.json`; cả helper thật giữ comment/chuỗi nhiều dòng, chỉ native config RPC.
3. Full suite DUY NHẤT: `env -u CODEX_SANDBOX PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s hybrid-hands/tests -q` → 397 tests trong 47.57s, exit 1, 396 pass/1 fail. Lỗi duy nhất `test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version`: USER_AGENT còn 0.24.0. Đã giao hand sửa đúng một dòng 0.25.0. Không chạy lại full theo giới hạn người dùng.
4. Trên code cuối sau sửa version: test Paseo mới 3/3 PASS; VersionTest 1/1 PASS. `git diff --check`, `node --check paseo_bridge.mjs` PASS. Log: `output/llm/sol-paseo-full-tests.log`, `sol-paseo-full-tests-result.json`, `sol-paseo-final-narrow-tests.json`.
5. Patch final có cả 4 file mới, 103359 bytes; apply trực tiếp vào main thất bại một hunk actions vì main đã có commit 128102b sửa thông báo stop (4.16). `git apply --3way --check` trên main PASS toàn bộ, không ghi main/index. Log: `sol-paseo-patch-result.json`. Chưa chạy test trên cây sau ghép vì chưa tích hợp.

### Live daemon (không mock)

Ngày 07/11/2026, khoảng 16:51–16:54 +07. Chạy chính binary mới trong worktree, `side-session start --provider codex --worktree --name paseo-smoke-20261107 --prompt-file ...`. Chỉ phiên thử được giao riêng; prompt cấm đọc repo/secret/delegate, yêu cầu ghi handoff + `.done` rồi dừng turn.

- Agent `ae4cfaec-4f80-4077-8fa1-f56f67439bc8`, provider `codex-hand`; workspace `wks_a3de8f3e911d1d6c`, cwd `/Users/anhtp/app/claude-plugins-wt/sol-paseo-wt/paseo-smoke-20261107`.
- `paseo ls` thấy agent model `gpt-6.1-sol`, thinking `high`, status idle. Workspace list thấy worktree tương ứng, `background:false`; đã đăng ký bằng workspace API chính thức, không sửa `~/.paseo/config.json`.
- `paseo logs --filter text` đọc được `PASEO_SMOKE_READY` và `PASEO_CONTROL_OK`. `paseo send ... --behavior steer --no-wait` thực sự gửi tin tiếp; agent ghi `paseo-control-proof.txt` đúng `PASEO_CONTROL_OK`. Lúc inspect trước gửi agent đã idle; không khẳng định đã kiểm nghiệm steer giữa một turn đang chạy.
- `side-session watch --once` báo done; `side-session handoff` đọc đúng khối Tóm tắt; `ls` báo done/handoff yes. State trước cleanup ghi tokens_used 8449; dòng context 20143/272000.
- Native thread `01a1b56b-9e3a-7d31-89a0-b7dde725a70b`, ghim đúng rollout trong `~/.codex-hand/sessions/2026/11/07/`. Chỉ trích xuất metadata turn cần kiểm: hai turn đều model/effort đúng, approval never, workspace-write, network true, writable roots đúng helper cũ.
- Không có Codex TUI screen; chỉ có watchdog screen riêng. Cleanup bằng side-session stop, Paseo delete đúng agent, archive đúng workspace; bỏ file control rồi remove đúng worktree/branch thử. Tất cả 5 assert cleanup PASS. Lưu bản sao handoff/done/control/log/state trong `output/llm/sol-paseo-live/`; không xoá output hay native rollout.

Chứng cứ: `output/llm/sol-paseo-live/{agents.json,workspaces.json,logs.json,state.json,turn-context.json,cleanup.json,paseo-control-proof.txt}`. Không có quyền quan sát màn hình điện thoại qua tool hiện tại: đã chứng minh agent/workspace và gửi/nhận/log qua daemon mà app sử dụng, chưa tuyên bố đã tap/nhìn UI điện thoại.

### Môi trường và thay đổi runtime

Paseo local target discovery trong sandbox lỗi `uv_uptime EPERM` trước kết nối. Live dùng endpoint đã biết `PASEO_HOST=127.0.0.1:6767`, bỏ env PASEO_HOME; CLI kiểm bằng `--host 127.0.0.1:6767`. Đây là workaround sandbox kiểm chứng, không hardcode host vào implementation. Không restart daemon. Một lệnh ps chẩn đoán bị sandbox từ chối; thiết kế cuối không phụ thuộc ps. py_compile ban đầu bị từ chối cache ngoài vùng ghi nên hand dùng compile() và PYTHONDONTWRITEBYTECODE.

Live helper đã đặt `model_auto_compact_token_limit=272000` trong config.toml của `~/.codex-hand` bằng native RPC chính thức; đây là thay đổi runtime có chủ đích để Paseo giữ compact như screen. Không đọc/in config hay auth, không thay tài khoản. Probe home tạm đã dọn. Tài liệu RPC tham chiếu: [Codex App Server](https://learn.chatgpt.com/docs/app-server). Adapter được kiểm với `@getpaseo/cli 0.15.0`; do dùng module client nội bộ của package, bản Paseo nâng cấp có thể cần chỉnh adapter. Thiếu client module thì cảnh báo và fallback screen trước create.

## Ghép, dùng trên điện thoại và việc còn mở

- Code nằm ở worktree này, chưa tích hợp main/cached plugin đang dùng; không commit/push. Base worktree `dff3b71bf5f6df8baba8e8b04837a984102283c5`.
- Patch đầy đủ: [sol-paseo-final.patch](/Users/anhtp/app/claude-plugins-wt/sol-paseo/output/llm/sol-paseo-final.patch). Opus có thể ghép ba chiều trên main sau kiểm trạng thái phiên khác: `git apply --3way /Users/anhtp/app/claude-plugins-wt/sol-paseo/output/llm/sol-paseo-final.patch`. Check đã PASS, không phải yêu cầu người dùng duyệt thêm. Giữ thay đổi 4.16 của main. Patch không đụng mục 4 Paseo/sol-53 hoặc statusline/sol-54.
- Sau tích hợp, từ điện thoại đã pair daemon: mở workspace mang tên worktree Sol mới, chọn agent theo tên phiên, đọc hội thoại/gửi tin như agent Paseo khác. Nếu danh sách cũ chưa cập nhật thì refresh workspace. Không cần import thread. Phiên TUI cũ đang chạy không được chuyển writer hồi tố; không stop nó trong task này.
- Cần người dùng/Opus xác nhận màn hình điện thoại thấy workspace/agent mới sau tích hợp. Nếu chính máy chạy production bị lỗi local target discovery như sandbox kiểm chứng, cấu hình endpoint PASEO_HOST chính thống của môi trường đó; không đổi auth/secret.
- `codex_profile` khác rỗng chưa hỗ trợ khi daemon sẵn sàng; lỗi create chưa biết ID cần kiểm/dừng agent trong app trước, rồi `side-session stop <name>` giải phóng slot. Không tự retry create để tránh trùng writer.
- Full suite không được báo all-green: có một lỗi version đã sửa và test riêng pass; tuân đúng một lần full. Chưa có test trên cây sau tích hợp main. Không có blocker code/live còn mở trong phạm vi này.
