# Spec: cấu hình global và key riêng cho phiên chính, phiên phụ, subagent

## Tóm tắt

- **Mục đích:** cho phép chọn provider, model, effort, account của phiên chính, phiên phụ và hand/subagent ở cấp global (máy/người dùng), không chỉ cấp repo. Đồng thời vá chỗ phiên chính Sol nhận policy thiếu so với phiên Claude.
- **Trạng thái:** mục 1-4 đã duyệt 09/11/2026, gói A đang chạy; mục 5 (bảo mật) chờ duyệt. Opus giao các gói theo plan `2026-11-09-cau-hinh-global-plan.md`.
- **Quyết định đề xuất:**
  - **File global:** `~/.hybrid-hands/config.json`, đổi đường dẫn bằng env `HYBRID_HANDS_CONFIG`. Schema giống hệt `.claude/hybrid-hands.json`.
  - **Thứ tự ưu tiên:** mặc định plugin → global → repo → cờ CLI. Dict được merge sâu, list và giá trị đơn bị thay nguyên.
  - **Key mới:** mục `main_session`; thêm `provider` và các key `claude_*` cho `side_session`; thêm `ext_hand.native` để bật/tắt subagent native.
  - **Lệnh mới:** `hand-ext config --json` in cấu hình hiệu lực, kèm nguồn (plugin/global/repo) của từng key.
  - **Phiên chính Sol:** template được điền đường dẫn tuyệt đối của bin, khuôn brief và đường dẫn các SKILL.md.
  - **Phiên Claude dưới Paseo:** thêm key `transport` (mặc định `paseo`) để side-session mở phiên Claude chính/phụ trên Paseo; truyền `CLAUDE_CONFIG_DIR` theo account; `cc-switch` giữ đúng account khi chuyển phiên.
  - **Bỏ luật cũ** "`claude_accounts` không có nguồn user config" trong AGENTS.md và các template.
  - **Bảo mật runtime (mục 5):** mục cấu hình `security` mặc định an toàn cho mọi thứ plugin khởi chạy (sandbox phiên Sol, permission mode phiên Claude, lọc env, chặn đọc file credential); lệnh `hand-ext doctor --security` kiểm tra phần plugin không khởi chạy. Plugin không sửa file cấu hình của người dùng.
- **Con số chính:** 7 gói giao Sol (A đang chạy; B, C, E, S0 sau A; S1 sau B và S0; S2 song song S1), 1 phần Opus tự làm. Phiên bản dự kiến hybrid-hands 0.34.0. Mức test: tối thiểu cho A/B/C/E, kỹ cho S0/S1/S2.
- **Rủi ro lớn nhất hiện nay:** agent Sol tạo qua Paseo chạy không sandbox trong khi relay Paseo bật, nên chiếm được điện thoại đã ghép là có shell toàn quyền trên máy.
- **Người dùng cần quyết:** mục 1-4 đã duyệt 09/11/2026; còn 3 điểm bảo mật ở mục 7.2.

## 1. Tầng cấu hình

### 1.1 Nguồn và thứ tự

| Thứ tự | Nguồn | Ghi chú |
|---|---|---|
| 1 | `DEFAULTS` của plugin | `lib/hand_ext/constants.py:97-135`, `lib/side_session/constants.py:40-61` |
| 2 | Global `~/.hybrid-hands/config.json` (hoặc `$HYBRID_HANDS_CONFIG`) | Mới. Cùng thư mục mặc định với `HYBRID_HANDS_STATE_DIR` |
| 3 | Repo `<git toplevel>/.claude/hybrid-hands.json` | Giữ nguyên, kể cả đường dự phòng về repo chính khi chạy trong worktree (`hand_ext/config.py:83-93`) |
| 4 | Cờ CLI | Giữ nguyên, luôn thắng |

- **Merge:** dict merge sâu theo key, ví dụ `ext_hand.backends.codex.effort` ở repo chỉ đè đúng key đó. List như `ext_hand.order` và `claude_args` bị thay nguyên.
- **Đường dẫn tương đối** ở cả global và repo đều tính từ repo hiện tại, như hiện nay.
- **Thiếu file global:** bỏ qua, không lỗi.
- **File global hỏng** (JSON sai, sai kiểu): báo lỗi kèm đường dẫn và thoát khác 0, không âm thầm bỏ qua. Lý do: bỏ qua sẽ chạy với backend người dùng không chọn.
- Các kiểm tra hiện có (`max_parallel` 1..4, guard `v1` ≥5%/ngày) áp lên kết quả sau merge.

### 1.2 Một bộ nạp chung

