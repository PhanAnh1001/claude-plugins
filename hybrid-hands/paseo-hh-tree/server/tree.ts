import type { RpcInput } from "@getpaseo/plugin";
import type { PluginSettings } from "@getpaseo/plugin/server";

import type { HhTreeSettingsSchema } from "../shared/settings";
import { treeRpc, type TreeResult } from "../shared/tree";
import { findAgentSession } from "./agent-record";
import { findHhPs, HH_PS_MISSING_ERROR, runHhPs } from "./hh-ps";

import { createCachedLoader } from "./cache";
import { revisionRpc } from "../shared/revision";
import { createRevisionTracker, TOUCH_INTERVAL_MS, touchStore } from "./revision";

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

/** Each handler shares executions and adaptive cache entries across its clients. */
export function createTreeHandler(settings: PluginSettings<HhTreeSettingsSchema>) {
  const load = createCachedLoader<string, TreeResult>(
    key => loadTree(JSON.parse(key) as RpcInput<typeof treeRpc>, settings),
    value => !value.ok,
  );
  const tracker = createRevisionTracker(load.invalidate);
  const tree = (input: RpcInput<typeof treeRpc>): Promise<TreeResult> =>
    load(JSON.stringify({ agentId: input.agentId, all: input.all === true }));
  return { tree, revision: createRevisionHandler(settings, tracker.read), close: tracker.close };
}

/** Cheap RPC: reads the revision file; at most once per minute touches hh-store. */
function createRevisionHandler(
  settings: PluginSettings<HhTreeSettingsSchema>,
  readRevision: () => number,
) {
  let lastTouch = 0;
  return async (_input: RpcInput<typeof revisionRpc>): Promise<{ revision: number }> => {
    if (Date.now() - lastTouch >= TOUCH_INTERVAL_MS) {
      lastTouch = Date.now();
      const command = await findHhPs(await configuredPath(settings)).catch(() => null);
      if (command) touchStore(command);
    }
    return { revision: readRevision() };
  };
}
