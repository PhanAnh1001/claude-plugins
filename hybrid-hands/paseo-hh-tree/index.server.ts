import type { PluginServerContext } from "@getpaseo/plugin/server";

import { listAgentSources } from "./server/agent-record";
import { inheritFromSource } from "./server/inherit";
import { createTreeHandler } from "./server/tree";
import { hhTreeSettings } from "./shared/settings";
import { revisionRpc } from "./shared/revision";
import { treeRpc } from "./shared/tree";

export default function contribute(server: PluginServerContext) {
  const settings = server.registerSettings(hhTreeSettings);
  const handlers = createTreeHandler(settings);
  server.handle(treeRpc, handlers.tree);
  server.handle(revisionRpc, handlers.revision);
  // Clear/new chat creates a bare agent; keep the previous session's provider/model/account.
  // Fail-open: an inherit error must never block agent creation.
  server.addHook("agent.create.before", async ({ request }) => {
    try {
      return inheritFromSource(request, await listAgentSources(request.config.cwd));
    } catch {
      return request;
    }
  });
  return handlers.close;
}
