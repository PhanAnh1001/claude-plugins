# GPT sources core report

Implemented in lib/hh_ps/: models.py, codex.py, native_source.py, machine_usage.py, render.py, compact.py, live_rate.py, usage_enrichment.py. Added tests/test_hh_ps_gpt_nguon.py with exactly three test methods. No existing test assertions changed.

- Appended Usage.week_pct_source default empty. Same-rollout session/native weekly measurements require at least two valid timestamped explicit 10080-minute samples. All samples must be nondecreasing, have the same current reset and valid bounded numeric percentages. Missing/broken/future/undated/changed-reset samples leave unknown; zero is measured. JSON only emits source when nonempty; text labels `riêng (đo)`. Account enrichment preserves measurement. Measurements describe account movement during the interval, so may include concurrent work.
- Machine USD sums timestamped cumulative counter deltas in the active weekly reset window, sessions and archives merged/deduplicated by thread/events, no ledger addition. Metadata-only threads no longer poison the observed sum; no in-window token events remains None. Existing baseline, mixed counter-reset, invalid cached delta, unknown price, unreadable source protections retained. Source now `codex_rollout_observed_deltas` to identify observed-events coverage. No last_token_usage fallback was introduced because the available fixtures do not evidence complete coverage without a cumulative baseline.
- GPT samples validate raw numeric percentages, sample timestamps and active window coverage; account windows preserve legacy primary=5h/secondary=weekly mapping when duration is missing, but only inspect primary/secondary and reject malformed or unknown explicit durations; measured weekly quota always requires explicit 10080 minutes; removed arbitrary TTL during Sol review. Claude cache/live samples accept ISO or numeric reset values through to_epoch, preserve existing 1800-second freshness policy, reject future/stale/expired/invalid samples. Actual Claude 5h samples also emit a Limit row with source claude_5h_cache or claude_5h_live, and work for tokenless rows. Presenter APIs _five_hour and load_codex unchanged.
- Pinned session USD resolves the actual rollout model instead of assigning the default model price to an unknown model. Prices remain canonical; no price table added.

Narrow verification (final run):

```text
python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_gpt_nguon.py
Ran 3 tests in 0.015s — OK
python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_codex.py
Ran 1 test in 0.063s — OK
python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_native.py
Ran 2 tests in 0.143s — OK
python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_limits.py
Ran 15 tests in 0.454s — OK
```

Initial test run exposed frozen Usage assignments; corrected with dataclasses.replace before final passing checks. One initial shell command used unavailable `python` (exit 127); subsequent commands used python3. No full suite, real rollouts/transcripts, hh-ps runtime, network, installation or daemon operations performed.

Lead policy applied: legacy account samples missing duration retain primary=5h/secondary=weekly compatibility. Measured weekly movement requires explicit duration, so the same legacy weekly samples never produce a per-session/native measured share. Malformed/unknown explicit durations never use fallback; nested non-window metadata is ignored. The existing three-method test file covers both compatibility and measurement exclusion. Final narrow stdout/stderr with actual commands and exit codes is saved in core-narrow.log. All four commands exited 0 (21 tests total). Machine source label intentionally changed to identify observed-events coverage.

## Repeated-enrichment regression fix

Sol reported the single final full-suite run failed test_hand_usage_panel.HandUsagePanelTest.test_missing_quota_is_unknown (expected None, got retained 23; 420 tests in 63.656s). Root cause: enrichment-created Claude 5h Limits survived a later invalid cache/live sample. Each enrichment pass now removes only rows with generated sources claude_5h_cache/claude_5h_live, then resamples; caller-owned Limit sources remain. No existing expectations or test methods changed.

Actual regression verification, captured in core-regression.log:

```text
python3 -m unittest discover -s hybrid-hands/tests -p test_hand_usage_panel.py
Ran 2 tests in 0.067s — OK (exit 0)
python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_gpt_nguon.py
Ran 3 tests in 0.014s — OK (exit 0)
```

No second full-suite run performed. Full-suite status remains failed pending the lead's gate decision; these narrow results do not establish a green full suite. No installation performed.
