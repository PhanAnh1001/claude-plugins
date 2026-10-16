---
name: measurement-evidence
description: Measurement standard for performance, latency and determinism claims - change one variable at a time, n >= 3 runs spread over time, record the environment, compare before vs after on the same harness, report raw numbers plus median, check determinism by hashing outputs, and never conclude from a single run; includes a results-table template. Use this whenever a claim rests on a number - slowness, speed-ups, regressions, flaky or non-deterministic output, benchmarks, TTFT or latency targets, "it improved" - and for every lane-L3 investigation. Vietnamese triggers - "đo", "chậm", "hiệu năng", "không tất định", "benchmark", "TTFT", "độ trễ", "lúc được lúc không", "nhanh hơn chưa".
---

# Measurement Evidence

## Summary

- **Purpose:** make every number in a report trustworthy: it measured the right thing, on a known
  environment, with enough samples, against a baseline measured the same way.
- **Six rules:**
  1. One variable per experiment.
  2. n ≥ 3 runs, spread over time, before any claim; state n beside the claim.
  3. Record the environment (commit, config, data, machine/endpoint, time).
  4. Before and after measured with the same harness in the same session.
  5. Report raw values plus the median (and min/max); never only an average.
  6. Determinism is checked by hashing outputs, not by eyeballing length or "looks the same".
- **Output:** a results table (template below) inside the bug report, design doc or final report.
- **Lane:** mandatory for L3 (hypothesis → measure → report and stop for approval → L1/L2).
- **Config keys used:** `[paths].bugs` (where an L3 report goes when no other doc owns it),
  `[project].doc_language`; read with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (see `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`).

## 1. Before measuring

### 1.1 Frame the question

- Write the hypothesis as a falsifiable sentence: "Removing X reduces TTFT p50 by ≥ 20 % on input set S."
- Ask what a **one-variable experiment** looks like. If the honest answer is "rerun everything and hope",
  label the claim a hypothesis and build an isolation harness first.
- Decide the metric precisely (e.g. time to first token vs. end-to-end time; wall clock vs. CPU time).

### 1.2 Build a faithful harness

- Prefer replaying **frozen inputs** at a stage boundary over rerunning non-deterministic upstream stages.
  Freeze every non-deterministic seam (model calls, clocks, random seeds, network), not only the obvious one.
- Prove the harness first: it reproduces the real run, and two repeat runs give byte-identical output
  where determinism is expected.
- Live-server measurements need a non-reloading instance and a recorded code version.
- Check the command actually touched the subject (count of items processed, log line from the code
  path). A plausible number from a no-op command is the most common false result.

### 1.3 Record the environment

Record once per session, in the report:

| Field | Example |
|---|---|
| Commit | `git rev-parse --short HEAD` + dirty flag (`git status --porcelain`) |
| Config / flags | env vars and settings that touch the metric |
| Data | input set name, size, hash of the input files |
| Machine / endpoint | host type, CPU/GPU, shared endpoint name, concurrency |
| Time window | start-end timestamp of the runs |

## 2. Running the experiment

### 2.1 Baseline vs change

- Materialise the baseline instead of trusting a remembered number: e.g. `git worktree add <tmpdir> <base>`
  or `git archive <base> | tar -x -C <tmpdir>`, then run the **same harness** over both trees.
- Never compare a fresh number with a relayed, remembered or older-session number.
- Interleave runs (A, B, A, B…) rather than all A then all B, so drift in a shared resource hits both sides.

### 2.2 Sample size and independence

- n ≥ 3 is the floor; use more when the spread is wide. Spread runs over time.
- Samples taken in one short window against a shared endpoint share a hidden variable (endpoint load);
  a larger n in that window only makes a wrong number look firmer.
- Cross-check a live measurement with accumulated data (one counting query over logs or the database
  across many days) when it exists; it shares no hidden variable with today's run.
- Suspend live measurement when the shared dependency is visibly degraded (mass timeouts, truncation).

### 2.3 Determinism checks

- Hash outputs (`sha256sum`/`md5sum` of the output file or of the extracted answer text) and compare
  hashes, not lengths or summaries.
- Repeating one identical input is not enough: **permute the input order** and assert the output is
  unchanged; check every sort has a unique tie-breaker.
- Seeing exactly one hash across a few runs of a sampled/LLM step does not prove determinism; say
  "stable in n runs" vs "deterministic by mechanism" and which one you mean.
- Drift is a defect to diagnose, not a property to accept. Do not pick the nicer run.

## 3. Reporting

### 3.1 Results table template

```markdown
**Hypothesis:** <one sentence>  ·  **Variable changed:** <one thing>  ·  **n:** <runs per side>
**Environment:** commit <sha>(+dirty?), <machine/endpoint>, <data set + hash>, <time window>
**Harness:** `<exact command>`

| Run | Baseline (<unit>) | Change (<unit>) | Output hash baseline | Output hash change |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| **Median** | | | | |
| Min / max | | | | |

**Delta (median):** <abs> (<%>)  ·  **Verdict:** confirmed / refuted / inconclusive - <why>
```

### 3.2 Wording rules

- "Improved" requires the delta to exceed the run-to-run spread; otherwise write "inconclusive".
- Every delta states how **both** ends were measured.
- A number written into code or docs carries its date and scope and says it is a measurement, not a
  constant of the system.
- When two measurements disagree, ask what each measured and which variable differs; do not pick the
  newer or larger one.
- Mark unproven mechanisms explicitly: a no-op change beside a real fix looks identical in the numbers.

### 3.3 Stop point (lane L3)

- After the report, stop and wait for approval of the next step; the follow-up fix runs as L1 or L2
  (`dev-workflow:bug-investigation` or `dev-workflow:spec-plan`).

## Brain/hand split

- **Hand:** build the harness, run the experiment, fill the table with raw output and exact commands.
- **Brain:** frames the hypothesis and the single variable, verifies the hand's numbers (reruns at least
  one sample or checks the harness touched the subject), writes the verdict, owns the stop-for-approval.
- A brief says "measure X and report", never "X is true, now confirm it".