- Một hàm duy nhất đọc và merge các tầng, trả dict kèm bản đồ nguồn của từng key. `hand_ext.load_config`, `side_session.load_config` và các chỗ đọc của `hh_ps` (`registry_source.py:51-60`, `repos.py:71-80`, `codex.py:420`, `limits.py:31-35`, `hand_ext/report.py:136-140`, `run_cmd.py:218-221`) đều gọi hàm này. Không còn chỗ nào tự `json.loads` file cấu hình.
- `hand-ext config --json` in cấu hình hiệu lực cùng nguồn từng key. Cấu hình không chứa secret, nhưng lệnh vẫn không in nội dung file auth mà `config_dir` trỏ tới.

## 2. Key mới

### 2.1 Phiên chính: mục `main_session`

| Key | Mặc định | Dùng khi |
|---|---|---|
| `provider` | `codex` | `side-session start --main` không có `--provider` |
| `codex_model` / `codex_effort` | `gpt-6.1-sol` / `high` | provider codex |
| `claude_model` / `claude_effort` / `claude_account` | `claude-opus-5-5` / `high` / `v1` | provider claude |

- `--main` thôi mượn `side_session.codex_model/codex_effort` (`paseo.py:267-268`).
- Phiên chính Opus mà người dùng tự mở bằng `claude` không đi qua side-session nên không đọc mục này. Mục này chỉ áp cho `--main`.

### 2.2 Phiên phụ: thêm vào `side_session`

| Key | Mặc định | Thay cho |
|---|---|---|
| `provider` | `codex` | Giá trị viết cứng ở `side_session/cli.py:70-74`. `--resume` vẫn là claude |
| `claude_model` / `claude_effort` | `claude-opus-5-5` / `high` | Hằng ở `constants.py:176-177` |
| `claude_account` | `v1` | Account mặc định khi `--provider claude` không có `--account` |

- Giữ `codex_model` và `codex_effort`. Provider dsh vẫn để hand-ext của repo tự quyết model/effort.

### 2.3 Hand và subagent: thêm `ext_hand.native`

```json
"native": {"claude": "auto", "codex": "auto"}
```

- `auto`: cho phép subagent native khi đủ điều kiện Ngoại lệ A (cùng account, đúng model/effort, đủ capability). `off`: luôn dùng `hand-ext run`.
- `hand-ext pick --json` trả thêm `native: true|false` và `native_reason`, để brain áp luật native theo kết quả pick, không tự suy.
- **Subagent Claude** (`agents/hand.md`): model/effort nằm cố định trong frontmatter (Opus 5.5, `low`); plugin không đổi được lúc chạy. Nếu `ext_hand.backends.claude-vN` đặt model/effort khác frontmatter thì `pick` trả `native: false` kèm lý do, và hand chạy qua `hand-ext`.
- **Subagent Codex native:** Sol dùng model/effort mà `pick` trả về.
- `claude_accounts` và `backends.*` nay đặt được ở global. Lý do: thư mục cấu hình account là thông tin của máy, không của repo.

## 3. Phiên chính Sol nhận đủ policy

Hook Claude không chạy trên Codex. Hiện phiên chính Sol chỉ nhận AGENTS.md (Codex tự đọc) và `templates/main-session-prompt-codex.md`. Template này thiếu ba thứ mà phiên Claude có, nên bổ sung vào template:

1. **Đường dẫn tuyệt đối** của `hand-ext`, `side-session`, `hh-ps`, điền như template phiên phụ codex (`commands.py:15,104`), thay vì trông vào PATH.
2. **Khuôn brief** nguyên văn từ `templates/hand-brief.md`.
3. **Đường dẫn tuyệt đối** của `skills/ext-hand/SKILL.md` và `skills/side-session/SKILL.md`, để Sol đọc khi cần. Không cài skill vào `~/.codex-hand`.

- Câu mở đầu template ghi model/effort thực tế của phiên, không viết cứng "gpt-6.1-sol high".
- Không đổi: env `CODEX_HOME`, `HYBRID_HANDS_HAND_SCOPE`, đường Paseo `codex-hand`.

## 4. Phiên Claude chạy dưới Paseo

Từ 09/11/2026 người dùng chuyển các phiên Opus của repo này sang agent Paseo, để xem trên Paseo. Phiên Opus chuyển bằng `/to-paseo` (`cc-switch paseo --self`) vẫn là Claude Code, nên hook, skill và subagent `hybrid-hands:hand` vẫn chạy. Ba chỗ cần sửa:

