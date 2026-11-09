// Paseo daemon transport for side-session (CLI compatibility: @getpaseo/cli 0.15.0).
//
// Protocol: one JSON object on stdin, one JSON object on stdout. Python owns every
// process/env decision; this file only calls the installed CLI's own client helpers so
// Paseo keeps ownership of credentials, target discovery and the daemon protocol.
//
// argv[2] is the resolved package root (parent of the CLI's `bin/`). We never print
// config, credentials or an endpoint containing one; errors are reduced to a code.
import { createHash } from "node:crypto";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_TIMEOUT_MS = 3000;
const SUBAGENT_TIMELINE_LIMIT = 100;
const DIRECTORY_PAGE_LIMIT = 200;
const DIRECTORY_MAX_PAGES = 100;
const SEND_QUEUED = "queued";
const TIMELINE_METADATA = [
  "provider", "direction", "epoch", "projection", "startCursor", "endCursor",
  "reset", "staleCursor", "gap", "window", "hasOlder", "hasNewer",
];

let sendPreDispatch = false;

function nonemptyId(value) {
  return typeof value === "string" && value.trim().length > 0;
}

async function archiveExactAgent(client, agentId) {
  // The client contract acknowledges persistence with archivedAt. A resolved
  // request alone must not release the side-session slot or stop its watchdog.
  const result = await client.archiveAgent(agentId);
  if (result?.error != null) {
    fail(errorCode({ code: result.error }));
    return false;
  }
  const archivedAt = result?.archivedAt;
  if (typeof archivedAt !== "string" || !archivedAt.trim()
      || !Number.isFinite(Date.parse(archivedAt))) {
    fail("AGENT_ARCHIVE_UNCONFIRMED");
    return false;
  }
  return true;
}

// Read the complete public workspace directory, including background workspaces.
async function exactWorkspace(client, request) {
  if (typeof client.fetchWorkspaces !== "function") {
    fail("WORKSPACE_DIRECTORY_UNCONFIRMED"); return null;
  }
  let cursor;
  let found;
  const ids = new Set(), cursors = new Set();
  for (let page = 0; page < DIRECTORY_MAX_PAGES; page++) {
    const result = await client.fetchWorkspaces({includeBackground: true,
      page: {limit: DIRECTORY_PAGE_LIMIT, ...(cursor ? {cursor} : {})}});
    if (result?.error != null || !Array.isArray(result?.entries)
        || !result.pageInfo || !Object.hasOwn(result.pageInfo, "nextCursor")) break;
    for (const entry of result.entries) {
      if (!nonemptyId(entry?.id) || ids.has(entry.id)) {
        fail("WORKSPACE_DIRECTORY_UNCONFIRMED"); return null;
      }
      ids.add(entry.id);
      if (entry.id === request.expectedWorkspaceId) found = entry;
    }
    cursor = result.pageInfo.nextCursor;
    if (cursor === null) {
      if (!found || !nonemptyId(request.workdir)
          || found.workspaceDirectory !== request.workdir) {
        fail("WORKSPACE_PATH_MISMATCH"); return null;
      }
      return found;
    }
    if (!nonemptyId(cursor) || cursors.has(cursor)) break;
    cursors.add(cursor);
  }
  fail("WORKSPACE_DIRECTORY_UNCONFIRMED"); return null;
}

