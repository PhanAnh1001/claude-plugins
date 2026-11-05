import type { ReactNode } from "react";
import { Pressable, Text } from "react-native";

import type { TreeSession } from "../shared/tree";
import { HandRunRow, SubagentRow } from "./ChildRows";
import {
  ageText,
  sessionRuntimeText,
  sessionStatusColor,
  sessionStatusLabel,
  sessionTokenText,
} from "./format";
import { Row, SEPARATOR, type TreeThemeProps } from "./TreeRow";

const MAIN_MARKER = "● phiên chính";

function Dot({ color, children }: { color: string; children: ReactNode }) {
  return <Text style={{ color }}>{children}</Text>;
}

function SessionRow({
  session,
  theme,
  compact,
  now,
  hasChildren,
  open,
  onToggle,
}: TreeThemeProps & {
  session: TreeSession;
  hasChildren: boolean;
  open: boolean;
  onToggle(): void;
}) {
  const statusColor = sessionStatusColor(theme, session);
  const tokens = sessionTokenText(session);
  const runtime = sessionRuntimeText(session, now);
  const age = ageText(session.last_activity, now);
  const label = hasChildren
    ? `${open ? "Thu gọn" : "Mở"} phiên ${session.name}`
    : undefined;
  return (
    <Pressable
      accessibilityRole={hasChildren ? "button" : undefined}
      accessibilityLabel={label}
      disabled={!hasChildren}
      onPress={onToggle}
    >
      <Row depth={0}>
        <Text style={{ color: theme.colors.foreground, fontSize: compact ? 13 : 14 }}>
          {hasChildren ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>{open ? "▾ " : "▸ "}</Text>
          ) : null}
          <Dot color={statusColor}>{session.live ? "●" : "○"} </Dot>
          <Text style={{ fontWeight: "600" }}>{session.name}</Text>
          {session.is_main ? (
            <Text style={{ color: theme.colors.accent, fontWeight: "600" }}>
              {SEPARATOR}
              {MAIN_MARKER}
            </Text>
          ) : null}
          <Text style={{ color: statusColor }}>
            {SEPARATOR}
            {sessionStatusLabel(session)}
          </Text>
          {!compact && session.cwd ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>
              {SEPARATOR}
              {session.cwd}
            </Text>
          ) : null}
          {tokens ? (
            <Text style={{ color: theme.colors.foreground }}>
              {SEPARATOR}
              {tokens}
            </Text>
          ) : null}
          {runtime ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>
              {SEPARATOR}chạy {runtime}
            </Text>
          ) : null}
          {!compact && age ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>
              {SEPARATOR}hoạt động {age}
            </Text>
          ) : null}
        </Text>
      </Row>
    </Pressable>
  );
}

export function SessionBlock({
  session,
  theme,
  compact,
  now,
  expanded,
  onToggle,
}: TreeThemeProps & {
  session: TreeSession;
  expanded: boolean | undefined;
  onToggle(): void;
}) {
  const runningChild = session.subagents.some((agent) => agent.status === "running");
  const hasChildren = session.subagents.length > 0 || session.hand_runs.length > 0;
  const open = expanded ?? (session.live || runningChild);
  return (
    <>
      <SessionRow
        session={session}
        theme={theme}
        compact={compact}
        now={now}
        hasChildren={hasChildren}
        open={open}
        onToggle={onToggle}
      />
      {open
        ? session.subagents.map((agent) => (
            <SubagentRow key={agent.agent_id} agent={agent} theme={theme} compact={compact} now={now} />
          ))
        : null}
      {open
        ? session.hand_runs.map((run) => (
            <HandRunRow key={run.run_id} run={run} theme={theme} compact={compact} now={now} />
          ))
        : null}
    </>
  );
}
