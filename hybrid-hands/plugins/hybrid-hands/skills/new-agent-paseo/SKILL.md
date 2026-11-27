---
name: new-agent-paseo
description: Mở agent Paseo mới ("main brain") ở TAB MỚI cùng workspace (phiên độc lập, không phải subagent), cho chọn GPT v1 (gpt-6.1-sol high), Claude v1 hoặc Claude v2 (Opus high) và context mới hoặc mang context phiên hiện tại (bàn giao); đồng thời đổi profile hybrid-hands của repo sang gpt-mono và bật subagent native. Dùng khi người dùng gõ /hybrid-hands:new-agent-paseo hoặc nói "mở agent paseo", "new agent paseo", "đổi sang gpt-mono", "mở brain sol", "mở phiên main brain", "mở brain claude v1/v2", "chuyển brain sang GPT", "mở tab brain sol high".
---

# new-agent-paseo

**Tóm tắt:** một lệnh `bin/new-agent-paseo` làm đủ 3 việc theo thứ tự: (1) đặt profile `gpt-mono` cho repo, (2) bật subagent native (`ext_hand.native.claude/codex = auto`), (3) mở phiên Paseo main brain ở tab mới cùng workspace, rồi kiểm phiên **không có phiên cha**. Chọn agent bằng `--brain`: `gpt-v1` theo vai `brain` của profile (`codex/gpt-6.1-sol`, thinking `high`, mode `full-access`); `claude-v1|claude-v2` mở `claude-opus-5-5` high (mode `bypassPermissions`) trên đúng tài khoản Claude đó. Dùng được ở Claude v1 và v2 (cùng plugin); Codex dùng skill `$new-agent-paseo` của plugin Codex hybrid-hands, gọi cùng script này.

## 1. Cách chạy

Người dùng chưa nói rõ thì hỏi bằng MỘT lần AskUserQuestion gồm các câu còn thiếu: header `Agent` (`GPT v1` → `--brain gpt-v1`, `Claude v1` → `--brain claude-v1`, `Claude v2` → `--brain claude-v2`) và header `Context` (`Context mới` → `--context new`; `Context phiên hiện tại` → viết bàn giao rồi `--context-file FILE`); huỷ thì dừng. Đã rõ ("mở agent claude v2, context mới") thì không hỏi. Bàn giao: ghi `/tmp/new-agent-paseo-<YYYYMMDD-HHMMSS>.md` (≤ 100 000 byte) theo mục 2 của lệnh `/hybrid-hands:new-agent-paseo` (mục tiêu, đã xong, đang dở, quyết định, việc tiếp theo, lưu ý), không chép secret hay transcript thô. Sau đó chạy đúng một lệnh bằng tool Bash tại thư mục repo hiện tại, luôn kèm `--brain` và các tham số người dùng đưa:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/new-agent-paseo" --brain <agent> [tham số]
```

Nếu `${CLAUDE_PLUGIN_ROOT}` không được thay, dùng `new-agent-paseo` trong PATH hoặc đường dẫn tuyệt đối tới `bin/` mà hook SessionStart in ra. Không tự làm lại từng bước bằng tay, không sửa script khi nó báo lỗi; in nguyên thông báo lỗi. Lệnh cần daemon Paseo cục bộ và ghi `.claude/hybrid-hands.json`: sandbox chặn thì xin quyền chạy ngoài sandbox.

## 2. Tham số

| Tham số | Ý nghĩa |
|---|---|
| `--brain gpt-v1\|claude-v1\|claude-v2` | Loại agent. Thiếu thì terminal hiện menu chọn; không có terminal thì báo lỗi kèm lựa chọn. `gpt-v1` (bí danh `gpt`, `sol`): theo vai brain của gpt-mono. `claude-v1`/`claude-v2` (viết tắt `v1`/`v2`): `claude-opus-5-5` high trên tài khoản đó. |
| `--context new\|current` | `new` (mặc định): không truyền gì thêm. `current`: gửi kèm nội dung `--context-file FILE` (bàn giao do phiên đang gọi viết, ≤ 100 000 byte) vào cuối tin nhắn đầu; thiếu file thì dừng trước khi ghi gì. |
| `--context-file FILE` | File bàn giao; có cờ này thì ngầm `--context current`. |
| `--model M`, `--effort E` | Ghi đè model hoặc mức thinking (ví dụ `--model gpt-6.2-sol`, `--effort xhigh`). |
| `--workspace WKS_ID` | Chọn workspace Paseo. Bỏ trống: gọi từ phiên Paseo còn sống thì dùng workspace của phiên đó; gọi từ terminal thì lấy workspace duy nhất có `cwd` trùng repo (nhiều hơn một thì script liệt kê để chọn). |
| `--prompt "..."` | Việc đầu tiên giao cho brain. Mặc định: đọc AGENTS.md/CLAUDE.md và bàn giao mới nhất ở `docs/handoff/`, tóm tắt rồi chờ. |
| `--title "..."` | Tên tab. Mặc định `main brain sol high` hoặc `main brain opus high (v1\|v2)`. |
| `--cwd DIR` | Repo khác thư mục hiện tại. |
| `--dry-run` | Chỉ in các bước sẽ làm, không ghi cấu hình, không mở phiên. |

## 3. Script làm gì

0. Chọn workspace trước khi ghi gì; giữ bản sao `.claude/hybrid-hands.json`.
1. `hand-ext profile set gpt-mono` (hand-ext cùng thư mục `bin/` với script) — chỉ ghi khoá `profile` của repo.
2. Ghi `ext_hand.native = {claude: auto, codex: auto}` vào cùng file (giữ khoá khác), rồi kiểm `hand-ext pick --role code` trả `native: true`.
3. Chọn model: `gpt-v1` đọc vai `brain` trong `hand-ext profile --json` (theo cả ô ghi đè `profiles.gpt-mono.brain`), tài khoản GPT `v1` ứng với provider Paseo `codex`; `claude-v1`/`claude-v2` dùng provider Paseo cùng tên.
4. `paseo run --no-wait` mở phiên; Paseo tạo thành subagent (gọi từ trong phiên Paseo) thì `paseo agent detach` ngay. Cuối cùng kiểm `ParentAgentId` là `null`.
- Lỗi ở bất kỳ bước nào trước khi mở được phiên → tự khôi phục `.claude/hybrid-hands.json` như cũ.

## 4. Sau khi chạy

- Báo agentId, provider/model của phiên mới; phiên mới không báo kết quả về phiên đang gọi.
- Profile mới áp dụng cho phiên mở sau; phiên đang chạy giữ vai và model cũ.
- `.claude/hybrid-hands.json` thường được Git theo dõi: commit theo luật của repo.
- Quay lại: `/hybrid-hands:profile claude-mono` (hoặc `claude-mono v2`). Phiên mới mở dùng profile cấu hình, không theo profile riêng phiên.
