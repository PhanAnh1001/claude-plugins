export const MIN_REFRESH_MS = 30_000
export const MAX_REFRESH_MS = 120_000
const DURATION_MULTIPLIER = 3
const ERROR_MULTIPLIER = 2

export function refreshDelay(durationMs: number, previousMs = MIN_REFRESH_MS, failed = false): number {
  return Math.min(MAX_REFRESH_MS, Math.max(
    MIN_REFRESH_MS,
    DURATION_MULTIPLIER * durationMs,
    failed ? previousMs * ERROR_MULTIPLIER : 0,
  ))
}

/** Wait after a revision signal so a burst of writes costs one hh-ps run. */
export const REVISION_DEBOUNCE_MS = 300
/** Fallback stat poll of the revision file (watchPaths may not fire). */
export const REVISION_POLL_MS = 1000
/** Keep hh-store's indexer alive while the pane is shown (it exits after 10 min idle). */
export const TOUCH_INTERVAL_MS = 60_000

/** Identity of the revision file; atomic rename changes mtime and usually size. */
export function revisionKey(stat: { mtimeMs: number, size: number } | undefined): string | undefined {
  return stat ? `${stat.mtimeMs}:${stat.size}` : undefined
}

/**
 * Remembers the last seen revision key. The first key is a baseline; a
 * missing/failed stat (undefined) never signals and keeps the baseline.
 */
export class RevisionWatch {
  private last: string | undefined
  changed(key: string | undefined): boolean {
    if (key === undefined) return false
    const isChange = this.last !== undefined && key !== this.last
    this.last = key
    return isChange
  }
}

/**
 * Debounced, single-flight trigger: `request` arms a run after the debounce;
 * `tick` fires it; a request while running queues exactly one more run.
 * `run` resolves false when it could not start (busy elsewhere).
 */
export class RefreshGate {
  private dueAt: number | undefined
  private running = false
  private again = false
  private readonly run: () => Promise<boolean>
  private readonly debounceMs: number
  constructor(run: () => Promise<boolean>, debounceMs = REVISION_DEBOUNCE_MS) {
    this.run = run
    this.debounceMs = debounceMs
  }

  request(now: number): void {
    if (this.running) { this.again = true; return }
    this.dueAt ??= now + this.debounceMs
  }

  async tick(now: number): Promise<void> {
    if (this.dueAt === undefined || now < this.dueAt || this.running) return
    this.dueAt = undefined
    this.running = true
    try {
      // false: another refresh held the slot; retry so the signal is not lost.
      if (!(await this.run())) this.again = true
    } finally {
      this.running = false
      if (this.again) { this.again = false; this.dueAt = now }
    }
  }
}
