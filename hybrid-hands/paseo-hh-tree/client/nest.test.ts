import assert from "node:assert/strict";
import { test } from "node:test";

// Node's --experimental-strip-types needs the explicit .ts specifier, which this
// tsconfig rejects because allowImportingTsExtensions is off.
// @ts-ignore
import { nestSessions } from "./nest.ts";

interface SessionOverrides {
  parent_session?: string | null;
  side_name?: string | null;
  provider?: string;
}

function session(id: string, overrides: SessionOverrides = {}) {
  return {
    session_id: id,
    name: id,
    status: "idle",
    cwd: "/tmp/project",
    context_tokens: null,
    started_at: null,
    last_activity: null,
    is_main: false,
    live: true,
    project_slug: "demo",
    transcript_path: null,
    token_cap: null,
    token_ratio: null,
    subagents: [],
    hand_runs: [],
    ...overrides,
  };
}

function ids(sessions: { session_id: string }[]): string[] {
  return sessions.map((item) => item.session_id);
}

test("con và cháu được lồng đúng, giữ thứ tự anh em", () => {
  const main = session("main-id");
  const first = session("first-id", {
    parent_session: "main-id",
    side_name: "first",
    provider: "dsh",
  });
  const second = session("second-id", {
    parent_session: "main-id",
    side_name: "second",
  });
  const grand = session("grand-id", {
    parent_session: "first-id",
    side_name: "grand",
    provider: "codex",
  });

  const result = nestSessions([first, grand, main, second]);

  assert.deepEqual(ids(result.roots), ["main-id"]);
  assert.deepEqual(ids(result.roots[0].children), ["first-id", "second-id"]);
  assert.deepEqual(ids(result.roots[0].children[0].children), ["grand-id"]);
  assert.deepEqual(result.orphanSides, []);
});

test("thiếu trường phiên phụ thì giữ nguyên thứ tự cũ", () => {
  const sessions = [session("c-id"), session("a-id"), session("b-id")];

  const result = nestSessions(sessions);

  assert.deepEqual(ids(result.roots), ["c-id", "a-id", "b-id"]);
  assert.equal(result.orphanSides.length, 0);
  assert.ok(result.roots.every((node) => node.children.length === 0));
});

test("parent_session rỗng được coi như không có cha", () => {
  const result = nestSessions([session("root-id", { parent_session: "" })]);

  assert.deepEqual(ids(result.roots), ["root-id"]);
  assert.equal(result.orphanSides.length, 0);
});

test("phiên có cha không khớp phiên nào thì vào orphanSides", () => {
  const known = session("known-id");
  const lost = session("lost-id", {
    parent_session: "missing-id",
    side_name: "lost",
    provider: "dsh",
  });

  const result = nestSessions([lost, known]);

  assert.deepEqual(ids(result.roots), ["known-id"]);
  assert.deepEqual(ids(result.orphanSides), ["lost-id"]);
});

test("vòng lặp cha con không treo và vẫn trả về đủ phiên", { timeout: 1_000 }, () => {
  const first = session("cycle-a", {
    parent_session: "cycle-b",
    side_name: "a",
  });
  const second = session("cycle-b", {
    parent_session: "cycle-a",
    side_name: "b",
  });

  const result = nestSessions([first, second]);

  assert.deepEqual(ids(result.roots), []);
  assert.deepEqual(ids(result.orphanSides), ["cycle-a", "cycle-b"]);
});