// Include archived agents: even an inactive sibling makes this workspace shared.
async function privateWorkspace(client, request, agent) {
  if (request.privateWorkspace !== true) {
    fail("WORKSPACE_NOT_PRIVATE");
    return false;
  }
  if (!nonemptyId(request.expectedWorkspaceId)
      || agent.workspaceId !== request.expectedWorkspaceId) {
    fail("WORKSPACE_ID_MISMATCH");
    return false;
  }
  if (typeof client.archiveWorkspace !== "function" || typeof client.fetchAgents !== "function") {
    fail("WORKSPACE_CLEANUP_UNSUPPORTED");
    return false;
  }
  const workspace = await exactWorkspace(client, request);
  if (!workspace) return false;
  if (workspace.workspaceKind !== "worktree" || !nonemptyId(workspace.projectRootPath)
      || workspace.projectRootPath === request.workdir) {
    fail("WORKSPACE_NOT_PRIVATE"); return false;
  }
  let cursor;
  const ids = new Set();
  const seen = new Set();
  for (let page = 0; page < DIRECTORY_MAX_PAGES; page++) {
    const payload = await client.fetchAgents({
      filter: { includeArchived: true },
      sort: [{ key: "created_at", direction: "desc" }],
      page: { limit: DIRECTORY_PAGE_LIMIT, ...(cursor ? { cursor } : {}) },
    });
    if (payload?.error != null || !Array.isArray(payload?.entries)
        || !payload.pageInfo || !Object.hasOwn(payload.pageInfo, "nextCursor") || payload.entries.some((entry) => !entry?.agent
          || !nonemptyId(entry.agent.id) || !nonemptyId(entry.agent.workspaceId))) {
      fail("WORKSPACE_DIRECTORY_UNCONFIRMED");
      return false;
    }
    for (const {agent: other} of payload.entries) {
      if (ids.has(other.id)) { fail("WORKSPACE_DIRECTORY_UNCONFIRMED"); return false; }
      ids.add(other.id);
    }
    if (payload.entries.some(({ agent: other }) =>
      other.workspaceId === request.expectedWorkspaceId && other.id !== request.agentId
      && other.archivedAt == null && !["closed"].includes(other.status))) {
      fail("WORKSPACE_SHARED");
      return false;
    }
    cursor = payload.pageInfo.nextCursor;
    if (cursor == null) return true;
    if (!nonemptyId(cursor) || seen.has(cursor)) break;
    seen.add(cursor);
  }
  fail("WORKSPACE_DIRECTORY_UNCONFIRMED");
  return false;
}

// Read-only complete directory snapshot; never expose provider details.
async function readAgentArchiveStates(client, key) {
  if (typeof client.fetchAgents !== "function") {
    fail("WORKSPACE_DIRECTORY_UNCONFIRMED");
    return;
  }
  const agents = [];
  const ids = new Set();
  const cursors = new Set();
  let cursor;
  for (let page = 0; page < DIRECTORY_MAX_PAGES; page++) {
    const payload = await client.fetchAgents({
      filter: { includeArchived: true },
      sort: [{ key: "created_at", direction: "desc" }],
      page: { limit: DIRECTORY_PAGE_LIMIT, ...(cursor ? { cursor } : {}) },
    });
    if (payload?.error != null || !Array.isArray(payload?.entries)
        || !payload.pageInfo || !Object.hasOwn(payload.pageInfo, "nextCursor")) break;
    for (const entry of payload.entries) {
      const agent = entry?.agent;
      if (!agent || !nonemptyId(agent.id) || !nonemptyId(agent.workspaceId)
          || (agent.archivedAt != null && typeof agent.archivedAt !== "string")
          || ids.has(agent.id)) {
        fail("WORKSPACE_DIRECTORY_UNCONFIRMED");
        return;
      }
      ids.add(agent.id);
      agents.push({ agentId: agent.id, workspaceId: agent.workspaceId,
        archivedAt: agent.archivedAt ?? null });
    }
    cursor = payload.pageInfo.nextCursor;
    if (cursor === null) {
      emit({ ok: true, agents, targetKey: key });
      return;
    }
    if (!nonemptyId(cursor) || cursors.has(cursor)) break;
    cursors.add(cursor);
  }
  fail("WORKSPACE_DIRECTORY_UNCONFIRMED");
}

async function archivePrivateWorkspace(client, workspaceId) {
  const result = await client.archiveWorkspace(workspaceId);
  if (result?.error != null) {
    fail(errorCode({ code: result.error }));
    return false;
  }
  if (typeof result?.archivedAt !== "string"
      || !Number.isFinite(Date.parse(result.archivedAt))) {
    fail("WORKSPACE_ARCHIVE_UNCONFIRMED");
    return false;
  }
  return true;
}

