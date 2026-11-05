import type {
  PluginAgentPanelProps,
  PluginClientContext,
  PluginScreenProps,
  PluginSidebarItemProps,
  PluginSurfaceProps,
} from "@getpaseo/plugin/client";
import { SidebarRow } from "@getpaseo/plugin/client/ui";

import { SettingsScreen } from "./client/SettingsScreen";
import { TreeView } from "./client/TreeView";

const PLUGIN_ID = "hh-tree";
const PLUGIN_SETTINGS_ID = "hh-tree-settings";
const PLUGIN_TITLE = "Cây phiên";
const PLUGIN_ICON = "ListTree";

function TreePanel({ agentId, params, theme, layout }: PluginAgentPanelProps) {
  const id = agentId || params?.agentId || undefined;
  return <TreeView agentId={id} theme={theme} layout={layout} />;
}

function TreeScreen({ theme, layout }: PluginScreenProps) {
  return <TreeView all theme={theme} layout={layout} />;
}

function TreeSettings({ theme, layout }: PluginSurfaceProps) {
  return <SettingsScreen theme={theme} layout={layout} />;
}

function TreeSidebarItem({ currentScreen, openScreen }: PluginSidebarItemProps) {
  return (
    <SidebarRow
      icon={PLUGIN_ICON}
      active={currentScreen?.screenId === PLUGIN_ID}
      onPress={() => openScreen({ screenId: PLUGIN_ID })}
    />
  );
}

export default function contribute(client: PluginClientContext) {
  client.addAgentPanel({
    id: PLUGIN_ID,
    title: PLUGIN_TITLE,
    icon: PLUGIN_ICON,
    Component: TreePanel,
  });
  client.addScreen({
    id: PLUGIN_ID,
    title: PLUGIN_TITLE,
    Component: TreeScreen,
  });
  client.addSidebarHeaderItem({
    id: PLUGIN_ID,
    title: PLUGIN_TITLE,
    Component: TreeSidebarItem,
  });
  client.addSettingsScreen({
    id: PLUGIN_SETTINGS_ID,
    title: PLUGIN_TITLE,
    icon: PLUGIN_ICON,
    Component: TreeSettings,
  });
  return () => {};
}
