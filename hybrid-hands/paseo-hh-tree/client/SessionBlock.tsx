import { ColoredRowText, ColoredSummary } from "./ColoredText";
import { Fragment } from "react";
import { Pressable } from "react-native";

import type { TreeSession } from "../shared/tree";
import {
  agentName,
  compactTree,
  summaryText,
  type AgentItem,
} from "./compact";
import type { NestedSession } from "./nest";
import { Row, type TreeThemeProps } from "./TreeRow";

type Props = TreeThemeProps & {
  session: NestedSession;
  depth: number;
  expanded: Record<string, boolean>;
  onToggle(session: TreeSession): void;
};

export function SessionBlock({
  session, depth, theme, compact, now, expanded, onToggle,
}: Props) {
  const view = compactTree(session);
  const open = expanded[session.session_id] ?? true;
  const summary = (text: string, at: number, key: string) => (
    <Row key={key} depth={at}>
      <ColoredSummary text={text} theme={theme} compact={compact} />
    </Row>
  );
  const agentRows = (
    shown: AgentItem[], hidden: AgentItem[], at: number, key: string,
  ) => (
    <>
      {shown.map((agent, index) => (
        <Row key={`${key}-${index}`} depth={at}>
          <ColoredRowText item={agent} name={agentName(agent)} now={now} theme={theme} compact={compact} />
        </Row>
      ))}
      {hidden.length
        ? summary(
            summaryText(hidden, `${hidden.length} subagent`),
            at,
            `${key}-summary`,
          )
        : null}
    </>
  );
  const rootAgents = view.agentsFor(session);

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${open ? "Thu gọn" : "Mở"} ${session.name}`}
        onPress={() => onToggle(session)}
      >
        <Row depth={depth}>
          <ColoredRowText item={session} name={session.side_name || session.name} now={now} theme={theme} compact={compact} prefix={open ? "▾ " : "▸ "} />
        </Row>
      </Pressable>
      {open ? (
        <>
          {agentRows(rootAgents.shown, rootAgents.hidden, depth + 1, "root")}
          {view.sides.map((side) => {
            const pool = view.agentsFor(side);
            return (
              <Fragment key={side.session_id}>
                <Row depth={depth + 1}>
                  <ColoredRowText item={side} name={side.side_name || side.name} now={now} theme={theme} compact={compact} />
                </Row>
                {agentRows(pool.shown, pool.hidden, depth + 2, side.session_id)}
              </Fragment>
            );
          })}
          {view.hiddenSides.length
            ? summary(
                summaryText(view.hiddenSides, `+${view.hiddenSides.length} cũ`),
                depth + 1,
                "old-sides",
              )
            : null}
          {view.hiddenShownAgents.length
            ? summary(
                view.latest.side_name || view.latest.name,
                depth + 2,
                "latest-name",
              )
            : null}
          {agentRows(view.hiddenShownAgents, view.hiddenAgents, depth + 2, "old-agents")}
        </>
      ) : null}
    </>
  );
}

export function OrphanSideBlock({
  sessions, ...props
}: Omit<Props, "session" | "depth"> & { sessions: TreeSession[] }) {
  return (
    <>
      {sessions.map((session) => (
        <SessionBlock
          key={session.session_id}
          {...props}
          session={{ ...session, children: [] }}
          depth={0}
        />
      ))}
    </>
  );
}
