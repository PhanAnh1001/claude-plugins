// Run: node --experimental-strip-types --test hh-tree-pane/tests/tree.test.ts
import assert from 'node:assert/strict'
import { test } from 'node:test'

// @ts-ignore -- Node's strip-types needs the explicit .ts specifier.
import { buildRows, LEGEND, limitLine, percentText } from '../hooks/tree.ts'

const NOW = '2026-11-06T10:00:00Z'

test('limit percent keeps one decimal', () => {
  assert.equal(percentText(12.34), '12.3%')
  assert.equal(percentText(12), '12.0%')
  assert.equal(percentText(0), '0.0%')
  assert.equal(percentText(0.01), '<0.1%')
  assert.equal(percentText(null), '')
})

test('rows show USD and limit % but no token counts', () => {
  const data = {
    generated_at: NOW,
    sessions: [{
      session_id: 'main', name: 'cha', status: 'busy', live: true, last_activity: NOW,
      context_tokens: 157_200, usage: { read: 1000, cache_read: 2000, cache_write: 300, out: 40, usd: 0.42, week_pct: null },
      subagents: [{ description: 'con', agent_type: 't', status: 'finished', context_tokens: 2000,
        duration_seconds: 60, ended_at: NOW, usage: { read: 5, out: 7, usd: 0.02 } }],
      hand_runs: [{ label: 'lượt hand', backend: 'dsh', status: 'ok', state: 'finished',
        tokens: { input: 1_000_000, cached_input: 400_000, output: 500_000 },
        usage: { read: 600_000, cache_read: 400_000, out: 500_000, usd: 0.7824,
          week_pct: 1.5648, week_pct_estimated: true },
        started_at: '2026-11-06T09:00:00Z', ended_at: NOW, duration_seconds: 3600 }],
    }],
  }
  const text = buildRows(data, 'main').rows.map(r => r.text).join('\n')
  assert.match(text, /\$0\.42/)
  assert.match(text, /\$0\.78\s+~1\.6% tuần/)
  for (const gone of ['|', 'ctx ', 'out ', '157k', '500k']) assert.ok(!text.includes(gone), `${gone} in\n${text}`)
  assert.ok(!LEGEND.includes('token'))
})

test('limits block sits at the top of the pane', () => {
  const now = new Date(2026, 10, 6, 14, 5, 0).getTime()
  const generated = new Date(now).toISOString()
  const data = {
    generated_at: generated,
    limits: [{
      plan: 'Go', window: 'tuần', this_machine_pct: 12.34, other_pct: 4.46,
      total_pct: 16.8, resets_at: new Date(2026, 10, 6, 14, 0, 0).toISOString(),
      source: 'go_live+ledger',
    }, {
      plan: 'Go', window: '5h', this_machine_pct: 1, other_pct: 1,
      total_pct: 2, resets_at: null, source: 'go_live+ledger',
    }],
    sessions: [],
  }
  const rows = buildRows(data, 'main').rows
  assert.equal(rows[0].text, 'Hạn mức')
  assert.equal(rows[1].text, 'Go tuần   máy này 12.3% · máy khác 4.5% · tổng 16.8% · reset 14:00')
  assert.ok(!rows.some(row => row.text.includes(' 5h ')), 'the 5h window is not rendered')
  assert.equal(limitLine({ plan: 'Go', window: 'tuần', this_machine_pct: 20,
    other_pct: null, total_pct: null, resets_at: null }, now),
  'Go tuần   máy này 20.0% · máy khác ? · tổng ?')
})
