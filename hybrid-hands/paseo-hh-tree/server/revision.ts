import { spawn } from "node:child_process";
import { existsSync, readFileSync, watch, type FSWatcher } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export const REVISION_FILE = "revision";
const HH_STORE_NAME = "hh-store";
/** Keeps the indexer alive (it exits after 10 min without reads) without spawning per poll. */
export const TOUCH_INTERVAL_MS = 60_000;

export function stateDir(env: NodeJS.ProcessEnv = process.env): string {
  return env.HYBRID_HANDS_STATE_DIR || join(homedir(), ".hybrid-hands", "state");
}

/** Missing or malformed revision file counts as 0; never throws. */
export function readRevision(dir: string): number {
  try {
    const value = Number.parseInt(readFileSync(join(dir, REVISION_FILE), "utf8").trim(), 10);
    return Number.isFinite(value) && value >= 0 ? value : 0;
  } catch {
    return 0;
  }
}

/** Fire-and-forget `hh-store touch` next to hh-ps; silently skipped on old installs. */
export function touchStore(hhPsCommand: string): void {
  const command = join(dirname(hhPsCommand), HH_STORE_NAME);
  if (!existsSync(command)) return;
  try {
    const child = spawn(command, ["touch"], { detached: true, stdio: "ignore" });
    child.on("error", () => {});
    child.unref();
  } catch {
    // Touch is best effort; the adaptive safety net still refreshes the tree.
  }
}

/** Tracks the revision, invalidating on change via fs.watch (dir, since the file is renamed in). */
export function createRevisionTracker(onChange: () => void, dir = stateDir()) {
  let current = readRevision(dir);
  let watcher: FSWatcher | null = null;
  const refresh = (): number => {
    const next = readRevision(dir);
    if (next !== current) {
      current = next;
      onChange();
    }
    return current;
  };
  const ensureWatch = (): void => {
    if (watcher) return;
    try {
      watcher = watch(dir, { persistent: false }, (_event, name) => {
        if (!name || String(name) === REVISION_FILE) refresh();
      });
      watcher.on("error", () => { watcher?.close(); watcher = null; });
    } catch {
      watcher = null; // Directory missing; retried on the next revision RPC.
    }
  };
  ensureWatch();
  return {
    read: (): number => { ensureWatch(); return refresh(); },
    close: (): void => { watcher?.close(); watcher = null; },
  };
}
