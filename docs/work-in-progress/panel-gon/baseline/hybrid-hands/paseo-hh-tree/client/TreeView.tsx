import type { PluginTheme } from "@getpaseo/plugin";
import { useRpc } from "@getpaseo/plugin/client";
import { Loading, ScrollView } from "@getpaseo/plugin/client/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Text, View } from "react-native";

import { treeRpc, type TreeResult, type TreeSession } from "../shared/tree";
import { durationText, clockText } from "./format";
import { LimitsBlock } from "./LimitsBlock";
import { nestSessions } from "./nest";
import { OrphanSideBlock, SessionBlock } from "./SessionBlock";

const REFRESH_INTERVAL_MS = 5_000;
const REFRESH_SECONDS = REFRESH_INTERVAL_MS / 1_000;
const SEPARATOR = " · ";

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
  const nested = nestSessions(tree.sessions);

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
      <LimitsBlock
        limits={tree.limits ?? []}
        theme={theme}
        compact={layout.compact}
        now={now}
      />
      <Text style={{ color: theme.colors.foreground, fontSize: 15, fontWeight: "600" }}>
        Cây phiên hybrid-hands
      </Text>
      <Text
        style={{
          color: theme.colors.foregroundMuted,
          fontSize: 12,
          marginTop: 2,
          marginBottom: 8,
        }}
      >
        Tự làm mới mỗi {REFRESH_SECONDS} giây
      </Text>
      {empty ? (
        <Text style={{ color: theme.colors.foregroundMuted, fontSize: 13 }}>
          Không có phiên hay lượt hand nào trong {durationText(tree.since_seconds)} qua.
        </Text>
      ) : null}
      {nested.roots.map((session) => (
        <View key={session.session_id} style={{ marginBottom: 6 }}>
          <SessionBlock
            session={session}
            depth={0}
            theme={theme}
            compact={layout.compact}
            now={now}
            expanded={expanded}
            onToggle={toggleSession}
          />
        </View>
      ))}
      <OrphanSideBlock
        sessions={nested.orphanSides}
        theme={theme}
        compact={layout.compact}
        now={now}
        expanded={expanded}
        onToggle={toggleSession}
      />
      <View
        style={{
          marginTop: 16,
          paddingTop: 8,
          borderTopWidth: 1,
          borderTopColor: theme.colors.border,
        }}
      >
        <Text style={{ color: theme.colors.foreground, fontSize: 13 }}>
          Tổng: {tree.totals.live_sessions} phiên sống
          {SEPARATOR}
          {tree.totals.running_subagents} subagent đang chạy
          {SEPARATOR}
          {tree.totals.running_hand_runs} hand ngoài đang chạy
        </Text>
        <Text style={{ color: theme.colors.foregroundMuted, fontSize: 12, marginTop: 2 }}>
          cập nhật lúc {clockText(tree.generated_at)}
        </Text>
      </View>
    </ScrollView>
  );
}
