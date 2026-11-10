# Spec đã duyệt: cấu hình model cho ba tầng hybrid

## Tóm tắt

`hand-ext models` xem và lưu lựa chọn model/effort/account theo repo cho brain chính, phiên phụ và hand, tái dùng schema `main_session`, `side_session`, `ext_hand`. **Trạng thái: đã được người dùng duyệt ngày 10/11/2026, triển khai bản 0.43.0.** Giữ mặc định brain trong code (`codex/gpt-6.1-sol/high`); brain/side chỉ nhận Claude hoặc Codex, account chỉ Claude. Model phải có giá canonical và capability provider; ghi atomic vào cùng file repo đã resolve như `parallel-subagents`, không tạo config riêng cho worktree. Unset chỉ theo cả tầng.

Không đổi phiên đang chạy, không bật parallel-subagents, không đổi credentials hay global config. Chênh lệch mặc định brain với AGENTS.md được xử lý trong thay đổi riêng.

## Hiện trạng

Các đường dẫn dưới đây tương đối với repo; số dòng ghi tại thời điểm soạn spec ngày 10/11/2026. Không đọc cấu hình cá nhân hoặc dữ liệu runtime.

| Tầng | Khóa hiện có | Nguồn khai báo/đọc/ghi |
|---|---|---|
| Brain chính | `main_session.provider`, `codex_model`, `codex_effort`, `claude_model`, `claude_effort`, `claude_account` | [shared_config.py](../../../hybrid-hands/plugins/hybrid-hands/lib/shared_config.py):225–230 khai báo; [actions.py](../../../hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py):121–158 đọc khi `start --main` |
| Phiên phụ | `side_session.provider`, `codex_model`, `codex_effort`, `claude_model`, `claude_effort`, `claude_account` | [constants.py](../../../hybrid-hands/plugins/hybrid-hands/lib/side_session/constants.py):41–58 mặc định; [config.py](../../../hybrid-hands/plugins/hybrid-hands/lib/side_session/config.py):86–107 nạp; actions.py:123–158 chọn theo provider |
| Hand | `ext_hand.order`, `ext_hand.backends.<backend>.model/effort`; account Claude nằm trong tên `claude-vN`, registry `ext_hand.claude_accounts.vN` | [constants.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/constants.py):97–139 mặc định; [config.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/config.py):175–200 giải alias/account; [cli.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/cli.py):136–149 pick; [run_cmd.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/run_cmd.py):132–133 ưu tiên cờ CLI |
| Native subagent (khác phiên phụ) | `parallel_subagents.backend`, `main_session.claude_account`; model/effort lấy từ backend hand | [parallel_cmd.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/parallel_cmd.py):42–62 ghi repo; [policy_mode.py](../../../hybrid-hands/plugins/hybrid-hands/lib/policy_mode.py):42–46,76–78 đọc và sinh chỉ dẫn |

Brain code mặc định `codex/gpt-6.1-sol/high`; profile Claude là `claude-opus-5-5/high/v1`. Side mặc định Codex Sol high, profile Claude Opus high v1. Hand mặc định dsh/off → codex/low → claude-v1/low → claude-v2/low. Không nhân bản bảng giá.

`ext_hand.claude_accounts` mặc định v1/v2 ở hand constants.py:103–106. Model/effort Claude còn có thể đến từ account entry hoặc alias legacy; thứ tự hợp nhất riêng được thực hiện tại hand config.py:186–200. `ext_hand.gpt_accounts` chỉ là registry nhãn (constants.py:107–108), không phải cơ chế đổi account GPT; home thực tế ở `ext_hand.backends.codex.home`, side ở `side_session.codex_home`. Không thêm account GPT trong lệnh này.

