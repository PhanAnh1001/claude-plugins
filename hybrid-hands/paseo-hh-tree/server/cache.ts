// Cache both successes and errors; concurrent callers share the same execution.
// @ts-ignore -- explicit extension also supports Node strip-types tests.
import { MIN_REFRESH_MS, refreshDelay } from "../shared/refresh.ts";

export function createCachedLoader<K, V>(load: (key: K) => Promise<V>, failed: (value: V) => boolean) {
  const entries = new Map<K, { value: V; expiresAt: number; delayMs: number }>();
  const pending = new Map<K, Promise<V>>();
  const get = (key: K): Promise<V> => {
    const cached = entries.get(key);
    if (cached && cached.expiresAt > Date.now()) return Promise.resolve(cached.value);
    const active = pending.get(key);
    if (active) return active;
    const started = Date.now();
    const promise = Promise.resolve().then(() => load(key)).then(value => {
      const delayMs = refreshDelay(Date.now() - started, cached?.delayMs ?? MIN_REFRESH_MS, failed(value));
      entries.set(key, { value, delayMs, expiresAt: Date.now() + delayMs });
      return value;
    }).finally(() => pending.delete(key));
    pending.set(key, promise);
    return promise;
  };
  /** Drop cached values (revision changed); in-flight runs are still shared. */
  const invalidate = (): void => entries.clear();
  return Object.assign(get, { invalidate });
}
