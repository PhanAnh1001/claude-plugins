import { readFile, readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

import { UUID_RE } from "../shared/tree";
import type { SourceAgent } from "./inherit";

export interface AgentSession {
  cwd: string | null;
  sessionId: string | null;
}

function expandHome(raw: string): string {
  if (raw === "~") {
    return homedir();
  }
  if (raw.startsWith("~/")) {
    return join(homedir(), raw.slice(2));
  }
  return raw;
}

function paseoHome(): string {
  const raw = process.env.PASEO_HOME?.trim();
  if (!raw) {
    return join(homedir(), ".paseo");
  }
  return resolve(expandHome(raw));
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function asSessionId(value: unknown): string | null {
  return typeof value === "string" && UUID_RE.test(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

async function readRecord(path: string): Promise<Record<string, unknown> | null> {
  try {
    const parsed: unknown = JSON.parse(await readFile(path, "utf8"));
    return asRecord(parsed);
  } catch {
    return null;
  }
}

/** Only reads cwd and the session id fields of a Paseo agent record. */
export async function findAgentSession(agentId: string): Promise<AgentSession | null> {
  if (!UUID_RE.test(agentId)) {
    return null;
  }
  const agentsDir = join(paseoHome(), "agents");
  let projects;
  try {
    projects = await readdir(agentsDir, { withFileTypes: true });
  } catch {
    return null;
  }
  for (const project of projects) {
    if (!project.isDirectory()) {
      continue;
    }
    const record = await readRecord(join(agentsDir, project.name, `${agentId}.json`));
    if (!record) {
      continue;
    }
    const runtime = asRecord(record.runtimeInfo);
    const persistence = asRecord(record.persistence);
    return {
      cwd: asString(record.cwd),
      sessionId:
        asSessionId(runtime?.sessionId) ?? asSessionId(persistence?.sessionId)
        ?? asSessionId(persistence?.nativeHandle),
    };
  }
  return null;
}

function asTime(value: unknown): number {
  const ms = typeof value === "string" ? Date.parse(value) : typeof value === "number" ? value : NaN;
  return Number.isFinite(ms) ? ms : 0;
}

function asStringMap(value: unknown): Record<string, string> | undefined {
  const map = asRecord(value);
  if (!map) return undefined;
  const out: Record<string, string> = {};
  for (const [key, item] of Object.entries(map)) if (typeof item === "string") out[key] = item;
  return out;
}

/** Agents saved for one cwd, archived ones included, for the create-time inherit hook. */
export async function listAgentSources(cwd: string): Promise<SourceAgent[]> {
  const agentsDir = join(paseoHome(), "agents");
  let projects;
  try {
    projects = await readdir(agentsDir, { withFileTypes: true });
  } catch {
    return [];
  }
  const sources: SourceAgent[] = [];
  for (const project of projects) {
    if (!project.isDirectory()) continue;
    const dir = join(agentsDir, project.name);
    let files: string[];
    try {
      files = (await readdir(dir)).filter(name => name.endsWith(".json")).sort();
    } catch {
      continue;
    }
    for (const file of files) {
      const record = await readRecord(join(dir, file));
      const config = asRecord(record?.config);
      const provider = asString(record?.provider);
      if (!record || !provider || asString(record.cwd) !== cwd) continue;
      sources.push({
        provider,
        cwd,
        model: asString(config?.model) ?? undefined,
        thinkingOptionId: asString(config?.thinkingOptionId) ?? undefined,
        launchEnv: asStringMap(record.launchEnv),
        internal: record.internal === true,
        timestamp: asTime(record.updatedAt) || asTime(record.createdAt),
      });
    }
  }
  return sources;
}