Loader chung [shared_config.py](../../../hybrid-hands/plugins/hybrid-hands/lib/shared_config.py):67–82,175–195,220–249 merge mặc định → global (`HYBRID_HANDS_CONFIG` hoặc đường dẫn mặc định) → repo; dict merge sâu, list/scalar thay nguyên. Consumer áp cờ CLI cuối. Repo đọc có fallback main worktree tại hand config.py:93–101. `hand-ext config` đã xem được cấu hình; lệnh models bổ sung góc nhìn ba tầng, không thay thế lệnh đó.

## Thiết kế CLI

```sh
hand-ext models [--json] [--cwd PATH]
hand-ext models set --brain claude:claude-opus-5-5:high@v1 --side codex:gpt-6.1-sol:high --dry-run
hand-ext models set --hand-order dsh,codex,claude-v1,claude-v2 --hand codex=gpt-6.1-sol:low
hand-ext models unset brain
hand-ext models unset side
hand-ext models unset hand
```

`--brain` và `--side` nhận `PROVIDER:MODEL[:EFFORT][@vN]`; `@vN` chỉ hợp lệ với Claude. `--hand BACKEND=MODEL[:EFFORT]` lặp được; account được chọn bằng backend canonical, không có cú pháp account thứ hai. Tách `unset TIER` thành subcommand để tránh trộn set/unset. Mọi subcommand hỗ trợ `--cwd`, `--json`; set/unset hỗ trợ `--dry-run`. Không có cờ global.

Không đối số: in ba nhóm; brain/side hiển thị provider đang chọn và profile còn lại; hand hiển thị toàn bộ order cùng model/effort/account từng backend, kể cả override ngoài order. Mỗi giá trị có nguồn plugin/global/repo và đường dẫn nguồn; phân biệt giá trị mặc định cho phiên mới với phiên đang chạy. Alias Claude phải báo canonical và nguồn thắng thực sau bước resolve account/alias, không chỉ nhìn `sources` của canonical key vốn có thể chưa tồn tại. JSON dùng cùng dữ liệu, account chỉ là slot cấu hình, không xuất ID tài khoản thật, home, key hoặc nguyên khối cấu hình.

Omit effort/account giữ profile hiệu lực hiện có, không tự lưu lại giá trị kế thừa; đổi provider chỉ ghi provider và model của provider đó. Validate toàn bộ profile kết quả để tránh giữ effort không hợp lệ. Không cho hai `--brain`, hai `--side`, backend trùng hay order rỗng/trùng. Set không có thay đổi là lỗi cú pháp; ghi cùng giá trị là no-op thành công.

`/hybrid-hands:models` gọi đúng CLI tại cwd, theo mẫu [parallel-subagents.md](../../../hybrid-hands/plugins/hybrid-hands/commands/parallel-subagents.md). Xem không cần xác nhận; chỉ thực thi set/unset khi người dùng đã yêu cầu thay đổi cụ thể. Khi ghi thành công nhắc mở phiên mới từ bàn giao; không đổi model/account của phiên hiện tại.

## Schema ghi

Ví dụ phần patch khi truyền đủ các cờ tương ứng (không phải cấu hình mặc định mới):

```json
{
  "main_session": {
    "provider": "claude",
    "claude_model": "claude-opus-5-5",
    "claude_effort": "high",
    "claude_account": "v1"
  },
  "side_session": {
    "provider": "codex",
    "codex_model": "gpt-6.1-sol",
    "codex_effort": "high"
  },
  "ext_hand": {
    "order": ["dsh", "codex", "claude-v1", "claude-v2"],
    "backends": {"codex": {"model": "gpt-6.1-sol", "effort": "low"}}
  }
}
```

Chỉ sửa leaf được truyền trong file repo `.claude/hybrid-hands.json` đã resolve bằng cùng hàm mà `parallel-subagents` dùng tại `lib/hand_ext/parallel_cmd.py` khoảng dòng 158 (kể cả fallback main worktree); giữ mọi khóa khác. Không ghi nguyên effective config. Claude hand ghi `ext_hand.backends.claude-vN.model/effort`, không ghi account registry hay alias legacy. Không tự đồng bộ `parallel_subagents.backend` với brain/side/hand order.

