// Metadata-only status plus an exact-agent send through the installed public client.
// Never fetch timelines, print lastError/config/auth, or mutate main's side state.
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const emit = value => process.stdout.write(JSON.stringify(value) + '\n');
let client;
try {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const { connectToDaemon } = await import(pathToFileURL(join(process.argv[2], 'dist/utils/client.js')).href);
  const target = request.target || (await import(pathToFileURL(join(process.argv[2], 'dist/utils/daemon-target.js')).href)).selectDaemonTarget({}, process.env, false);
  const key = target.kind === 'instance' ? `home:${target.home}`
    : `host:${createHash('sha256').update(target.host).digest('hex')}`;
  if (request.command !== 'discover' && key !== request.target_key) throw new Error('identity');
  delete process.env.PASEO_AGENT_ID;
  delete process.env.PASEO_WORKSPACE_ID;
  client = await connectToDaemon({target, timeout: 3000});
  const agent = (await client.fetchAgent({agentId: request.agent_id}))?.agent;
  const native = agent?.persistence?.nativeHandle || agent?.runtimeInfo?.sessionId
    || agent?.persistence?.sessionId;
  if (request.command === 'discover') {
    emit({agent_id: agent?.id, workspace_id: agent?.workspaceId, native_id: native,
      cwd: agent?.cwd, paseo_provider: agent?.provider, target, target_key: key});
  } else {
  if (!agent || agent.id !== request.agent_id || agent.workspaceId !== request.workspace_id
      || agent.cwd !== request.cwd || native !== request.native_id
      || agent.provider !== request.paseo_provider) {
    emit({valid: true, closed: true, idle: false, receipt: 'not_sent'});
  } else {
  // Do not return provider text; just classify this current metadata event.
  const quota = agent.attentionReason === 'error' && typeof agent.lastError === 'string'
    && /(?:usage.?limit|rate.?limit|quota|limit.?reached|out of usage)/i.test(agent.lastError)
    && !/(?:capacity|overload|prefill_cap)/i.test(agent.lastError);
  const stamp = quota ? Date.parse(agent.attentionTimestamp) / 1000 : null;
  const idle = (agent.status === 'idle' || (agent.status === 'error' && quota))
    && !agent.activeTurn && Array.isArray(agent.pendingPermissions)
    && agent.pendingPermissions.length === 0 && !agent.archivedAt && !agent.providerUnavailable;
  // A finished attention event ends a turn, not the registered brain work.
  const closed = Boolean(agent.archivedAt) || ['closed', 'stopped'].includes(agent.status);
  const result = {valid: true, idle, blocked_at: Number.isFinite(stamp) ? stamp : null,
    closed, status: agent.status};
  if (request.command === 'send') {
    if (!idle || closed) { emit({receipt: 'not_sent'}); }
    else {
      // Public sendMessage resolves only on daemon acceptance; queued is not yet
      // accepted and deliberately leaves the durable watcher reservation pending.
      const ack = await client.sendMessage(agent.id, request.text);
      emit({receipt: ack && typeof ack === 'object' && !Array.isArray(ack)
        && ack.error == null && ack.deliveryStatus == null ? 'accepted' : 'unknown'});
    }
  } else emit(result);
  }
  }
} catch {
  emit({valid: false, receipt: 'unknown'});
} finally {
  try { await client?.close(); } catch { /* bounded by Python timeout */ }
}
