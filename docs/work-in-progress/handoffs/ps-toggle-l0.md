## Tóm tắt
- Kết quả: xong L0, hybrid-hands 0.37.1; lệnh cuối `hand-ext parallel [on|off]`, không cần alias `psa`.
- Ví dụ: `hand-ext parallel`; `hand-ext parallel --json`; `hand-ext parallel on|off --cwd /duong/dan/repo` (chỉ sau khi người dùng chốt).
- Commit `899c6c48a662e0efbb8090ea1589648dccb5d55e`; merge `c68f0e9ed376ec3a2ea021589baf948f80f210d7`, đã push nhánh và main.
- `lib/hand_ext/cli.py`, `parallel_cmd.py`: thêm trạng thái/provenance và ghi config atomic đúng fallback worktree, giữ key/thứ tự.
- `tests/test_hand_parallel_cmd.py`: 3 ca trong thư mục tạm, gồm preservation/fallback/global warning, off idempotent, config lỗi không đổi.
- `AGENTS.md`, `hybrid-hands/README.md`: làm rõ cấm sửa config chỉ trong usage panel, hướng dẫn đổi mode qua lệnh sau khi người dùng chốt.
- `plugins/hybrid-hands/CHANGELOG.md`, `.claude-plugin/plugin.json`: release 0.37.1; marketplace không mang version nên giữ nguyên.
- Test mới 3/3 pass; `test_policy_mode.py` 3/3 pass; JSON manifests, plugin/marketplace validate và diff check đạt.
- Review Sol đạt; managed hand Codex/low exit 0, review-approved và archived exact child; không cần fallback hay sửa lại qua review.
- Cập nhật chính thức scope user v1/v2 0.37.0 → 0.37.1; xác minh version/path trên 14 repo (28 lượt); chi tiết và evidence bên dưới.
- Config thật giữ nguyên, không bật mode thật; file untracked có sẵn giữ nguyên. Cần reload/mở phiên mới để hook nạp luật.
- Chưa chạy full suite theo brief; chưa toggle trên repo thật theo lệnh cấm; validate có thông báo catalog LICENSE/icon thiếu sẵn, validation chính vẫn pass.

## Triển khai và review
Đã đọc AGENTS.md áp dụng; không có AGENTS/CLAUDE con cho hybrid-hands. `hand-ext pick --json` chọn codex / gpt-6.1-sol / low / account gpt, native eligible. Repo đang opt-in `ext_hand.mode=auto`, nên giao bằng managed hand:

```sh
hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --mode paseo-required --brief /Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/ps-toggle-l0-hand-brief.md --cwd /Users/anhtp/app/claude-plugins --label ps-toggle-l0 --keep-worktree
```

Exit 0, không gặp PARENT_REQUIRED, không fallback shell, không tự viết code/test/tài liệu tính năng. Brief có đủ luật dữ liệu nguyên văn. Sol đã đọc report và toàn bộ diff, kể cả hai file mới, đối chiếu yêu cầu và chạy lại kiểm chứng hẹp. Không có lỗi cần giao lại. Hand từng sửa fixture đường dẫn macOS sau một test fail trong quá trình tự kiểm tra; bản cuối trên repo chính chạy đủ 3 test đều pass.

- Key: `772e3df8-4f79-445c-924b-3e8b43c8f4cb:3122d6e1-7b33-4b9d-a1bc-ef85893fdd64:1`.
- Agent: `b93daf80-4788-49cf-bfc7-79f5768ace24`; workspace: `wks_4558af48238a3364`.
- `hand-ext managed review-approve` exit 0, review_approved=true; `managed archive` exit 0, state=archived, không warning.
- Report: `/Users/anhtp/app/claude-plugins/output/llm/hand-ext/20261110-090145-772710-ps-toggle-l0-codex/b294f7e01ff386da6a55666e8b3908f082fb02d6aa04839e174611a8c237043b/report.md`.
- Worktree giữ lại: `/Users/anhtp/.hybrid-hands/worktrees/claude-plugins-20261110-090145-772710-ps-toggle-l0-codex`.
- Không tạo hay để lại tiến trình nền đang chạy từ phiên này; artifacts/history/worktree/output giữ nguyên. Token/USD/quota không đọc: `?`.

Lệnh dùng shared loader để lấy trạng thái và đường dẫn repo/fallback, raw-read file đích để không làm mất key/sibling do normalization. Ghi cùng thư mục bằng file tạm, flush/fsync rồi os.replace; dọn file tạm khi lỗi. JSON hỏng/root không object/section không object đều bị từ chối, nonzero, giữ bytes. Trạng thái default in nguồn file `lib/shared_config.py`; global true vẫn cảnh báo và off/global. `--json` chỉ xuất dữ liệu liên quan mode, không dump config khác. Không thêm khóa hay thay slots/order/config thật.

