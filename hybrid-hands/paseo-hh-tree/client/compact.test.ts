import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires .ts.
import { accountQuotaText, compactTree, outcome, summaryText, rowText, finishedTime, panelRows, shortName, agentName } from "./compact.ts";
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
test("eight sides flatten to six, running first, overflow retains all outcomes", () => {
  const sides = Array.from({ length: 8 }, (_, i) => session(`s${i}`, {
    parent_session: i === 5 ? "s0" : "root", ended_at: at(i + 1),
    ...(i === 0 ? { live: true, status: "busy", ended_at: null } : {}),
    ...(i === 1 ? { status: "failed" } : {}),
  }));
  const view = tree([session("root"), ...sides]);
  assert.deepEqual(view.sides.map((s: TreeSession) => s.session_id), ["s0", "s7", "s6", "s5", "s4", "s3"]);
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
  const view = tree([root, recent, hidden, ...Array.from({ length: 6 }, (_, i) => session(`side${i}`, { parent_session: "root", ended_at: at(20 + i) }))]);
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
    ...Array.from({ length: 6 }, (_, i) => session(`running${i}`, {
      parent_session: "root", status: "busy", live: true, started_at: at(20), ended_at: null,
    }))]);
  assert.equal(hiddenLatest.latest.session_id, "recent");
  assert.equal(hiddenLatest.sides.length, 6);
  assert.equal(hiddenLatest.hiddenShownAgents.length, 4);
  assert.equal(hiddenLatest.hiddenAgents.length, 2);
  const otherRoot = session("other", { subagents: [agent("own", { ended_at: at(200) })] });
  assert.equal(tree([otherRoot]).agentsFor(otherRoot).shown.length, 1);
});
test("compact child text omits quota and labels; elapsed ticks then freezes, missing stays unknown", () => {
  const child = agent("worker", { status: "running", ended_at: null, duration_seconds: 1,
    usage: { account_5h_pct: 23, account_week_pct: 42 } });
  const line = rowText(child, "worker", 60000);
  assert.equal(line, "● worker · ?·? · 1p · ~$? · ? riêng ? tuần");
  assert.doesNotMatch(line, /5h|đang chạy|MODEL|EFFORT|fixture/);
  assert.match(rowText(child, "worker", 120000), /2p/);
  const done = { ...child, status: "finished", ended_at: at(60) };
  assert.equal(rowText(done, "worker", 60000), rowText(done, "worker", 120000));
  assert.equal(rowText({ status: "mystery" }, "?", 120000), "? ? · ?·? · ? · ~$? · ? riêng ? tuần");
  assert.doesNotMatch(rowText(child, "root", 60000, true), /5h|23.0%|42.0%/);
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
test("native Codex outcomes and hand exits share the four-agent pool with unknown cost", () => {
  const native = ["completed", "failed", "errored", "cancelled", "unknown"].map((status, i) =>
    agent(`native-${i}`, { agent_type: "native-codex", provider: "codex",
      parent_session: "root", status, exit_code: null, model: "gpt-6.1-sol", effort: "low",
      ended_at: at(100 + i), usage: null }));
  const root = session("root", { subagents: native, hand_runs: [{
    run_id: "bad-exit", label: "hand", backend: "codex", model: "gpt-6.1-sol",
    status: "completed", state: "running", exit_code: 2, parent_session: "root",
    started_at: at(0), ended_at: at(110), duration_seconds: 110,
    pid: null, child_pid: null, tokens: { input: 0, cached_input: 0, output: 0 },
  }] });
  const view = tree([root]);
  const { shown, hidden } = view.agentsFor(root);
  assert.equal(shown.length, 4);
  assert.equal(hidden.length, 2);
  assert.equal(shown[0].kind, "hand");
  assert.equal(shown.filter(item => item.kind === "subagent").length, 3);
  assert.equal(summaryText([...shown, ...hidden], "6 subagent"), "6 subagent: 1✓ 4✗ ?1");
  assert.equal(summaryText(hidden, "2 subagent"), "2 subagent: 1✓ 1✗");
  assert.match(rowText(shown[0], "hand", 120000), /^✗/);
  for (const child of native) {
    const icon = child.status === "completed" ? "✓" : child.status === "unknown" ? "?" : "✗";
    assert.equal(rowText(child, child.agent_type, 120000),
      `${icon} native-codex · gpt-6.1-sol·low · 1p · ${finishedTime(child, 120000)} · ~$? · GPT riêng ? tuần`);
  }
  assert.equal(outcome({ status: "finished" }), "done");
  assert.equal(outcome({ status: "errored", state: "running", exit_code: 0 }), "error");
  assert.equal(view.quotaText, "TK 5h ? · tuần ?");
});

test("panel row list starts with machine summaries; own share and local finish exclude running end", () => {
  const now = new Date(2026, 10, 7, 15, 0).getTime();
  const end = new Date(2026, 10, 7, 14, 30).toISOString();
  const done = session("root", { provider: "codex", status: "completed", ended_at: end,
    usage: { usd: 999, week_pct: 2.5, account_plan: "GPT", account_5h_pct: 11, account_week_pct: 22 } });
  const rows = panelRows({ sessions: [done], machine_usage: [
    { plan: "GPT", window: "tuần", usd: 7, source: "fixture" },
  ], limits: [{ plan: "Claude", window: "tuần", total_pct: 33, source: "fixture",
    this_machine_pct: null, other_pct: null, resets_at: null }] });
  assert.deepEqual(rows.map(row => row.kind), ["summary", "summary"]);
  assert.equal(rows[0].kind === "summary" && rows[0].text, "Claude máy này tuần ~$? · Claude 5h ? · tuần 33.0%");
  assert.equal(rows[1].kind === "summary" && rows[1].text, "GPT máy này tuần ~$7.00 · GPT 5h 11.0% · tuần 22.0%");
  assert.match(rowText(done, "root", now), /14:30.*GPT riêng 2.5% tuần/);
  assert.match(rowText({ ...done, usage: { ...done.usage, week_pct_source: "codex_rate_limits_delta" } }, "root", now), /GPT riêng \(đo\) 2.5% tuần/);
  assert.match(rowText({ ...done, usage: { account_plan: "GPT", week_pct_source: "codex_rate_limits_delta" } }, "root", now), /GPT riêng \? tuần/);
  assert.doesNotMatch(rowText(done, "root", now), /11.0%|22.0%|5h/);
  assert.match(rowText({ ...done, ended_at: new Date(2026, 10, 6, 14, 30).toISOString() }, "root", now), /06\/11 14:30/);
  assert.doesNotMatch(rowText({ ...done, status: "running", live: true }, "root", now), /14:30/);
  assert.match(rowText({ ...done, status: "idle", live: false }, "root", now), /14:30/);
  assert.match(rowText({ ...done, status: "idle", live: true, exit_code: 2 }, "root", now), /^✗.*14:30/);
  assert.equal(outcome({ state: "lost", status: "running" }), "unknown");
  assert.match(rowText({ status: "completed", provider: "codex", usage: { account_week_pct: 80 } }, "native", now), /GPT riêng \? tuần$/);
  assert.deepEqual(panelRows({ sessions: [] }).map(row => row.kind === "summary" && row.text), [
    "Claude máy này tuần ~$? · Claude 5h ? · tuần ?", "GPT máy này tuần ~$? · GPT 5h ? · tuần ?",
  ]);
});

test("running roots retain children and names use short descriptions", () => {
  const rows = panelRows({ sessions: [session("lost", { parent_session: "missing" }),
    session("child", { parent_session: "root" }), session("root", { live: true, status: "busy" })] });
  assert.deepEqual(rows.filter(r => r.kind === "session").map(r => r.session.session_id), ["root"]);
  const root = rows.find(r => r.kind === "session");
  assert.equal(root?.kind === "session" && root.session.children[0].session_id, "child");
  const description = "  Sửa sidebar\n và panel " + "x".repeat(60);
  const child = agent("id", { description });
  assert.equal(shortName(child), "Sửa sidebar và panel xxxxxxxxxx…");
  assert.equal(child.description, description);
  assert.equal(agentName({ ...child, kind: "subagent", value: child }), shortName(child));
  assert.equal(shortName({ description: "  ", agent_type: "native-codex", agent_id: "id" }), "native-codex");
});


test("ended/error/unknown roots hide whole trees without promoting live children", () => {
  const roots = [session("live", { live: true }), session("busy", { status: "busy" }),
    session("done"), session("failed", { live: true, status: "failed" }),
    session("exit", { live: true, status: "running", exit_code: 1 }),
    session("lost", { live: true, status: "lost" }), session("unknown", { status: "mystery" })];
  const children = roots.map(root => session(`${root.session_id}-child`, {
    parent_session: root.session_id, live: true, status: "running" }));
  const rows = panelRows({ sessions: [...children, ...roots,
    session("orphan", { parent_session: "missing", live: true, status: "running" })] });
  const visible = rows.filter(row => row.kind === "session");
  assert.deepEqual(visible.map(row => row.session.session_id), ["live", "busy"]);
  assert.deepEqual(visible.map(row => row.session.children.length), [1, 1]);
  assert.equal(panelRows({ sessions: roots.slice(2) }).length, 2);
});

test("session and hand descriptions win; fallback avoids raw IDs", () => {
  assert.equal(shortName({ session_id: "abcdef12-1234", name: "abcdef12", side_name: "Sửa panel" }), "Sửa panel");
  assert.equal(shortName({ session_id: "abcdef12-1234", name: "abcdef12" }), "?");
  assert.equal(shortName({ run_id: "run-42", label: "run-42" }), "?");
  assert.equal(shortName({ run_id: "run-42", label: "Kiểm tra giao diện", description: "  Sửa\n tên phiên " }), "Sửa tên phiên");
  assert.equal(shortName({ name: "Tiêu đề phiên", description: "Tóm tắt công việc" }), "Tóm tắt công việc");
  assert.equal(shortName({ description: " ", name: "Tiêu đề phiên" }), "Tiêu đề phiên");
  assert.equal(shortName({ description: "Mô tả", ai_title: "AI title", name: "Tên phiên" }), "Mô tả");
  assert.equal(shortName({ description: " ", ai_title: "  Sửa\n panel ", name: "Tên phiên" }), "Sửa panel");
  assert.equal(shortName({ ai_title: null, name: "Tên phiên" }), "Tên phiên");
  assert.equal(shortName({ session_id: "abcdef12-1234", ai_title: "abcdef12", name: "Tên phiên" }), "Tên phiên");
});
