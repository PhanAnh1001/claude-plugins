# Limit watch — approved implementation brief (2026-11-12)

You are the executor hand, not Sol. Implement directly; do not delegate, spawn agents, call hand-ext/side-session to do work, inspect other sessions or review another hand. No commit/push. Read /Users/anhtp/app/claude-plugins/AGENTS.md before changes. Work directly in /Users/anhtp/app/claude-plugins, no worktree. Preserve all existing uncommitted work.

## Approved design and scope

Read /Users/anhtp/.hybrid-hands/briefs/limit-watch-research-2026-11-12.md. Implement Câu 5 without significant redesign. User approved stale Claude fallback: prefer fresh observations; after max(all blocking reset epochs)+buffer, attempt precisely once with label `reset dự kiến`; a quota rejection must not lead to unlimited retries. No user notification. No account rotation, OAuth endpoint, paid API, API key or guard bypass. Preserve Claude v1 day_guard (8%/day) and existing main send guards.

Write ONLY hybrid-hands/plugins/hybrid-hands/**. Tests must be in this plugin's tests/ directory (outside top-level hybrid-hands/tests because write scope is limited). Add plugin README.md within scope and update skills/ext-hand/SKILL.md as appropriate. Do not edit dev-workflow; record cross-link as deferred. Root config order already has dsh removed; do not touch any other config, models, slots, parallel setting, install registry, auth or LaunchAgent. Sol will do live smoke checks and full suite once at the end. Bump plugin 0.57.0 -> 0.58.0 and CHANGELOG. No plugin installation/update (out of write scope).

Implement `hand-ext limit-watch on|off|status|tick [--persistent]`. `on --persistent` must support registering explicit exact target identity, provider/account home, cwd, unfinished checkpoint, next step and proof/observation of blocking (do not infer target blocked just from account full); document usable CLI registration examples. on without a target must safely report/help, not arm arbitrary sessions. State ~/.hybrid-hands/limit-watch/state.json atomic 0600 + flock; all writes serialized, no duplicates. Store generation, target identity, observed blocking windows/time, attempts/dispatch ACK. States armed -> blocked -> eligible -> dispatch_pending -> resumed. Fresh available account on first tick stays silent. Persistent resumes become armed again only awaiting a NEW blocking event; old blocking observations must not immediately re-trigger. One-shot disables after all registered targets resumed/done/cancelled. off invalidates generation and unloads/removes job but does not stop resumed sessions. Job local.hybrid-hands.limit-watch.plist uses absolute paths, StartCalendarInterval minutes 0,15,30,45, finite ticks, launchctl bootstrap/bootout.

Codex: use official CLI app-server JSON RPC initialize + initialized notification + account/rateLimits/read (all relevant windows and rateLimitReachedType, actual bucket IDs). Never turn/start or auth file reads. Bound IO timeouts/cleanup. Claude: .hh-claude-rate-limit.json -> statusline cache -> official paseo usage --json, correct account; timestamp observations, do not treat mtime/rewrite of stale fallback as freshness. Read code of existing collectors and reuse safe parsers where applicable. Treat missing/future/partial/unknown windows conservatively, retain blocking resets across stale samples. Check day guard for v1 before actual continuation.

Adapters: brain via verified Paseo exact host/target + agentId + workspaceId, idle/not permission pending/not stopped/done; official paseo send or existing public bridge. Sol via existing side-session send to exact registered side identity, never role main; avoid CLI invocation in tests. tmux only if runtime pane/session identity and safe prompt state are provable; fail closed otherwise (document limitation). Never send to shell/menu/running session. Dispatch command exit 0 alone is NOT resumed: require accepted/new-turn receipt or observed start; uncertain ACK stays dispatch_pending, no repeated sends. Reconcile on subsequent ticks; no exactly-once claim absent transport guarantees. Continuation says `làm tiếp` and checkpoint/next step. No real resume during implementation/tests.

## Acceptance and tests (write before implementation; MAXIMUM 3 main tests)

1. Available quota: newly armed unfinished target, repeated ticks send nothing, including invalid/running/done identity where applicable using subcases.
2. Explicit blocked target -> fresh eligible windows -> one dispatch, confirmed resume disables one-shot; persistent waits for new block; pending/uncertain/crash recovery never duplicate, using fixtures/mocks in this test.
3. Stale Claude -> wait until max reset+buffer -> one expected-reset attempt; quota rejection/unknown ACK doesn't retry forever; guard/lock/generation checks using subcases if useful.

Only public fake fixtures/mocked subprocess and temp homes; no real accounts/CLI/LLM/transcript/log. Run ONLY these narrow tests, not full suite. Sol reviews changes. Report exact test command/output and open limitations at docs/limit-watch-executor-report.md (within plugin). Keep changes compact and maintainable.

## Social listening

Luật nguyên văn: "Bạn quản lý source code repo này, khi đưa ra một giải pháp hoặc workflow cần tham khảo thêm nguồn social listening về lĩnh vực, quy trình đó."
Approved source links + post dates are in the research above (read them and cite in technical docs): Claude #98996 (2026-10-02), #92004 (2026-09-04), Codex #8310 (2025-12-19), Claude #100447 (2026-10-08), #35744 (2026-03-18; comment 2026-05-28), unsnooze/claude-auto (read 2026-11-12). Keep identity pinning, no stale banners, all reset windows, bounded retries/checkpoints. If significant design change necessary, stop that part and report; do not invent verified sources.

## Mandatory data law (verbatim)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
