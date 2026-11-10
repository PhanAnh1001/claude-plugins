import assert from 'node:assert/strict'
import { test } from 'node:test'
// @ts-ignore -- Node strip-types requires an explicit extension.
import { refreshDelay, RefreshGate, revisionKey, RevisionWatch } from '../hooks/refresh.ts'

test('adaptive delay follows duration and caps repeated errors', () => {
  assert.equal(refreshDelay(15_000), 45_000)
  assert.equal(refreshDelay(1_000), 30_000)
  let delay = 30_000
  for (const expected of [60_000, 120_000, 120_000]) {
    delay = refreshDelay(1_000, delay, true)
    assert.equal(delay, expected)
  }
})

test('revision change refreshes once after debounce; signals while running add one run', async () => {
  let runs = 0
  let release = (): void => {}
  const gate = new RefreshGate(() => { runs++; return new Promise(r => { release = () => r(true) }) }, 1000)
  const watch = new RevisionWatch()
  assert.equal(watch.changed(revisionKey({ mtimeMs: 1, size: 2 })), false)
  assert.equal(watch.changed(revisionKey({ mtimeMs: 5, size: 2 })), true)
  gate.request(0)
  await gate.tick(999)
  assert.equal(runs, 0)
  const running = gate.tick(1000)
  gate.request(1100); gate.request(1200)
  release(); await running
  const second = gate.tick(1300); release(); await second
  await gate.tick(5000)
  assert.equal(runs, 2)
})

test('unchanged or missing revision file does not refresh', () => {
  const watch = new RevisionWatch()
  assert.equal(watch.changed(undefined), false)
  watch.changed(revisionKey({ mtimeMs: 1, size: 2 }))
  assert.equal(watch.changed(revisionKey({ mtimeMs: 1, size: 2 })), false)
  assert.equal(watch.changed(undefined), false)
  assert.equal(watch.changed(revisionKey({ mtimeMs: 1, size: 2 })), false)
})
