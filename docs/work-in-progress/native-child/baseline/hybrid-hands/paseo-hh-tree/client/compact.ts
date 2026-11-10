import type {
  TreeSession, TreeSubagent, TreeHandRun, TreeUsage,
} from "../shared/tree";
import type { NestedSession } from "./nest";
// @ts-ignore -- Also run directly with Node strip-types.
import { durationText, limitPercentText, truncate, usdText } from "./format.ts";

export const MAX_SIDE_SESSIONS = 4;
export const MAX_SUBAGENTS = 4;
export type Outcome = "running" | "done" | "error" | "unknown";

export interface CompactItem {
  status?: string;
  state?: string;
  live?: boolean;
  exit_code?: number | null;
  exit?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  last_activity?: string | null;
  duration_seconds?: number | null;
  model?: string;
  effort?: string;
  usage?: TreeUsage;
}

export interface AgentItem extends CompactItem {
  kind: "subagent" | "hand";
  value: TreeSubagent | TreeHandRun;
}

export function outcome(item: CompactItem): Outcome {
  const states = [item.status, item.state].map(
    (state) => state?.toLowerCase().replaceAll("-", "_"),
  );
  const errors = [
    "failed", "failure", "error", "timeout", "timed_out", "killed",
    "cancelled", "canceled",
  ];
  const successes = ["ok", "success", "succeeded", "completed", "finished", "done"];
  const failedExit = [item.exit_code, item.exit].some(
    (exit) => typeof exit === "number" && Number.isFinite(exit) && exit !== 0,
  );
  if (states.some((state) => errors.includes(state ?? "")) || failedExit) {
    return "error";
  }
  if (
    item.live === true ||
    states.some((state) => ["running", "busy"].includes(state ?? ""))
  ) {
    return "running";
  }
  // `state=finished` only says the lifecycle ended; unknown status stays unknown.
  if (
    successes.includes(item.status?.toLowerCase() ?? "") ||
    item.exit_code === 0 || item.exit === 0
  ) {
    return "done";
  }
  return "unknown";
}

export function statusIcon(item: CompactItem): string {
  return { running: "●", done: "✓", error: "✗", unknown: "?" }[outcome(item)];
}

function moment(iso?: string | null): number {
  return iso && Number.isFinite(Date.parse(iso)) ? Date.parse(iso) : 0;
}

function recent(item: CompactItem): number {
  return Math.max(moment(item.ended_at), moment(item.started_at));
}

function prioritized<T extends CompactItem>(items: T[]): T[] {
  // Stable sort preserves the flattened tree/agent input order for ties.
  return [...items].sort((a, b) => (
    Number(outcome(b) === "running") - Number(outcome(a) === "running") ||
    recent(b) - recent(a)
  ));
}

function agents(session: TreeSession): AgentItem[] {
  return [
    ...session.subagents.map((value) => ({
      ...value, kind: "subagent" as const, value,
    })),
    ...session.hand_runs
      .filter((value) => value.parent_session === session.session_id)
      .map((value) => ({ ...value, kind: "hand" as const, value })),
  ];
}

/** One intact sample per account plan; never combine windows from different rows. */
export function accountQuotaText(items: CompactItem[]): string {
  const samples = new Map<string, TreeUsage>();
  const completeness = (usage: TreeUsage) => Number(
    usage?.account_5h_pct != null || usage?.gpt_5h_pct != null,
  ) + Number(usage?.account_week_pct != null || usage?.gpt_week_pct != null);
  items.forEach((item) => {
    const usage = item.usage;
    const hasGpt = usage?.gpt_5h_pct != null || usage?.gpt_week_pct != null;
    const plan = usage?.account_plan || (hasGpt ? "GPT" : "TK");
    // Unknown unlabelled usages must not add a fictitious account to the tree.
    if (!usage?.account_plan && !hasGpt && completeness(usage) === 0) return;
    if (!samples.has(plan) || completeness(usage) > completeness(samples.get(plan))) {
      samples.set(plan, usage);
    }
  });
  if (!samples.size) return "TK 5h ? · tuần ?";
  return [...samples].map(([plan, usage]) => {
    const five = limitPercentText(usage?.account_5h_pct ?? usage?.gpt_5h_pct);
    const week = limitPercentText(usage?.account_week_pct ?? usage?.gpt_week_pct);
    return `${plan} 5h ${five} · tuần ${week}`;
  }).join(" · ");
}

