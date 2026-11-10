import { readFile, readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

import { UUID_RE } from "../shared/tree";

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