function nativePayloadValid(payload, parentAgentId) {
  if (!payload || typeof payload !== "object") {
    fail("PASEO_BRIDGE_PROTOCOL");
    return false;
  }
  // Provider errors are nullable strings, potentially containing private details.
  // Preserve a safe machine code only; never forward error text or other fields.
  if (payload.error != null) {
    fail(errorCode({ code: payload.error }));
    return false;
  }
  if (payload.parentAgentId !== parentAgentId) {
    fail("SUBAGENT_PARENT_MISMATCH");
    return false;
  }
  return true;
}

async function readNativeSubagents(client, request, key) {
  const parent = request.agentId;
  const timeline = request.command === "subagent-timeline";
  if (!nonemptyId(parent) || (timeline && !nonemptyId(request.subagentId))) {
    fail("INVALID_AGENT_ID");
    return;
  }
  if (typeof client.listProviderSubagents !== "function"
      || (timeline && typeof client.fetchProviderSubagentTimeline !== "function")) {
    fail("NATIVE_SUBAGENTS_UNSUPPORTED");
    return;
  }
  const listed = await client.listProviderSubagents(parent);
  if (!nativePayloadValid(listed, parent)) {
    return;
  }
  if (!Array.isArray(listed.subagents)) {
    fail("PASEO_BRIDGE_PROTOCOL");
    return;
  }
  if (!listed.subagents.every((child) => child && nonemptyId(child.id)
      && child.parentAgentId === parent)) {
    fail("SUBAGENT_PARENT_MISMATCH");
    return;
  }
  if (!timeline) {
    emit({ ok: true, parentAgentId: parent, subagents: listed.subagents, targetKey: key });
    return;
  }
  if (!listed.subagents.some((child) => child.id === request.subagentId)) {
    fail("SUBAGENT_NOT_FOUND");
    return;
  }
  const fetched = await client.fetchProviderSubagentTimeline(parent, request.subagentId, {
    limit: SUBAGENT_TIMELINE_LIMIT,
  });
  if (!nativePayloadValid(fetched, parent)) {
    return;
  }
  if (fetched.subagentId !== request.subagentId || !Array.isArray(fetched.rows)) {
    fail("PASEO_BRIDGE_PROTOCOL");
    return;
  }
  const metadata = {};
  for (const field of TIMELINE_METADATA) {
    if (Object.hasOwn(fetched, field)) {
      metadata[field] = fetched[field];
    }
  }
  emit({ ok: true, parentAgentId: parent, subagentId: request.subagentId,
    rows: fetched.rows, ...metadata, targetKey: key });
}

// Exact agent identity, before any mutation: id echo, stored workspace and target.
async function fetchExactAgent(client, request) {
  const fetched = await client.fetchAgent({ agentId: request.agentId });
  if (!nonemptyId(request.agentId) || !nonemptyId(request.expectedWorkspaceId)) {
    fail("INVALID_AGENT_ID");
    return null;
  }
  if (!fetched || !fetched.agent) {
    fail("AGENT_NOT_FOUND", { agentId: request.agentId });
    return null;
  }
  if (fetched.agent.id !== request.agentId) {
    fail("AGENT_ID_MISMATCH");
    return null;
  }
  if (fetched.agent.workspaceId !== request.expectedWorkspaceId) {
    fail("WORKSPACE_ID_MISMATCH");
    return null;
  }
  return fetched.agent;
}

// archivedAt != null means archived; null or undefined means unarchived.
function agentArchived(agent) {
  return agent.archivedAt != null;
}

// Public client 0.15.0 sendMessage resolves {} once the daemon accepted the message;
// only a queued delivery carries {deliveryStatus: "queued"}. Anything else is unknown.
function sendAcknowledged(ack) {
  if (!ack || typeof ack !== "object" || Array.isArray(ack) || ack.error != null) return false;
  return ack.deliveryStatus == null || ack.deliveryStatus === SEND_QUEUED;
}

