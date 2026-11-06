import { Text } from "react-native";

import type { TreeHandRun, TreeSubagent } from "../shared/tree";
import {
  costText,
  durationText,
  handRunStatusColor,
  handRunStatusLabel,
  resetText,
  subagentStatusColor,
  subagentStatusLabel,
  truncate,
} from "./format";
import { BULLET, Row, SEPARATOR, type TreeThemeProps } from "./TreeRow";

const ORPHAN_HEADING = "hand ngoài không rõ phiên gọi";

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
  const ended = agent.status === "finished" ? resetText(agent.ended_at, now) : "";
  const description = truncate(agent.description);
  return (
    <Row depth={depth}>
      <Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
        <Text style={{ color: theme.colors.foregroundMuted }}>{BULLET}</Text>
        {agent.agent_type ? (
          <Text style={{ fontWeight: "600" }}>{agent.agent_type}</Text>
        ) : null}
        {description ? (
          <Text>
            {agent.agent_type ? SEPARATOR : ""}
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
  const ended = run.state === "running" ? "" : resetText(run.ended_at, now);
  const cost = costText(run.usage);
  return (
    <Row depth={depth}>
      <Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
        <Text style={{ color: theme.colors.foregroundMuted }}>{BULLET}</Text>
        <Text style={{ fontWeight: "600" }}>{run.backend || "hand"}</Text>
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

export function OrphanBlock({
  runs,
  theme,
  compact,
  now,
}: TreeThemeProps & { runs: TreeHandRun[] }) {
  if (!runs.length) {
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
          {ORPHAN_HEADING}
        </Text>
      </Row>
      {runs.map((run) => (
        <HandRunRow
          key={run.run_id}
          run={run}
          depth={1}
          theme={theme}
          compact={compact}
          now={now}
        />
      ))}
    </>
  );
}
