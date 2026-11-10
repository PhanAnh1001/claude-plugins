# Executor brief: hand-ext parallel, release 0.37.1 (L0)
You are a hand executor, not Sol. Read applicable AGENTS.md first. Work directly; do not call hand-ext, side-session, subagents, other sessions or review another hand. Do not commit/push/merge or update installations. Sol reviews and releases. Only public code/synthetic fixtures. Preserve unrelated changes and all docs/work-in-progress/*.

## Data rules (verbatim)
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## PHẠM VI GHI
- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/; lib/shared_config.py only if needed helper
- hybrid-hands/tests/ new narrow test file
- hybrid-hands/README.md; hybrid-hands/plugins/hybrid-hands/CHANGELOG.md; hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json; marketplace manifest if it carries version
- AGENTS.md at repo root (minimal changes around lines 26/31/37)
Do NOT modify real .claude/hybrid-hands.json in any repo, even by new command. Only tests may write config in temporary directories. Do NOT touch parallel-subagents/, statusline/, credential/settings/installed_plugins.json; do NOT delete/move output/llm/. Do not read real transcripts/logs.

## Acceptance criteria
1. Add `hand-ext parallel [on|off]` (name available; otherwise psa with explanation). No action prints `parallel_subagents: on|off (nguồn: <default|global|repo>, file: <path>)` based on effective shared config/provenance, warnings include ignored global true. Support --cwd like config, --json for status (existing convention). Map plugin source to default and meaningful default file path. Do not dump unrelated config.
2. on/off writes exactly bool at parallel_subagents.enabled, preserves other keys and insertion order (including sibling keys in section), UTF-8 indent 2 + final newline, atomic same-directory temporary file + rename, clean temp on failure. Existing JSON invalid/non-object or invalid section must fail with path and nonzero, unchanged. Create .claude/file when missing. Use exact loader config path including main-checkout fallback when called in linked worktree. Idempotent. Print explicit written path and `mở phiên mới để hook nạp luật`. Do not toggle any real repo during development.
3. Minimal AGENTS edit: split usage-panel-specific ban from general policy. Make it clear the ban on listed config/settings files applies only in usage panel work. `parallel_subagents` only changed through `hand-ext parallel on|off` after user approval per repo; brain/hand cannot enable on their own. Keep lines 26 and 37 consistent, add command at line 37. Legacy parallel-subagents stays off.
4. README parallel_subagents section: replace manual JSON edit instructions with new commands/status/json and new-session reminder, explain fallback write path. Bump version to 0.37.1 + changelog, marketplace only if version present.

## Acceptance tests (at most 3 test methods/functions, no extra tests)
(a) `on` preserves unrelated keys/order and section sibling, status on/repo; include synthetic linked-worktree fallback and global-true warning/status subcases in same method if useful.
(b) `off` creates absent config and is idempotent.
(c) malformed JSON => nonzero, path included, exact bytes unchanged; non-object/invalid section can be subcases here.
Run ONLY new test file + hybrid-hands/tests/test_policy_mode.py (no full suite), e.g. python3 -m unittest discover ... separate runs if needed. JSON validate manifests. Report exact tests/results and changed files, no claims about installations. Do not add documentation tests.
