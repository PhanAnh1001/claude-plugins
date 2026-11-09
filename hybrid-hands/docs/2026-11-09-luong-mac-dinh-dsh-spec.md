# Spec: luồng mặc định Opus → Sol → dsh, chọn tài khoản và tối ưu cache

## Tóm tắt

- **Mục đích:** chốt luồng mặc định mới do người dùng quyết ngày 09/11/2026, kèm 3 sửa rò cache. Không thêm lớp router.
- **Trạng thái:** chờ người dùng duyệt (L2). Duyệt xong, Opus cắt thành các gói cỡ L1 theo plan `2026-11-09-luong-mac-dinh-dsh-plan.md` và giao các phiên Sol.
- **Quyết định đã chốt (09/11/2026):**
  - **Phiên chính:** mặc định Opus 5.5 high tài khoản `v1`. Đổi được sang Opus 5.5 high `v2` hoặc Sol 6.1 high.
  - **Phiên phụ:** mặc định Sol 6.1 high. Đổi được sang Opus 5.5 high `v1` hoặc `v2`.
  - **`ext_hand.order`:** `dsh` (DeepSeek V4.1 Flash bản 1017, tắt thinking) → `codex` (`gpt-6.1-sol` low) → `claude-v1` (Opus 5.5 low, có chặn %/ngày) → `claude-v2` (Opus 5.5 low).
  - **Tài khoản Claude đánh số `v1`, `v2`, `v3`…:** `v1` = tài khoản cũ `~/.claude`, `v2` = tài khoản mới `~/.claude-hand`. Thêm tài khoản bằng cấu hình, không sửa code.
  - **Subagent hay hand:** hand cùng tài khoản với phiên phụ thì chạy subagent native, khác tài khoản thì chạy `hand-ext`. Đây là bản mở rộng của Ngoại lệ A cho mọi model.
  - **Sáng tạo UI:** mặc định giao Claude `v1`, effort low. Chặn ≥5%/ngày của `v1` giữ nguyên.
  - Luật test giữ nguyên.
- **Con số chính:**
  - 4 nhóm thay đổi, 3 gói giao Sol (A, B song song; C sau A và B), 1 phần Opus tự làm.
  - Phiên bản dự kiến: hybrid-hands 0.33.0.
  - Hook mỗi prompt giảm từ ≤1800 xuống ≤300 ký tự.

## 1. Luồng vai trò và tài khoản

### 1.1 Ba tầng

| Tầng | Mặc định | Đổi được sang | Vai trò |
|---|---|---|---|
| Phiên chính | Opus 5.5 high, `v1` | Opus 5.5 high `v2`/`v…`; Sol 6.1 high (`--main`) | Thư ký, SA, BA, PM. Review spec, plan, giải pháp; đọc bàn giao |
| Phiên phụ | Sol 6.1 high (Codex, `~/.codex-hand`) | Opus 5.5 high `v1`/`v2`/`v…` | Lead tech, lead QA. Spec L1, review code hand mình giao |
| Hand | Theo `ext_hand.order` | Gọi tường minh `--backend` | Dev, tester |

- Mọi lần đổi model hay tài khoản đều là **mở phiên mới** từ tài liệu bàn giao, không dùng `/model` giữa phiên. Lý do: cache gắn với model và tài khoản, đổi giữa phiên phải ghi lại toàn bộ ngữ cảnh.
- Bảng lane, luật review và luật dữ liệu giữ nguyên.

### 1.2 Chọn hand trong phiên phụ

1. Lấy backend mà `auto` sẽ chọn bằng lệnh mới `hand-ext pick` (mục 2.4).
2. Nếu tài khoản của backend đó trùng tài khoản phiên phụ thì chạy subagent native với đúng model/effort. Nếu khác thì chạy `hand-ext run --backend auto`.

| Phiên phụ | dsh | codex (Sol low) | claude-v1 (Opus low) | claude-v2 (Opus low) | UI (Claude v1, low) |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex subagent | hand-ext | hand-ext | `hand-ext --backend claude-v1` |
| Opus v1 | hand-ext | hand-ext | Agent `hybrid-hands:hand` | hand-ext | Agent `hybrid-hands:hand` |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent `hybrid-hands:hand` | `hand-ext --backend claude-v1` |

