import type { TreeSession } from "../shared/tree";

export type NestedSession = TreeSession & { children: NestedSession[] };

export interface NestedSessions {
  roots: NestedSession[];
  orphanSides: TreeSession[];
}

function parentIdOf(session: TreeSession): string | null {
  const raw = session.parent_session?.trim();
  return raw ? raw : null;
}

/**
 * Builds the session forest from the flat `hh-ps` list.
 *
 * Roots keep the input order and every node's children keep the input order.
 * A session without a parent id is a root. When a parent id is dangling (parent
 * filtered out) or forms a cycle, no session is dropped: everything no root
 * reaches goes to `orphanSides` in the input order.
 */
export function nestSessions(sessions: TreeSession[]): NestedSessions {
  const ordered: NestedSession[] = sessions.map((session) => ({
    ...session,
    children: [],
  }));
  const byId = new Map<string, NestedSession>();
  for (const node of ordered) {
    if (!byId.has(node.session_id)) {
      byId.set(node.session_id, node);
    }
  }

  const roots: NestedSession[] = [];
  for (const node of ordered) {
    const parentId = parentIdOf(node);
    if (!parentId) {
      roots.push(node);
      continue;
    }
    const parent = byId.get(parentId);
    if (parent) {
      parent.children.push(node);
    }
  }

  const reached = new Set<NestedSession>();
  const visit = (node: NestedSession): void => {
    if (reached.has(node)) {
      return;
    }
    reached.add(node);
    for (const child of node.children) {
      visit(child);
    }
  };
  for (const root of roots) {
    visit(root);
  }

  const orphanSides = ordered.filter((node) => !reached.has(node));
  return { roots, orphanSides };
}
