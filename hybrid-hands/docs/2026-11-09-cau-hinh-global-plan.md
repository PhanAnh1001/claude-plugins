# Plan: cấu hình global và key riêng cho phiên chính, phiên phụ, subagent

## Tóm tắt

- **Spec:** `2026-11-09-cau-hinh-global-spec.md`. Trạng thái: chờ người dùng duyệt spec.
- **Giao việc:** gói A (đang chạy, phiên `cfg-goi-a`) trước; B, C, E, S0 song song sau khi A merge (khác file; S0 chỉ thử nghiệm, không sửa code); S1 sau B và S0 (cùng file `side_session/paseo.py`); S2 song song S1; phần D Opus tự làm cuối. Tối đa 4 phiên Sol cùng lúc.
- **Mức test:** tối thiểu cho A/B/C/E (≤3 ca mỗi gói); kỹ cho S0/S1/S2 (canary, SAST, quét dependency). Full suite chạy đúng một lần ở cuối, trên một hand riêng.
- **Release:** hybrid-hands 0.34.0, cập nhật cài đặt plugin qua công cụ chính thức ở mọi repo đang dùng.

## Gói A: bộ nạp cấu hình chung (Sol)

- [ ] Hàm merge tầng plugin → global → repo, merge sâu dict, kèm bản đồ nguồn; hỗ trợ `HYBRID_HANDS_CONFIG`; file global hỏng thì lỗi kèm đường dẫn.
- [ ] `hand_ext.load_config`, `side_session.load_config` và các chỗ đọc của hh_ps, report, run_cmd dùng hàm chung.
- [ ] Lệnh `hand-ext config --json`.
- [ ] Ca test: global < repo < CLI cho `ext_hand.backends.codex.effort`; thiếu file global; file global hỏng.

## Gói B: side-session (Sol, sau A)

- [ ] Mục `main_session` và các key `side_session.provider`, `claude_model`, `claude_effort`, `claude_account`; bỏ phần viết cứng ở `cli.py:70-74` và `constants.py:176-177`.
- [ ] Template `main-session-prompt-codex.md`: đường dẫn bin tuyệt đối, khuôn brief, đường dẫn SKILL.md, model/effort thực tế.
- [ ] Key `transport` cho provider claude (mặc định `paseo`). Mở phiên Claude chính/phụ qua Paseo với model, effort, `CLAUDE_CONFIG_DIR` của account; Paseo lỗi thì báo lỗi, không lùi về `screen`. Bước đầu: xác nhận provider Claude của Paseo nhận được `env`/model/effort, ghi kết quả vào bàn giao.
- [ ] Ca test: `--main --dry-run` lấy model từ `main_session`; `start --provider claude --account v2 --dry-run` dựng lệnh Paseo có `CLAUDE_CONFIG_DIR` của v2; template có đường dẫn `hand-ext` tuyệt đối.

## Gói C: native trong pick (Sol, sau A)

- [ ] `ext_hand.native` (`auto`/`off`); `pick --json` trả `native`, `native_reason`; so model/effort backend Claude với frontmatter `agents/hand.md`.
- [ ] Ca test: `native.claude=off` → `native:false`; effort backend khác frontmatter → `native:false`.

## Gói E: cc-switch giữ account (Sol, sau A)

- [ ] Kiểm tra `cc-switch paseo --self` với phiên đang chạy account `v2`: phiên mở lại trên Paseo dùng thư mục account nào. Nếu không phải `v2` thì truyền `CLAUDE_CONFIG_DIR` của phiên hiện tại sang agent Paseo.
- [ ] Ca test: phiên có `CLAUDE_CONFIG_DIR=~/.claude-hand` → lời gọi tạo agent Paseo mang đúng biến đó.

## Gói S0: xác minh khả năng sandbox (Sol, sau A; chỉ dùng canary giả)

- [ ] Sol Codex chạy `workspace-write` + `writable_roots` (repo, `worktree_root`, thư mục state) + network: vẫn chạy được `hand-ext run` với dsh, codex, claude-v1 và `side-session start --dry-run`.
- [ ] Claude Code bản đang cài: tên key `--settings` cho deny và sandbox; deny chặn được `cat`/`python -c` đọc canary chưa.
- [ ] Codex: `-c shell_environment_policy...` lọc được biến canary; sandbox có chặn đọc ngoài workspace không.
- [ ] dsh: biến key có lọt vào bash của hand không; network bash có mở không.
- [ ] Bàn giao: ma trận runtime × biện pháp → được/không, kèm lệnh đã chạy. Opus chốt mặc định mục 5.3 theo ma trận.

## Gói S1: áp mục `security` khi khởi chạy (Sol, sau B và S0)

- [ ] Đọc mục `security` qua bộ nạp chung; lọc env chung; Sol chính/phụ (screen và Paseo) theo `session_sandbox`/`env_policy`; phiên Claude theo `session_permission_mode` + `--settings` deny/sandbox; hand Claude tắt WebFetch; dsh tắt network trừ `--browser`; `allow_unsafe` để quay về chế độ cũ.
- [ ] Ca test kỹ: canary `.env` và biến env giả không đọc được qua Read, `cat`, `python -c`, `env` ở từng runtime mà S0 xác nhận hỗ trợ; `allow_unsafe=false` thì không còn cờ bypass trong lệnh dựng ra (`--dry-run`).

## Gói S2: `hand-ext doctor --security` (Sol, song song S1)

- [ ] Kiểm tra chỉ đọc theo spec mục 5.4; chỉ in tên key và `ok`/`cảnh báo`, kèm đoạn cấu hình đề xuất.
- [ ] Ca test với fixture giả: file settings có `bypassPermissions` → cảnh báo; key dạng secret không bao giờ xuất hiện giá trị trong output.

## Kiểm chứng bảo mật (Opus giao một hand riêng, cuối)

- [ ] `bandit` cho `lib/`; `pip-audit`, `npm audit` cho bridge Paseo nếu công cụ có sẵn; kiểm tra daemon Paseo chỉ nghe `127.0.0.1`.

## Phần D: Opus

- [ ] AGENTS.md repo, template policy, README, skill side-session/ext-hand: bỏ luật "không có nguồn user config", mô tả tầng global và key mới.
- [ ] Đọc bàn giao A, B, C; chạy full suite một lần; tăng version 0.34.0 cùng CHANGELOG; commit, merge `main`, push; cập nhật cài đặt plugin và kiểm version đã nạp.