1. **side-session chưa mở được phiên Claude trên Paseo.** Đường Paseo hiện chỉ dành cho codex (`actions.py:164`, `paseo.py:201`); `--provider claude` (kể cả `--main`) chạy trong `screen`. Thêm key `transport` (`paseo` | `screen`) vào `main_session` và `side_session` cho provider claude, mặc định `paseo`. Nếu Paseo lỗi thì báo lỗi, không tự lùi về `screen`, giống codex.
2. **Account khi chạy dưới Paseo.** Phiên Claude mở qua Paseo phải nhận `CLAUDE_CONFIG_DIR` của account đã chọn (`claude_account` hoặc `--account`) qua `env` khi tạo agent, giống `CODEX_HOME` của codex (`paseo.py:122`). `lib/cc_switch` hiện không xử lý account nào. Gói E phải kiểm tra trước: khi chuyển phiên `v2` sang Paseo, phiên có giữ đúng thư mục account không. Nếu không giữ thì sửa cho giữ.
3. **Tầng global dưới Paseo.** Agent do daemon Paseo sinh ra dùng môi trường của daemon, không dùng môi trường của shell người dùng. Vì vậy tầng global dựa vào đường dẫn cố định `~/.hybrid-hands/config.json`. `HYBRID_HANDS_CONFIG` chỉ có tác dụng khi daemon cũng có biến này; `hand-ext config --json` phải ghi rõ file global nào đã được đọc.

- Không đổi: cách gắn cha theo `PASEO_AGENT_ID`/`CODEX_THREAD_ID` ở `run_cmd.py:214-226`. Gói A chỉ thay phần đọc file cấu hình ở đó.

## 5. Bảo mật các runtime

Nguồn: khảo sát chỉ đọc ngày 09/11/2026, báo cáo ở `output/llm/hand-ext/20261109-141449-391490-security-survey-claude-v1/report.md`. Phần này thuộc nhóm "bảo mật chống tấn công từ ngoài", nên dùng mức test kỹ.

### 5.1 Hiện trạng và rủi ro, xếp theo mức nghiêm trọng

| # | Runtime | Hiện trạng | Rủi ro |
|---|---|---|---|
| 1 | Paseo + Codex Sol | Relay bật. Agent do plugin tạo chạy `danger-full-access`, không hỏi quyền (`paseo.py:110-111`) | Ai chiếm được điện thoại đã ghép hoặc keypair của daemon thì có shell không sandbox trên máy |
| 2 | Codex Sol | `--dangerously-bypass-approvals-and-sandbox` (`commands.py:83`). Không có `shell_environment_policy` | Sol đọc được `.env`, `auth.json`, mọi file trong HOME; mọi biến `*_TOKEN` của shell cha lọt vào lệnh shell |
| 3 | Claude v1 | `defaultMode=bypassPermissions`, `deny=[]`, không sandbox; chỉ có hook `env-guard`. Phiên phụ Claude cũng chạy `bypassPermissions` (`side_session/constants.py:46`) | Hook vòng qua được bằng `python`/`node -e`. Credential trong `~/.claude*`, `~/.codex-hand`, `~/.paseo` không bị chặn |
| 4 | Claude v2 | Có deny `Read/Edit(**/.env*)`, nhưng allow toàn bộ Bash và WebFetch | `Bash(cat .env)` không bị chặn; WebFetch là đường gửi dữ liệu ra ngoài |
| 5 | dsh | Đã chạy từ thư mục rỗng, có sandbox fs/bash theo workspace, lọc env `DEEPSEEK_*` (`dsh.py:285-305`) | Chưa kiểm chứng: key Go có lọt vào lệnh bash của hand không; bash có đọc được ngoài workspace không; network có mở không |

Hand-ext Codex và Claude đã lọc biến API key (`codex.py:125`, `claude.py:75-78`) và chạy có sandbox. Tầng hand an toàn hơn tầng phiên.

### 5.2 Nguyên tắc

1. **Plugin chỉ kiểm soát những gì nó khởi chạy**, bằng cờ CLI, override `-c` của Codex, `--settings` của Claude Code, `env` và `providerOptions` của Paseo. Plugin không sửa `~/.claude/settings.json`, `~/.codex-hand/config.toml`, `~/.paseo/config.json`.
2. **Phần plugin không khởi chạy** (phiên Opus bạn tự mở, daemon Paseo, file cấu hình người dùng): plugin chỉ kiểm tra và báo, kèm đoạn cấu hình đề xuất. Người dùng tự áp.
3. **Mặc định an toàn.** Nới quyền phải bật tường minh trong cấu hình global hoặc repo; `hand-ext config --json` hiện rõ chỗ nào đang nới.
4. **Lọc env chung** cho mọi runtime: bỏ biến có tên khớp `KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH`, trừ danh sách cho phép mà runtime cần.

### 5.3 Mục cấu hình `security`

