## Tóm tắt
- Kết quả: xong một phần; phương án A hoạt động thật, còn điều kiện full test xanh và cập nhật bản cài.
- Quyết định: dùng subagent Codex native; không triển khai B vì CLI 0.166.0/Paseo 0.15.0 đã trả đúng parent và hội thoại.
- Model/effort thực: gpt-6.1-sol/low, fork_turns=none, approval never; hai native hand đã completed.
- File đổi: 14 file gồm bridge/Python API, 3 test mới, prompt/hooks, skills/README/AGENTS, manifest/CHANGELOG và User-Agent dsh.
- Full chạy đúng một lần: 414 test/47.002s, exit 1 với 3 lỗi; chưa có kết quả full xanh.
- Hai lỗi version/policy đã sửa; các test liên quan đạt. Test PID chạy riêng đạt, nghi race có sẵn; chưa sửa cc-switch.
- Kiểm chứng thật: native hand đọc README, timeline có tool event và trả lời 3 dòng dưới đúng Sol.
- 8 lượt hand-ext --backend auto hoàn tất exit 0; Sol review toàn bộ diff; không commit/push, không sửa config cấm.
- Bản cài: 9 record user/project/local vẫn ghi 0.26.0, readFromFolder hiện 0.27.0; chưa chạy update vì thiếu full xanh.
- Điện thoại: mở phiên Sol, bấm tab Native readme hand; chưa kiểm thao tác trực tiếp trên điện thoại.
- Còn mở: xử lý/xác nhận race PID, cho phép lượt full tiếp theo, rồi cập nhật mọi scope bằng CLI.
- Bằng chứng: [runtime](../../../output/llm/sol-hand-paseo/runtime-evidence.json), [full test](../../../output/llm/sol-hand-paseo/full-suite-first.txt), [diff riêng lượt này](../../../output/llm/sol-hand-paseo/task-changes.patch).

## Quyết định giải pháp (≤1 trang)

