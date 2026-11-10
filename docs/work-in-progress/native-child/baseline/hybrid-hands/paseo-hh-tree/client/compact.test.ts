import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires .ts.
import { accountQuotaText, compactTree, outcome, summaryText, rowText } from "./compact.ts";
// @ts-ignore
import { nestSessions } from "./nest.ts";
import type { TreeSession, TreeSubagent } from "../shared/tree";
const at = (n: number) => new Date(n * 1000).toISOString();
function session(id: string, extra: Partial<TreeSession> = {}): TreeSession {
  return { session_id: id, name: id, status: "finished", cwd: "/fixture", context_tokens: null,
    started_at: at(0), ended_at: at(10), last_activity: null, is_main: false, live: false,
    project_slug: "fixture", transcript_path: null, token_cap: null, token_ratio: null,
    subagents: [], hand_runs: [], ...extra };
}
function agent(id: string, extra: Partial<TreeSubagent> = {}): TreeSubagent {
  return { agent_id: id, agent_type: id, description: "fixture", status: "finished",
    context_tokens: null, duration_seconds: 10, started_at: at(0), ended_at: at(10), ...extra };
}
function tree(sessions: TreeSession[]) { return compactTree(nestSessions(sessions).roots[0]); }
test("six sides flatten to four, running first, overflow retains all outcomes", () => {
  const sides = Array.from({ length: 6 }, (_, i) => session(`s${i}`, {
    parent_session: i === 5 ? "s0" : "root", ended_at: at(i + 1),
    ...(i === 0 ? { live: true, status: "busy", ended_at: null } : {}),
    ...(i === 1 ? { status: "failed" } : {}),
  }));
  const view = tree([session("root"), ...sides]);
  assert.deepEqual(view.sides.map((s: TreeSession) => s.session_id), ["s0", "s5", "s4", "s3"]);
  assert.equal(summaryText(view.hiddenSides, "+2 cũ"), "+2 cũ: 1✓ 1✗");
  const overflow = tree([session("root"), ...sides.map(s => ({ ...s, live: true, status: "busy" })),
    session("unknown", { parent_session: "root", status: "mystery", ended_at: null })]);
  assert.match(summaryText(overflow.hiddenSides, "+3 cũ"), /●2.*\?1/);
});
test("latest per tree pools four agents; old and hidden sessions retain summaries", () => {
  const pooled = Array.from({ length: 5 }, (_, i) => agent(`a${i}`, { ended_at: at(100 + i) }));
  const root = session("root", { is_main: true, subagents: [agent("old")] });
  const recent = session("recent", { parent_session: "root", ended_at: at(100), subagents: pooled,
    hand_runs: [{ run_id: "hand", label: "hand", backend: "codex", model: "", status: "running",
        state: "running", parent_session: "recent", started_at: at(110), ended_at: null,
        duration_seconds: 1, pid: null, child_pid: null, tokens: { input: 0, cached_input: 0, output: 0 } }] });
  const hidden = session("hidden", { parent_session: "root", ended_at: at(1), subagents: [agent("lost", { status: "mystery" })] });
  const view = tree([root, recent, hidden, ...Array.from({ length: 4 }, (_, i) => session(`side${i}`, { parent_session: "root", ended_at: at(20 + i) }))]);
  assert.equal(view.latest.session_id, "recent");
  assert.equal(view.agentsFor(root).shown.length, 0);
  assert.equal(view.agentsFor(root).hidden.length, 1);
  assert.equal(view.agentsFor(recent).shown.length, 4);
  assert.equal(view.agentsFor(recent).shown[0].value.run_id, "hand");
  assert.equal(view.agentsFor(recent).hidden.length, 2);
  assert.equal(view.hiddenAgents.length, 1);
  assert.equal(summaryText(view.hiddenAgents, "1 subagent"), "1 subagent: 0✓ 0✗ ?1");
  for (const status of ["failed", "error", "timeout", "timed_out", "killed"])
    assert.equal(outcome({ status, live: true }), "error");
  assert.equal(outcome({ state: "running", exit_code: 2 }), "error");
  assert.equal(outcome({ status: "finished", exit: 1 }), "error");
  assert.equal(outcome({ status: "mystery" }), "unknown");
  assert.equal(outcome({ status: "finished" }), "done");
  assert.equal(outcome({ state: "finished", status: "mystery" }), "unknown");
  assert.equal(outcome({ state: "lost", status: "mystery" }), "unknown");
  assert.equal(outcome({ live: true, status: "finished" }), "running");
  assert.equal(outcome({ state: "running", status: "ok" }), "running");
  const hiddenLatest = tree([root, { ...recent, ended_at: at(1) },
    ...Array.from({ length: 4 }, (_, i) => session(`running${i}`, {
      parent_session: "root", status: "busy", live: true, started_at: at(20), ended_at: null,
    }))]);
  assert.equal(hiddenLatest.latest.session_id, "recent");
  assert.equal(hiddenLatest.sides.length, 4);
  assert.equal(hiddenLatest.hiddenShownAgents.length, 4);
  assert.equal(hiddenLatest.hiddenAgents.length, 2);
  const otherRoot = session("other", { subagents: [agent("own", { ended_at: at(200) })] });
  assert.equal(tree([otherRoot]).agentsFor(otherRoot).shown.length, 1);
});
test("compact child text omits quota and labels; elapsed ticks then freezes, missing stays unknown", () => {
  const child = agent("worker", { status: "running", ended_at: null, duration_seconds: 1,
    usage: { account_5h_pct: 23, account_week_pct: 42 } });
  const line = rowText(child, "worker", 60000);
  assert.equal(line, "● worker · ?·? · 1p · ~$?");
  assert.doesNotMatch(line, /5h|tuần|đang chạy|MODEL|EFFORT|fixture/);
  assert.match(rowText(child, "worker", 120000), /2p/);
  const done = { ...child, status: "finished", ended_at: at(60) };
  assert.equal(rowText(done, "worker", 60000), rowText(done, "worker", 120000));
  assert.equal(rowText({ status: "mystery" }, "?", 120000), "? ? · ?·? · ? · ~$?");
  assert.match(rowText(child, "root", 60000, true), /5h 23.0% · tuần 42.0%/);
  assert.equal(accountQuotaText([
    { usage: null },
    { usage: { account_plan: "Claude", account_5h_pct: 10, account_week_pct: 20 } },
    { usage: { account_plan: "GPT", account_5h_pct: 30, account_week_pct: 40 } },
    { usage: { account_plan: "GPT", account_5h_pct: 80 } },
  ]), "Claude 5h 10.0% · tuần 20.0% · GPT 5h 30.0% · tuần 40.0%");
  assert.equal(accountQuotaText([{ usage: null }]), "TK 5h ? · tuần ?");
  assert.equal(accountQuotaText([
    { usage: { account_plan: "GPT", account_5h_pct: 30 } },
    { usage: { account_plan: "GPT", account_week_pct: 40 } },
  ]), "GPT 5h 30.0% · tuần ?");
});
