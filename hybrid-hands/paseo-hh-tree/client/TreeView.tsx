import type { PluginTheme } from "@getpaseo/plugin";
import { useRpc } from "@getpaseo/plugin/client";
import { Loading, ScrollView } from "@getpaseo/plugin/client/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";

import { MAX_REFRESH_MS } from "../shared/refresh";
import { REVISION_POLL_MS, revisionRpc } from "../shared/revision";
import { treeRpc, type TreeResult, type TreeSession } from "../shared/tree";
import { panelRows } from "./compact";
import { createRevisionGate } from "./revision-gate";
import { SessionBlock } from "./SessionBlock";

// Old servers without hh-tree.revision: poll the tree like before.
const LEGACY_REFRESH_MS = 30_000;
// With revision support the tree is refetched on change; this is only the safety net.
const SAFETY_REFRESH_MS = MAX_REFRESH_MS;
// While the revision RPC fails, retry it so a reloaded server switches back automatically.
const REVISION_RETRY_MS = 60_000;

interface TreeViewProps {
  agentId?: string;
  all?: boolean;
  theme: PluginTheme;
  layout: { compact: boolean };
}

export function TreeView({ agentId, all = false, theme, layout }: TreeViewProps) {
  const getTree = useRpc(treeRpc);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const getRevision = useRpc(revisionRpc);
  const gate = useRef(createRevisionGate()).current;
  // react-query skips interval refetches while the app is hidden (refetchIntervalInBackground=false).
  const revision = useQuery({
    queryKey: ["hh-tree-revision"],
    queryFn: () => getRevision({}),
    refetchInterval: (q) => (q.state.status === "error" ? REVISION_RETRY_MS : REVISION_POLL_MS),
    retry: false,
  });
  const query = useQuery<TreeResult>({
    queryKey: ["hh-tree", agentId ?? "all", all],
    queryFn: () => getTree({ agentId, all }),
    refetchInterval: revision.isError ? LEGACY_REFRESH_MS : SAFETY_REFRESH_MS,
  });
  const refetchTree = query.refetch;
  useEffect(() => {
    if (revision.data && gate(revision.data.revision)) void refetchTree();
  }, [revision.data, gate, refetchTree]);

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
  const rows = panelRows(tree);
  const empty = !rows.some(row => row.kind === "session");

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
      {rows.map((row, i) => row.kind === "summary" ? (
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
          Không có phiên chính đang chạy.
        </Text>
      ) : null}

    </ScrollView>
  );
}