function workspaceUnarchivable(inspected, request) {
  return inspected?.kind === "recoverable" && inspected.action === "unarchive"
    && inspected.workspaceId === request.expectedWorkspaceId;
}

function workspaceActive(inspected, request) {
  return inspected?.kind === "unavailable"
    && inspected.reason === "workspace_not_archived"
    && inspected.workspaceId === request.expectedWorkspaceId;
}

// Revive only an agent the user already unarchived whose own workspace is still
// archived and can be unarchived in place (no worktree recreate, no restore).
async function reviveAgent(client, request, agent, key) {
  if (agentArchived(agent)) {
    emit({ ok: true, revived: false, archived: true, agentId: agent.id,
      workspaceId: agent.workspaceId, targetKey: key });
    return;
  }
  if (typeof client.inspectWorkspaceRecovery !== "function"
      || typeof client.restoreWorkspace !== "function") {
    fail("WORKSPACE_RECOVERY_UNSUPPORTED");
    return;
  }
  const inspected = await client.inspectWorkspaceRecovery(request.expectedWorkspaceId);
  let restored = false;
  if (!workspaceActive(inspected, request)) {
    if (!workspaceUnarchivable(inspected, request)) {
      fail("WORKSPACE_RECOVERY_UNSUPPORTED");
      return;
    }
    await client.restoreWorkspace(request.expectedWorkspaceId);
    restored = true;
    const after = await client.inspectWorkspaceRecovery(request.expectedWorkspaceId);
    if (!workspaceActive(after, request)) {
      fail("WORKSPACE_RESTORE_UNCONFIRMED");
      return;
    }
  }
  emit({ ok: true, revived: true, restored, agentId: agent.id,
    workspaceId: agent.workspaceId, targetKey: key });
}

// A revived session ended again: hide its private workspace only. The agent keeps
// its archive (or stays active); this never cancels or archives the agent again.
async function rearchiveWorkspace(client, request, agent, key) {
  if (!agentArchived(agent)) {
    emit({ ok: true, archived: false, agentId: agent.id, workspaceId: agent.workspaceId,
      targetKey: key });
    return;
  }
  if (request.privateWorkspace !== true) { fail("WORKSPACE_NOT_PRIVATE"); return; }
  // An archived workspace is absent from the public directory: recognise the exact
  // already-archived workspace first as a no-op, without any mutation.
  if (typeof client.inspectWorkspaceRecovery === "function") {
    const inspected = await client.inspectWorkspaceRecovery(request.expectedWorkspaceId);
    if (workspaceUnarchivable(inspected, request)) {
      emit({ok: true, archived: true, agentId: agent.id, workspaceId: agent.workspaceId,
        targetKey: key}); return;
    }
    if (!workspaceActive(inspected, request)) { fail("WORKSPACE_ARCHIVE_UNCONFIRMED"); return; }
  }
  // Any mutation still needs the complete public worktree/path/sibling validation.
  if (!await privateWorkspace(client, request, agent)) return;
  if (!await archivePrivateWorkspace(client, request.expectedWorkspaceId)) return;
  emit({ ok: true, archived: true, agentId: agent.id, workspaceId: agent.workspaceId,
    targetKey: key });
}

