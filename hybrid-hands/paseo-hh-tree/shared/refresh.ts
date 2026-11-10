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
