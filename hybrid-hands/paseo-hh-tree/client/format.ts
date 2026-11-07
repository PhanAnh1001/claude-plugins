import type { PluginTheme } from "@getpaseo/plugin";

import type {
  TreeHandRun,
  TreeLimit,
  TreeSession,
  TreeSubagent,
  TreeUsage,
} from "../shared/tree";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE;
const SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR;
const MILLISECONDS_PER_SECOND = 1000;
// Same cost formats as hh-tree-pane (hooks/tree.ts) and hh-ps (timeutil.py).
const USD_DECIMALS = 2;
const USD_MIN_VISIBLE = 0.01;
const PERCENT_DECIMALS = 1;
const PERCENT_MIN_VISIBLE = 0.1;
// Three spaces separate the plan/window label from the split, as in hh-ps.
const LIMIT_GAP = "   ";
const UNKNOWN_PERCENT = "?";
const WEEK_WINDOW = "tuần";
const GPT_PLAN = "GPT";
const GPT_5H_WINDOW = "5h";

export const DESCRIPTION_MAX_LEN = 60;

/** `$0.42`, `<$0.01` under one cent, `$0` for nothing used, "" without an estimate. */
export function usdText(usd: number | null | undefined, estimated = false): string {
  if (usd === null || usd === undefined || !Number.isFinite(usd)) {
    return "";
  }
  const mark = estimated ? "~" : "";
  if (usd <= 0) {
    return `${mark}$0`;
  }
  return `${mark}${usd < USD_MIN_VISIBLE ? "<$0.01" : `$${usd.toFixed(USD_DECIMALS)}`}`;
}

/** Share of the weekly plan limit, one decimal (`12.3%`); "" when unknown. */
export function percentText(pct: number | null | undefined, estimated = false): string {
  if (pct === null || pct === undefined || !Number.isFinite(pct)) {
    return "";
  }
  const mark = estimated ? "~" : "";
  if (pct > 0 && pct < PERCENT_MIN_VISIBLE / 2) {
    return `${mark}<${PERCENT_MIN_VISIBLE}%`;
  }
  return `${mark}${Math.max(0, pct).toFixed(PERCENT_DECIMALS)}%`;
}

/** `GPT 5h 12.3% · tuần 4.5%`; "" when the row has no account sample. */
export function gptShareText(usage: TreeUsage): string {
  const five = usage?.gpt_5h_pct;
  const week = usage?.gpt_week_pct;
  if (five == null && week == null) return "";
  const windows: string[] = [];
  if (five != null) windows.push(`${GPT_5H_WINDOW} ${percentText(five)}`);
  if (week != null) windows.push(`${WEEK_WINDOW} ${percentText(week)}`);
  return `GPT ${windows.join(" · ")}`;
}

/** `$0.78 · 1.6% tuần`, only the parts the row has; "" when it has neither. */
export function ownShareLabel(usage: TreeUsage): string {
  return usage?.week_pct != null && Number.isFinite(usage.week_pct) &&
    usage.week_pct_source === "codex_rate_limits_delta" ? "riêng (đo)" : "riêng";
}

export function costText(usage: TreeUsage): string {
  const five = usage?.account_5h_pct ?? usage?.gpt_5h_pct;
  const week = usage?.account_week_pct ?? usage?.gpt_week_pct;
  const own = percentText(usage?.week_pct, usage?.week_pct_estimated === true);
  return `${usage?.usd == null ? '~$?' : usdText(usage.usd, true)} · ${usage?.account_plan || 'TK'} 5h ${limitPercentText(five)} · tuần ${limitPercentText(week)}${own ? ` · ${ownShareLabel(usage)} ${own} tuần` : ''}`;

}

/** Limit-cell text: `?` when hh-ps did not know the share. */
export function limitPercentText(
  pct: number | null | undefined,
  estimated = false,
): string {
  return pct === null || pct === undefined || !Number.isFinite(pct)
    ? UNKNOWN_PERCENT
    : percentText(pct, estimated);
}

/** True for every plan window hh-ps and both panels display: weekly + GPT 5h. */
export function isShownLimit(limit: TreeLimit): boolean {
  return (
    (limit.window === WEEK_WINDOW && (limit.plan !== GPT_PLAN || limit.total_pct != null)) ||
    (limit.plan === GPT_PLAN && limit.window === GPT_5H_WINDOW && limit.total_pct != null)
  );
}

