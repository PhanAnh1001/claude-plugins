---
status: in-progress
lane: L2
approved: 2026-11-05 (người dùng: "làm hết, tận dụng dsh")
---

# side-session v2: một cách mở phiên phụ, có Chrome, nối cây, chạy được DeepSeek

## Tóm tắt

- **Mục đích:** gom mọi cách mở phiên phụ về `side-session` (bỏ `launch.sh` riêng của repo live-tiktok-games), để phiên phụ:
  - mở Chrome khi cần (chỉ provider `claude`);
  - nhớ phiên brain đã mở nó, nên cây `hh-ps`, dải terminal và plugin Paseo vẽ phiên phụ làm con của phiên chính;
  - chạy được bằng hand ngoài DeepSeek (`dsh`, `opencode`) qua `hand-ext run`, tận dụng gói thứ hai.
- **Quyết định chính:**
  1. `side-session start` thêm `--chrome`/`--no-chrome`, `--budget-exempt`, `--force-budget`, provider `dsh` và `opencode`; ghi `parent_session` = `CLAUDE_CODE_SESSION_ID` của brain.
  2. Phiên phụ ngoài = `hand-ext run --backend <dsh|opencode>` chạy trong `screen`, nhãn `side:<tên>`; bắt buộc `--worktree`; cấm `--chrome`; prompt phải có mục `LUẬT BẮT BUỘC`.
  3. Trần ngày là lệnh cấu hình `budget_check_cmd` (repo live-tiktok-games trỏ `day-budget.sh status`).
  4. `hh-ps --json` giữ danh sách `sessions` phẳng, mỗi phiên thêm `parent_session`, `side_name`, `provider`; phiên phụ ngoài hiện thành dòng phiên tổng hợp từ state.
- **Việc người đọc cần làm:** không có; kế hoạch ở cuối, brain tick khi xong.

## 1. Hợp đồng dữ liệu (các nhánh dùng chung)

### 1.1 State phiên phụ `<state_dir>/<tên>.json`

Thêm vào `SessionState` (đã có trên nhánh nền, đọc file cũ thiếu trường vẫn được, trường lạ bị bỏ qua):

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `parent_session` | str | `CLAUDE_CODE_SESSION_ID` của phiên gọi `start`; `""` khi không có |
| `chrome` | bool | phiên mở bằng `--chrome` |
| `budget_exempt` | bool | bỏ qua mã 20 của trần ngày khi `watch` |

Với provider ngoài, `uuid` là id ngẫu nhiên của phiên phụ (không có transcript Claude).

### 1.2 `hh-ps --json`

Mỗi phần tử `sessions[]` thêm (mọi consumer phải chịu được khi thiếu):

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `parent_session` | str \| null | id phiên cha theo state phiên phụ |
| `side_name` | str \| null | tên phiên phụ |
| `provider` | str | `claude` (mặc định), `codex`, `dsh`, `opencode` |

- Phiên phụ có cha nằm trong phạm vi lọc (`--cwd` hoặc `--all`) thì được đưa vào kể cả khi cwd của nó ở worktree ngoài project.
- Phiên phụ provider khác `claude`: một dòng phiên tổng hợp từ state (`session_id` = `uuid`, `name` = tên, `status` = trạng thái state, `live` = trạng thái `running`, `context_tokens` = `tokens_used`, `token_cap` = `max_tokens`), các lượt `hand-ext` có nhãn `side:<tên>` gắn vào `hand_runs` của dòng này thay vì phiên brain.
- `totals.live_sessions` tính cả phiên phụ ngoài đang chạy.

### 1.3 Nhãn hand-ext của phiên phụ ngoài

`side:<tên>`; `hh-ps` và `side-session watch` tìm lượt chạy theo nhãn này và `started_at >= state.started`.

## 2. side-session

- `--chrome` thay `--no-chrome` trong `claude_args`; `--chrome` với provider khác `claude` → thoát 2.
- Trần ngày: `budget_check_cmd` (argv, đường dẫn tương đối tính từ repo). `start`: mã khác 0 → từ chối thoát 4, trừ `--budget-exempt` hoặc `--force-budget`. `watch`: mã 20 và không miễn → dừng phiên, trạng thái `daystop`.
- Provider ngoài: chạy `hand-ext run --backend <p> --brief <file prompt> --label side:<tên> --cwd <worktree> --max-tokens <trần>` trong `screen`; `watch` đọc token từ registry `hand-ext`, khi lượt chạy kết thúc thì chép `report.md` thành file bàn giao `<handoff_dir>/<tên>.md` nếu chưa có.
- Biến môi trường của phiên con: bỏ `CLAUDE_CODE_CHILD_SESSION` (như `launch.sh`).

## 3. Hiển thị cây

- `hh-ps` dạng chữ, dải terminal `hh-tree-band` và plugin Paseo `hh-tree` vẽ phiên có `parent_session` khớp một phiên đang hiện thành nhánh con thụt lề dưới phiên đó, kèm subagent và hand của chính nó; phiên phụ không rõ cha gom vào nhóm "phiên phụ chưa rõ phiên cha".

## 4. Kế hoạch

- [x] T-SS2-01 Nhánh nền: trường state dùng chung, tài liệu này — covers: §1.1 — estimate: 0.5h
- [ ] T-SS2-02 side-session: Chrome, phiên cha, trần ngày, provider dsh/opencode, test — covers: §2 — estimate: 2h (hand dsh)
- [x] T-SS2-03 hh-ps: trường mới, phiên phụ ngoài phạm vi cwd, dòng phiên ngoài, dạng chữ lồng nhau, test — covers: §1.2, §1.3, §3 — estimate: 1.5h (hand dsh)
- [x] T-SS2-04 Plugin Paseo hh-tree: schema và vẽ lồng nhau — covers: §3 — estimate: 1h (hand dsh)
- [x] T-SS2-05 Dải terminal hh-tree-band vẽ lồng nhau, test mod — covers: §3 — estimate: 0.5h (brain)
- [ ] T-SS2-06 live-tiktok-games: cấu hình `budget_check_cmd`, `launch.sh` thành lớp chuyển tiếp — covers: §2 — estimate: 0.5h (brain)
- [ ] T-SS2-07 Thử thật: một phiên phụ Claude và một phiên phụ dsh nhỏ, xem cây — covers: §1–§3 — estimate: 0.5h (brain)

### Kiểm chứng

- [ ] `python3 -m unittest discover -s hybrid-hands/tests -q` xanh trên nhánh gộp
- [ ] `claude plugin validate hybrid-hands/plugins/hybrid-hands` đạt
