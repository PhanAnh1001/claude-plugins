---
id: bug-2026-11-15-limit-watch-paseo-closed-done
title: limit-watch adapter paseo tự chuyển done/work_finished khi phiên Paseo khởi động lại
status: fixed
owner: phiên chính claude-plugins (Opus 5.5 v2)
last-reviewed: 2026-11-15
severity: major
lane: L1
---

# Lỗi: limit-watch adapter paseo tự chuyển done khi phiên Paseo khởi động lại

## Tóm tắt

- **Triệu chứng:** target limit-watch adapter `paseo` đang `armed`, `work_pending=True` tự chuyển `state=done, reason=work_finished` sau khi phiên Paseo khởi động lại. Agent vẫn sống, `archivedAt=null`, định danh khớp, nhưng target không tự armed lại. Đã xảy ra ở 3 brain repo 3d-scenic-wonders trong ngày 15/11/2026, một brain bị hai lần.
- **Nguyên nhân gốc:** bridge coi `status` `closed`/`stopped` và lúc tạm không lấy được agent là "đã kết thúc" (`paseo_bridge.mjs:42`, `:28-31`). Engine biến `closed` thành `done` (`engine.py:77`, `:111`), mà `done` là trạng thái cuối (`engine.py:9`). Trong khi đó daemon Paseo **chủ động** ghi `running → closed` mỗi lần khởi động rồi resume agent về `running`, nên `closed` chỉ là trạng thái tạm.
- **Là regression:** không. Đây là lỗi tiềm ẩn có từ commit đưa limit-watch vào, `ce27635` (0.61.0, 13/11/2026).
- **Test đỏ:** 3 test mới trong `test_limit_watch.py`; 2 ca fail-side đỏ ở `AssertionError: 'done' != 'armed'`, ca archivedAt và 12 test cũ xanh.
- **Phương án đề xuất:** A — chỉ `archivedAt` mới là kết thúc; `closed` chưa archive thì giữ armed; agent null hoặc định danh lệch thì trả `valid=false`. Sửa 2 file mã (`paseo_bridge.mjs`, docstring `engine.py`), 1 file test, cùng version/changelog/skill doc. Bump 0.61.2.
- **Việc người đọc cần làm:** duyệt phương án ở mục 3 (A/B/C) để agent bắt đầu sửa.

## 1. Hiện tượng

### 1.1 Triệu chứng

Nguồn: bàn giao `docs/work-in-progress/handoffs/limit-watch-paseo-closed.md`, do phiên brain luồng A repo 3d-scenic-wonders báo ngày 15/11/2026 (hai lần).

- `~/.hybrid-hands/limit-watch/state.json`: target `0ea7062b…` (A), `87326411…` (B), sau đó thêm `brain-3d-main` (C), đều `done/work_finished` trong khi `work_pending=True`.
- `get_agent_status` cùng lúc: A `running`, B `idle`, `archivedAt=null`; agent_id, workspace, cwd, nativeHandle, provider đều khớp bản đăng ký.
- Cả ba vừa khởi động lại (tên peer đổi, instruction files nạp lại).
- Workaround hiện tại: mỗi lần như vậy phải chạy lại `limit-watch add --self`.

### 1.2 Cách tái hiện

1. Đăng ký target paseo `armed`, `work_pending=True`.
2. Tick với agent `status=running` → vẫn `armed`.
3. Tick với agent `status=closed`, `archivedAt=null`, định danh khớp (đúng snapshot daemon trả lúc khởi động lại). Hoặc tick khi `fetchAgent` trả `null`.
4. **Kết quả thực tế:** target `done/work_finished`, các tick sau bỏ qua. **Kết quả mong đợi:** giữ `armed`, và tick `running` kế tiếp vẫn `armed`.

Môi trường: nhánh `main`, commit `b9ba466`, plugin hybrid-hands 0.61.1, Paseo CLI cài tại `~/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli`.

### 1.3 Test đỏ