Chọn **A**. Tài liệu chính thức [Subagents của OpenAI](https://learn.chatgpt.com/docs/agent-configuration/subagents) là điểm đối chiếu; kết luận dựa trên CLI và runtime cài sẵn. `codex --version` trả `codex-cli 0.166.0`; `codex features list` có `multi_agent stable true`; `paseo --version` trả `0.15.0`. Provider Codex trong Paseo nhận `collabAgentToolCall`/`subAgentActivity`, phát metadata/timeline native child và có API `listProviderSubagents`/`fetchProviderSubagentTimeline`.

Trong chính Sol hiện tại, hai lần spawn với `model=gpt-6.1-sol`, `reasoning_effort=low`, `fork_turns=none` thành công. Paseo trả cả hai child `completed` dưới parent `848562d1-f371-4b74-9544-a6b33004791c`; bridge đọc được câu trả lời và lệnh đọc README. Metadata rollout của đúng các probe xác nhận model/effort, approval `never`, sandbox `danger-full-access`. Không đọc/in auth hoặc credential.

Prompt/policy mới ưu tiên native chỉ cho Sol Codex trên Paseo khi backend thực theo `ext_hand.order` là Codex/model/effort trên và schema tool hỗ trợ override riêng. Thiếu capability trước spawn thì dùng `hand-ext --backend auto` như cũ; unknown sau spawn không tạo writer trùng. Tổng native + hand-ext do Sol điều phối ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Không bật parallel-subagents hay sửa config. Native completed giữ lịch sử dưới Sol; B tạo agent ngang hàng/archive không cần triển khai.

Native dùng báo cáo/usage native/Paseo, không sinh run/meta/report/ledger hand-ext. Slot kernel hand-ext không đếm native. Đây là khác biệt có chủ ý, được ghi rõ trong template và skills.

## File thay đổi và review của Sol

Đã đối chiếu từng file với snapshot trước lượt này, giữ các thay đổi chưa commit có sẵn. Patch riêng không chứa các thay đổi của lượt usage panel trước.

| File | Lý do |
|---|---|
| `AGENTS.md` | Ghi ngoại lệ native cho Sol, cap chung, fallback và giới hạn dữ liệu. |
| `hybrid-hands/README.md` | Hướng dẫn native tab và liên kết policy/kiểm chứng bridge. |
| `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` | Bump minor 0.26.0 → 0.27.0. |
| `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` | Ghi hành vi 0.27.0. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py` | Thêm wrappers `subagents` và `subagent_timeline`. |
| `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo_bridge.mjs` | Đọc child/timeline, kiểm đúng parent và endpoint, lỗi chỉ trả mã an toàn. |
| `hybrid-hands/plugins/hybrid-hands/templates/side-session-prompt-codex.md` | Giao native đúng model/effort, brief độc lập, lifecycle và chống writer trùng. |
| `hybrid-hands/plugins/hybrid-hands/scripts/inject-policy.sh` | Ngoại lệ ngắn, giữ luật dữ liệu; output cuối 1498 ký tự, dưới 1800. |
| `hybrid-hands/plugins/hybrid-hands/scripts/session-start-policy.sh` | Đồng bộ ngoại lệ cho Sol, giữ mặc định Opus/Claude/dsh. |
| `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md` | Policy native đầy đủ và phân biệt báo cáo/usage. |
| `hybrid-hands/plugins/hybrid-hands/skills/side-session/SKILL.md` | Hướng dẫn native và bàn giao Sol/brain. |
| `hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md` | Tab trên điện thoại và JSON bridge chỉ đọc. |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py` | Chỉ đổi User-Agent sang 0.27.0 để khớp manifest; giữ mọi logic/thay đổi có sẵn. |
| `hybrid-hands/tests/test_side_session_native.py` | Đúng 3 ca mới chạy bridge Node thật với client giả. |

Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, settings/credential/installed_plugins.json bằng tay, `statusline/`, hoặc code `cc_switch`. Không xoá/di chuyển/dọn dữ liệu có sẵn trong `output/llm/`.

## Kiểm chứng thực tế

Các lệnh đọc version và danh sách:

```text
codex --version
codex-cli 0.166.0
codex features list
multi_agent    stable    true
paseo --version
0.15.0
paseo ls -a -g --json
[lọc đúng id parent] id=848562d1-f371-4b74-9544-a6b33004791c
provider=codex-hand/gpt-6.1-sol status=running
```

Hai lệnh tool native dùng `fork_turns=none`, model/effort nêu trên, task `native_paseo_probe` và `native_readme_hand`. Probe thứ hai là brief chỉ đọc README, đủ luật dữ liệu, không ghi file/recursion.

Sau khi code bridge được áp, Sol gọi các wrapper thật:

```python
ready = paseo.ready()
children = paseo.subagents(parent_id, ready["targetKey"])
timeline = paseo.subagent_timeline(parent_id, child_id, ready["targetKey"])
```

Output rút gọn, chỉ dữ liệu của probe tự tạo:

```json
{
  "parentAgentId": "848562d1-f371-4b74-9544-a6b33004791c",
  "children": [
    {"id": "01a1b674-e6a3-7d82-b3f4-ca8ad23f0309", "description": "native_paseo_probe", "status": "completed", "model": "gpt-6.1-sol", "effort": "low", "timeline_rows": 1},
    {"id": "01a1b678-3b2c-7b31-8dc8-628c1f62898f", "description": "native_readme_hand", "status": "completed", "model": "gpt-6.1-sol", "effort": "low", "timeline_rows": 3, "tool_events": 1}
  ]
}
```

Câu trả lời cuối đọc được qua timeline:

```text
Hybrid-hands điều phối ba tầng Opus, Sol và hand để chia việc và tiết kiệm hạn mức.
Sol giao code, test, tài liệu cho hand rồi review; các việc cùng file phải tuần tự.
Plugin có công cụ quản lý phiên, theo dõi usage và quy định bảo vệ dữ liệu, không dùng API key.
```

Usage lấy từ metadata/token_count của đúng hai probe: lượt đầu input 16791, cached 12032, output 23; lượt README input 36117, cached 33408, output 150. Không suy quota từ token. Runtime evidence lưu riêng, không chứa auth/credential hay hội thoại phiên khác.

Bridge chứng minh parent/history đã sẵn sàng cho UI. Chưa trực tiếp bấm app điện thoại. Native child completed giữ lịch sử; không archive/dừng agent Sol hay phiên khác. Các ca daemon-ready/fallback/archive của B không triển khai do A đạt; fallback hand-ext hiện tại không được biến thành agent Paseo.

## Test và điều kiện chưa đạt

Thêm đúng **3 ca mới**: list/timeline thành công; child sai/daemon lỗi/ID rỗng trả mã an toàn; endpoint khác bị chặn trước khi đọc. Không thêm test text tài liệu.

| Lệnh | Kết quả thật |
|---|---|
| `python3 -m unittest discover -s hybrid-hands/tests -p test_side_session_native.py -q` | 3 test, OK. |
| `python3 -m unittest discover -s hybrid-hands/tests -p test_side_session_paseo.py -q` | 4 test, OK; lifecycle/fallback cũ không đổi. |
| `python3 -m unittest discover -s hybrid-hands/tests -p test_side_session_codex.py -q` | 13 test, OK. |
| `python3 -m unittest discover -s hybrid-hands/tests -p test_policy_brain_context.py -q` | 3 test, OK sau rút gọn hook. |
| `python3 -m unittest discover -s hybrid-hands/tests -q` | **Chạy đúng một lần: 414 test/47.002s, FAILED (3), exit 1.** |
| `PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_dsh.VersionTest -q` | Sau sửa User-Agent: 1 test, OK, hand chạy. |
| `PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_isolation.PolicyTextTest test_policy_brain_context -q` | Sau bổ sung cụm luật dữ liệu: 4 test, OK, hand chạy. |
| `PYTHONPATH=hybrid-hands/tests python3 -m unittest test_cc_switch_self.CcSwitchSelfTest.test_worker_sigterms_tui_then_reloads_paseo -q` | Chạy riêng đúng một lần: 1 test/1.849s, OK, hand điều tra chạy. |
| `bash -n` hai hook; `node --check` bridge; `git diff --check` phạm vi | Đạt; manifest JSON và 6 link mới/2 JSON mẫu cũng đạt trong hand tài liệu. |

Full test đầu phát hiện hai lỗi task đã sửa (User-Agent/version và cụm luật dữ liệu) cùng một lỗi PID ngoài phần native. Không chạy lại full để giữ giới hạn đúng một lần của brief, vì vậy **không claim full suite cuối đã xanh**.

Điều tra PID chỉ đọc: `cc_switch/proc.py:38` có khoảng đua giữa `pid_alive` và `ps`; khi process biến mất giữa hai lệnh, kết quả có thể còn được coi là sống. `self_cmd.py:201` chấp nhận zombie đã thoát, sau đó `paseo_cmd.py:138` kiểm PID lần nữa, trong khi test cha reap fixture tại `test_cc_switch_self.py:223`. Đây là giả thuyết phù hợp triệu chứng, chưa tái hiện có kiểm soát; test chạy riêng đạt. Không sửa code/test cc-switch hay mở rộng phạm vi.

## Giao hand và hoàn tất tiến trình

Mọi code/test/tài liệu triển khai giao qua:

```text
/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --brief <brief> --label <label> --cwd /Users/anhtp/app/claude-plugins --timeout-min 30
```

Theo cấu hình hiện có, 8 lượt đều chọn Codex `gpt-6.1-sol` low, exit 0, worktree được dọn; tối đa 3 hand-ext song song, hoặc 3 hand-ext + 1 probe native (tổng 4) trong Sol này. Các sửa cùng file chạy tuần tự. Mọi diff đã được Sol review, không giao hand review hand khác.

Report được giữ nguyên tại `output/llm/hand-ext/`:

- `20261107-214407-310298-sol-hand-paseo-prompt-codex/report.md`
- `20261107-214407-317598-sol-hand-paseo-bridge-codex/report.md`
- `20261107-214407-310292-sol-hand-paseo-docs-codex/report.md`
- `20261107-214653-545450-sol-hand-paseo-policy-fix-codex/report.md`
- `20261107-214653-545453-sol-hand-paseo-docs-fix-codex/report.md`
- `20261107-215209-398623-sol-hand-paseo-release-fix-codex/report.md`
- `20261107-215209-398623-sol-hand-paseo-data-rule-fix-codex/report.md`
- `20261107-215209-398628-sol-hand-paseo-pid-investigate-codex/report.md`

Ba lần khởi động hand sửa lỗi ban đầu thoát 2 vì brief chưa được tạo sau lỗi encoding ở lệnh ghi brief; tạo lại brief rồi chạy thành công. Không dùng lỗi này để Sol tự code. Không có exit 7/8, không chạy doctor hoặc đổi backend. Các tiến trình hand-ext/full test do lượt này tạo đã thoát; hai native probe completed. Không dừng/gửi tin các phiên phụ khác.

## Cài đặt và phần còn mở

`claude plugin list --json` lọc riêng hybrid-hands: 9 record ở scope user/project/local, tất cả version đăng ký `0.26.0`, `readFromFolder` trỏ source và `folderVersion=0.27.0`. Có 5 record đường dẫn worktree. Metadata trước/sau lưu tại [installed-before](../../../output/llm/sol-hand-paseo/installed-before.json) và [installed-not-updated](../../../output/llm/sol-hand-paseo/installed-not-updated.json).

**Chưa gọi `claude plugin update`/install**, vì brief đặt cập nhật sau test xanh và chưa có kết quả full xanh. Không kết luận CLI không cập nhật được worktree vì chưa thử. Không chỉnh registry/settings bằng tay.

Việc còn lại cho gói tiếp theo: xác nhận/xử lý race PID nếu cần, cho phép một lượt full tiếp theo để xác nhận trạng thái sau hai sửa lỗi; khi xanh, cập nhật bằng CLI cho mọi scope và kiểm lại 9 record, ghi rõ các worktree không cập nhật được nếu có.

Người dùng trên điện thoại có thể mở Sol hiện tại và bấm **Native readme hand** để kiểm tra hội thoại probe. Để prompt/policy mới áp dụng ổn định cho lượt Sol mới, hoàn tất bước cập nhật plugin rồi mở phiên mới; không cần ghép điện thoại hay sửa cấu hình kết nối lại.
