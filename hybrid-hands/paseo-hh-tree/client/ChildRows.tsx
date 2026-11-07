import { ColoredRowText } from "./ColoredText";
import type { TreeHandRun, TreeSubagent } from "../shared/tree";
import { Row, type TreeThemeProps } from "./TreeRow";
export function SubagentRow({ agent, depth, theme, compact, now }: TreeThemeProps & {
  agent: TreeSubagent;
  depth: number;
}) {
  return <Row depth={depth}><ColoredRowText item={agent} name={agent.agent_type || agent.agent_id} now={now} theme={theme} compact={compact} /></Row>;
}
export function HandRunRow({ run, depth, theme, compact, now }: TreeThemeProps & {
  run: TreeHandRun;
  depth: number;
}) {
  return <Row depth={depth}><ColoredRowText item={run} name={run.label || run.run_id} now={now} theme={theme} compact={compact} /></Row>;
}
