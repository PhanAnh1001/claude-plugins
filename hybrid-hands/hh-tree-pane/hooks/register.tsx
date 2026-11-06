// Pane beside the chat showing the hybrid-hands session tree (`hh-ps --json`),
// refreshed every few seconds; the session the pane lives in is listed first.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Tone, TreeSnapshot } from '../types'
import { buildRows, LEGEND } from './tree'
import type { HhPs } from './tree'

const PANE = 'hh-tree'
const HH_PS = '/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hh-ps'
const SINCE = '3h'
const REFRESH_MS = 5000

const tree = atom(
  { plugin: 'hh-tree-pane', key: 'tree' } as const,
  { rows: [], header: '', error: null } as TreeSnapshot,
  { shape: 'tree-3' },
)

let busy = false

async function refresh($: EngineInterface): Promise<void> {
  if (busy) return
  busy = true
  try {
    const here = await $.session.id()
    const r = await $.process.run([HH_PS, '--since', SINCE, '--json', '--main-session', here], { timeoutMs: 20000 })
    if (r.exitCode !== 0) {
      const error = r.stderr.trim().split('\n').pop() || `hh-ps exit ${r.exitCode}`
      await update($, tree, old => ({ ...old, error }))
      return
    }
    const { rows, header } = buildRows(JSON.parse(r.stdout) as HhPs, here)
    const at = new Date().toTimeString().slice(0, 8)
    await update($, tree, () => ({ rows, header: `${header} · ${at}`, error: null }))
  } catch (err) {
    await update($, tree, old => ({ ...old, error: String(err).slice(0, 200) }))
  } finally {
    busy = false
  }
}

const COLOR: Partial<Record<Tone, string>> = { main: 'cyan', busy: 'green', idle: 'yellow', running: 'green', bad: 'red' }

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'hh-tree', description: 'Mở pane cây hh-ps (phiên brain → subagent → hand ngoài)' })
    void $.ui.open({ id: PANE, title: 'hh-ps' })
    void refresh($)
    $.clock.every(REFRESH_MS, () => void refresh($))
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
    const room = Math.max(3, (e.viewport?.rows ?? 40) - 7)
    const rows = snap.rows.length > room ? [...snap.rows.slice(0, room - 1), { text: `… +${snap.rows.length - room + 1} dòng`, tone: 'dim' as Tone, indent: 0 }] : snap.rows
    return (
      <Box flexDirection="column">
        <Text dimColor wrap="truncate-end">{snap.header || 'Đang tải hh-ps…'}</Text>
        <Text dimColor wrap="truncate-end">{LEGEND}</Text>
        {snap.error && <Text color="red" wrap="truncate-end">{snap.error}</Text>}
        {rows.map(row => (
          <Text wrap="truncate-end" bold={row.tone === 'main'} dimColor={row.tone === 'dim'} color={COLOR[row.tone]}>
            {'  '.repeat(row.indent)}{row.text}{row.bad ? <Text color="red">{row.bad}</Text> : null}
          </Text>
        ))}
      </Box>
    )
  })
}
