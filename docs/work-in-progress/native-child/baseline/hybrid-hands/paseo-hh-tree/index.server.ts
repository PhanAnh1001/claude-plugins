import type { PluginServerContext } from "@getpaseo/plugin/server";

import { createTreeHandler } from "./server/tree";
import { hhTreeSettings } from "./shared/settings";
import { treeRpc } from "./shared/tree";

export default function contribute(server: PluginServerContext) {
  const settings = server.registerSettings(hhTreeSettings);
  server.handle(treeRpc, createTreeHandler(settings));
  return () => {};
}
