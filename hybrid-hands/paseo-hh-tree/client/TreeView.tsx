import type { PluginTheme } from "@getpaseo/plugin";
import { useRpc } from "@getpaseo/plugin/client";
import { Loading, ScrollView } from "@getpaseo/plugin/client/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Text, View } from "react-native";

import { treeRpc, type TreeResult, type TreeSession } from "../shared/tree";
import { panelRows } from "./compact";
import { durationText } from "./format";
import { SessionBlock } from "./SessionBlock";

const REFRESH_INTERVAL_MS = 5_000;

interface TreeViewProps {
  agentId?: string;
  all?: boolean;
  theme: PluginTheme;
  layout: { compact: boolean };
}

export function TreeView({ agentId, all = false, theme, layout }: TreeViewProps) {
  const getTree = useRpc(treeRpc);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const query = useQuery<TreeResult>({
    queryKey: ["hh-tree", agentId ?? "all", all],
    queryFn: () => getTree({ agentId, all }),
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  if (query.isPending) {
    return <Loading />;
  }

  const warningStyle = {
    color: theme.colors.statusWarning,
    padding: layout.compact ? 12 : 20,
    fontSize: 14,
  };
  if (query.isError || !query.data) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.colors.surface0 }}>
        <Text style={warningStyle}>Không tải được cây phiên.</Text>
      </View>
    );
  }
  if (!query.data.ok) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.colors.surface0 }}>
        <Text style={warningStyle}>{query.data.error}</Text>
      </View>
    );
  }

  const tree = query.data.tree;
  const now = Date.now();
  const empty = tree.sessions.length === 0;

  const toggleSession = (session: TreeSession) => {
    const fallback = true;
    setExpanded((previous) => {
      const current = previous[session.session_id] ?? fallback;
      return { ...previous, [session.session_id]: !current };
    });
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.colors.surface0 }}
      contentContainerStyle={{ padding: layout.compact ? 12 : 20 }}
    >
      {panelRows(tree).map((row, i) => row.kind === "summary" ? (
        <Text key={`summary-${i}`} style={{ color: theme.colors.foregroundMuted, fontSize: layout.compact ? 12 : 13 }}>{row.text}</Text>
      ) : (
        <View key={row.session.session_id} style={{ marginBottom: 6 }}>
          <SessionBlock
            session={row.session}
            depth={0}
            theme={theme}
            compact={layout.compact}
            now={now}
            expanded={expanded}
            onToggle={toggleSession}
          />
        </View>
      ))}
      {empty ? (
        <Text style={{ color: theme.colors.foregroundMuted, fontSize: 13 }}>
          Không có phiên hay lượt hand nào trong {durationText(tree.since_seconds)} qua.
        </Text>
      ) : null}

    </ScrollView>
  );
}
