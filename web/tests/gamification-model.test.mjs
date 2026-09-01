import assert from "node:assert/strict";
import { test } from "node:test";

import {
  calculateLevel,
  calculateStreak,
  evaluateAchievements,
  reconcileXpEvents,
  summarizeGamification,
} from "../src/features/gamification/gamificationModel.js";

const now = new Date("2026-08-31T12:00:00+08:00");

test("level progress uses one increasing threshold policy", () => {
  assert.deepEqual(calculateLevel(0), {
    level: 1,
    totalXp: 0,
    currentLevelXp: 0,
    nextLevelXp: 100,
    progress: 0,
  });
  assert.deepEqual(calculateLevel(100), {
    level: 2,
    totalXp: 100,
    currentLevelXp: 0,
    nextLevelXp: 125,
    progress: 0,
  });
  assert.deepEqual(calculateLevel(-20), calculateLevel(0));
});

test("reconciliation awards real completed sources once", () => {
  const facts = {
    completedTasks: [
      { id: "task-high", status: "completed", importance: "high", completed_at: "2026-08-31T08:30:00+08:00" },
      { id: "task-normal", status: "completed", importance: "normal", completed_at: "2026-08-30T09:00:00+08:00" },
    ],
    completedFocusSessions: [
      { id: "focus-25", mode: "focus", status: "completed", duration_seconds: 1500, ended_at: "2026-08-31T10:00:00+08:00" },
      { id: "focus-short", mode: "focus", status: "completed", duration_seconds: 1200, ended_at: "2026-08-31T11:00:00+08:00" },
    ],
  };

  const first = reconcileXpEvents({ version: 1, events: [], achievements: [] }, facts, now);
  assert.deepEqual(first.events.map((event) => [event.id, event.xp]), [
    ["TASK_COMPLETED:task-high", 30],
    ["TASK_COMPLETED:task-normal", 20],
    ["FOCUS_SESSION_COMPLETED:focus-25", 15],
    ["DAILY_TASK_GOAL:2026-08-31", 20],
  ]);
  assert.equal(first.totalXp, 85);

  const second = reconcileXpEvents(first, facts, now);
  assert.deepEqual(second.events, first.events);
  assert.equal(second.totalXp, 85);
});

test("daily focus goal is awarded once after sixty real minutes", () => {
  const facts = {
    completedTasks: [],
    completedFocusSessions: [
      { id: "focus-a", mode: "focus", status: "completed", duration_seconds: 1500, ended_at: "2026-08-31T09:00:00+08:00" },
      { id: "focus-b", mode: "focus", status: "completed", duration_seconds: 2100, ended_at: "2026-08-31T10:00:00+08:00" },
    ],
  };
  const snapshot = reconcileXpEvents({ version: 1, events: [], achievements: [] }, facts, now);

  assert.deepEqual(snapshot.events.map((event) => event.id), [
    "FOCUS_SESSION_COMPLETED:focus-a",
    "FOCUS_SESSION_COMPLETED:focus-b",
    "DAILY_FOCUS_GOAL:2026-08-31",
  ]);
  assert.equal(snapshot.totalXp, 60);
});

test("streak uses activity dates and may continue from yesterday", () => {
  assert.equal(calculateStreak(["2026-08-30", "2026-08-29", "2026-08-28", "invalid"], now), 3);
  assert.equal(calculateStreak(["2026-08-31", "2026-08-30", "2026-08-28"], now), 2);
  assert.equal(calculateStreak([], now), 0);
});

test("achievement evaluator unlocks qualifying achievements once", () => {
  const facts = {
    completedTasks: Array.from({ length: 50 }, (_, index) => ({
      id: `task-${index}`,
      status: "completed",
      completed_at: `2026-08-${String(25 + (index % 7)).padStart(2, "0")}T08:00:00+08:00`,
    })),
    completedFocusSessions: [
      { id: "focus-long", mode: "focus", status: "completed", duration_seconds: 36_000, ended_at: "2026-08-31T10:00:00+08:00" },
    ],
  };

  const first = evaluateAchievements({ version: 1, events: [], achievements: [] }, facts, now);
  assert.deepEqual(first.achievements.map((item) => item.id), [
    "first-focus",
    "focus-60",
    "focus-600",
    "task-hunter-50",
    "streak-7",
  ]);

  const second = evaluateAchievements(first, facts, new Date("2026-09-01T12:00:00+08:00"));
  assert.deepEqual(second.achievements, first.achievements);
});

