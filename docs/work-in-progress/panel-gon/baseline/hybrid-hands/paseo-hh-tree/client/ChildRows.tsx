import { Text } from "react-native";

import type { TreeHandRun, TreeSubagent } from "../shared/tree";
import {
  costText,
  durationText,
  handRunStatusColor,
  handRunStatusLabel,
  completedText,
  subagentStatusColor,
  subagentStatusLabel,
  truncate,
} from "./format";
import { BULLET, Row, SEPARATOR, type TreeThemeProps } from "./TreeRow";

export function SubagentRow({
  agent,
  depth,
  theme,
  compact,
  now,
}: TreeThemeProps & { agent: TreeSubagent; depth: number }) {
  const statusColor = subagentStatusColor(theme, agent);
  const cost = costText(agent.usage);
  const duration = durationText(agent.duration_seconds);
  const ended = agent.status === "finished" ? completedText(agent.ended_at) : "đang chạy";
  const description = truncate(agent.description);
  return (
    <Row depth={depth}>
      <Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
        <Text style={{ color: theme.colors.foregroundMuted }}>{BULLET}</Text>
        <Text style={{ fontWeight: "600" }}>{agent.agent_type || "?"} MODEL/EFFORT {agent.model || "?"}/{agent.effort || "?"}</Text>
        {description ? (
          <Text>
            {SEPARATOR}
            {description}
          </Text>
        ) : null}
        <Text style={{ color: statusColor }}>
          {SEPARATOR}
          {subagentStatusLabel(agent)}
        </Text>
        {cost ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {cost}
          </Text>
        ) : null}
        {duration ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {duration}
          </Text>
        ) : null}
        {ended ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {ended}
          </Text>
        ) : null}
      </Text>
    </Row>
  );
}

export function HandRunRow({
  run,
  depth,
  theme,
  compact,
  now,
}: TreeThemeProps & { run: TreeHandRun; depth: number }) {
  const statusColor = handRunStatusColor(theme, run);
  const duration = durationText(run.duration_seconds);
  const ended = run.state === "running" ? "đang chạy" : completedText(run.ended_at);
  const cost = costText(run.usage);
  return (
    <Row depth={depth}>
      <Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
        <Text style={{ color: theme.colors.foregroundMuted }}>{BULLET}</Text>
        <Text style={{ fontWeight: "600" }}>{run.backend || "hand"} MODEL/EFFORT {run.model || "?"}/{run.effort || "?"}</Text>
        <Text>
          {SEPARATOR}
          {run.label || run.run_id}
        </Text>
        <Text style={{ color: statusColor }}>
          {SEPARATOR}
          {handRunStatusLabel(run)}
        </Text>
        {cost ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {cost}
          </Text>
        ) : null}
        {duration ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {duration}
          </Text>
        ) : null}
        {ended ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {ended}
          </Text>
        ) : null}
      </Text>
    </Row>
  );
}
