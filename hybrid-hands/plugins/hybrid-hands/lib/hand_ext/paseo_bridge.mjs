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
    idempotencyKey:r.agentKey, env:r.gatewayEnv, config:{...(r.title ? {title:r.title} : {}), provider:r.providerId, cwd:r.cwd,
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
async function childIdentity(client, r) {
  const owner = await parent(client, r);
  check(typeof r.agentId === 'string' && r.agentId.trim().length > 0
    && r.agentId !== r.parentAgentId && typeof r.workspaceId === 'string'
    && r.workspaceId.trim().length > 0 && r.workspaceId !== owner.parentWorkspaceId, 'CHILD_ID_INVALID');
  const a = (await client.fetchAgent({agentId: r.agentId}))?.agent;
  check(a?.id === r.agentId && a.workspaceId === r.workspaceId, 'CHILD_MISMATCH');
  check(a.provider === r.providerId && a.cwd === r.cwd
    && a.labels?.['paseo.parent-agent-id'] === r.parentAgentId, 'PLACEMENT_MISMATCH');
  if (r.model) check(a.model === r.model, 'MODEL_MISMATCH');
  if (r.effort) check(a.thinkingOptionId === r.effort, 'EFFORT_MISMATCH');
  return a;
}
async function exact(client, r) {
  const a = await childIdentity(client, r);
  await activeWorkspace(client, r);
  return a;
}
const archived = a => typeof a?.archivedAt === 'string' && Number.isFinite(Date.parse(a.archivedAt));
async function activeWorkspace(client, r) {
  const w = await workspace(client, r.workspaceId);
  check(w?.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
  return w;
}
async function archivedAgent(client, agentId) {
  let cursor;
  const seen = new Set();
  for (let page = 0; page < 20; page++) {
    const result = await client.fetchAgents({filter:{includeArchived:true},
      page:{limit:200, ...(cursor ? {cursor} : {})}});
    check(!result?.error && Array.isArray(result?.entries), 'AGENT_UNCONFIRMED');
    const hit = result.entries.find(entry => entry?.agent?.id === agentId);
    if (hit) return hit.agent;
    cursor = result.pageInfo?.nextCursor;
    if (cursor === null) return null;
    check(typeof cursor === 'string' && cursor && !seen.has(cursor), 'AGENT_UNCONFIRMED');
    seen.add(cursor);
  }
  check(false, 'AGENT_UNCONFIRMED');
}
async function agentTerminal(client, r, fingerprint) {
  check(typeof r.agentId === 'string' && r.agentId.length > 0
    && typeof r.workspaceId === 'string' && r.workspaceId.length > 0, 'CHILD_ID_INVALID');
  let fetched = null;
  // A fetch error is not proof either way; fall back to the archived listing.
  try { fetched = (await client.fetchAgent({agentId:r.agentId, timeout:3000}))?.agent ?? null; }
  catch { fetched = null; }
  const a = fetched ?? await archivedAgent(client, r.agentId);
  check(a?.id === r.agentId && a.workspaceId === r.workspaceId, 'CHILD_MISMATCH');
  // Archived agents can come back with empty labels; identity is already pinned by
  // agentId+workspaceId, so an absent parent label passes but a wrong one never does.
  const labels = a.labels ?? {};
  const hasParent = Object.prototype.hasOwnProperty.call(labels, 'paseo.parent-agent-id');
  check(!hasParent || labels['paseo.parent-agent-id'] === r.parentAgentId, 'PLACEMENT_MISMATCH');
  return {ok:true, targetKey:fingerprint, agentId:a.id, workspaceId:a.workspaceId,
    status:a.status, archived:archived(a), parentLabel:hasParent ? 'match' : 'absent'};
}
async function recoveryPlan(client, r) {
  const plan = await client.inspectWorkspaceRecovery(r.workspaceId);
  check(plan?.workspaceId === r.workspaceId, 'RECOVERY_BLOCKED');
  if (plan.kind === 'recoverable' && plan.action === 'unarchive') return 'archived';
  check(plan.kind === 'unavailable' && plan.reason === 'workspace_not_archived', 'RECOVERY_BLOCKED');
  await activeWorkspace(client, r);
  return 'active';
}
async function archivedMembers(client, r) {
  let cursor;
  const seen = new Set(), ids = new Set();
  let found = false;
  for (let page = 0; page < 20; page++) {
    const result = await client.fetchAgents({filter:{includeArchived:true},
      page:{limit:200, ...(cursor ? {cursor} : {})}});
    check(!result?.error && Array.isArray(result?.entries), 'MEMBERSHIP_UNCONFIRMED');
    for (const entry of result.entries) {
      const a = entry?.agent;
      check(typeof a?.id === 'string' && a.id.trim().length > 0
        && typeof a.workspaceId === 'string' && a.workspaceId.trim().length > 0 && !ids.has(a.id),
        'MEMBERSHIP_UNCONFIRMED');
      ids.add(a.id);
      if (a.workspaceId !== r.workspaceId) continue;
      check(archived(a), 'WORKSPACE_ACTIVE_MEMBER');
      // This private workspace belongs only to the verified child. Archived
      // siblings still have unknown ownership, regardless of labels/provider.
      check(a.id === r.agentId, 'WORKSPACE_UNOWNED_MEMBER');
      found = true;
    }
    cursor = result.pageInfo?.nextCursor;
    if (cursor === null) { check(found, 'MEMBERSHIP_UNCONFIRMED'); return; }
    check(typeof cursor === 'string' && cursor.length > 0 && !seen.has(cursor), 'MEMBERSHIP_UNCONFIRMED');
    seen.add(cursor);
  }
  die('MEMBERSHIP_UNCONFIRMED');
}
async function names(client, r) {
  check(typeof r.title === 'string' && [...r.title].length <= 60 && !/[\x00-\x1f\x7f/\\]/.test(r.title), 'NAME_INVALID');
  const owner = await parent(client, r), a = await childIdentity(client, r);
  const main = a => a.main_session || a.role === 'main' || a.labels?.main_session || a.labels?.role === 'main';
  check(!main(a), 'NAME_MAIN_BLOCKED');
  if (r.apply && a.title !== r.title) {
    const updated = await client.updateAgent(r.agentId, {name:r.title});
    check(!updated?.error && (await childIdentity(client, r)).title === r.title, 'NAME_AGENT_UNCONFIRMED');
  }
  let eligible = false;
  try {
    check(r.workspaceOwned === true && r.workspaceId !== owner.parentWorkspaceId, 'NAME_WORKSPACE_UNOWNED');
    const expected = new Map((r.ownedChildren ?? []).filter(x => x.workspaceId === r.workspaceId).map(x => [x.agentId, x]));
    check(expected.size === 1 && expected.has(r.agentId), 'NAME_WORKSPACE_UNOWNED');
    let cursor, complete = false; const seen = new Set(), ids = new Set(); let members = 0;
    for (let page = 0; page < 20; page++) {
      const result = await client.fetchAgents({filter:{includeArchived:true}, page:{limit:200, ...(cursor ? {cursor} : {})}});
      check(!result?.error && Array.isArray(result?.entries), 'MEMBERSHIP_UNCONFIRMED');
      for (const entry of result.entries) {
        const m = entry?.agent;
        check(typeof m?.id === 'string' && m.id && typeof m.workspaceId === 'string' && m.workspaceId && !ids.has(m.id), 'MEMBERSHIP_UNCONFIRMED');
        ids.add(m.id);
        if (m.workspaceId !== r.workspaceId) continue;
        const known = expected.get(m.id);
        check(known && !main(m) && m.id !== r.parentAgentId && m.provider === known.providerId
          && m.cwd === known.cwd && m.labels?.['paseo.parent-agent-id'] === known.parentAgentId, 'NAME_WORKSPACE_UNOWNED');
        members++;
        check(members === 1 && m.id === r.agentId, 'NAME_WORKSPACE_SHARED');
      }
      cursor = result.pageInfo?.nextCursor;
      if (cursor === null) {complete = true; break;}
      check(typeof cursor === 'string' && cursor && !seen.has(cursor), 'MEMBERSHIP_UNCONFIRMED');
      seen.add(cursor);
    }
    check(complete && members === 1, 'MEMBERSHIP_UNCONFIRMED');
    const w = await workspace(client, r.workspaceId);
    check(w?.projectId === r.projectId, 'WORKSPACE_UNCONFIRMED');
    if (r.apply && w.title !== r.title) {
      const updated = await client.setWorkspaceTitle(r.workspaceId, r.title);
      check(!updated?.error && updated?.title === r.title, 'NAME_WORKSPACE_UNCONFIRMED');
    }
    eligible = true;
  } catch { /* Workspace refusal never blocks the separately owned agent. */ }
  return {ok:true, targetKey:r.targetKey, agentId:r.agentId, workspaceId:r.workspaceId,
    title:r.title, applied:r.apply === true, workspace:{eligible}, ...(eligible ? {} : {warning:'NAME_WORKSPACE_BLOCKED'})};
}
async function lifecycle(client, r, observe = false) {
  const a = await childIdentity(client, r);
  const state = await recoveryPlan(client, r);
  const archive = (r.pending ?? r.command) === 'archive';
  if (archive) {
    check(r.settled === true && r.quiescent === true, 'SETTLEMENT_REQUIRED');
    if (!archived(a)) {
      if (observe) return 'unresolved';
      check(state === 'active', 'ARCHIVE_UNCONFIRMED');
      const result = await client.archiveAgent(r.agentId);
      check(!result?.error && archived(result), 'ARCHIVE_UNCONFIRMED');
      check(archived(await childIdentity(client, r)), 'ARCHIVE_UNCONFIRMED');
    }
    await archivedMembers(client, r);
    if (state === 'active') {
      if (observe) return 'unresolved';
      const result = await client.archiveWorkspace(r.workspaceId);
      check(!result?.error && archived(result), 'ARCHIVE_UNCONFIRMED');
    }
    check(await recoveryPlan(client, r) === 'archived', 'ARCHIVE_UNCONFIRMED');
    return 'archived';
  }
  check(r.reviewed === true && r.quiescent === true, 'REVIEW_REQUIRED');
  if (!a.archivedAt) {
    check(state === 'active', 'REOPEN_UNCONFIRMED');
    await exact(client, r);
    return 'reopened'; // Includes reconciliation after refresh ACK loss; never refresh twice.
  }
  check(archived(a), 'REOPEN_UNCONFIRMED');
  if (observe) return 'unresolved';
  if (state === 'archived') await client.restoreWorkspace(r.workspaceId);
  await directory(r.cwd);
  await exact(client, r); // Full active placement must be restored before refresh.
  await client.refreshAgent(r.agentId);
  check(!(await exact(client, r)).archivedAt, 'REOPEN_UNCONFIRMED');
  return 'reopened';
}
// Public CreationClient uses this same observation API (daemon-client.js:452).
// Failed + outcomeUnknown=false implies inFlight=null in pinned CreationService
// catch path (creation/index.js:145-164); the public snapshot omits inFlight.
async function creationFailure(client, r, target) {
  check(typeof r.agentKey === 'string' && r.agentKey.length > 0, 'CREATION_UNCONFIRMED');
  const info = client.getLastServerInfoMessage();
  check(info && info.features && typeof info.features === 'object', 'CAPABILITY_UNCONFIRMED');
  check(info.features.creationLifecycle === undefined || typeof info.features.creationLifecycle === 'boolean',
    'CAPABILITY_UNCONFIRMED');
  let snapshot, inFlight;
  if (info.features.creationLifecycle === true) {
    // Only this pinned server transition proves the omitted inFlight field.
    check(info.version === '0.15.0', 'CREATION_UNCONFIRMED');
    const observation = client.observe('creation.subscribe.response', {
      type:'creation.subscribe.request', kind:'agent', idempotencyKey:r.agentKey});
    let timer;
    try {
      snapshot = await new Promise((done, fail) => {
        timer = setTimeout(() => fail(new Error('timeout')), 3000);
        observation.subscribe({snapshot(result) {
          if (result?.error !== null || !result?.snapshot) return fail(new Error('unavailable'));
          done(result.snapshot);
        }, error:fail});
      });
    } finally {
      clearTimeout(timer);
      await observation.release();
    }
    check(snapshot?.phase === 'failed' && snapshot.outcomeUnknown === false
      && snapshot.failedStage === 'agent', 'CREATION_UNCONFIRMED');
    inFlight = null; // Proven by the pinned lifecycle transition, not UI idle.
  } else {
    // Fixed instance-only receipt; never scan config, auth, logs or other files.
    check(target.kind === 'instance' && typeof target.home === 'string'
      && resolve(target.home) === target.home, 'CREATION_UNCONFIRMED');
    const identity = createHash('sha256').update(JSON.stringify(['agent', r.agentKey])).digest('hex');
    const receipt = JSON.parse(await readFile(join(target.home, 'creations', identity+'.json'), 'utf8'));
    snapshot = receipt.snapshot;
    inFlight = receipt.inFlight;
  }
  check(snapshot?.kind === 'agent' && snapshot.idempotencyKey === r.agentKey
    && snapshot.agentId === r.agentId && snapshot.workspaceId === r.workspaceId
    && snapshot.phase === 'failed' && snapshot.outcomeUnknown === false
    && snapshot.failedStage === 'agent' && inFlight === null && !snapshot.agent, 'CREATION_UNCONFIRMED');
  // CLI agent inspect maps exactly this successful null return to AGENT_NOT_FOUND.
  // fetchAgent throws on errors; undefined/malformed responses are never absence.
  check(await client.fetchAgent({agentId:r.agentId, timeout:3000}) === null, 'CHILD_ABSENCE_UNCONFIRMED');
  return {ok:true, targetKey:r.targetKey, agentId:r.agentId, agentKey:r.agentKey,
    workspaceId:r.workspaceId, phase:'failed', outcomeUnknown:false, inFlight:null,
    absence:'AGENT_NOT_FOUND'};
}
const methods = ['fetchAgent','fetchAgents','archiveWorkspace','fetchWorkspaces','listAvailableProviders','createWorkspace','createAgent',
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
    // Recovery observes an immutable child receipt, even after its parent or
    // workspace is archived. Never use this exception for mutation requests.
    if (r.command === 'creation-failure') {
      check(typeof r.agentId === 'string' && r.agentId.length > 0
        && typeof r.parentAgentId === 'string' && r.parentAgentId.length > 0
        && r.agentId !== r.parentAgentId
        && typeof r.workspaceId === 'string' && r.workspaceId.length > 0, 'CHILD_ID_INVALID');
      const w = await workspace(client, r.workspaceId);
      // A successful directory miss is not proof; exact creation and public
      // fetchAgent absence below remain mandatory. Directory errors reject.
      if (w) check(w.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
      return await creationFailure(client, r, target);
    }
    // Read-only operator_reconcile probe; the child may be archived and its cwd gone.
    if (r.command === 'agent-terminal') return await agentTerminal(client, r, fingerprint);
    if (r.command === 'names') return await names(client, r);
    await directory(r.cwd);
    await parent(client, r);
    if (r.command === 'prompt-failure') {
      const a = await exact(client, r);
      check(['error', 'closed'].includes(a.status), 'GATEWAY_NOT_TERMINATED');
      return {ok:true, targetKey:fingerprint, agentId:r.agentId,
        workspaceId:r.workspaceId, messageId:r.messageId, status:a.status};
    }
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
      const owner = await parent(client, r);
      check(typeof r.agentId === 'string' && r.agentId.trim().length > 0
        && r.agentId !== r.parentAgentId && r.workspaceId !== owner.parentWorkspaceId, 'CHILD_ID_INVALID');
      const providers = await client.listAvailableProviders();
      check(providers?.providers?.some(p => p.provider === r.providerId && p.available && !p.error), 'PROVIDER_UNAVAILABLE');
      const {type, ...options} = wire;
      await client.createAgent(options);
      await exact(client, r);
    } else if (['archive','reopen'].includes(r.command)
        || (r.command === 'reconcile' && ['archive','reopen'].includes(r.pending))) {
      return {ok:true, state:await lifecycle(client, r, r.command === 'reconcile'), targetKey:fingerprint};
    } else if (r.command === 'reconcile') {
      const w = await workspace(client, r.workspaceId);
      if (!w) return {ok:true, state:'unresolved', targetKey:fingerprint};
      check(w.projectId === r.projectId && w.workspaceDirectory === r.cwd, 'WORKSPACE_MISMATCH');
      if (r.pending === 'workspace' || (!r.createConfirmed && !r.agentKey))
        return {ok:true, state:'workspace_verified', targetKey:fingerprint};
      const fetched = await client.fetchAgent({agentId:r.agentId});
      if (!fetched?.agent) return {ok:true, state:'unresolved', targetKey:fingerprint};
      const observed = await exact(client, r);
      if (r.cancelPending) return {ok:true,state:'unresolved',targetKey:fingerprint};
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
      else die('COMMAND_INVALID');
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
