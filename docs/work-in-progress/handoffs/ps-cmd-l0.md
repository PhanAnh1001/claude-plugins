## Tóm tắt
- Kết quả: **xong một phần, bị chặn phát hành bởi managed hand unresolved**; không tạo writer trùng.
- Ví dụ sau phát hành: `/hybrid-hands:parallel-subagents on|off` trong Claude Code; `hand-ext parallel-subagents on|off` trong terminal/Codex; bỏ đối số chỉ xem.
- Bản sửa **0.37.2 chỉ ở worktree hand** và [patch đã review](ps-cmd-l0-reviewed.patch); repo gốc/cài đặt vẫn **0.37.1**.
- `lib/hand_ext/cli.py`: tên chính đầy đủ, giữ `parallel` alias cũ chung parser/handler và flags.
- `commands/parallel-subagents.md`: vỏ Bash gọi CLI trong cwd hiện tại, in kết quả, nhắc mở phiên mới khi đổi.
- `test_hand_parallel_cmd.py`: giữ 3 test, đổi helper và thêm assert alias; `parallel_cmd.py` không cần đổi.
- `AGENTS.md`, `README.md`: đổi tên và hướng dẫn hai lối vào; `CHANGELOG.md`, `plugin.json`: chuẩn bị release 0.37.2.
- Sol chạy lại `test_hand_parallel_cmd.py`: **3/3 OK**; `test_policy_mode.py`: **3/3 OK**; không full suite.
- JSON hợp lệ; `claude plugin validate` plugin, marketplace, commands: **exit 0**; diff/check và patch apply-check đạt.
- Hand Codex backend exit **0**, nhưng containment `inventory_complete=false`; `managed recover` dry-run **exit 1 / StateConflict**.
- Wrapper `hand-ext run --backend auto` chờ unresolved đã được dừng đúng PID, **exit 143**; giữ reservation/state/artifacts.
- Commit/merge mới: **chưa có**; `main`/`origin/main` vẫn `c68f0e9ed376ec3a2ea021589baf948f80f210d7`.
- Repo đã cập nhật runtime: **chưa có**; v1/v2 đều user scope 0.37.1. Chưa kiểm slash thực tế; cần phát hành/cập nhật rồi reload.
- Opus cần giải quyết settlement exact invocation bên dưới trước áp patch, commit/push/merge và cập nhật v1/v2.

## Bản sửa đã review

Worktree được giữ nguyên:
`/Users/anhtp/.hybrid-hands/worktrees/claude-plugins-20261110-090852-884842-ps-cmd-l0-codex`.

Patch bảy file: `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/ps-cmd-l0-reviewed.patch`.
`git apply --check` tại repo gốc exit 0; **chưa áp patch**. Nhánh chuẩn bị `feat/parallel-subagents-command-0372` vẫn ở base, chưa có commit. Repo gốc đã trở về `main`, không có thay đổi tracked. Các file WIP untracked cũ được giữ.

Review của Sol: phạm vi đúng; argparse `aliases=["parallel"]` dùng chung handler, help ghi rõ alias cũ; không thay logic config. Slash command chỉ gọi `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" parallel-subagents $ARGUMENTS`, không đối số chỉ xem, không tự bật, không ghi JSON riêng. Không đổi mode repo thật. Không sửa `parallel-subagents/`, `statusline/`, settings, credential hoặc sổ cài đặt bằng tay. Không thêm test cho text command.

## Kiểm chứng thật do Sol chạy

Cwd cho các lệnh kiểm bản sửa là worktree hand ở trên:

| Lệnh | Kết quả |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s hybrid-hands/tests -p test_hand_parallel_cmd.py` | exit 0, 3 tests OK |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s hybrid-hands/tests -p test_policy_mode.py` | exit 0, 3 tests OK; warning global true bị bỏ qua từ fixture tạm, đúng contract |
| `python3 -m json.tool hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` | exit 0 |
| `claude plugin validate hybrid-hands/plugins/hybrid-hands` | exit 0, Validation passed |
| `claude plugin validate hybrid-hands` | exit 0, Validation passed |
| `claude plugin validate hybrid-hands/plugins/hybrid-hands/commands` | exit 0, Validation passed; command mới được kiểm qua validator components |
| `git diff --check` | exit 0 |
| `git apply --check /Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/ps-cmd-l0-reviewed.patch` tại repo gốc | exit 0, không ghi code |

Validator plugin nêu thiếu LICENSE và icon cho catalog directory submission, đồng thời ghi rõ không ảnh hưởng kết quả validate mặc định. Không mở rộng scope để sửa metadata cũ này.
Không chạy full suite. Chưa gọi slash runtime và chưa kiểm cache 0.37.2 vì chưa phát hành.

## Lỗi hand-ext và rào chặn

Preflight `hand-ext pick --json` chọn `codex`, model `gpt-6.1-sol`, effort `low`, account `gpt`, native eligible. Repo hiệu lực order `codex → dsh → claude-v1 → claude-v2`, mode `auto`, max_parallel 4; không thay cấu hình.

Đã giao đúng đường wrapper:

```sh
/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --brief /Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/ps-cmd-l0-hand-brief.md --cwd /Users/anhtp/app/claude-plugins --label ps-cmd-l0
```

