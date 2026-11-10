import type { PluginServerContext } from "@getpaseo/plugin/server";

import { createTreeHandler } from "./server/tree";
import { hhTreeSettings } from "./shared/settings";
import { revisionRpc } from "./shared/revision";
import { treeRpc } from "./shared/tree";

export default function contribute(server: PluginServerContext) {
  const settings = server.registerSettings(hhTreeSettings);
  const handlers = createTreeHandler(settings);
  server.handle(treeRpc, handlers.tree);
  server.handle(revisionRpc, handlers.revision);
  return handlers.close;
}
