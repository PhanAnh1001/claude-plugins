import assert from 'node:assert/strict'
import { test } from 'node:test'
// @ts-ignore -- Node strip-types requires an explicit extension.
import { refreshDelay } from '../hooks/refresh.ts'

test('adaptive delay follows duration and caps repeated errors', () => {
  assert.equal(refreshDelay(15_000), 45_000)
  assert.equal(refreshDelay(1_000), 30_000)
  let delay = 30_000
  for (const expected of [60_000, 120_000, 120_000]) {
    delay = refreshDelay(1_000, delay, true)
    assert.equal(delay, expected)
  }
})
