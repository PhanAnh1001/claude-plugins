import { Text } from "react-native";

import type { TreeHandRun, TreeSubagent } from "../shared/tree";
import {
  durationText,
  handRunStatusColor,
  handRunStatusLabel,
  subagentStatusColor,
  subagentStatusLabel,
  tokenText,
  truncate,
} from "./format";
import { BULLET, Row, SEPARATOR, type TreeThemeProps } from "./TreeRow";

const ORPHAN_HEADING = "hand ngoài không rõ phiên gọi";

export function SubagentRow({
  agent,
  theme,
  compact,
}: TreeThemeProps & { agent: TreeSubagent }) {
  const statusColor = subagentStatusColor(theme, agent);
  const context = tokenText(agent.context_tokens);
  const duration = durationText(agent.duration_seconds);
  const description = truncate(agent.description);
  return (
    <Row depth={1}>
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
        {context ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}ctx {context}
          </Text>
        ) : null}
        {duration ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {duration}
          </Text>
        ) : null}
      </Text>
    </Row>
  );
}

export function HandRunRow({
  run,
  theme,
  compact,
}: TreeThemeProps & { run: TreeHandRun }) {
  const statusColor = handRunStatusColor(theme, run);
  const duration = durationText(run.duration_seconds);
  return (
    <Row depth={1}>
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
        <Text style={{ color: theme.colors.foregroundMuted }}>
          {SEPARATOR}vào {tokenText(run.tokens.input) || "0"}
          {SEPARATOR}cache {tokenText(run.tokens.cached_input) || "0"}
          {SEPARATOR}ra {tokenText(run.tokens.output) || "0"}
        </Text>
        {duration ? (
          <Text style={{ color: theme.colors.foregroundMuted }}>
            {SEPARATOR}
            {duration}
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
        <HandRunRow key={run.run_id} run={run} theme={theme} compact={compact} now={now} />
      ))}
    </>
  );
}
