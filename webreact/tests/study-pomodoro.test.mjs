import test from "node:test";
import assert from "node:assert/strict";
import {
  advancePomodoro,
  createPomodoroState,
  pausePomodoro,
  resetPomodoro,
  skipPomodoro,
  startPomodoro,
} from "../src/features/study/pomodoro.js";

test("a focus session expires into a paused short break and counts one completed round", () => {
  const started = startPomodoro(createPomodoroState({ focusMinutes: 25, breakMinutes: 5 }), 1_000);
  const next = advancePomodoro(started, started.expiresAt);

  assert.equal(next.mode, "break");
  assert.equal(next.round, 1);
  assert.equal(next.completed, 1);
  assert.equal(next.remaining, 5 * 60);
  assert.equal(next.isRunning, false);
});

test("pausing freezes the remaining time and resuming creates a new deadline", () => {
  const started = startPomodoro(createPomodoroState({ focusMinutes: 25 }), 10_000);
  const paused = pausePomodoro(started, 16_500);
  const resumed = startPomodoro(paused, 20_000);

  assert.equal(paused.remaining, 25 * 60 - 6);
  assert.equal(paused.isRunning, false);
  assert.equal(resumed.remaining, paused.remaining);
  assert.equal(resumed.expiresAt, 20_000 + paused.remaining * 1_000);
});

test("skip changes mode without awarding a completed focus round", () => {
  const focus = createPomodoroState({ focusMinutes: 25, breakMinutes: 5 });
  const breakState = skipPomodoro(focus);
  const nextFocus = skipPomodoro(breakState);

  assert.equal(breakState.mode, "break");
  assert.equal(breakState.completed, 0);
  assert.equal(nextFocus.mode, "focus");
  assert.equal(nextFocus.round, 2);
  assert.equal(nextFocus.remaining, 25 * 60);
});

test("reset clears progress and returns to the configured focus duration", () => {
  const state = skipPomodoro(startPomodoro(createPomodoroState({ focusMinutes: 50, breakMinutes: 10 }), 1_000));
  const reset = resetPomodoro(state);

  assert.deepEqual(reset, {
    mode: "focus",
    round: 1,
    completed: 0,
    focusMinutes: 50,
    breakMinutes: 10,
    isRunning: false,
    remaining: 50 * 60,
    expiresAt: null,
  });
});
