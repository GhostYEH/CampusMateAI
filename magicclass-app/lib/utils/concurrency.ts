/** A FIFO counting semaphore: at most `size` `run()` callbacks execute at once. */
function createSemaphore(size: number) {
  const max = Math.max(1, Math.floor(size));
  let active = 0;
  const queue: Array<() => void> = [];

  const pump = () => {
    while (active < max && queue.length > 0) {
      active += 1;
      const start = queue.shift()!;
      start();
    }
  };

  return {
    run<R>(fn: () => Promise<R>): Promise<R> {
      return new Promise<R>((resolve, reject) => {
        queue.push(() => {
          fn()
            .then(resolve, reject)
            .finally(() => {
              active -= 1;
              pump();
            });
        });
        pump();
      });
    },
  };
}

/** Limits individual requests and lowers the cap when a provider rejects a burst. */
export function createAdaptiveConcurrencyLimiter(initialLimit: number) {
  let limit = Number.isFinite(initialLimit) ? Math.max(1, Math.floor(initialLimit)) : 1;
  let active = 0;
  let cooldownUntil = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const queue: Array<{
    start: () => void;
    signal?: AbortSignal;
    abort: () => void;
  }> = [];

  const pump = () => {
    if (timer) {
      clearTimeout(timer);
      timer = undefined;
    }
    if (queue.length === 0) return;
    const delay = cooldownUntil - Date.now();
    if (delay > 0) {
      timer = setTimeout(pump, delay);
      return;
    }
    while (active < limit && queue.length > 0) {
      const entry = queue.shift()!;
      entry.signal?.removeEventListener('abort', entry.abort);
      if (entry.signal?.aborted) {
        entry.abort();
        continue;
      }
      active++;
      entry.start();
    }
  };

  return {
    run<R>(fn: () => Promise<R>, signal?: AbortSignal): Promise<R> {
      if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
      return new Promise<R>((resolve, reject) => {
        const entry = {
          signal,
          abort: () => {
            const index = queue.indexOf(entry);
            if (index >= 0) queue.splice(index, 1);
            reject(new DOMException('Aborted', 'AbortError'));
            pump();
          },
          start: () => {
            Promise.resolve()
              .then(fn)
              .then(resolve, reject)
              .finally(() => {
                active--;
                pump();
              });
          },
        };
        queue.push(entry);
        signal?.addEventListener('abort', entry.abort, { once: true });
        pump();
      });
    },
    rateLimited(retryAfterMs?: number) {
      // Several 429s from one burst describe one limit, not several successive limits.
      if (Date.now() >= cooldownUntil) limit = Math.max(1, Math.floor(limit / 2));
      const delay = Number.isFinite(retryAfterMs)
        ? Math.max(1_000, Math.min(60_000, retryAfterMs!))
        : 1_000;
      cooldownUntil = Math.max(cooldownUntil, Date.now() + delay);
      pump();
    },
    get limit() {
      return limit;
    },
  };
}

/**
 * Start `fn` over every item with at most `limit` calls in flight at once, and
 * return one promise per item **immediately**, in input order — without awaiting
 * them. Each item acquires a `limit`-sized semaphore slot before `fn` runs, so
 * all the promises exist up front but only `limit` execute concurrently.
 *
 * This is the no-barrier primitive: the caller can `await` the promises in any
 * order (e.g. sequentially) and each resolves as soon as *its* work is done,
 * while later items keep running in the background. `shouldContinue` is checked
 * when an item reaches the front of the queue; once it returns false, the
 * remaining items resolve to `undefined` without running `fn`.
 *
 * `limit` is clamped to `[1, items.length]`, so a raw/too-large concurrency is
 * safe to pass.
 */
export function lazyBoundedMap<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
  options?: { shouldContinue?: () => boolean },
): Array<Promise<R | undefined>> {
  const shouldContinue = options?.shouldContinue ?? (() => true);
  const semaphore = createSemaphore(Math.min(Math.floor(limit), items.length || 1));
  return items.map((item, index) =>
    semaphore.run(async () => (shouldContinue() ? fn(item, index) : undefined)),
  );
}

/**
 * Run `fn` over `items` with at most `limit` calls in flight at once and await
 * them all (a barrier). Results are returned in input order; a slot is
 * `undefined` if its item was skipped because `shouldContinue` turned false.
 *
 * Prefer {@link lazyBoundedMap} when you can consume results incrementally —
 * this wrapper waits for every item before returning.
 */
export async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
  options?: { shouldContinue?: () => boolean },
): Promise<Array<R | undefined>> {
  return Promise.all(lazyBoundedMap(items, limit, fn, options));
}
