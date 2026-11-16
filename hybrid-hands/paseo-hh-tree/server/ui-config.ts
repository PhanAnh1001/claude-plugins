// Reads hybrid-hands `ui.hh_panel.enabled` via `hand-ext config --json`.
// Pure except for the injected runner, so Node strip-types tests need no Paseo SDK.
import { realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export const HAND_EXT_NAME = "hand-ext";
export const PANEL_ENABLED_KEY = "ui.hh_panel.enabled";
// Config rarely changes; 30 s keeps RPC bursts from spawning hand-ext each time.
export const UI_CONFIG_CACHE_MS = 30_000;
export const HAND_EXT_TIMEOUT_MS = 5_000;
const UNKNOWN_SOURCE = "?";

export interface PanelConfig {
  enabled: boolean;
  source: string;
}

/** Runs `command args` with cwd and returns stdout; throws on failure. */
export type CommandRunner = (command: string, args: string[], cwd: string) => Promise<string>;

const ENABLED_FALLBACK: PanelConfig = { enabled: true, source: UNKNOWN_SOURCE };

/** Fail-open: anything but an explicit boolean false keeps the panel on. */
export function parsePanelEnabled(stdout: string): PanelConfig {
  let data: unknown;
  try {
    data = JSON.parse(stdout);
  } catch {
    return ENABLED_FALLBACK;
  }
  const root = data as { effective?: { ui?: { hh_panel?: { enabled?: unknown } } }; sources?: Record<string, unknown> } | null;
  const enabled = root?.effective?.ui?.hh_panel?.enabled;
  if (typeof enabled !== "boolean") return ENABLED_FALLBACK;
  const source = root?.sources?.[PANEL_ENABLED_KEY];
  return { enabled, source: typeof source === "string" ? source : UNKNOWN_SOURCE };
}

export function disabledMessage(source: string): string {
  return `Cây phiên đang tắt bởi ${PANEL_ENABLED_KEY}=false (nguồn: ${source})`;
}

async function handExtBeside(hhPsCommand: string): Promise<string> {
  const real = await realpath(hhPsCommand).catch(() => hhPsCommand);
  return join(dirname(real), HAND_EXT_NAME);
}

/** Cached per cwd; errors fail open (enabled). */
export function createPanelConfigReader(run: CommandRunner, now: () => number = Date.now) {
  const cache = new Map<string, { value: PanelConfig; expiresAt: number }>();
  return async (hhPsCommand: string, cwd?: string): Promise<PanelConfig> => {
    const key = cwd ?? "";
    const hit = cache.get(key);
    if (hit && hit.expiresAt > now()) return hit.value;
    const args = ["config", "--json", ...(cwd ? ["--cwd", cwd] : [])];
    let value = ENABLED_FALLBACK;
    try {
      value = parsePanelEnabled(await run(await handExtBeside(hhPsCommand), args, cwd ?? homedir()));
    } catch {
      value = ENABLED_FALLBACK;
    }
    cache.set(key, { value, expiresAt: now() + UI_CONFIG_CACHE_MS });
    return value;
  };
}

export type DisabledResult = { ok: false; disabled: true; error: string };

/** Returns the disabled result without running the tree loader, else the loader's result. */
export async function gateTree<T>(
  config: PanelConfig,
  loadTree: () => Promise<T>,
): Promise<T | DisabledResult> {
  if (!config.enabled) return { ok: false, disabled: true, error: disabledMessage(config.source) };
  return loadTree();
}
