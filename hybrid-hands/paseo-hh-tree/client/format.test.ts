import assert from "node:assert/strict";
import { test } from "node:test";

// @ts-ignore -- Node's --experimental-strip-types needs the explicit .ts specifier.
import { costText, limitLine, limitPercentText, percentText, usdText } from "./format.ts";

test("limit percent keeps one decimal", () => {
  assert.equal(percentText(12.34), "12.3%");
  assert.equal(percentText(12), "12.0%");
  assert.equal(percentText(0), "0.0%");
  assert.equal(percentText(0.01), "<0.1%");
  assert.equal(percentText(null), "");
});

test("usd keeps the hh-tree-pane format", () => {
  assert.equal(usdText(0.42), "$0.42");
  assert.equal(usdText(0.004), "<$0.01");
  assert.equal(usdText(0), "$0");
  assert.equal(usdText(undefined), "");
});

test("cost shows only what the row has", () => {
  assert.equal(costText({ usd: 0.7824, week_pct: 1.5648 }), "$0.78 · 1.6% tuần");
  assert.equal(costText({ usd: 0.42, week_pct: null }), "$0.42");
  assert.equal(costText({ usd: 0.42, week_pct: 1.2, week_pct_estimated: true }),
    "$0.42 · ~1.2% tuần");
  assert.equal(costText(null), "");
});

test("limit split keeps one decimal and marks unknowns", () => {
  assert.equal(limitPercentText(12.34), "12.3%");
  assert.equal(limitPercentText(0), "0.0%");
  assert.equal(limitPercentText(null), "?");
  assert.equal(limitPercentText(undefined), "?");
});

test("limit line shows machine, other, total and reset", () => {
  const now = new Date(2026, 10, 6, 14, 5, 0).getTime();
  const line = limitLine({
    plan: "Go",
    window: "tuần",
    this_machine_pct: 12.34,
    other_pct: 4.46,
    total_pct: 16.8,
    resets_at: new Date(2026, 10, 6, 14, 0, 0).toISOString(),
    source: "go_live+ledger",
  }, now);
  assert.equal(line, "Go tuần   máy này 12.3% · máy khác 4.5% · tổng 16.8% · reset 14:00");
});

test("missing total prints ? for other and total", () => {
  const now = new Date(2026, 10, 6, 14, 5, 0).getTime();
  const line = limitLine({
    plan: "Go",
    window: "tuần",
    this_machine_pct: 20,
    other_pct: null,
    total_pct: null,
    resets_at: null,
    source: "ledger",
  }, now);
  assert.equal(line, "Go tuần   máy này 20.0% · máy khác ? · tổng ?");
});

test("estimated week split carries the statusline tilde", () => {
  const now = new Date(2026, 10, 6, 14, 5, 0).getTime();
  const line = limitLine({
    plan: "Claude",
    window: "tuần",
    this_machine_pct: 6.2,
    other_pct: 3.8,
    total_pct: 10.0,
    resets_at: null,
    source: "statusline_cache+week_split",
    estimated: true,
  }, now);
  assert.equal(line, "Claude tuần   máy này ~6.2% · máy khác ~3.8% · tổng ~10.0%");
});