| Key | Mặc định | Áp cho |
|---|---|---|
| `security.env_deny_patterns` / `env_allow` | Mẫu ở 5.2 / `[]` | Mọi tiến trình plugin khởi chạy |
| `security.deny_paths` | `**/.env*`, `**/auth.json`, `~/.claude*/.credentials*`, `~/.codex*/auth.json`, `~/.paseo/**`, `~/.dsh-hand/*.key` | Claude (`--settings` deny Read/Edit và `Bash(cat/head/…)`), Codex và dsh qua sandbox đọc nếu runtime hỗ trợ |
| `security.codex.session_sandbox` | `workspace-write`, kèm `writable_roots` gồm repo, `worktree_root`, thư mục state | Phiên Sol chính/phụ (thay cờ bypass), cả đường Paseo |
| `security.codex.network` | `true` (Sol cần mạng để gọi hand) | Phiên Sol |
| `security.codex.env_policy` | `inherit=core`, exclude theo mẫu 5.2 | Override `shell_environment_policy` qua `-c` |
| `security.claude.session_permission_mode` | `acceptEdits`; `bypassPermissions` phải bật tường minh | Phiên Claude chính/phụ do side-session mở |
| `security.claude.sandbox` | bật | Phiên và hand Claude, qua `--settings` |
| `security.claude.hand_webfetch` | `false` | Hand Claude |
| `security.dsh.network` | `false`, trừ khi có `--browser` | Hand dsh |
| `security.paseo.agent_sandbox` | theo `security.codex.session_sandbox` | `providerOptions` khi tạo agent, gồm cả hand-ext `--mode paseo` (merge `e077e8a`, `lib/hand_ext/paseo_transport.py`) |
| `security.allow_unsafe` | `false` | Công tắc duy nhất cho phép quay về chế độ bypass cũ, `hand-ext config` cảnh báo khi bật |

Tên key Claude `--settings`/sandbox và khả năng chặn đọc của Codex/dsh phải được gói S0 xác minh với phiên bản đang cài trước khi chốt. Key nào runtime không hỗ trợ thì bỏ và ghi lý do, không giả lập.

### 5.4 Lệnh kiểm tra bảo mật

`hand-ext doctor --security` chỉ đọc, kiểm tra:
- Claude v1/v2: `defaultMode`, `skipDangerousModePermissionPrompt`, `deny`, sandbox, hook env-guard.
- Codex `~/.codex-hand` và `~/.codex`: `sandbox_mode`, `approval_policy`, `shell_environment_policy`.
- Paseo: `relay`, `listen`, `allowedOrigins`.
- dsh: sandbox và network.

Lệnh chỉ in tên key và trạng thái `ok`/`cảnh báo`, không in giá trị của key khác hay key có tên dạng secret. Mỗi cảnh báo kèm đoạn cấu hình đề xuất để người dùng tự áp.

### 5.5 Kiểm chứng mức kỹ

- **Thử thoát bằng canary:** tạo file `.env` giả và biến env giả (giá trị ngẫu nhiên, không phải secret thật) trong thư mục test. Với mỗi runtime (phiên Sol, phiên Claude, hand codex/claude/dsh), lệnh đọc canary bằng Read, `cat`, `python -c` và `env` phải thất bại hoặc không thấy giá trị.
- **SAST:** `bandit` cho `lib/`, `semgrep` nếu đã có sẵn trên máy.
- **Quét dependency:** `pip-audit` và `npm audit` cho bridge Paseo, nếu công cụ đã có sẵn, không tải gói trả phí.
- **DAST:** dự án không có staging. Thay bằng kiểm tra daemon Paseo chỉ nghe `127.0.0.1` và lệnh audit báo đúng trạng thái relay.

## 6. Ngoài phạm vi

- Env riêng cho từng key (ví dụ `HYBRID_HANDS_SIDE_PROVIDER`). Chỉ thêm `HYBRID_HANDS_CONFIG`.
- Đổi model/account giữa phiên. Luật mở phiên mới từ bàn giao giữ nguyên.
- Sinh hoặc ghi đè file agent để đổi effort của subagent Claude.
- `statusline/` và `hh-tree-pane`.

## 7. Quyết định

### 7.1 Đã duyệt (09/11/2026)

1. File global `~/.hybrid-hands/config.json`.
2. File global hỏng thì báo lỗi và dừng.
3. `--main` mặc định provider `codex`.
4. Phiên Claude mặc định transport `paseo`.

### 7.2 Chờ duyệt: bảo mật (mục 5)

1. **Relay Paseo:** đề xuất giữ relay (cần để dùng điện thoại ngoài mạng LAN), giảm rủi ro bằng cách sandbox agent. Phương án khác là tắt relay, chỉ dùng trong LAN.
2. **Sandbox phiên Sol:** đề xuất bật `workspace-write` làm mặc định nếu gói S0 chứng minh Sol trong sandbox vẫn gọi được mọi hand. Nếu S0 thất bại một phần thì Opus báo lại để người dùng quyết.
3. **Phiên Opus v1 bạn tự mở** (`bypassPermissions`, `deny` rỗng): plugin không sửa. `doctor --security` in đoạn cấu hình đề xuất để người dùng tự áp.
