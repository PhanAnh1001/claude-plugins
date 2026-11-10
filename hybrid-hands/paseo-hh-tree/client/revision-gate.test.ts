import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires an explicit extension.
import { createRevisionGate } from "./revision-gate.ts";

test("tree refetch fires once per revision change, never on same revision", () => {
  const observe = createRevisionGate();
  assert.deepEqual([3, 3, 3, 4, 4].map(observe), [false, false, false, true, false]);
});
