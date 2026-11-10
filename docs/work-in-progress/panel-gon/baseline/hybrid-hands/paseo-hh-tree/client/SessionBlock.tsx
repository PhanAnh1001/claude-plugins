import type { ReactNode } from "react";
import { Pressable, Text, View } from "react-native";

import type { TreeSession } from "../shared/tree";
import { HandRunRow, SubagentRow } from "./ChildRows";
import {
  ageText,
  costText,
  completedText,
  sessionRuntimeText,
  sessionStatusColor,
  sessionStatusLabel,
} from "./format";
import type { NestedSession } from "./nest";
import { Row, SEPARATOR, type TreeThemeProps } from "./TreeRow";

const MAIN_MARKER = "● phiên chính";
const SIDE_NAME_PREFIX = "phiên phụ ";
const DEFAULT_PROVIDER = "claude";
const ORPHAN_SIDE_HEADING = "Phiên phụ chưa rõ phiên cha";

function Dot({ color, children }: { color: string; children: ReactNode }) {
  return <Text style={{ color }}>{children}</Text>;
}

function sessionTitle(session: TreeSession): string {
  const sideName = session.side_name?.trim();
  return sideName ? `${SIDE_NAME_PREFIX}${sideName}` : session.name;
}

function providerLabel(session: TreeSession): string {
  const provider = session.provider?.trim();
  return provider && provider !== DEFAULT_PROVIDER ? provider : "";
}

function SessionRow({
  session,
  depth,
  theme,
  compact,
  now,
  hasChildren,
  open,
  onToggle,
}: TreeThemeProps & {
  session: TreeSession;
  depth: number;
  hasChildren: boolean;
  open: boolean;
  onToggle(): void;
}) {
  const statusColor = sessionStatusColor(theme, session);
  const cost = costText(session.usage);
  const runtime = sessionRuntimeText(session, now);
  const ended = session.live ? "đang chạy" : completedText(session.ended_at);
  const age = ageText(session.last_activity, now);
  const provider = providerLabel(session);
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
      <Row depth={depth}>
        <Text style={{ color: theme.colors.foreground, fontSize: compact ? 13 : 14 }}>
          {hasChildren ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>{open ? "▾ " : "▸ "}</Text>
          ) : null}
          <Dot color={statusColor}>{session.live ? "●" : "○"} </Dot>
          <Text style={{ fontWeight: "600" }}>{sessionTitle(session)} ({session.side_name ? "side" : "root"} session) MODEL/EFFORT {session.model || "?"}/{session.effort || "?"}</Text>
          {provider ? (
            <Text style={{ color: theme.colors.accent }}>
              {SEPARATOR}
              {provider}
            </Text>
          ) : null}
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
          {cost ? (
            <Text style={{ color: theme.colors.foreground }}>
              {SEPARATOR}
              {cost}
            </Text>
          ) : null}
          {runtime ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>
              {SEPARATOR}chạy {runtime}
            </Text>
          ) : null}
          {ended ? (
            <Text style={{ color: theme.colors.foregroundMuted }}>
              {SEPARATOR}kết thúc {ended}
            </Text>
          ) : null}
          {!compact && !ended && age ? (
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
  depth,
  theme,
  compact,
  now,
  expanded,
  onToggle,
}: TreeThemeProps & {
  session: NestedSession;
  depth: number;
  expanded: Record<string, boolean>;
  onToggle(session: TreeSession): void;
}) {
  const runningChild = session.subagents.some((agent) => agent.status === "running");
  const hasChildren =
    session.subagents.length > 0 ||
    session.hand_runs.length > 0 ||
    session.children.length > 0;
  const open = expanded[session.session_id] ?? true;
  const childDepth = depth + 1;
  return (
    <>
      <SessionRow
        session={session}
        depth={depth}
        theme={theme}
        compact={compact}
        now={now}
        hasChildren={hasChildren}
        open={open}
        onToggle={() => onToggle(session)}
      />
      {open
        ? session.subagents.map((agent) => (
            <SubagentRow
              key={agent.agent_id}
              agent={agent}
              depth={childDepth}
              theme={theme}
              compact={compact}
              now={now}
            />
          ))
        : null}
      {open
        ? session.hand_runs.map((run) => (
            <HandRunRow
              key={run.run_id}
              run={run}
              depth={childDepth}
              theme={theme}
              compact={compact}
              now={now}
            />
          ))
        : null}
      {open
        ? session.children.map((child) => (
            <SessionBlock
              key={child.session_id}
              session={child}
              depth={childDepth}
              theme={theme}
              compact={compact}
              now={now}
              expanded={expanded}
              onToggle={onToggle}
            />
          ))
        : null}
    </>
  );
}

export function OrphanSideBlock({
  sessions,
  theme,
  compact,
  now,
  expanded,
  onToggle,
}: TreeThemeProps & {
  sessions: TreeSession[];
  expanded: Record<string, boolean>;
  onToggle(session: TreeSession): void;
}) {
  if (!sessions.length) {
    return null;
  }
  return (
    <>
      <Row depth={0}>
        <Text
          style={{
            color: theme.colors.foregroundMuted,
            fontSize: compact ? 13 : 14,
            fontWeight: "600",
            marginTop: 8,
          }}
        >
          {ORPHAN_SIDE_HEADING}
        </Text>
      </Row>
      {sessions.map((session) => (
        <View key={session.session_id} style={{ marginBottom: 6 }}>
          <SessionBlock
            session={{ ...session, children: [] }}
            depth={1}
            theme={theme}
            compact={compact}
            now={now}
            expanded={expanded}
            onToggle={onToggle}
          />
        </View>
      ))}
    </>
  );
}