- **Phần Ngoại lệ A giữ nguyên:**
  - `fork_turns=none` (với Codex).
  - Brief tự chứa, chép nguyên văn luật dữ liệu.
  - Executor không recursion.
  - Tổng native + hand-ext ≤ `ext_hand.max_parallel`.
  - Unknown sau spawn không tạo writer trùng.
  - Báo usage qua runtime, thiếu thì `?`.
- **Chặn %/ngày của `v1` vẫn áp cho subagent native `v1`** (phiên phụ Opus v1): trước khi spawn thì kiểm bằng `hand-ext pick`. Bị chặn thì `pick` đã chuyển sang backend kế tiếp.
- Subagent Claude (`hybrid-hands:hand`) đã là Opus effort low, không cần định nghĩa agent mới.
- Không bật parallel-subagents.

### 1.3 Leo thang khi hand làm hỏng

- Sol review thấy lỗi thì giao lại cùng backend đúng **một lần**.
- Lần thứ hai vẫn hỏng thì chuyển sang backend kế tiếp trong order: dsh → codex → claude-v1 → claude-v2.
- Lý do: dsh tắt thinking rẻ mỗi lượt, nhưng mỗi vòng review rồi giao lại tốn lượt Sol high. Đó là chi phí ẩn lớn hơn.

## 2. Hand ngoài

### 2.1 Sổ tài khoản Claude

- **Khoá cấu hình mới `claude_accounts`**, mặc định trong `lib/hand_ext/constants.py`:
  - `v1`: `config_dir` `~/.claude`, `max_day_pct` 5;
  - `v2`: `config_dir` `~/.claude-hand`, không chặn ngày.
- Cấu hình repo (`.claude/hybrid-hands.json`) thêm `v3`… cùng dạng. Chưa có nguồn cấu hình cấp người dùng. Mỗi tài khoản tự sinh một backend `claude-v<N>`: model `claude-opus-5-5`, effort `low`.
- **Tương thích ngược:** `claude-main` là alias của `claude-v1`; `claude` là alias của `claude-v2`. Ledger, `hh-ps`, panel đọc được cả tên cũ lẫn tên mới.
- Chặn %/ngày tính theo đúng cách hiện có của `claude-main`, áp cho mọi tài khoản có `max_day_pct`.

### 2.2 Order và `auto`

- Mặc định: `order = ["dsh", "codex", "claude-v1", "claude-v2"]`; `codex` là `gpt-6.1-sol` effort `low`.
- `auto` thử từng backend theo order. Backend hết hạn mức, chưa đăng nhập hoặc bị chặn %/ngày thì sang backend kế tiếp.
- **Exit 7** chỉ xảy ra khi mọi backend trong order đều không dùng được. Khi đó chạy `hand-ext doctor` và ghi lý do vào bàn giao để Opus quyết. Bỏ luật cũ "dsh hết quota thì codex medium".
- Exit 8 giữ nguyên: chờ slot.
- **Cấu hình repo:** `claude-plugins/.claude/hybrid-hands.json` hiện ghi `order: ["codex"]` (tạm dừng dsh từ 07/11). Khi tính năng xong thì bỏ khối `ext_hand` này để dùng mặc định của plugin. Chỉ sửa file này, không sửa cấu hình repo khác.

### 2.3 dsh bản 1017, tắt thinking

- Trước khi sửa code, kiểm chứng 2 điểm và ghi kết quả vào plan:
  1. ID model chính xác của bản 1017 trên OpenCode Go (trang công khai).
  2. dsh có cách tắt thinking không (cờ, effort `none`, hay tham số request).
- Có cả hai thì đặt mặc định backend `dsh` theo model và cách tắt đó. Thêm entry giá cho ID mới vào `config/model-prices.json`, có `source` và `price_date`.
- Thiếu một trong hai thì dừng gói A ở bước này và báo lại cho Opus. Không đoán ID, không fallback giá.

### 2.4 Lệnh `hand-ext pick`

- `hand-ext pick [--json]` in backend mà `auto` sẽ chọn lúc này: tên, model, effort, tài khoản (`dsh`, `gpt`, `claude-v1`, `claude-v2`…) và lý do bỏ qua các backend đứng trước.
- Lệnh chỉ đọc: không chạy hand, không ghi ledger, không in giá trị credential.
- Exit 0 khi có backend dùng được, exit 7 khi không có.

## 3. Phiên phụ và phiên chính chọn tài khoản

- **Phiên phụ:** `side-session start --provider claude --account v1|v2|v…`, mặc định `v1`.
  - Lấy `config_dir` từ `claude_accounts` (mục 2.1).
  - `v1` giữ chặn ngày hiện có.
