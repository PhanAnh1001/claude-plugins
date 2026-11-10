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

test("missing or malformed revision file reads as 0", async () => {
  // @ts-ignore -- Node strip-types requires an explicit extension.
  const { readRevision } = await import("./revision.ts");
  const { mkdtempSync, writeFileSync } = await import("node:fs");
  const { join } = await import("node:path");
  const dir = mkdtempSync(join((await import("node:os")).tmpdir(), "hh-rev-"));
  assert.equal(readRevision(join(dir, "none")), 0);
  writeFileSync(join(dir, "revision"), "garbage\n");
  assert.equal(readRevision(dir), 0);
  writeFileSync(join(dir, "revision"), "7\n");
  assert.equal(readRevision(dir), 7);
});