- **Test:** `hybrid-hands/plugins/hybrid-hands/tests/test_limit_watch.py`
  - `test_paseo_restart_closed_stays_armed` (fail-side): chạy bridge Node thật trên client giả, chuỗi `running → closed → running`.
  - `test_paseo_restart_missing_agent_stays_armed` (fail-side): chuỗi agent có → `null` → có.
  - `test_paseo_archived_agent_finishes_work` (pass-side): `archivedAt` có giá trị → `done/work_finished`.
- **Lệnh** (workdir `hybrid-hands/plugins/hybrid-hands/tests`): `python3 -m unittest test_limit_watch`
- **Đầu ra (đỏ đúng lý do):**

```text
FAIL: test_paseo_restart_closed_stays_armed (...) (tick=1, status='closed')
AssertionError: 'done' != 'armed'
FAIL: test_paseo_restart_closed_stays_armed (...) (tick=2, status='running')
AssertionError: 'done' != 'armed'
FAIL: test_paseo_restart_missing_agent_stays_armed (...) (tick=1, missing=True)
AssertionError: 'done' != 'armed'
FAIL: test_paseo_restart_missing_agent_stays_armed (...) (tick=2, missing=False)
AssertionError: 'done' != 'armed'
Ran 15 tests in 1.161s
FAILED (failures=4)
```

- Hand codex (`gpt-6.1-sol` low) viết test. Phiên chính đã review diff (+37 dòng, chỉ file test) và chạy lại lệnh trên.
- **Cần chỉnh khi sửa:** helper `bridge_tick` đang `assertIs(live.get('valid'), True)`. Phương án A trả `valid=false` cho agent null, nên ca null phải bỏ assertion này và kiểm thêm `reason == 'identity_or_runtime_unconfirmed'`.

## 2. Phân tích

### 2.1 Lịch sử Git

| Commit | Ngày | Nội dung | Liên quan |
|---|---|---|---|
| ce27635 | 2026-11-13 | feat(hybrid-hands,statusline): limit-watch … (0.61.0) | đưa vào `paseo_bridge.mjs:28-31,42` và `engine.py:77-78` (blame) |
| 988877d | 2026-11-15 | fix(hybrid-hands): explain limit-watch registration conflicts (0.61.1) | chỉ đổi thông báo đăng ký, không đụng đường closed |

Lệnh đã dùng: `git log --oneline -- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/limit_watch`, `git blame -L 28,31` và `-L 40,43 paseo_bridge.mjs`, `git blame -L 77,80 engine.py`. Không có commit tốt trước đó nên không bisect. Không có fix cũ nào trên đường này, nên phương án A không làm sống lại lỗi đã sửa.

### 2.2 Nguyên nhân gốc