function emit(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function fail(code, data = {}) {
  emit({ ok: false, code, data: {...data, ...(sendPreDispatch ? {notSent: true} : {})} });
  process.exitCode = 1;
}

function errorCode(error) {
  if (error && typeof error === "object" && typeof error.code === "string"
      && /^[A-Z0-9_]+$/.test(error.code)) {
    return error.code;
  }
  return "PASEO_ERROR";
}

function targetKey(target) {
  if (target.kind === "instance") {
    return `home:${target.home}`;
  }
  return `host:${createHash("sha256").update(target.host).digest("hex")}`;
}

function threadId(agent) {
  const persistence = agent && agent.persistence;
  if (persistence && typeof persistence.nativeHandle === "string" && persistence.nativeHandle) {
    return persistence.nativeHandle;
  }
  const runtime = agent && agent.runtimeInfo;
  if (runtime && typeof runtime.sessionId === "string" && runtime.sessionId) {
    return runtime.sessionId;
  }
  if (persistence && typeof persistence.sessionId === "string" && persistence.sessionId) {
    return persistence.sessionId;
  }
  return "";
}

async function readRequest() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function main() {
  const packageRoot = process.argv[2];
  if (!packageRoot) {
    fail("BRIDGE_USAGE");
    return;
  }
  const request = await readRequest();
  sendPreDispatch = request.command === "send";
  const clientModule = await import(
    pathToFileURL(join(packageRoot, "dist", "utils", "client.js")).href);
  const targetModule = await import(
    pathToFileURL(join(packageRoot, "dist", "utils", "daemon-target.js")).href);

  // A side session must never inherit another workspace/agent from a Paseo terminal.
  delete process.env.PASEO_AGENT_ID;
  delete process.env.PASEO_WORKSPACE_ID;
  const target = targetModule.selectDaemonTarget({}, process.env, false);
  const key = targetKey(target);
  if (request.expectedTargetKey && request.expectedTargetKey !== key) {
    fail("TARGET_CHANGED");
    return;
  }

  const client = await clientModule.connectToDaemon({
    target,
    timeout: request.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  });
  try {
    if (request.command === "agent-archive-states") {
      await readAgentArchiveStates(client, key);
      return;
    }
    if (request.command === "subagents" || request.command === "subagent-timeline") {
      await readNativeSubagents(client, request, key);
      return;
    }
    if (request.command === "send") {
      const agent = await fetchExactAgent(client, request);
      if (!agent) return;
      if (["running", "busy", "starting", "initializing"].includes(agent.status)) {
        fail("AGENT_ALREADY_RUNNING"); return;
      }
      if (typeof client.inspectWorkspaceRecovery !== "function"
          || typeof client.restoreWorkspace !== "function") {
        fail("WORKSPACE_RECOVERY_UNSUPPORTED"); return;
      }
      // The public directory lists active workspaces only: inspect and restore the
      // exact archived workspace in place first, then verify its public ID/cwd.
      const inspected = await client.inspectWorkspaceRecovery(request.expectedWorkspaceId);
      if (!workspaceActive(inspected, request)) {
        if (!workspaceUnarchivable(inspected, request)) {
          fail("WORKSPACE_RECOVERY_UNSUPPORTED"); return;
        }
        const restored = await client.restoreWorkspace(request.expectedWorkspaceId);
        if (restored?.error != null) { fail(errorCode({code: restored.error})); return; }
        if (!workspaceActive(await client.inspectWorkspaceRecovery(request.expectedWorkspaceId), request)) {
          fail("WORKSPACE_RESTORE_UNCONFIRMED"); return;
        }
      }
      if (!await exactWorkspace(client, request)) return;
      sendPreDispatch = false;
      const ack = await client.sendMessage(request.agentId, request.text);
      if (!sendAcknowledged(ack)) { fail("SEND_ACK_UNKNOWN"); return; }
      emit({ok: true, accepted: true, agentId: agent.id,
        workspaceId: agent.workspaceId, targetKey: key});
      return;
    }
    if (request.command === "revive" || request.command === "rearchive") {
      // Every identity check fails closed before any mutation.
      const agent = await fetchExactAgent(client, request);
      if (agent === null) return;
      if (request.command === "revive") {
        await reviveAgent(client, request, agent, key);
      } else {
        await rearchiveWorkspace(client, request, agent, key);
      }
      return;
    }
    if (request.command === "ready") {
      // Read-only probe: an accepted daemon connection plus a list request.
      await client.fetchAgents({ page: { limit: 1 } });
      emit({ ok: true, targetKey: key });
      return;
    }

    if (request.command === "start") {
      // Directory allocation without projectId registers the side worktree as a
      // persistent PROJECT. Workspace/agent archive never removes that project.
      // Register the configured repo instead, retaining the side cwd as workspace.
      // Fail closed before workspace creation on older/incompatible clients.
      if (!nonemptyId(request.projectRoot) || typeof client.addProject !== "function") {
        fail("PROJECT_REGISTRATION_UNSUPPORTED");
        return;
      }
      const registered = await client.addProject(request.projectRoot);
      const projectId = registered?.project?.projectId;
      if (registered?.error || !nonemptyId(projectId)) {
        fail("PROJECT_REGISTRATION_FAILED");
        return;
      }
      const workspace = await client.createWorkspace({
        source: { ...request.source, projectId },
      });
      const workspaceId = workspace && workspace.workspace && workspace.workspace.id;
      if (!workspaceId) {
        fail("WORKSPACE_CREATE_FAILED");
        return;
      }
      let agent;
      const createArgs = {
        provider: request.provider,
        cwd: request.workdir,
        workspaceId,
        title: request.title,
        model: request.model,
        thinkingOptionId: request.effort,
        initialPrompt: request.initialPrompt,
        env: request.env,
        providerOptions: request.providerOptions,
      };
      // Older clients reject an explicit null; only Claude requests carry a mode.
      if (typeof request.modeId === "string" && request.modeId) {
        createArgs.modeId = request.modeId;
      }
      try {
        agent = await client.createAgent(createArgs);
      } catch (error) {
        fail("AGENT_CREATE_FAILED", { workspaceId });
        return;
      }
      if (!agent || typeof agent.id !== "string" || !agent.id) {
        fail("AGENT_CREATE_NO_ID", { workspaceId });
        return;
      }
      // From here on the mutation is known: always return the agent id, even when the
      // follow-up read for the native thread id fails.
      let detail = agent;
      try {
        const fetched = await client.fetchAgent({ agentId: agent.id });
        if (fetched && fetched.agent) {
          detail = fetched.agent;
        }
      } catch {
        // Keep the creation response; the agent id is what matters for lifecycle.
      }
      emit({
        ok: true,
        agentId: agent.id,
        workspaceId: detail.workspaceId || workspaceId,
        threadId: threadId(detail) || threadId(agent),
        targetKey: key,
      });
      return;
    }

    if (request.command === "status") {
      const fetched = await client.fetchAgent({ agentId: request.agentId });
      if (!fetched || !fetched.agent) {
        fail("AGENT_NOT_FOUND", { agentId: request.agentId });
        return;
      }
      emit({
        ok: true,
        status: fetched.agent.status,
        agentId: fetched.agent.id,
        workspaceId: fetched.agent.workspaceId || "",
        threadId: threadId(fetched.agent),
        targetKey: key,
      });
      return;
    }

    if (request.command === "stop" || request.command === "finish") {
      const fetched = await client.fetchAgent({ agentId: request.agentId });
      if (!fetched || !fetched.agent) {
        fail("AGENT_NOT_FOUND", { agentId: request.agentId });
        return;
      }
      // Never mutate an agent resolved to a different identity in a shared project.
      if (!nonemptyId(request.agentId) || fetched.agent.id !== request.agentId) {
        fail("AGENT_ID_MISMATCH");
        return;
      }
      if (request.command === "finish"
          && fetched.agent.workspaceId !== request.expectedWorkspaceId) {
        fail("WORKSPACE_ID_MISMATCH"); return;
      }
      const previous = fetched.agent.status;
      if (previous === "running") await client.cancelAgent(request.agentId);
      if (request.command === "finish") {
        if (!await archiveExactAgent(client, request.agentId)) return;
        emit({ok: true, agentArchived: true, agentId: fetched.agent.id,
          workspaceId: fetched.agent.workspaceId, targetKey: key});
        return;
      }
      emit({
        ok: true,
        status: request.command === "finish" ? "archived" : "stopped",
        previousStatus: previous,
        agentId: fetched.agent.id,
        workspaceId: fetched.agent.workspaceId || "",
        threadId: threadId(fetched.agent),
        targetKey: key,
      });
      return;
    }

    fail("BRIDGE_COMMAND_UNKNOWN");
  } finally {
    await client.close().catch(() => undefined);
  }
}

main().catch((error) => {
  fail(errorCode(error));
});