Unset brain/side xóa riêng các leaf provider, codex_model/effort, claude_model/effort/account trong section tương ứng. Unset hand xóa `ext_hand.order` và leaf model/effort của các backend được hỗ trợ (gồm alias Claude legacy); đồng thời xóa model/effort legacy trong `ext_hand.claude_accounts.vN` để thực sự trả về kế thừa. Giữ config_dir, home, guard, nhãn, max_turns, native, slots và enabled. Chỉ bỏ object rỗng do thao tác vừa tạo ra. Dry-run nêu chính xác leaf bị xóa và giá trị/nguồn kế thừa mới; không hứa trả về plugin defaults nếu global còn override.

Không tạo file config riêng cho worktree, không sao chép raw fallback sang file mới. Tái dùng đúng hàm resolve đường dẫn ghi của `parallel_cmd.py`; nếu đường dẫn resolve là config main worktree thì patch đúng file đó. Dry-run nêu đường dẫn đích và các leaf thay đổi. Đọc/validate raw object, merge candidate trong bộ nhớ, rồi ghi tạm cùng thư mục + fsync + atomic replace theo parallel_cmd.py:26–65. Kiểm file nguồn/đích chưa đổi trước replace; nếu đổi thì dừng, yêu cầu chạy lại, không ghi đè sửa đổi đồng thời. Dry-run không tạo thư mục/file. Không in raw diff cả cấu hình; chỉ in diff leaf thuộc allowlist model và slot.

## Validate & lỗi

Validate offline, không auth probe, không gọi model/API và không đọc secret. Provider brain/side bản đầu chỉ `claude|codex`; dsh side đang được runtime hỗ trợ nhưng nằm ngoài giao diện chỉnh mới. Backend hand chỉ dsh/codex/claude-vN đã tồn tại hiệu lực; nhận alias `claude-main`/`claude` và chuẩn hóa v1/v2. Không tạo backend/account mới.

Model phải có entry trong nguồn [model-prices.json](../../../hybrid-hands/plugins/hybrid-hands/config/model-prices.json), dùng resolver hiện có [usage_pricing.py](../../../hybrid-hands/plugins/hybrid-hands/lib/usage_pricing.py) và tôn trọng `HYBRID_HANDS_PRICING_FILE`; không chép giá hay fallback model family. Membership chỉ chứng minh có giá, chưa chứng minh provider hỗ trợ. Model đồng thời phải thuộc danh sách capability provider riêng `MODEL_CAPABILITIES` trong `lib/hand_ext/constants.py`, khởi tạo từ các model mặc định hiện có của Claude/Codex/dsh; không suy provider từ tiền tố model. Effort hợp lệ đã chốt: Claude `low|medium|high|max`, Codex `low|medium|high|xhigh`, dsh `off|low|high|max`. Không im lặng fallback effort.

Claude account phải là vN có trong `ext_hand.claude_accounts` hiệu lực; không sửa đường dẫn account, không xác minh auth. Codex/dsh từ chối @account. Đọc JSON/schema lỗi, giá thiếu, model/effort/account sai, backend/order sai hoặc xung đột file: không ghi bất kỳ phần nào. Lỗi chỉ nêu tên khóa và nguyên nhân, không dump cấu hình. Exit: 0 thành công/no-op/dry-run, 2 cú pháp/validation, 1 I/O hoặc xung đột. Unset phải cho phép gỡ giá trị model sai tại leaf được xóa rồi validate candidate.

## Runtime tiêu thụ

