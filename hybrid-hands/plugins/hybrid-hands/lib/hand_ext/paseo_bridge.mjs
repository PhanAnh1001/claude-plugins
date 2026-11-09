// Official @getpaseo/cli 0.15.0 public client only. No daemon RPC or config edits.
import {createHash} from 'node:crypto';
import {readFile, stat} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const die = code => { throw Object.assign(new Error(code), {safeCode: code}); };
const check = (value, code) => { if (!value) die(code); };
export function targetFingerprint(target) {
  check(target && ['instance', 'endpoint'].includes(target.kind), 'TARGET_INVALID');
  return createHash('sha256').update(JSON.stringify(target.kind === 'instance'
    ? ['instance', target.home] : ['endpoint', target.host])).digest('hex');
}
export async function validatePackage(root) {
  check(Number(process.versions.node.split('.')[0]) >= 22, 'NODE_UNSUPPORTED');
  check(typeof root === 'string' && root.startsWith('/'), 'PACKAGE_INVALID');
  const pkg = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
  check(pkg.name === '@getpaseo/cli' && pkg.version === '0.15.0' && pkg.type === 'module', 'PACKAGE_UNSUPPORTED');
}
async function directory(path) {
  check(typeof path === 'string' && resolve(path) === path, 'CWD_INVALID');
  check(await stat(path).then(x => x.isDirectory(), () => false), 'CWD_MISSING');
}
// Resolve only from the pinned CLI dependency tree; never download or substitute schemas.
export async function loadSchemas(root) {
  await validatePackage(root);
  const require = createRequire(join(root, 'package.json'));
  return import(pathToFileURL(require.resolve('@getpaseo/protocol/messages')));
}
const schemaNames = {workspace:'WorkspaceCreateRequestSchema', create:'AgentCreateRequestSchema',
  send:'SendAgentMessageRequestSchema', 'validate-workspace-id':'WorkspaceCreateRequestSchema'};
