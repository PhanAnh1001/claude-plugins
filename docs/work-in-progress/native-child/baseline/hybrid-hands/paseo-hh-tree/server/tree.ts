import type { RpcInput } from "@getpaseo/plugin";
import type { PluginSettings } from "@getpaseo/plugin/server";

import type { HhTreeSettingsSchema } from "../shared/settings";
import { treeRpc, type TreeResult } from "../shared/tree";
import { findAgentSession } from "./agent-record";
import { findHhPs, HH_PS_MISSING_ERROR, runHhPs } from "./hh-ps";

export const CACHE_TTL_MS = 3_000;

interface CacheEntry {
  expiresAt: number;
  value: TreeResult;
}

const cache = new Map<string, CacheEntry>();
const inFlight = new Map<string, Promise<TreeResult>>();

async function configuredPath(
  settings: PluginSettings<HhTreeSettingsSchema>,
): Promise<string> {
  try {
    const state = await settings.read();
    return state.status === "ready" ? state.values.hhPsPath : "";
  } catch {
    return "";
  }
}

async function loadTree(
  input: RpcInput<typeof treeRpc>,
  settings: PluginSettings<HhTreeSettingsSchema>,
): Promise<TreeResult> {
  const command = await findHhPs(await configuredPath(settings));
  if (!command) {
    return { ok: false, error: HH_PS_MISSING_ERROR };
  }
  const agent = input.agentId ? await findAgentSession(input.agentId) : null;
  return runHhPs(command, {
    cwd: agent?.cwd ?? undefined,
    sessionId: agent?.sessionId ?? undefined,
    all: input.all === true,
  });
}

/**
 * Handler for hh-tree.get. Reuses a 3 second cache and the in-flight promise so
 * panels polling the same key do not spawn concurrent hh-ps processes.
 */
export function createTreeHandler(settings: PluginSettings<HhTreeSettingsSchema>) {
  return async (input: RpcInput<typeof treeRpc>): Promise<TreeResult> => {
    const key = `${input.agentId ?? ""}|${input.all === true ? "1" : "0"}`;
    const cached = cache.get(key);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.value;
    }
    const pending = inFlight.get(key);
    if (pending) {
      return pending;
    }
    const promise = loadTree(input, settings);
    inFlight.set(key, promise);
    try {
      const value = await promise;
      cache.set(key, { expiresAt: Date.now() + CACHE_TTL_MS, value });
      return value;
    } finally {
      inFlight.delete(key);
    }
  };
}
