import { describe, expect, it, vi } from 'vitest';

import {
  createAdaptiveConcurrencyLimiter,
  lazyBoundedMap,
  mapWithConcurrency,
} from '@/lib/utils/concurrency';

const tick = (ms = 5) => new Promise((resolve) => setTimeout(resolve, ms));

describe('mapWithConcurrency', () => {
  it('returns results in input order regardless of completion order', async () => {
    // Later items resolve first, but results must stay aligned with input.
    const out = await mapWithConcurrency([30, 10, 20], 3, async (ms, i) => {
      await tick(ms);
      return i;
    });
    expect(out).toEqual([0, 1, 2]);
  });

  it('never runs more than `limit` workers at once', async () => {
    let active = 0;
    let peak = 0;
    await mapWithConcurrency(
      Array.from({ length: 9 }, (_, i) => i),
      3,
      async (n) => {
        active += 1;
        peak = Math.max(peak, active);
        await tick();
        active -= 1;
        return n;
      },
    );
    expect(peak).toBeLessThanOrEqual(3); // never exceeds the pool
  });

  it('clamps the limit to the item count (no over-spawn)', async () => {
    let active = 0;
    let peak = 0;
    const out = await mapWithConcurrency([1, 2], 100, async (n) => {
      active += 1;
      peak = Math.max(peak, active);
      await tick();
      active -= 1;
      return n;
    });
    expect(peak).toBeLessThanOrEqual(2);
    expect(out).toEqual([1, 2]);
  });

  it('stops pulling new items once shouldContinue() turns false', async () => {
    const processed: number[] = [];
    let done = 0;
    await mapWithConcurrency(
      [1, 2, 3, 4, 5, 6],
      1,
      async (n) => {
        processed.push(n);
        done += 1;
        return n;
      },
      { shouldContinue: () => done < 3 },
    );
    // limit 1 + stop after 3 ⇒ items 4–6 are never started.
    expect(processed).toEqual([1, 2, 3]);
  });

  it('handles an empty list without spawning workers', async () => {
    expect(await mapWithConcurrency([], 4, async (n) => n)).toEqual([]);
  });
});

describe('createAdaptiveConcurrencyLimiter', () => {
  it('starts eight requests, lowers the cap once per rate-limit wave, and drains in order', async () => {
    vi.useFakeTimers();
    try {
      const limiter = createAdaptiveConcurrencyLimiter(8);
      const releases: Array<() => void> = [];
      const requests = Array.from({ length: 12 }, (_, i) =>
        limiter.run(async () => {
          await new Promise<void>((resolve) => releases.push(resolve));
          return i;
        }),
      );
      await Promise.resolve();
      expect(releases).toHaveLength(8);

      limiter.rateLimited();
      limiter.rateLimited(); // Both responses belong to the first burst.
      expect(limiter.limit).toBe(4);
      releases.splice(0).forEach((release) => release());
      await vi.advanceTimersByTimeAsync(999);
      expect(releases).toHaveLength(0);
      await vi.advanceTimersByTimeAsync(1);
      expect(releases).toHaveLength(4);
      releases.splice(0).forEach((release) => release());
      expect(await Promise.all(requests)).toEqual(Array.from({ length: 12 }, (_, i) => i));
    } finally {
      vi.useRealTimers();
    }
  });

  it('lowers the cap again after a later 429 and cancels queued requests', async () => {
    vi.useFakeTimers();
    try {
      const limiter = createAdaptiveConcurrencyLimiter(4);
      limiter.rateLimited();
      expect(limiter.limit).toBe(2);
      await vi.advanceTimersByTimeAsync(1_000);
      limiter.rateLimited();
      expect(limiter.limit).toBe(1);

      const controller = new AbortController();
      const blocked = limiter.run(async () => 'unexpected', controller.signal);
      controller.abort();
      await expect(blocked).rejects.toMatchObject({ name: 'AbortError' });
      await vi.advanceTimersByTimeAsync(1_000);
      expect(await limiter.run(async () => 'ready')).toBe('ready');
    } finally {
      vi.useRealTimers();
    }
  });
});


describe('lazyBoundedMap', () => {
  it('returns promises immediately and resolves them without a barrier', async () => {
    const started: number[] = [];
    const promises = lazyBoundedMap([0, 1, 2], 1, async (n) => {
      started.push(n);
      await tick();
      return n * 10;
    });
    expect(promises).toHaveLength(3); // the array of promises exists synchronously
    expect(await promises[0]).toBe(0); // the first resolves on its own…
    expect(started.length).toBeLessThan(3); // …without forcing the last item to run (no barrier)
    expect(await Promise.all(promises)).toEqual([0, 10, 20]); // order + values preserved
  });

  it('caps in-flight work at `limit`', async () => {
    let active = 0;
    let peak = 0;
    await Promise.all(
      lazyBoundedMap(
        Array.from({ length: 8 }, (_, i) => i),
        3,
        async (n) => {
          active += 1;
          peak = Math.max(peak, active);
          await tick();
          active -= 1;
          return n;
        },
      ),
    );
    expect(peak).toBeLessThanOrEqual(3);
    expect(peak).toBeGreaterThan(1);
  });

  it('skips items via shouldContinue without running fn', async () => {
    const ran: number[] = [];
    let done = 0;
    const out = await Promise.all(
      lazyBoundedMap(
        [1, 2, 3, 4, 5],
        1,
        async (n) => {
          ran.push(n);
          done += 1;
          return n;
        },
        { shouldContinue: () => done < 2 },
      ),
    );
    expect(ran).toEqual([1, 2]); // fn ran only twice
    expect(out).toEqual([1, 2, undefined, undefined, undefined]); // skipped → undefined
  });
});
