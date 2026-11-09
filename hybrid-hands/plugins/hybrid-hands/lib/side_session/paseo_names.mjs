// Titles are optional public API operations, separate from lifecycle mutations.
const PAGE_LIMIT = 200;
const MAX_PAGES = 100;
const TITLE_LIMIT = 60;
const main = agent => ["main", "main_session"].includes(agent?.role)
  || agent?.main_session === true;

async function members(client, workspaceId) {
  const ids = new Set(), cursors = new Set(), found = [];
  let cursor;
  for (let page = 0; page < MAX_PAGES; page++) {
    const result = await client.fetchAgents({filter: {includeArchived: true},
      sort: [{key: "created_at", direction: "desc"}],
      page: {limit: PAGE_LIMIT, ...(cursor ? {cursor} : {})}});
    if (result?.error || !Array.isArray(result?.entries) || !result.pageInfo) return null;
    for (const entry of result.entries) {
      const agent = entry?.agent;
      if (!agent?.id || !agent.workspaceId || ids.has(agent.id)) return null;
      ids.add(agent.id);
      if (agent.workspaceId === workspaceId) found.push(agent);
    }
    cursor = result.pageInfo.nextCursor;
    if (cursor === null) return found;
    if (typeof cursor !== "string" || !cursor || cursors.has(cursor)) return null;
    cursors.add(cursor);
  }
  return null;
}

export async function nameSession(client, request) {
  const result = {agentId: request.agentId, workspaceId: request.expectedWorkspaceId,
    title: request.title, agentEligible: false, workspaceEligible: false,
    agentNamed: false, workspaceNamed: false};
  try {
    if (typeof request.title !== "string" || [...request.title].length > TITLE_LIMIT
        || !/^[\p{L}\p{N}_-]+ · (Sol|Opus (v[1-9][0-9]*|\?)|dsh|\?) phụ$/u.test(request.title)) {
      return {...result, warning: "NAME_TITLE_INVALID"};
    }
    const owners = request.workspaceOwners;
    if (!Array.isArray(owners) || !owners.some(o => o.agentId === request.agentId
        && o.workspaceId === request.expectedWorkspaceId && !main(o))
        || owners.some(o => o.agentId === request.agentId && main(o))) {
      return {...result, warning: "NAME_OWNERSHIP_BLOCKED"};
    }
    const fetched = await client.fetchAgent({agentId: request.agentId});
    const agent = fetched?.agent;
    if (fetched?.error || !agent || agent.id !== request.agentId
        || agent.workspaceId !== request.expectedWorkspaceId || main(agent)) {
      return {...result, warning: "NAME_AGENT_BLOCKED"};
    }
    result.agentEligible = true;
    // Workspace naming requires exactly one recorded and publicly confirmed member.
    // Shared workspaces keep their title even when every member is plugin-owned.
    let directory = null;
    try { directory = await members(client, request.expectedWorkspaceId); } catch {}
    result.workspaceEligible = owners.length === 1 && !main(owners[0])
      && owners[0].agentId === agent.id && directory?.length === 1
      && directory[0].id === agent.id && !main(directory[0]);
    if (request.apply !== true) {
      return {...result, ...(result.workspaceEligible ? {} : {warning: "NAME_WORKSPACE_BLOCKED"})};
    }
    if (agent.title === request.title) result.agentNamed = true;
    else {
      try {
        const updated = await client.updateAgent(agent.id, {name: request.title});
        if (!updated?.error) {
          const confirmed = await client.fetchAgent({agentId: agent.id});
          result.agentNamed = confirmed?.agent?.id === agent.id
            && confirmed.agent.workspaceId === agent.workspaceId
            && confirmed.agent.title === request.title;
        }
      } catch {}
    }
    if (result.workspaceEligible) {
      try {
        const updated = await client.setWorkspaceTitle(agent.workspaceId, request.title);
        result.workspaceNamed = !updated?.error && updated?.title === request.title;
      } catch {}
    }
    if (!result.agentNamed || !result.workspaceNamed) {
      result.warning = result.workspaceEligible ? "NAME_RENAME_FAILED" : "NAME_WORKSPACE_BLOCKED";
    }
    return result;
  } catch {
    return {...result, warning: "NAME_RENAME_FAILED"};
  }
}
