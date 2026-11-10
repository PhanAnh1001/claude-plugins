// Synthetic public fixture only. No runtime/session/log data is read.
import { compactTree, rowText, summaryText, agentName } from "../../../hybrid-hands/paseo-hh-tree/client/compact.ts";
import { nestSessions } from "../../../hybrid-hands/paseo-hh-tree/client/nest.ts";
import { costText, durationText, completedText } from "./baseline/hybrid-hands/paseo-hh-tree/client/format.ts";
import type { TreeSession, TreeSubagent } from "../../../hybrid-hands/paseo-hh-tree/shared/tree";

const at = (n: number) => new Date(Date.UTC(2026, 10, 7, 0, n)).toISOString();
const now = Date.parse(at(60));
function session(id: string, extra: Partial<TreeSession> = {}): TreeSession {
  return {
    session_id: id, name: id, status: "finished", live: false, cwd: "/fixture/project",
    context_tokens: null, started_at: at(0), ended_at: at(10), duration_seconds: 600,
    last_activity: null, is_main: false, project_slug: "fixture", transcript_path: null,
    token_cap: null, token_ratio: null, model: "fixture-model", effort: "low",
    subagents: [], hand_runs: [], usage: { usd: 0.01 }, ...extra,
  };
}
const agents: TreeSubagent[] = Array.from({ length: 6 }, (_, i) => ({
  agent_id: `agent-${i}`, agent_type: `worker-${i}`, description: "Synthetic fixture task",
  status: i === 0 ? "running" : "finished", context_tokens: null,
  started_at: at(20), ended_at: i === 0 ? null : at(30 + i), duration_seconds: 600,
  model: "fixture-model", effort: "low", usage: { usd: 0.01 },
}));
const sessions = [
  session("main-fixture", { live: true, status: "busy", ended_at: null, is_main: true,
    usage: { usd: 0.12, account_plan: "Fixture", account_5h_pct: 12, account_week_pct: 34 },
    subagents: [{ ...agents[1], agent_type: "old-worker", ended_at: at(12) }] }),
  ...Array.from({ length: 6 }, (_, i) => session(`side-${i}`, {
    parent_session: i === 5 ? "side-0" : "main-fixture", side_name: `side-${i}`,
    ended_at: at(10 + i),
    ...(i === 0 ? { live: true, status: "busy", ended_at: null, subagents: agents } : {}),
    ...(i === 1 ? { status: "failed" } : {}),
  })),
];
console.log("FIXTURE ONLY: model/plan/name placeholders; no runtime rendering or reload.");
console.log("BEFORE (reconstructed baseline row template + baseline format functions):");
for (const s of sessions) {
  const name = s.side_name ? `phiên phụ ${s.side_name}` : s.name;
  console.log(`${s.live ? "●" : "○"} ${name} (${s.side_name ? "side" : "root"} session) MODEL/EFFORT ${s.model}/${s.effort} · ${costText(s.usage)} · chạy ${durationText(s.duration_seconds ?? null)} · kết thúc ${s.live ? "đang chạy" : completedText(s.ended_at)}`);
  for (const a of s.subagents) {
    console.log(`  • ${a.agent_type} MODEL/EFFORT ${a.model}/${a.effort} · ${a.description} · ${a.status === "running" ? "đang chạy" : "xong"} · ${costText(a.usage)} · ${durationText(a.duration_seconds)} · ${a.status === "finished" ? completedText(a.ended_at) : "đang chạy"}`);
  }
}
console.log("AFTER (same compactTree/rowText/summaryText used by SessionBlock UI):");
const view = compactTree(nestSessions(sessions).roots[0]);
console.log(`${rowText(view.root, view.root.name, now)} · ${view.quotaText}`);
function printAgents(s: TreeSession) {
  const pool = view.agentsFor(s);
  pool.shown.forEach(a => console.log(`    ${rowText(a, agentName(a), now)}`));
  if (pool.hidden.length) console.log(`    ${summaryText(pool.hidden, `${pool.hidden.length} subagent`)}`);
}
printAgents(view.root);
for (const s of view.sides) {
  console.log(`  ${rowText(s, s.side_name || s.name, now)}`);
  printAgents(s);
}
console.log(`  ${summaryText(view.hiddenSides, `+${view.hiddenSides.length} cũ`)}`);
if (view.hiddenAgents.length) console.log(`    ${summaryText(view.hiddenAgents, `${view.hiddenAgents.length} subagent`)}`);
