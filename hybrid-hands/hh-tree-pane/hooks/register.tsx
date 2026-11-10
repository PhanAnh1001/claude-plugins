// Pane beside the chat showing the hybrid-hands session tree (`hh-ps --json`),
// refreshed on an adaptive interval; the session the pane lives in is listed first.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Tone, TreeSnapshot } from '../types'
import { buildRows, LEGEND } from './tree'
import { MIN_REFRESH_MS, refreshDelay } from './refresh'
import type { HhPs } from './tree'

const PANE = 'hh-tree'
// Resolve only executable paths; never read installed-plugin/auth metadata.
const HH_PS_SHIM = `
import os, re, shutil, sys
from pathlib import Path
cache = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "plugins/cache"
paths = [p for p in cache.glob("*/hybrid-hands/*/bin/hh-ps")
         if re.fullmatch(r"[0-9]+(?:\\.[0-9]+)*", p.parent.parent.name) and os.access(p, os.X_OK)]
paths.sort(key=lambda p: tuple(map(int, p.parent.parent.name.split("."))), reverse=True)
command = str(paths[0]) if paths else shutil.which("hh-ps")
if not command:
    sys.exit("Không tìm thấy hh-ps trong plugin đã cài hoặc PATH")
os.execv(command, [command, *sys.argv[1:]])
`
const SINCE = '3h'
const SCHEDULER_TICK_MS = 1000

const tree = atom(
  { plugin: 'hh-tree-pane', key: 'tree' } as const,
  { rows: [], header: '', error: null } as TreeSnapshot,
  { shape: 'tree-3' },
)

let busy = false
let delayMs = MIN_REFRESH_MS
let nextRefreshAt = 0

async function refresh($: EngineInterface, automatic = false): Promise<void> {
  if (busy) return
  busy = true
  const started = Date.now()
  let failed = true
  let attempted = true
  try {
    if (automatic && !(await $.ui.panes()).some(pane => pane.id === PANE && pane.isShown && pane.isPlaced)) {
      attempted = false
      return
    }
    const here = await $.session.id()
    const r = await $.process.run(['python3', '-c', HH_PS_SHIM, '--since', SINCE, '--json', '--ended', '--full', '--main-session', here], { timeoutMs: 20000 })
    if (r.exitCode !== 0) {
      const error = r.stderr.trim().split('\n').pop() || `hh-ps exit ${r.exitCode}`
      await update($, tree, old => ({ ...old, error }))
      return
    }
    const { rows, header } = buildRows(JSON.parse(r.stdout) as HhPs, here)
    failed = false
    const at = new Date().toTimeString().slice(0, 8)
    await update($, tree, () => ({ rows, header: `${header} · ${at}`, error: null }))
  } catch (err) {
    await update($, tree, old => ({ ...old, error: String(err).slice(0, 200) }))
  } finally {
    if (attempted) {
      delayMs = refreshDelay(Date.now() - started, delayMs, failed)
      nextRefreshAt = Date.now() + delayMs
    }
    busy = false
  }
}

const COLOR: Partial<Record<Tone, string>> = { main: 'cyan', busy: 'green', idle: 'yellow', running: 'green', bad: 'red' }

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'hh-tree', description: 'Mở pane cây hh-ps (phiên brain → subagent → hand ngoài)' })
    void $.ui.open({ id: PANE, title: 'hh-ps' })
    void refresh($)
    $.clock.every(SCHEDULER_TICK_MS, () => {
      if (Date.now() >= nextRefreshAt) void refresh($, true)
    })
    return next(e)
  })

  on('command.run', { command: 'hh-tree' }, async $ => {
    const opened = await $.ui.open({ id: PANE, title: 'hh-ps' })
    void refresh($)
    return {
      text: opened.isPlaced ? 'Đã mở pane hh-ps.' : 'Pane hh-ps đang chờ: terminal cần rộng hơn (khoảng 110 cột trở lên).',
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const snap = await read($, tree)
    const rows = snap.rows
    return (
      <Box flexDirection="column">
        <Text dimColor wrap="truncate-end">{snap.header || 'Đang tải hh-ps…'}</Text>
        <Text dimColor wrap="truncate-end">{LEGEND}</Text>
        {snap.error && <Text color="red" wrap="truncate-end">{snap.error}</Text>}
        {rows.map(row => (
          <Text bold={row.tone === 'main'} dimColor={row.tone === 'dim'} color={COLOR[row.tone]}>
            {'  '.repeat(row.indent)}{row.text}{row.bad ? <Text color="red">{row.bad}</Text> : null}
          </Text>
        ))}
      </Box>
    )
  })
}
