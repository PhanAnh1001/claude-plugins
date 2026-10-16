---
name: resume-work
description: Recover and continue interrupted work without redoing or overwriting what is already done - after context ran out or was compacted, a 529 Overloaded or usage-limit error, a subagent (hand) that died mid-task, or uncommitted changes that were lost. Rebuilds state from the open plan, git status/diff and the latest session transcripts, records progress in the plan, and sets up /loop or ScheduleWakeup to resume automatically. Use this whenever the user says to continue or the session restarts in the middle of a task. Vietnamese triggers - "tiếp tục", "làm tiếp", "resume", "hết context", "bật loop", "mất việc", "mất code", "hand chết", "bị 529".
---

# Resume Work

## Summary

- **Purpose:** continue exactly where the work stopped, from verified state, not from memory.
- **Three situations, one recovery order:**
  1. **Context exhausted / compacted** → rebuild state, continue.
  2. **Transient API failure** (529 Overloaded, usage limit) or a dead hand → set up an automatic resume
     loop, resume the same hand.
  3. **Lost uncommitted work** → restore from transcripts, never rewrite from memory.
- **Recovery order:** open plan → git state → transcripts → reconcile → write status into the plan → continue.
- **Never:** redo a ticked item without checking it, launch a fresh hand over a dead hand's partial work,
  or reconstruct lost code from memory.
- **Config keys used:** `[paths].plans`, `[paths].specs`, `[paths].bugs`, `[gate].commands`;
  read with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (see `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`).

## 1. Rebuild state (every situation)

### 1.1 The plan

- Find the active plan: files under `[paths].plans` (and `[paths].specs`, `[paths].bugs`) with
  `status: in-progress` or recent modification: `git log -1 --format=%cr -- <file>` and
  `git status --porcelain <dir>`.
- Read unticked `- [ ]` items and any "status" or "next step" notes. The plan is the source of truth for
  scope; the transcript only fills gaps.

### 1.2 Git state

- `git status --porcelain`, `git diff --stat`, `git diff` for touched files, `git log --oneline -10`,
  `git stash list`.
- Map each changed file to a plan item. A changed file with no plan item is a question for the user,
  not something to revert.

### 1.3 Transcripts (only when plan + git are not enough)

- Claude Code stores session transcripts as JSONL files in its per-user **projects directory**, one
  sub-folder per repository (sub-agent transcripts in a nested folder). Locate it from the Claude Code
  documentation or the current session; do not hard-code a machine path in any repo file.
- Files are large: shortlist with `grep -l '<distinctive string>'`, newest first; never print a whole file.
- Parse line by line as JSON (`json.loads`) to read tool calls and results; raw `grep` output keeps
  JSON escapes (`\n`) and corrupts code.
- Look for: the last user instruction, the last hand brief and its report, the last test/gate output.

### 1.4 Reconcile and record

- For each plan item decide: done-and-verified, done-unverified, in progress, not started.
  "Done-unverified" means rerun its check (test, gate command), do not redo the work.
- Write a short status block into the plan (date, what is verified, what is next, open blockers), then
  continue with the next unfinished item.
- If the plan and the working tree disagree, report the conflict before editing anything.

## 2. Transient failure or dead hand

### 2.1 Schedule an automatic resume

- Create the resume loop as soon as a hand dies on a transient error (529 Overloaded, usage/session
  limit) or when the user asks for a standing loop ("bật loop"). The user being present is not a
  substitute.
- Mechanism: the `/loop` skill with a fixed interval (default 15 minutes, cron `*/15 * * * *`), or its
  dynamic mode where `ScheduleWakeup` picks the next wake-up. Use an error's reset timestamp only to
  choose the first wake-up.
- Keep the job ID so it can be deleted when the user says stop. Session crons live only for the
  session; mention that in the report.

### 2.2 What the loop prompt does on each wake-up

1. Check real state first: is the hand still running? Is the plan item already ticked and verified?
   If so, do nothing this round.
2. If a hand is confirmed dead from an API error, resume **that same hand** (e.g. `SendMessage` to it)
   with "continue from where you stopped; do not redo finished steps".
3. Only if the hand cannot be resumed, launch a new one whose brief lists what is already done (from
   section 1.4) and forbids touching those files except to finish them.
4. Update the plan status block.

### 2.3 Treat empty results as unfinished

- A hand that returns nothing, or a report without evidence, is unfinished work, never a completed task
  with an empty report.

## 3. Lost uncommitted work

- Git, container images and bytecode usually do not hold uncommitted edits. Transcripts do: the verbatim
  output of any `git diff`, file write or edit an agent made.
- Recover by parsing transcript lines as JSON, extracting the diff `+` lines or the written file
  content, and restoring character for character.
- Restore into the working tree, then show `git diff` to the user and run the relevant tests.
- Reconstructing from memory is not recovery; it invents code and drops real lines. If the transcript
  does not contain it, say what is lost.

## 4. Prevent the next interruption

- Tick plan items in the session they finish; keep the status block current so the next resume is cheap.
- Split large tasks so each hand finishes within one context.
- Before context runs low, write the status block and the exact next command into the plan.

## Brain/hand split

- **Brain:** rebuilds state, owns the plan status, creates/deletes the loop, decides resume-vs-relaunch.
- **Hand:** may be asked to parse transcripts or rerun checks; it reports raw findings and does not
  decide what counts as done.
