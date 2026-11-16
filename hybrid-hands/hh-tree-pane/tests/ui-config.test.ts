import assert from 'node:assert/strict'
import { test } from 'node:test'
// @ts-ignore -- Node strip-types requires an explicit extension.
import { parseUiToggle } from '../hooks/ui-config.ts'

test('ui toggle: disabled output turns pane off; broken/empty output fails open', () => {
  assert.deepEqual(parseUiToggle('{"enabled": false, "source": "global"}'), { enabled: false, source: 'global' })
  for (const [out, code] of [['', 0], ['not json', 0], ['{"enabled": false}', 1]] as const) {
    assert.equal(parseUiToggle(out, code).enabled, true)
  }
})
