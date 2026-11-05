import type { PluginTheme } from "@getpaseo/plugin";

import type { TreeHandRun, TreeSession, TreeSubagent } from "../shared/tree";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE;
const SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR;
const MILLISECONDS_PER_SECOND = 1000;
const TOKEN_KILO = 1000;
const TOKEN_MEGA = 1_000_000;

export const DESCRIPTION_MAX_LEN = 60;

function trimNumber(value: number): string {
  return Number(value.toFixed(1)).toString();
}

export function tokenText(value: number | null): string {
  if (value === null) {
    return "";
  }
  const count = Math.max(0, Math.floor(value));
  if (count < TOKEN_KILO) {
    return String(count);
  }
  if (count < TOKEN_MEGA) {
    return `${trimNumber(count / TOKEN_KILO)}k`;
  }
  return `${trimNumber(count / TOKEN_MEGA)}M`;
}

export function durationText(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) {
    return "";
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
  const sinceStart = secondsSince(session.started_at, now);
  if (sinceStart === null) {
    return "";
  }
  if (session.live) {
    return durationText(sinceStart);
  }
  const sinceActivity = secondsSince(session.last_activity, now);
  return sinceActivity === null ? "" : durationText(Math.max(0, sinceStart - sinceActivity));
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

export function ratioPercent(ratio: number | null): string {
  if (ratio === null || !Number.isFinite(ratio)) {
    return "";
  }
  return `${trimNumber(ratio * 100)}%`;
}

export function sessionTokenText(session: TreeSession): string {
  const context = tokenText(session.context_tokens);
  const cap = tokenText(session.token_cap);
  if (context && cap) {
    const ratio =
      session.token_ratio !== null
        ? ratioPercent(session.token_ratio)
        : ratioPercent(
            session.token_cap ? (session.context_tokens ?? 0) / session.token_cap : null,
          );
    return `ctx ${context}/${cap}${ratio ? ` (${ratio})` : ""}`;
  }
  if (cap) {
    return `ctx ?/${cap}`;
  }
  return context ? `ctx ${context}` : "";
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
