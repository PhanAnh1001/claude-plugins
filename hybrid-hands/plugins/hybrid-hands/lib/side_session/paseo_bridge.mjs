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
const TIMELINE_METADATA = [
  "provider", "direction", "epoch", "projection", "startCursor", "endCursor",
  "reset", "staleCursor", "gap", "window", "hasOlder", "hasNewer",
];

function nonemptyId(value) {
  return typeof value === "string" && value.trim().length > 0;
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

function emit(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function fail(code, data = {}) {
  emit({ ok: false, code, data });
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
    if (request.command === "subagents" || request.command === "subagent-timeline") {
      await readNativeSubagents(client, request, key);
      return;
    }
    if (request.command === "ready") {
      // Read-only probe: an accepted daemon connection plus a list request.
      await client.fetchAgents({ page: { limit: 1 } });
      emit({ ok: true, targetKey: key });
      return;
    }

    if (request.command === "start") {
      const workspace = await client.createWorkspace({ source: request.source });
      const workspaceId = workspace && workspace.workspace && workspace.workspace.id;
      if (!workspaceId) {
        fail("WORKSPACE_CREATE_FAILED");
        return;
      }
      let agent;
      try {
        agent = await client.createAgent({
          provider: request.provider,
          cwd: request.workdir,
          workspaceId,
          title: request.title,
          model: request.model,
          thinkingOptionId: request.effort,
          initialPrompt: request.initialPrompt,
          env: request.env,
          providerOptions: request.providerOptions,
        });
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
      const previous = fetched.agent.status;
      if (previous === "running") {
        await client.cancelAgent(request.agentId);
      }
      if (request.command === "finish") {
        // Native archive snapshots history and closes runtime without deleting workspace.
        await client.archiveAgent(request.agentId);
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