## Kiểm chứng thực tế
Tất cả lệnh sau chạy tại `/Users/anhtp/app/claude-plugins`:

```sh
python3 -m unittest discover -s hybrid-hands/tests -p test_hand_parallel_cmd.py
# Ran 3 tests in 0.232s — OK, exit 0
python3 -m unittest discover -s hybrid-hands/tests -p test_policy_mode.py
# Ran 3 tests in 3.380s — OK, exit 0
claude plugin validate hybrid-hands/plugins/hybrid-hands
# Validation passed, exit 0
claude plugin validate hybrid-hands
# Validation passed, exit 0
git diff --check
# Không output, exit 0
hybrid-hands/plugins/hybrid-hands/bin/hand-ext parallel
# parallel_subagents: off (nguồn: default, file: /Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/lib/shared_config.py)
```

Hai JSON manifest được parse thành công, version plugin đúng 0.37.1; source tương đối trong marketplace resolve tồn tại. Phần README/AGENTS sửa không thêm Markdown link mới. Plugin validate có advisory directory-check: LICENSE_MISSING và ICON_MISSING có từ trước; không tự thêm license/icon ngoài brief. Đây không phải lỗi validation chính (exit 0). Test policy có warning global true dự kiến.

SHA256 `.claude/hybrid-hands.json` thật trước/sau trùng `6125a7026b05f84427a0d92a79c59c6eae68e414de3bd85e1d26c12dac81342f`; không in nội dung config. Không chạy parallel on/off ở repo thật. Không chạy full suite, không sửa parallel-subagents/statusline/settings/credential, không chỉnh thủ công installed_plugins.json, không xóa/di chuyển output/llm/ hay file WIP có sẵn.

## Git và phát hành
- Branch: `feat/ps-toggle-l0-0371`, đã push origin và giữ lại.
- Commit tính năng: `899c6c48a662e0efbb8090ea1589648dccb5d55e`.
- Merge: `c68f0e9ed376ec3a2ea021589baf948f80f210d7` (origin/main cùng SHA).
- `git fetch origin` trước phát hành: local main và origin/main đều `39a9e4a8f6fef148d0f53c9ca6ce0d6c45fd1e6c`.
- Commit 7 file đúng phạm vi, push nhánh, `git merge --no-ff ...` vào main, push main thành công.
- Kết thúc: main đồng bộ origin/main; chỉ còn các thư mục/file docs/work-in-progress untracked được giữ lại.

## Cập nhật cài đặt chính thức và xác minh
Đã chạy dưới v1 (mặc định `~/.claude`) và v2 (`CLAUDE_CONFIG_DIR=/Users/anhtp/.claude-hand`):

```sh
claude plugin marketplace update hybrid-hands-local --json
claude plugin update hybrid-hands@hybrid-hands-local --scope user --json
```

Cả 4 lệnh exit 0, updateOutcome=updated, oldVersion=0.37.0, newVersion=0.37.1. Chỉ cập nhật installation đang tồn tại ở scope user, không enable ở repo nào. Plugin list cho tất cả repo tìm thấy chỉ có installation user này; không có project/local installation riêng phải update.

Sau update, chạy `claude plugin list --json` tại từng repo cho cả hai account, kiểm version/folderVersion=0.37.1, scope=user, readFromFolder đúng source; đọc manifest ở installPath và readFromFolder để xác minh version, kiểm file parallel_cmd.py tồn tại. Tổng 28/28 check pass.

- Đường dẫn source được CLI báo sẽ nạp: `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands`.
- Cache v1: `/Users/anhtp/.claude/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.1`.
- Cache v2: `/Users/anhtp/.claude-hand/plugins/cache/hybrid-hands-local/hybrid-hands/0.37.1`.
- Evidence metadata từng repo/account: [ps-toggle-l0-install-verification.json](ps-toggle-l0-install-verification.json).

14 repo đã xác minh, đều dưới `/Users/anhtp/app/`: ai-comic-video, ai-luxian, ai-practice-english, claude-plugins, codex-plugins, common-modules, hrm-open-sources, live-tiktok-games, live-tiktok-games-preview-publish, skill-key, slt-ocr-pro, tcp-assistant, tcp-assistant-main, team-ai-gitops. Update scope user cũng áp dụng các repo khác dùng cùng installation; chỉ 14 repo trên đã được kiểm riêng bằng CLI.

## Việc còn lại và giới hạn
Không còn hạng mục code/phát hành/cập nhật cài đặt trong brief. Operator cần reload/mở phiên mới ở các phiên đang chạy; luật đã nạp không tự hot-load. Chưa chứng minh hook mới trong một phiên mới sau update, không tự restart phiên của người dùng. Không chạy on/off trên repo thật; đường ghi chỉ kiểm chứng bằng fixture tạm. Không full suite theo brief. Thông báo LICENSE/icon của catalog nằm ngoài phạm vi L0 này.
