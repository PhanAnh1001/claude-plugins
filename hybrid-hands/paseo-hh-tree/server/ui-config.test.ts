import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires an explicit extension.
import { gateTree, parsePanelEnabled } from "./ui-config.ts";

test("enabled=false is reported with its source", () => {
  const out = JSON.stringify({
    effective: { ui: { hh_panel: { enabled: false } } },
    sources: { "ui.hh_panel.enabled": "repo" },
  });
  assert.deepEqual(parsePanelEnabled(out), { enabled: false, source: "repo" });
});

test("broken, empty or non-bool output fails open", () => {
  for (const out of ["", "{oops", JSON.stringify({ effective: { ui: { hh_panel: { enabled: "no" } } } })]) {
    assert.equal(parsePanelEnabled(out).enabled, true);
  }
});

test("disabled config returns disabled without loading the tree", async () => {
  let called = false;
  const result = await gateTree({ enabled: false, source: "global" }, async () => { called = true; return 1; });
  assert.equal(called, false);
  assert.deepEqual(result, { ok: false, disabled: true, error: "Cây phiên đang tắt bởi ui.hh_panel.enabled=false (nguồn: global)" });
});