| Runtime | Hiện đã có | Phần cần triển khai |
|---|---|---|
| `side-session start --main` | actions.py:123–158 chọn `main_session`, cờ CLI ưu tiên | Tái dùng profile resolver/validator chung; giữ account isolation, không đổi phiên sống |
| `side-session start` | Cùng hàm chọn `SideConfig`, đã đọc model/effort/account persist | Giữ override CLI và resume giữ state; không dùng profile mới để đổi phiên resume |
| `hand-ext pick/run` | cli.py:146–149 và run_cmd.py:132–133 đọc backend options | Tái dùng resolution cho phần hiển thị nguồn; giữ guard, admission, native capability và fallback order |
| SessionStart hook | [session-start-policy.sh](../../../hybrid-hands/plugins/hybrid-hands/scripts/session-start-policy.sh):5 gọi policy_mode; policy_mode.py:42–46,76–78 chỉ dẫn backend native và account brain | Có thể thêm mô tả profile cho lần mở sau; hook không đổi được model/account của brain đã được host khởi chạy |
| Brain do host mở trực tiếp | Không có đoạn đọc profile để cấu hình host trong hook trên | Ngoài phạm vi tự điều khiển host; thông báo dùng launcher `side-session start --main` hoặc tự chọn profile khi mở host |

Phiên phụ là agent dài hạn do side-session tạo; native subagent vẫn dùng backend policy riêng. Đổi hand backend model có thể đổi model native subagent dùng cùng backend; hiển thị cảnh báo tác động này dù không đổi enabled/backend policy. Không thay quy tắc giới hạn pool, account matching hay preflight.

## Tương thích/migration

Không đổi schema version, không tự migrate file, không đổi mặc định trong bản đầu. Config cũ và alias vẫn đọc như hiện tại; lần ghi mới chuẩn hóa backend được yêu cầu. Config có backend khác như gemini vẫn được giữ và hiển thị là ngoài phạm vi chỉnh, không bị xóa. Lệnh parallel-subagents giữ nguyên hành vi ghi account brain + backend subagent; models độc lập nên cảnh báo mismatch thay vì tự sửa. Thứ tự thao tác ghi sau cùng thắng cùng leaf.

Bản triển khai là 0.43.0; brain điều phối kiểm chứng, review và cập nhật plugin theo AGENTS.md. Không thay credentials, settings, transport, quota hay native policy.

## Test tối thiểu (kế hoạch, chưa chạy)

1. Fixture ba nguồn và alias/account: xem đủ ba tầng, nguồn đúng sau resolve; CLI launch vẫn ưu tiên profile persist; không ghi khi xem.
2. Set/dry-run tại worktree có fallback: patch đúng leaf, giữ khóa khác, dry-run không ghi; ghi thật đúng file repo đã resolve như parallel-subagents (không tạo config riêng worktree) và repeat no-op; input model/effort/account sai hoặc file đổi thì không ghi (tham số hóa trong cùng test).
3. Unset: chỉ xóa allowlist cả legacy model/effort; hiện lại nguồn kế thừa, giữ guard/home/enabled và resume state.

Tối đa ba test gọn khi triển khai; spec chỉ kiểm link và JSON minh họa, không thêm/chạy test code.

## Quyết định đã chốt

Người dùng duyệt ngày 10/11/2026:

1. Giữ mặc định brain trong code `codex/gpt-6.1-sol/high`; chênh lệch với AGENTS.md xử lý ở thay đổi riêng.
2. Bản đầu `--brain`/`--side` chỉ nhận provider `claude|codex`; `@vN` chỉ Claude. Không dsh side, không account GPT.
3. Model phải có trong `model-prices.json` và danh sách capability provider riêng `MODEL_CAPABILITIES` tại `lib/hand_ext/constants.py`, khởi tạo từ model mặc định hiện có cho Claude/Codex/dsh. Effort: Claude `low|medium|high|max`; Codex `low|medium|high|xhigh`; dsh `off|low|high|max`.
4. Không tạo config riêng cho worktree: ghi vào đúng file repo bằng cùng hàm resolve mà `parallel-subagents` dùng tại `lib/hand_ext/parallel_cmd.py` khoảng dòng 158; ghi atomic theo dòng 26–65.
5. `unset` chỉ theo cả tầng `brain|side|hand`, không unset từng backend.
