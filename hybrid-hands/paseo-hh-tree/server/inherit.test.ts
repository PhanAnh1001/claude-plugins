import assert from "node:assert/strict";
import { test } from "node:test";
// @ts-ignore -- Node strip-types requires an explicit extension.
import { inheritFromSource, type CreateRequest, type SourceAgent } from "./inherit.ts";

const CWD = "/repo";
const v2: SourceAgent = { provider: "claude", cwd: CWD, model: "claude-opus-5-5", thinkingOptionId: "high",
  launchEnv: { CLAUDE_CONFIG_DIR: "/h/.claude-hand", OTHER: "x" }, timestamp: 2 };
const old: SourceAgent = { provider: "claude", cwd: CWD, model: "old", launchEnv: {}, timestamp: 1 };
const bare: CreateRequest = { config: { provider: "claude", cwd: CWD, model: "default" } };

test("bare create inherits newest same-cwd account env and model/effort only", () => {
  const out = inheritFromSource(bare, [old, v2]);
  assert.deepEqual(out.env, { CLAUDE_CONFIG_DIR: "/h/.claude-hand" });
  assert.equal(out.config.model, "claude-opus-5-5");
  assert.equal(out.config.thinkingOptionId, "high");
  const codex: SourceAgent = { provider: "codex-hand", cwd: CWD, launchEnv: { CODEX_HOME: "/h/.codex-hand" }, timestamp: 9 };
  assert.deepEqual(inheritFromSource(bare, [v2, codex]).env, { CLAUDE_CONFIG_DIR: "/h/.claude-hand" });
});

test("explicit account env or no source leaves the request unchanged", () => {
  const explicit = { ...bare, env: { CODEX_HOME: "/h/.codex-hand" } };
  assert.equal(inheritFromSource(explicit, [v2]), explicit);
  assert.equal(inheritFromSource(bare, [{ ...v2, cwd: "/elsewhere" }]), bare);
});