- **Phiên chính:** `side-session start --main` mặc định vẫn là Sol 6.1 high. Thêm `--main --provider claude --account v2` để mở phiên chính Opus 5.5 high tài khoản `v2`.
- **Template:** phiên phụ Claude nhận template ghi rõ tài khoản của nó, để áp đúng bảng 1.2.
- **Tương thích:** cờ cũ (nếu có) giữ làm alias, không đổi hành vi đang có.

## 4. Policy và tối ưu cache

### 4.1 Nội dung policy

Sửa đồng bộ theo mục 1 đến 3, dùng tên `v1`/`v2` thay cho "cũ/mới" và `claude-main`/`claude`, ở các file:

- `scripts/session-start-policy.sh`, `scripts/inject-policy.sh`
- `templates/*.md`: side-session, main-session, hand-brief, ext-hand-preamble
- `skills/ext-hand`, `skills/side-session`, `skills/paseo`
- `agents/hand.md` (nếu có nhắc order)
- `README.md`, `CHANGELOG.md`
- `AGENTS.md` ở gốc repo: đoạn "Phiên chính Sol", Ngoại lệ A, luật exit 7

### 4.2 Ba sửa rò cache

1. **Hook mỗi prompt (`inject-policy.sh`):** rút xuống ≤300 ký tự. Chỉ giữ con trỏ tới policy đầy đủ và 3 luật hay quên nhất:
   - hand theo order;
   - không tự tra cứu;
   - cấm hiện secret.

   Policy đầy đủ đã được SessionStart chèn lại lúc startup, resume, clear và compact.
2. **SessionStart (`session-start-policy.sh`):** bỏ các đoạn trùng nguyên văn với AGENTS.md, thay bằng một dòng "xem AGENTS.md mục …". Chỉ áp khi AGENTS.md của repo đó thật sự chứa đoạn đó; repo khác không có thì giữ nguyên.
3. **Thứ tự khuôn brief (`templates/hand-brief.md` và khuôn trong hook):** đưa phần tĩnh lên đầu, phần riêng của từng task xuống cuối:
   - thứ tự mới: `LUẬT BẮT BUỘC` → `KHÔNG ĐƯỢC ĐỤNG` → `TRẢ VỀ` → `MỤC TIÊU` → `NGỮ CẢNH` → `PHẠM VI GHI` → `KIỂM CHỨNG`;
   - lý do: dsh và Codex cache theo tiền tố nên các hand song song dùng chung phần đầu. dsh đọc cache $0,006/MTok so với $0,30/MTok input thường (`lib/hand_ext/constants.py:46-48`).

## 5. Kiểm chứng

### 5.1 Test tự động (mức tối thiểu, mỗi gói ≤2 ca)

- **Gói A:**
  - Order mặc định gồm 4 backend đúng model/effort.
  - `pick` bỏ qua `claude-v1` khi bị chặn ngày; exit 7 khi hết mọi backend.
- **Gói B:**
  - `--account v2` trỏ đúng `config_dir`.
  - Tài khoản lạ (không có trong `claude_accounts`) thì báo lỗi.
- **Gói C:** cập nhật `tests/test_policy_brain_context.py` theo giới hạn ≤300 ký tự và marker mới.

### 5.2 Kiểm thực tế

1. Một task L0 thật qua phiên Sol: `hand-ext pick` ra `dsh`; report hiện model bản 1017, thinking tắt, token và USD~.
2. Dùng fixture giả lập dsh và codex không dùng được, `claude-v1` bị chặn ngày: `hand-ext pick --json` ra `claude-v2`.
3. Kiểm version và đường dẫn plugin được nạp thực tế ở các repo đang dùng hybrid-hands. Ledger cũ có `claude-main`/`claude` vẫn hiện đúng trên `hh-ps`.

### 5.3 Đo sau 1 tuần (16/11/2026)

So với baseline 07/11 ở plan `2026-11-07-ba-tang-opus-sol-dsh-plan.md` mục 4.3:

- Token Opus mỗi lượt và tổng tuần.
- Tỉ lệ hand dsh phải giao lại sau review.
- Tỉ lệ lượt Opus không dẫn tới giao việc hay quyết định. Nếu chiếm ≥30% hạn mức Opus tuần thì xem lại phương án router. Ngưỡng 30% là ước lượng, không có nguồn.
