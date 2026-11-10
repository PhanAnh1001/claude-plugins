import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires an explicit extension.
import { createCachedLoader } from "./cache.ts";

test("concurrent requests spawn once and reuse the cached result", async () => {
  let spawns = 0;
  const load = createCachedLoader(async (_key: string) => { spawns++; return { ok: true }; }, value => !value.ok);
  const first = load("same");
  assert.equal(load("same"), first);
  await first;
  await load("same");
  assert.equal(spawns, 1);
});
