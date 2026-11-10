import { Text } from "react-native";
import type { TreeHandRun, TreeSubagent } from "../shared/tree";
import { rowText } from "./compact";
import { Row, type TreeThemeProps } from "./TreeRow";
export function SubagentRow({ agent, depth, theme, compact, now }: TreeThemeProps & {
  agent: TreeSubagent;
  depth: number;
}) {
  return <Row depth={depth}><Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
  {rowText(agent, agent.agent_type || agent.agent_id, now)}
 </Text></Row>;
}
export function HandRunRow({ run, depth, theme, compact, now }: TreeThemeProps & {
  run: TreeHandRun;
  depth: number;
}) {
  return <Row depth={depth}><Text style={{ color: theme.colors.foreground, fontSize: compact ? 12 : 13 }}>
  {rowText(run, run.label || run.run_id, now)}
 </Text></Row>;
}