export function payload(r) {
  const requestId = r.requestKey ?? r.messageId ?? 'preflight';
  if (r.command === 'workspace') return {type:'workspace.create.request', requestId,
    source:{kind:'directory', path:r.cwd, projectId:r.projectId}, workspaceId:r.workspaceId,
    callerAgentId:r.parentAgentId, idempotencyKey:r.workspaceKey};
  if (r.command === 'create') return {type:'agent.create.request', requestId,
    agentId:r.agentId, workspaceId:r.workspaceId, callerAgentId:r.parentAgentId,
    idempotencyKey:r.agentKey, env:r.gatewayEnv, config:{provider:r.providerId, cwd:r.cwd,
      ...(r.model ? {model:r.model} : {}), ...(r.effort ? {thinkingOptionId:r.effort} : {})}};
  if (r.command === 'send') return {type:'send_agent_message_request', requestId,
    agentId:r.agentId, text:r.brief, messageId:r.messageId, sourceAgentId:r.parentAgentId,
    activeTurnBehavior:'steer'};
}
export function preflight(r, schemas) {
  const name = schemaNames[r.command];
  if (!name) return null;
  const schema = schemas?.[name];
  check(typeof schema?.safeParse === 'function', 'SCHEMA_UNAVAILABLE');
  const result = r.command === 'validate-workspace-id'
    ? schema.shape.workspaceId.safeParse(r.workspaceId) : schema.safeParse(payload(r));
  if (result.success) return null;
  return {ok:false, code:'REQUEST_SCHEMA_REJECTED', notSent:true, schema:name,
    issues:result.error.issues.map(x => ({path:r.command === 'validate-workspace-id'
      ? ['workspaceId', ...x.path] : x.path, code:x.code}))};
}
// Public directory contains active workspaces. Missing archived metadata fails closed.
async function workspace(client, id) {
  let cursor;
  const seen = new Set();
  for (let page = 0; page < 20; page++) {
    const result = await client.fetchWorkspaces({filter: {idPrefix:id},
      page: {limit: 200, ...(cursor ? {cursor} : {})}});
    check(!result?.error && Array.isArray(result?.entries), 'WORKSPACE_UNCONFIRMED');
    const entry = result.entries.find(x => x.id === id);
    if (entry) return entry;
    cursor = result.pageInfo?.nextCursor;
    if (cursor === null) return null;
    check(typeof cursor === 'string' && !seen.has(cursor), 'WORKSPACE_UNCONFIRMED');
    seen.add(cursor);
  }
  die('WORKSPACE_UNCONFIRMED');
}
async function parent(client, r) {
  const a = (await client.fetchAgent({agentId: r.parentAgentId}))?.agent;
  check(a?.id === r.parentAgentId && a.workspaceId, 'PARENT_MISMATCH');
  const w = await workspace(client, a.workspaceId);
  check(w?.projectId, 'PROJECT_UNVERIFIED');
  if (r.projectId) check(w.projectId === r.projectId, 'PROJECT_MISMATCH');
  return {projectId: w.projectId, parentAgentId: a.id, parentWorkspaceId: a.workspaceId};
}
async function exact(client, r) {
  await parent(client, r);
  check(r.agentId && r.agentId !== r.parentAgentId && r.workspaceId, 'CHILD_ID_INVALID');
  const a = (await client.fetchAgent({agentId: r.agentId}))?.agent;
  check(a?.id === r.agentId && a.workspaceId === r.workspaceId, 'CHILD_MISMATCH');
  check(a.provider === r.providerId && a.cwd === r.cwd
    && a.labels?.['paseo.parent-agent-id'] === r.parentAgentId, 'PLACEMENT_MISMATCH');
  if (r.model) check(a.model === r.model, 'MODEL_MISMATCH');
  if (r.effort) check(a.thinkingOptionId === r.effort, 'EFFORT_MISMATCH');
  const w = await workspace(client, r.workspaceId);
  check(w?.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
  return a;
}
const methods = ['fetchAgent','fetchWorkspaces','listAvailableProviders','createWorkspace','createAgent',
  'sendMessage','fetchAgentTimeline','cancelAgent','archiveAgent','inspectWorkspaceRecovery','restoreWorkspace','refreshAgent'];
// Injectable entry exercises the same request shapes and identity gates as production.
export async function handleRequest(client, r, target, schemas) {
  try {
    const rejected = preflight(r, schemas);
    if (rejected) return rejected;
    const wire = payload(r);
    const fingerprint = targetFingerprint(target);
    check(r.targetKey === fingerprint, 'TARGET_MISMATCH');
    if (r.command === 'probe') {
      check(methods.every(x => typeof client[x] === 'function'), 'CAPABILITY_MISSING');
      const p = await client.listAvailableProviders();
      check(!p?.error && Array.isArray(p?.providers), 'CAPABILITY_UNCONFIRMED');
      return {ok: true, targetKey: fingerprint,
        providers: p.providers.filter(x => x.available && !x.error).map(x => x.provider)};
    }
    if (r.command === 'parent') return {ok: true, targetKey: fingerprint, ...await parent(client, r)};
    await directory(r.cwd);
    await parent(client, r);
    if (r.command === 'verify-workspace') {
      const w = await workspace(client, r.workspaceId);
      check(w?.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
    } else if (r.command === 'workspace') {
      const before = await workspace(client, r.workspaceId);
      check(!before, 'WORKSPACE_ALREADY_EXISTS');
      await client.createWorkspace(wire);
      const w = await workspace(client, r.workspaceId);
      check(w?.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
    } else if (r.command === 'create') {
      const w = await workspace(client, r.workspaceId);
      check(w?.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
      check(r.agentId !== r.parentAgentId, 'CHILD_ID_INVALID');
      const providers = await client.listAvailableProviders();
      check(providers?.providers?.some(p => p.provider === r.providerId && p.available && !p.error), 'PROVIDER_UNAVAILABLE');
      const {type, ...options} = wire;
      await client.createAgent(options);
      await exact(client, r);
    } else if (r.command === 'reconcile') {
      const w = await workspace(client, r.workspaceId);
      if (!w) return {ok:true, state:'unresolved', targetKey:fingerprint};
      check(w.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
      if (r.pending === 'workspace' || (!r.createConfirmed && !r.agentKey))
        return {ok:true, state:'workspace_verified', targetKey:fingerprint};
      const fetched = await client.fetchAgent({agentId:r.agentId});
      if (!fetched?.agent) return {ok:true, state:'unresolved', targetKey:fingerprint};
      const observed = await exact(client, r);
      if (r.pending === 'archive' && Number.isFinite(Date.parse(observed.archivedAt)))
        return {ok:true,state:'archived',targetKey:fingerprint};
      // Cancel ACK loss cannot prove process/group quiescence from public idle.
      if (r.cancelPending) return {ok:true,state:'unresolved',targetKey:fingerprint};
      if (r.pending === 'reopen')
        return {ok:true,state:'unresolved',targetKey:fingerprint}; // no refresh receipt API
      let delivered = false;
      if (r.messageId) {
        const t = await client.fetchAgentTimeline(r.agentId, {limit:200});
        check(!t?.error && t.agentId === r.agentId && Array.isArray(t.entries), 'RECEIPT_UNCONFIRMED');
        delivered = t.entries.some(x => x.item?.type === 'user_message' && x.item.messageId === r.messageId);
      }
      return {ok:true, state:r.messageId ? (delivered ? 'delivered' : 'unresolved') : 'child_verified', targetKey:fingerprint};
    } else {
      const a = await exact(client, r);
      if (r.command === 'verify-child') { /* Read-only binding for a fresh epoch. */ }
      else if (r.command === 'send') {
        check(r.admitted === true && r.quiescent === true && !a.archivedAt, 'ADMISSION_REQUIRED');
        check(typeof r.messageId === 'string' && r.messageId.length > 0, 'MESSAGE_ID_REQUIRED');
        await client.sendMessage(wire.agentId, wire.text, wire);
      } else if (r.command === 'cancel') await client.cancelAgent(r.agentId);
      else if (r.command === 'archive') {
        check(r.reviewed === true && r.quiescent === true, 'REVIEW_REQUIRED');
        const result = await client.archiveAgent(r.agentId);
        check(!result?.error && Number.isFinite(Date.parse(result?.archivedAt)), 'ARCHIVE_UNCONFIRMED');
      } else if (r.command === 'reopen') {
        check(r.quiescent === true && a.archivedAt, 'QUIESCENCE_REQUIRED');
        const recovery = await client.inspectWorkspaceRecovery(r.workspaceId);
        const active = recovery?.kind === 'unavailable' && recovery.reason === 'workspace_not_archived';
        const unarchive = recovery?.kind === 'recoverable' && recovery.action === 'unarchive';
        check(recovery?.workspaceId === r.workspaceId && (active || unarchive), 'RECOVERY_BLOCKED');
        await directory(r.cwd);
        if (unarchive) {
          await client.restoreWorkspace(r.workspaceId);
          const restored = await client.inspectWorkspaceRecovery(r.workspaceId);
          check(restored?.workspaceId === r.workspaceId && restored.kind === 'unavailable'
            && restored.reason === 'workspace_not_archived', 'RESTORE_UNCONFIRMED');
          await exact(client, r);
        }
        await client.refreshAgent(r.agentId);
        const after = await exact(client, r);
        check(!after.archivedAt, 'REOPEN_UNCONFIRMED');
      } else die('COMMAND_INVALID');
    }
    return {ok:true, state:'confirmed', targetKey:fingerprint};
  } catch (error) {
    // Never forward upstream error messages, arbitrary codes, endpoint or config.
    return {ok:false, code:error?.safeCode ?? 'TRANSPORT_UNRESOLVED'};
  }
}
async function main() {
  try {
    const root = process.argv[2];
    await validatePackage(root);
    let input = '';
    for await (const chunk of process.stdin) { input += chunk; check(input.length < 2_000_000, 'REQUEST_TOO_LARGE'); }
    const r = JSON.parse(input);
    const schemas = await loadSchemas(root);
    const rejected = preflight(r, schemas);
    if (rejected || r.command === 'validate-workspace-id') {
      process.stdout.write(JSON.stringify(rejected ?? {ok:true})+'\n');
      return;
    }
    const {selectDaemonTarget} = await import(pathToFileURL(join(root,'dist/utils/daemon-target.js')));
    const {connectToDaemon} = await import(pathToFileURL(join(root,'dist/utils/client.js')));
    check(r.target && ['instance','endpoint'].includes(r.target.kind), 'TARGET_INVALID');
    const options = r.target.kind === 'instance' ? {home:r.target.home} : {host:r.target.host};
    const target = selectDaemonTarget(options, process.env, false);
    check(targetFingerprint(target) === r.targetKey, 'TARGET_MISMATCH');
    const client = await connectToDaemon({target, timeout:3000});
    try { process.stdout.write(JSON.stringify(await handleRequest(client,r,target,schemas))+'\n'); }
    finally { await client.close(); }
  } catch { process.stdout.write(JSON.stringify({ok:false,code:'BRIDGE_UNAVAILABLE'})+'\n'); }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main();