export function compactTree(root: NestedSession) {
  const all: NestedSession[] = [];
  const visited = new Set<NestedSession>();
  const visit = (node: NestedSession) => {
    if (visited.has(node)) return;
    visited.add(node);
    all.push(node);
    node.children.forEach(visit);
  };
  visit(root);

  const activity = (session: TreeSession) => Math.max(
    moment(session.last_activity),
    recent(session),
    ...agents(session).map((agent) => Math.max(
      moment(agent.last_activity), recent(agent),
    )),
  );
  const latest = [...all].sort((a, b) => activity(b) - activity(a))[0];
  const orderedSides = prioritized(all.slice(1));
  const sides = orderedSides.slice(0, MAX_SIDE_SESSIONS);
  const hiddenSides = orderedSides.slice(MAX_SIDE_SESSIONS);
  const agentsFor = (session: TreeSession) => {
    const pool = prioritized(agents(session));
    const count = session.session_id === latest.session_id ? MAX_SUBAGENTS : 0;
    return { shown: pool.slice(0, count), hidden: pool.slice(count) };
  };

  // A hidden latest session keeps its agents beneath the old-sides aggregate.
  return {
    root, sides, hiddenSides, latest, agentsFor,
    quotaText: accountQuotaText(all.flatMap((session) => [session, ...agents(session)])),
    hiddenAgents: hiddenSides.flatMap((session) => agentsFor(session).hidden),
    hiddenShownAgents: hiddenSides.flatMap((session) => agentsFor(session).shown),
  };
}

export function summaryText(items: CompactItem[], label: string): string {
  const counts = { running: 0, done: 0, error: 0, unknown: 0 };
  items.forEach((item) => counts[outcome(item)]++);
  return `${label}: ${counts.done}✓ ${counts.error}✗` +
    `${counts.running ? ` ●${counts.running}` : ""}` +
    `${counts.unknown ? ` ?${counts.unknown}` : ""}`;
}

export function elapsedText(item: CompactItem, now: number): string {
  const start = item.started_at ? Date.parse(item.started_at) : NaN;
  const end = item.ended_at ? Date.parse(item.ended_at) : NaN;
  const running = outcome(item) === "running";
  if (Number.isFinite(start) && (running || Number.isFinite(end))) {
    return durationText(((running ? now : end) - start) / 1000);
  }
  // Finished snapshots may have only a fixed duration. A running duration without
  // a start cannot safely be advanced between snapshots.
  return durationText(item.duration_seconds ?? null);
}

export function rowText(
  item: CompactItem, name: string, now: number, root = false,
): string {
  const usage = item.usage;
  const cost = usage?.usd == null ? "~$?" : usdText(usage.usd, true);
  const base = `${statusIcon(item)} ${truncate(name || "?", 32)} · ` +
    `${item.model || "?"}·${item.effort || "?"} · ` +
    `${elapsedText(item, now)} · ${cost}`;
  if (!root) return base;
  const five = limitPercentText(usage?.account_5h_pct ?? usage?.gpt_5h_pct);
  const week = limitPercentText(usage?.account_week_pct ?? usage?.gpt_week_pct);
  return `${base} · ${usage?.account_plan || "TK"} 5h ${five} · tuần ${week}`;
}

export function agentName(agent: AgentItem): string {
  if (agent.kind === "hand") {
    const run = agent.value as TreeHandRun;
    return run.label || run.run_id;
  }
  const subagent = agent.value as TreeSubagent;
  return subagent.agent_type || subagent.agent_id;
}