**Cơ chế:** bridge gộp "agent tạm không chạy" với "agent đã kết thúc". Engine coi tín hiệu gộp đó là kết thúc vĩnh viễn.

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/limit_watch/paseo_bridge.mjs:42`: `closed = Boolean(agent.archivedAt) || ['closed','stopped'].includes(agent.status)`.
- `paseo_bridge.mjs:28-31`: agent `null` hoặc lệch bất kỳ trường định danh nào đều emit `{valid: true, closed: true}`, kể cả khi daemon đang chuyển. Đây là kết luận "đã xác nhận" từ một lần quan sát.
- `engine.py:77-78`: `work_finished()` trả `True` khi `live.closed`. Docstring (`engine.py:71-73`) nói chỉ "confirmed closure" mới kết thúc, nhưng bridge không cấp được xác nhận đó.
- `engine.py:111-112`: đặt `done/work_finished`; `engine.py:9` `TERMINAL` chứa `done`, nên `engine.py:98` bỏ qua target ở mọi tick sau.

**Bằng chứng `closed` là tạm thời** (mã Paseo server đã cài, `@getpaseo/server/dist/server/server/agent/`):

- `restart-recovery/index.js:16-26` `prepareStartup()`: mỗi lần daemon khởi động, mọi record `lastStatus` `running`/`initializing` bị ghi thành `"closed"` và đánh dấu `resumeOnStartup`. Sau đó `resumePending()` dispatch lại để agent về `running`. Resume chỉ chọn record `!record.archivedAt` (dòng 4).
- `agent-manager.js:1360-1371`: agent đã lưu nhưng chưa nạp được dựng với `lifecycle: "closed"`, `runtimeInfo: undefined`. `persistence.nativeHandle` vẫn còn nên định danh vẫn khớp.
- `agent/mcp-shared.js:6`: enum status là `initializing | idle | running | error | closed`, không có `stopped`.
- Như vậy `archivedAt` là tín hiệu kết thúc duy nhất mà Paseo dùng nhất quán.

**Giả thuyết chưa chứng minh:** sau khi resume, `nativeHandle` có thể đổi nếu provider tạo session mới. Khi đó `paseo_bridge.mjs:29` cũng emit `closed`. Bằng chứng 15/11 cho thấy native vẫn khớp nên đây không phải nguyên nhân lần này. Muốn chứng minh, cần so `nativeHandle` trước và sau một lần restart thật.

**Ảnh hưởng:**

- Mọi target adapter `paseo` (brain chính) ở mọi repo. Mỗi lần daemon hoặc phiên khởi động lại, limit-watch âm thầm ngừng theo dõi: không gửi "làm tiếp" khi hết hạn mức, đúng triệu chứng người dùng hỏi hai lần.
- Adapter `side` không bị: nó kết thúc theo `.done`/stopped của side-session state (`adapters.py:46-50`). Bridge chỉ đặt `idle`.
- Không làm hỏng dữ liệu. `state.json` chỉ giữ target `done`, và `add --self` cùng ID rearm được.

## 3. Phương án sửa

| Phương án | Mô tả | Rủi ro | File bị đổi |
|---|---|---|---|
| **A (đề xuất)** | Bridge: `closed = Boolean(agent.archivedAt)`. Status `closed` chưa archive thì `closed:false`, `idle:false`, vẫn trả `status`. Agent `null` hoặc định danh lệch thì `{valid:false}`, engine giữ nguyên trạng thái với `reason=identity_or_runtime_unconfirmed` (`engine.py:102-104`, đã có). Engine giữ logic, chỉ sửa docstring. Test chỉnh như mục 1.3; giữ test cũ `native changed → not_sent`. | Agent bị xoá hẳn mà không archive sẽ treo ở `armed` với reason unconfirmed. Nó không bao giờ gửi (valid false), người dùng tự `limit-watch done` được. Không tệ hơn hiện tại. | `lib/hand_ext/limit_watch/paseo_bridge.mjs`, `engine.py` (docstring), `tests/test_limit_watch.py`, `skills/limit-watch/SKILL.md` (1 câu), `CHANGELOG.md`, `plugin.json` → 0.61.2 |
| B | A, cộng thêm: định danh lệch hoặc agent `null` liên tiếp N=3 tick thì `done/identity_lost`. Thêm bộ đếm `mismatch_ticks` vào target và reset khi khớp. | Thêm trạng thái vào `state.json` và nhiều test hơn. N tick theo chu kỳ launchd có thể vẫn ngắn hơn một lần restart chậm, nên vẫn có thể done nhầm. | như A + `engine.py` (logic) + `store.py` nếu cần default |
| C | A, cộng thêm: tự bám theo agent mới khi `nativeHandle` đổi nhưng `agent_id`/workspace/cwd giữ nguyên (cập nhật `native_id`). | Nới định danh pin có thể gửi nhầm phiên. Trái nguyên tắc "identity-pinned" của `adapters.py:1`. Chưa có bằng chứng native đổi. Nên thành việc riêng L2 nếu cần. | như A + `paseo_bridge.mjs`/`engine.py`/`registration.py` |

**Đề xuất: A.** A sửa đúng cơ chế đã chứng minh (Paseo tự ghi `closed` lúc khởi động) với diff nhỏ nhất. A dùng nhánh `valid=false` sẵn có của engine, và không nới định danh pin. Social listening cũng nghiêng về "một lần quan sát thất bại không được dẫn tới hành động vĩnh viễn". B chỉ đáng làm nếu người dùng muốn target tự dọn khi agent bị xoá hẳn. C để sau, khi có bằng chứng `nativeHandle` đổi.

### Social listening

- Kubernetes probe dùng `failureThreshold` (mặc định 3 lần thất bại liên tiếp) trước khi hành động, để chịu được lỗi tạm thời. Khuyến nghị là không đưa phụ thuộc ngoài vào liveness vì có thể gây restart hàng loạt khi phụ thuộc chập chờn ([OneUptime, 02/2026](https://oneuptime.com/blog/post/2026-02-09-probe-failure-success-threshold/markdown); [OneUptime, 02/2026](https://oneuptime.com/blog/post/2026-02-09-liveness-probes-avoid-false-positives/markdown); [Red Hat](https://www.redhat.com/en/blog/liveness-and-readiness-probes), xem 15/11/2026). Rút ra: không kết luận "chết" từ một tick. Đây là cơ sở cho nhánh tuỳ chọn của B.
- Pitchfork discussion #634: một race khi restart cưỡng bức làm monitor cũ ghi đè trạng thái daemon mới thành `stopped`, khiến tiến trình thay thế mất theo dõi ([GitHub jdx/pitchfork #634](https://github.com/jdx/pitchfork/discussions/634), xem 15/11/2026). Rút ra: cùng một mẫu lỗi. Trạng thái tạm lúc restart bị coi là cuối, nên supervisor ngừng theo dõi.
- Supervisord mô tả `BACKOFF`/`STOPPING` là trạng thái trung gian, và chuyển `RUNNING ↔ EXITED` không giới hạn số lần ([supervisor docs](https://supervisor.readthedocs.io/en/latest/subprocess.html), xem 15/11/2026). Rút ra: phải tách trạng thái trung gian khỏi trạng thái cuối, như phương án A tách `closed` khỏi `archivedAt`.
- Cả ba nguồn là blog/tài liệu kỹ thuật hoặc discussion, không phải nghiên cứu. Không có nguồn nào bàn riêng về Paseo.

## 4. Cổng duyệt

- **Quyết định:** duyệt phương án A
- **Người duyệt:** người dùng
- **Ngày:** 2026-11-15

## 5. Kết quả sau sửa

- **Đã sửa (phương án A, 0.61.2):** `paseo_bridge.mjs` chỉ coi `archivedAt` là kết thúc; agent null/lệch định danh emit `{valid:false, receipt:'not_sent'}`. `engine.py` chỉ sửa docstring. Test bỏ assertion `valid is True` trong helper, thêm kiểm sender không gọi và reason `identity_or_runtime_unconfirmed`. Hand claude-v1 (Opus 5.5 low) sửa; phiên chính review và giao lại một lần để sửa 2 câu tài liệu mô tả sai nhánh `closed`.
- **Test đỏ → xanh:** `python3 -m unittest test_limit_watch` (workdir `hybrid-hands/plugins/hybrid-hands/tests`): 15 test OK; 2 ca fail-side đã xanh, ca archivedAt và 12 test cũ vẫn xanh.
- **Gate:** repo không có `.claude/dev-workflow.toml`. Đã chạy `node --check paseo_bridge.mjs` OK, `git diff --check` sạch, `claude plugin validate hybrid-hands/plugins/hybrid-hands` passed.
- **Hiệu lực:** launchd `local.hybrid-hands.limit-watch` chạy `hand-ext limit-watch tick` thẳng từ mã nguồn repo này, nên bản sửa áp dụng từ tick kế tiếp. Target đã `done` trước khi sửa vẫn phải `add --self` lại một lần.
- **Tài liệu đã cập nhật:** `hybrid-hands/plugins/hybrid-hands/skills/limit-watch/SKILL.md`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` (0.61.2), `plugin.json` 0.61.2.
