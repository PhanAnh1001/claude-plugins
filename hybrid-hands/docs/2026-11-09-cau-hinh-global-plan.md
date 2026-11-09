# Plan: cấu hình global và key riêng cho phiên chính, phiên phụ, subagent

## Tóm tắt

- **Spec:** `2026-11-09-cau-hinh-global-spec.md`. Trạng thái: chờ người dùng duyệt spec.
- **Giao việc:** gói A (đang chạy, phiên `cfg-goi-a`) trước; B, C, E, S0 song song sau khi A merge (khác file; S0 chỉ thử nghiệm, không sửa code); S1a/S1b/S1c song song sau khi người dùng duyệt 7.2; S2 đang chạy; S3 sau khi người dùng khai báo provider Paseo; phần D Opus tự làm cuối. Tối đa 4 phiên Sol cùng lúc.
- **Mức test:** tối thiểu cho A/B/C/E (≤3 ca mỗi gói); kỹ cho S0/S1a/S1b/S1c/S2/S3 (canary, SAST, quét dependency). Full suite chạy đúng một lần ở cuối, trên một hand riêng.
- **Release:** hybrid-hands 0.34.0, cập nhật cài đặt plugin qua công cụ chính thức ở mọi repo đang dùng.

## Gói A: bộ nạp cấu hình chung (Sol)

- [x] Hàm merge tầng plugin → global → repo, merge sâu dict, kèm bản đồ nguồn; hỗ trợ `HYBRID_HANDS_CONFIG`; file global hỏng thì lỗi kèm đường dẫn.
- [x] `hand_ext.load_config`, `side_session.load_config` và các chỗ đọc của hh_ps, report, run_cmd dùng hàm chung.
- [x] Lệnh `hand-ext config --json`.
- [x] Ca test: global < repo < CLI cho `ext_hand.backends.codex.effort`; thiếu file global; file global hỏng.

## Gói B: side-session (Sol, sau A)

- [x] Mục `main_session` và các key `side_session.provider`, `claude_model`, `claude_effort`, `claude_account`; bỏ phần viết cứng ở `cli.py:70-74` và `constants.py:176-177`.
- [x] Template `main-session-prompt-codex.md`: đường dẫn bin tuyệt đối, khuôn brief, đường dẫn SKILL.md, model/effort thực tế.
- [x] Key `transport` cho provider claude (mặc định `paseo`). Mở phiên Claude chính/phụ qua Paseo với model, effort, `CLAUDE_CONFIG_DIR` của account; Paseo lỗi thì báo lỗi, không lùi về `screen`. Bước đầu: xác nhận provider Claude của Paseo nhận được `env`/model/effort, ghi kết quả vào bàn giao.
- [x] Ca test: `--main --dry-run` lấy model từ `main_session`; `start --provider claude --account v2 --dry-run` dựng lệnh Paseo có `CLAUDE_CONFIG_DIR` của v2; template có đường dẫn `hand-ext` tuyệt đối.

## Gói C: native trong pick (Sol, sau A)

- [x] `ext_hand.native` (`auto`/`off`); `pick --json` trả `native`, `native_reason`; so model/effort backend Claude với frontmatter `agents/hand.md`.
- [x] Ca test: `native.claude=off` → `native:false`; effort backend khác frontmatter → `native:false`.

## Gói E: cc-switch giữ account (Sol, sau A)

- [x] Kiểm tra `cc-switch paseo --self` với phiên đang chạy account `v2`: phiên mở lại trên Paseo dùng thư mục account nào. Nếu không phải `v2` thì truyền `CLAUDE_CONFIG_DIR` của phiên hiện tại sang agent Paseo.
- [x] Ca test: phiên có `CLAUDE_CONFIG_DIR=~/.claude-hand` → lời gọi tạo agent Paseo mang đúng biến đó.

## Gói S0: xác minh khả năng sandbox (Sol, sau A; chỉ dùng canary giả)

