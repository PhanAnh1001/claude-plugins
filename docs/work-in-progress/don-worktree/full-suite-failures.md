# Full suite — lần chạy duy nhất

575 tests, 2 failures, 3 errors; xem full-suite-result.json. Hai errors auto GC đã sửa và test hẹp xanh; không chạy lại full suite.

```text
ERROR: test_account_sync (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_account_sync
Traceback (most recent call last):
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/unittest/loader.py", line 436, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/unittest/loader.py", line 377, in _get_module_from_name
    __import__(name)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/tests/test_account_sync.py", line 7, in <module>
    import pytest
ModuleNotFoundError: No module named 'pytest'
ERROR: test_daemon_absent_falls_back_but_create_failure_does_not (test_side_session_paseo.PaseoStartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/tests/test_side_session_paseo.py", line 425, in test_daemon_absent_falls_back_but_create_failure_does_not
    self.assertEqual(actions.start(cfg, start_args("fallback")), 0)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py", line 215, in start
    disk_result = _worktree_preflight(cfg, a)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py", line 132, in _worktree_preflight
    report = gc.apply(cfg, include_unmerged=False, prune_branches=False,
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 233, in apply
    common = common_dir(cfg.repo)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 139, in common_dir
    return Path(os.fsdecode(git(repo, "rev-parse", "--path-format=absolute",
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 27, in git
    return result.stdout
AttributeError: 'types.SimpleNamespace' object has no attribute 'stdout'
ERROR: test_start_creates_codex_hand_agent_and_stores_live_state (test_side_session_paseo.PaseoStartTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/tests/test_side_session_paseo.py", line 355, in test_start_creates_codex_hand_agent_and_stores_live_state
    self.assertEqual(actions.start(cfg, start_args("n")), 0)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py", line 215, in start
    disk_result = _worktree_preflight(cfg, a)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/actions.py", line 132, in _worktree_preflight
    report = gc.apply(cfg, include_unmerged=False, prune_branches=False,
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 237, in apply
    report = inspect(cfg, name=name)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 168, in inspect
    entries = worktrees(cfg.repo)
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/lib/side_session/gc.py", line 77, in worktrees
    for field in git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0"):
TypeError: must be str or None, not bytes
FAIL: test_data_rule_is_present_in_policy_surfaces (test_hand_ext_isolation.PolicyTextTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/tests/test_hand_ext_isolation.py", line 348, in test_data_rule_is_present_in_policy_surfaces
    self.assertIn("dữ liệu khách hàng", path.read_text(encoding="utf-8"), str(path))
AssertionError: 'dữ liệu khách hàng' not found in '#!/bin/bash\n# SessionStart: shared policy renderer, preserving the stable JSON envelope.\nset -euo pipefail\nROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"\nTEXT="$(python3 "$ROOT/lib/policy_mode.py" session "$ROOT")"\njq -n --arg ctx "$TEXT" \'{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}\'\n' : /Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/plugins/hybrid-hands/scripts/session-start-policy.sh
FAIL: test_inject_policy_has_short_form_and_stays_short (test_policy_brain_context.BrainContextPolicyTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/anhtp/app/claude-plugins-wt/don-worktree/hybrid-hands/tests/test_policy_brain_context.py", line 53, in test_inject_policy_has_short_form_and_stays_short
    self.assertIn(marker, text)
AssertionError: 'AGENTS.md' not found in 'chế độ parallel_subagents bật bởi /Users/anhtp/app/claude-plugins-wt/don-worktree/.claude/hybrid-hands.json\nPOLICY: xem SessionStart. Brain giao subagent backend claude-v1 khác file song song ≤ 4, cùng file/phụ thuộc tuần tự; brain review code hand mình giao. hand-ext pick --json --backend claude-v1 trước mỗi lượt giao; guard v1 thiếu nguồn/chặn thì không spawn. Tài khoản brain `v1`: nếu phiên brain hiện tại không chạy trên `v1` (pick trả native false do khác account) thì dùng `hand-ext run --backend claude-v1` và đề nghị người dùng mở phiên brain mới bằng `side-session start --main --provider claude --account v1`. Brain không tự tra cứu; cấm hiện .env/token/credential.\n'

----------------------------------------------------------------------
Ran 575 tests in 94.874s

FAILED (failures=2, errors=3)
```