Lần này dispatch managed thành công, **không gặp PARENT_REQUIRED**. Không thử shell vì đã có invocation/writer managed.

- Key: `15ad6c74-c7b1-4ded-b24e-cfa17e253238:08d403f7-cbe7-4744-bbe7-5454f5b1cf2f:1`.
- Run: `20261110-090852-884842-ps-cmd-l0-codex`.
- Exact child: `af4cbef3-593a-4331-a830-bcd2e8658413`; workspace: `wks_21bf4560c531c09d`.
- Parent canonical: `a9d38c00-5fbd-4be4-beef-cda213d67f41`; parent Paseo: `4dd2427c-1914-4746-9a11-9ae8ab392918`.
- State: `unresolved`; pending backend status `ok`, backend_exit_code `0`; root PID `37664` đã reaped/vắng, retained inventory PIDs đều vắng tại kiểm tra.
- Quiescence chưa confirmed; `inventory_complete=false`; first fatal `{stage: marker, error: unavailable, pid: 42185, start: "1794276606:987009"}`. Worker owner có `owner_done`; reservation vẫn giữ.
- Worker ACP owner PID `37424` là process do daemon quản lý; không tự signal hay sửa state để vượt guard. Giữ exact child/workspace, không archive khi chưa settlement.

Recovery chính thức đã chạy, không apply:

```sh
hand-ext managed recover --cwd /Users/anhtp/app/claude-plugins --key 15ad6c74-c7b1-4ded-b24e-cfa17e253238:08d403f7-cbe7-4744-bbe7-5454f5b1cf2f:1
```

Kết quả **exit 1**, `{"ok": false, "code": "StateConflict"}`. Recovery hiện có chỉ hỗ trợ post-hoc cancelled với inventory đầy đủ hoặc pre-dispatch proof; trường hợp backend ok nhưng inventory không đầy đủ này không thoả. Không dùng legacy attest cho record hiện đại, không sửa state/reservation, không tạo duplicate shell/native writer.

Đã kết thúc đúng CLI đang chờ: kiểm argv exact của PID `37011` trước SIGTERM; tool trả **exit 143**. Sau đó PID `37011` và backend PID `37664` đều vắng. Không có tiến trình chờ local do Sol tạo còn chạy.

Report hand:
`/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261110-090852-884842-ps-cmd-l0-codex/a2217bc003d0a4dd10f785373f20e03206e0416144aa886c4fd250e2660e2668/report.md`.

State metadata:
`/Users/anhtp/.hybrid-hands/executions/a2217bc003d0a4dd10f785373f20e03206e0416144aa886c4fd250e2660e2668.json`.

AGENTS.md yêu cầu: “Unknown sau spawn phải reconcile/wait, không tạo duplicate writer.” Brief cũng giữ reservation khi writer chưa xác minh settled. Vì vậy không áp patch hoặc phát hành khi lỗi này còn tồn tại; đây là rào chặn lifecycle thực tế, ngoài phạm vi sửa bảy file của L0 này.

## Cài đặt/runtime và công việc còn lại

Qua `claude plugin list --json` và `claude plugin marketplace list --json` chính thức:

| Account | Scope/version hiện tại | Đường dẫn cache | Source |
|---|---|---|---|
| v1 (`~/.claude`) | user / 0.37.1 | `/Users/anhtp/.claude/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.1` | `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands` |
| v2 (`~/.claude-hand`) | user / 0.37.1 | `/Users/anhtp/.claude-hand/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.1` | cùng source |

Đã dùng official list ở 14 checkout cấp app (v1): ai-comic-video, ai-luxian, ai-practice-english, claude-plugins, codex-plugins, common-modules, hrm-open-sources, live-tiktok-games, live-tiktok-games-preview-publish, skill-key, slt-ocr-pro, tcp-assistant, tcp-assistant-main, team-ai-gitops. Cùng bản user scope 0.37.1, enabled true; giữ nguyên projectEnabled false từ output, không diễn giải lại hay tự enable. V2 được kiểm tại repo hiện tại và chỉ có một bản user scope hybrid-hands.

**Không repo nào được cập nhật runtime trong lượt này.** Không sửa trực tiếp settings hoặc installed_plugins.json; không chạy on/off trên repo thật.

Sau khi lifecycle được xử lý an toàn: áp patch đã review vào nhánh, commit/push nhánh, merge `main` và push `main` theo brief. Sau đó chạy công cụ chính thức cho cả v1/v2: `claude plugin marketplace update hybrid-hands-local`, `claude plugin update hybrid-hands@hybrid-hands-local --scope user` (v2 dùng `CLAUDE_CONFIG_DIR=/Users/anhtp/.claude-hand`). Đối chiếu list/details, version/path và command mới trong cache; rà mọi scope project/local nếu official list phát hiện thêm. Không enable repo mới.

Chưa có SHA commit/merge mới để bàn giao; base/main/origin-main là `c68f0e9ed376ec3a2ea021589baf948f80f210d7`. Cần reload/mở phiên Claude Code mới sau khi cài đặt 0.37.2 để kiểm slash không đối số trước; chỉ thử on/off trong thư mục tạm hoặc khi user chốt riêng cho repo đó.