- [x] Sol Codex chạy `workspace-write` + `writable_roots` (repo, `worktree_root`, thư mục state) + network: vẫn chạy được `hand-ext run` với dsh, codex, claude-v1 và `side-session start --dry-run`.
- [x] Claude Code bản đang cài: tên key `--settings` cho deny và sandbox; deny chặn được `cat`/`python -c` đọc canary chưa.
- [x] Codex: `-c shell_environment_policy...` lọc được biến canary; sandbox có chặn đọc ngoài workspace không.
- [x] dsh: biến key có lọt vào bash của hand không; network bash có mở không.
- [x] Bàn giao: ma trận runtime × biện pháp → được/không, kèm lệnh đã chạy. Opus chốt mặc định mục 5.4 theo ma trận. Kết quả: seatbelt không lồng được, xem spec 5.3.

> **Tạm dừng (09/11/2026):** người dùng dừng mọi gói bảo mật (S1a, S1b, S1c, S2, S3 và kiểm chứng bảo mật). Phần D chỉ phát hành A, B, C, E.

## Gói S1a: Claude (Sol, sau duyệt 7.2)

- [ ] Phiên Claude chính/phụ (screen và Paseo `modeId`) theo `security.claude.session_permission_mode`; `--settings` sandbox + `permissions.deny` + `credentials.envVars` cho phiên và hand Claude; hand tắt WebFetch. Xác minh `excludedCommands` cho bin plugin trong phiên có sandbox.
- [ ] Ca test kỹ: canary `.env`/env giả không đọc được qua Read, `cat`, `python -c` ở hand Claude; phiên có sandbox vẫn gọi được `hand-ext pick`; `allow_unsafe=false` thì dry-run không còn `bypassPermissions`.

## Gói S1b: Codex (Sol, song song S1a)

- [ ] Phiên Sol `session_mode=trusted` với `shell_environment_policy` core + exclude; hand codex dùng profile `-P` deny đọc `deny_paths`.
- [ ] Ca test kỹ: biến canary không tới lệnh shell của Sol và hand codex; hand codex không đọc được canary ở đường dẫn deny.

## Gói S1c: dsh (Sol, song song S1a)

- [ ] `sandbox-exec` cả tiến trình dsh với deny đọc `deny_paths`, key Go truyền qua env do wrapper cấp; Bash con tắt mạng trừ `--browser`.
- [ ] Ca test kỹ: tool Read gốc và Bash của dsh không đọc được canary ở đường dẫn deny; dsh vẫn xác thực và chạy xong brief nhỏ.

## Gói S3: Sol sandboxed (Sol, sau khi người dùng khai báo provider `hh-hand`)

- [ ] `session_mode=sandboxed`: Sol `workspace-write` + mạng `127.0.0.1`, hand bắt buộc `--mode paseo`; đổi mặc định sang `sandboxed` khi chạy hoàn tất được.
- [ ] Ca test kỹ: Sol không đọc được canary ở đường dẫn deny; hand qua Paseo chạy xong và báo cáo về.

## Gói S2: `hand-ext doctor --security` (Sol, song song S1)

- [ ] Kiểm tra chỉ đọc theo spec mục 5.5; chỉ in tên key và `ok`/`cảnh báo`, kèm đoạn cấu hình đề xuất.
- [ ] Ca test với fixture giả: file settings có `bypassPermissions` → cảnh báo; key dạng secret không bao giờ xuất hiện giá trị trong output.

## Kiểm chứng bảo mật (Opus giao một hand riêng, cuối)

- [ ] `bandit` cho `lib/`; `pip-audit`, `npm audit` cho bridge Paseo nếu công cụ có sẵn; kiểm tra daemon Paseo chỉ nghe `127.0.0.1`.

## Phần D: Opus

- [ ] AGENTS.md repo, template policy, README, skill side-session/ext-hand: bỏ luật "không có nguồn user config", mô tả tầng global và key mới.
- [ ] Đọc bàn giao A, B, C; chạy full suite một lần; tăng version 0.34.0 cùng CHANGELOG; commit, merge `main`, push; cập nhật cài đặt plugin và kiểm version đã nạp.