test("gamification summary reports only real current-week activity", () => {
  const snapshot = {
    version: 1,
    events: [
      { id: "TASK_COMPLETED:today", xp: 30, awardedAt: "2026-08-31T08:00:00+08:00" },
      { id: "TASK_COMPLETED:yesterday", xp: 20, awardedAt: "2026-08-30T08:00:00+08:00" },
      { id: "FOCUS_SESSION_COMPLETED:today", xp: 15, awardedAt: "2026-08-31T09:00:00+08:00" },
      { id: "DAILY_TASK_GOAL:2026-08-31", xp: 20, awardedAt: "2026-08-31T10:00:00+08:00" },
      { id: "DAILY_FOCUS_GOAL:2026-08-31", xp: 30, awardedAt: "2026-08-31T11:00:00+08:00" },
    ],
    achievements: [{ id: "first-focus", unlockedAt: "2026-08-31T11:00:00+08:00" }],
  };
  const facts = {
    completedTasks: [
      { id: "today", status: "completed", completed_at: "2026-08-31T08:00:00+08:00" },
      { id: "yesterday", status: "completed", completed_at: "2026-08-30T08:00:00+08:00" },
    ],
    completedFocusSessions: [
      { id: "focus", mode: "focus", status: "completed", duration_seconds: 3600, ended_at: "2026-08-31T09:00:00+08:00" },
    ],
  };

  const summary = summarizeGamification(snapshot, facts, now);

  assert.equal(summary.weekXp, 95);
  assert.deepEqual(summary.weekXpSeries, [95, 0, 0, 0, 0, 0, 0]);
  assert.equal(summary.weekFocusMinutes, 60);
  assert.equal(summary.weekCompletedTasks, 1);
  assert.deepEqual(summary.dailyAdventure, {
    completed: 2,
    total: 2,
    focusMinutes: 60,
    completedTasks: 1,
    todayXp: 95,
    nextReward: null,
  });
  assert.equal(summary.streak, 2);
  assert.equal(summary.recentAchievements[0].title, "初心者");
  assert.deepEqual(summary.achievementCollection.slice(0, 3).map((item) => ({
    id: item.id,
    unlocked: item.unlocked,
    current: item.current,
    target: item.target,
    unit: item.unit,
  })), [
    { id: "first-focus", unlocked: true, current: 1, target: 1, unit: "次专注" },
    { id: "focus-60", unlocked: false, current: 60, target: 60, unit: "分钟" },
    { id: "focus-600", unlocked: false, current: 60, target: 600, unit: "分钟" },
  ]);
});

test("gamification summary exposes only the next unearned daily reward", () => {
  const facts = {
    completedTasks: [
      { id: "task-today", status: "completed", completed_at: "2026-08-31T08:00:00+08:00" },
    ],
    completedFocusSessions: [
      { id: "focus-50", mode: "focus", status: "completed", duration_seconds: 3000, ended_at: "2026-08-31T09:00:00+08:00" },
    ],
  };
  const withEvents = reconcileXpEvents({ version: 1, events: [], achievements: [] }, facts, now);
  const snapshot = evaluateAchievements(withEvents, facts, now);
  const summary = summarizeGamification(snapshot, facts, now);

  assert.equal(summary.dailyAdventure.todayXp, 55);
  assert.deepEqual(summary.dailyAdventure.nextReward, { type: "focus-goal", xp: 30, remainingMinutes: 10 });
  assert.equal(summary.achievementCollection[0].id, "first-focus");
  assert.equal(summary.achievementCollection[0].unlocked, true);
  assert.equal(summary.achievementCollection[1].id, "focus-60");
  assert.equal(summary.achievementCollection[1].unlocked, false);
  assert.equal(summary.achievementCollection[1].current, 50);
});