/** `Go tuần   máy này 12.3% · máy khác 4.5% · tổng 16.8% · reset 14:00` */
export function limitLine(limit: TreeLimit, now: number): string {
  const reset = resetText(limit.resets_at, now);
  const mark = limit.estimated === true;
  const split =
    limit.plan === GPT_PLAN
      ? [`tổng ${limitPercentText(limit.total_pct, mark)}`]
      : [
          `máy này ${limitPercentText(limit.this_machine_pct, mark)}`,
          `máy khác ${limitPercentText(limit.other_pct, mark)}`,
          `tổng ${limitPercentText(limit.total_pct, mark)}`,
        ];
  if (reset) {
    split.push(`reset ${reset}`);
  }
  return `${limit.plan} ${limit.window}${LIMIT_GAP}${split.join(" · ")}`;
}

export function durationText(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) {
    return "?";
  }
  const total = Math.max(0, Math.floor(seconds));
  const days = Math.floor(total / SECONDS_PER_DAY);
  const restAfterDays = total % SECONDS_PER_DAY;
  const hours = Math.floor(restAfterDays / SECONDS_PER_HOUR);
  const restAfterHours = restAfterDays % SECONDS_PER_HOUR;
  const minutes = Math.floor(restAfterHours / SECONDS_PER_MINUTE);
  const secs = restAfterHours % SECONDS_PER_MINUTE;
  if (days) {
    return hours ? `${days}ng${hours}g` : `${days}ng`;
  }
  if (hours) {
    return minutes ? `${hours}g${minutes}p` : `${hours}g`;
  }
  if (minutes) {
    return `${minutes}p`;
  }
  return `${secs}s`;
}

function parseMoment(iso: string | null): number | null {
  if (!iso) {
    return null;
  }
  const moment = Date.parse(iso);
  return Number.isFinite(moment) ? moment : null;
}

export function secondsSince(iso: string | null, now: number): number | null {
  const moment = parseMoment(iso);
  if (moment === null) {
    return null;
  }
  return Math.max(0, (now - moment) / MILLISECONDS_PER_SECOND);
}

export function ageText(iso: string | null, now: number): string {
  const seconds = secondsSince(iso, now);
  const text = durationText(seconds);
  return text ? `${text} trước` : "";
}

export function sessionRuntimeText(session: TreeSession, now: number): string {
  return durationText(session.duration_seconds ?? null);
}

/** Reset time: `HH:MM` today, `dd/mm HH:MM` on another local day; "" when unknown. */
export function resetText(iso: string | null, now: number): string {
  const moment = parseMoment(iso);
  if (moment === null) {
    return "";
  }
  const date = new Date(moment);
  const pad = (part: number) => String(part).padStart(2, "0");
  const clock = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const sameDay = date.toDateString() === new Date(now).toDateString();
  return sameDay ? clock : `${pad(date.getDate())}/${pad(date.getMonth() + 1)} ${clock}`;
}

export function completedText(iso: string | null | undefined): string {
  if (!iso || !Number.isFinite(Date.parse(iso))) return "?";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function clockText(iso: string): string {
  const moment = parseMoment(iso);
  if (moment === null) {
    return "--:--:--";
  }
  const date = new Date(moment);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function truncate(text: string, limit = DESCRIPTION_MAX_LEN): string {
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

export function sessionStatusLabel(session: TreeSession): string {
  if (!session.live) {
    return "đã kết thúc";
  }
  return session.status === "busy" ? "đang bận" : "rảnh";
}

export function subagentStatusLabel(agent: TreeSubagent): string {
  if (agent.status === "running") {
    return "đang chạy";
  }
  return agent.status === "silent" ? "im lặng" : "xong";
}

export function handRunStatusLabel(run: TreeHandRun): string {
  if (run.state === "lost") {
    return "mất";
  }
  if (run.state === "running") {
    return "đang chạy";
  }
  return "xong";
}

export function sessionStatusColor(theme: PluginTheme, session: TreeSession): string {
  if (!session.live) {
    return theme.colors.foregroundMuted;
  }
  return session.status === "busy" ? theme.colors.statusSuccess : theme.colors.statusWarning;
}

export function subagentStatusColor(theme: PluginTheme, agent: TreeSubagent): string {
  if (agent.status === "running") {
    return theme.colors.statusSuccess;
  }
  return agent.status === "silent" ? theme.colors.statusWarning : theme.colors.foregroundMuted;
}

export function handRunStatusColor(theme: PluginTheme, run: TreeHandRun): string {
  if (run.state === "lost") {
    return theme.colors.statusDanger;
  }
  return run.state === "running" ? theme.colors.statusSuccess : theme.colors.foregroundMuted;
}
