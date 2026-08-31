import assert from "node:assert/strict";
import { test } from "node:test";

import { createLocalGamificationRepository } from "../src/features/gamification/gamificationRepository.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

test("repository isolates snapshots by account and restores saved events", () => {
  const repository = createLocalGamificationRepository(memoryStorage());
  const snapshot = {
    version: 1,
    events: [{ id: "TASK_COMPLETED:t1", xp: 20, awardedAt: "2026-08-31T08:00:00+08:00" }],
    achievements: [],
  };

  repository.save("student-a", snapshot);

  assert.deepEqual(repository.load("student-a"), snapshot);
  assert.deepEqual(repository.load("student-b"), { version: 1, events: [], achievements: [] });
});

test("repository falls back safely when persisted JSON is corrupt", () => {
  const storage = memoryStorage({ "campus_gamification_v1:student-a": "{broken" });
  const repository = createLocalGamificationRepository(storage);

  assert.deepEqual(repository.load("student-a"), { version: 1, events: [], achievements: [] });
});

test("repository discards malformed records instead of trusting local storage", () => {
  const storage = memoryStorage({
    "campus_gamification_v1:student-a": JSON.stringify({
      version: 99,
      events: [{ id: "valid", xp: 15 }, { id: "", xp: 999 }, null],
      achievements: [{ id: "first-focus", unlockedAt: "2026-08-31T10:00:00+08:00" }, { nope: true }],
    }),
  });
  const repository = createLocalGamificationRepository(storage);

  assert.deepEqual(repository.load("student-a"), {
    version: 1,
    events: [{ id: "valid", xp: 15, awardedAt: "" }],
    achievements: [{ id: "first-focus", unlockedAt: "2026-08-31T10:00:00+08:00" }],
  });
});
