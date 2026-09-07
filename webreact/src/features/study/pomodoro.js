const MIN_MINUTES = 5;
const MAX_MINUTES = 180;

export function clampMinutes(value, fallback = 25) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.min(MAX_MINUTES, Math.max(MIN_MINUTES, Math.round(numeric)));
}

export function createPomodoroState({ focusMinutes = 25, breakMinutes = 5 } = {}) {
  const focus = clampMinutes(focusMinutes);
  const rest = clampMinutes(breakMinutes, 5);
  return {
    mode: "focus",
    round: 1,
    completed: 0,
    focusMinutes: focus,
    breakMinutes: rest,
    isRunning: false,
    remaining: focus * 60,
    expiresAt: null,
  };
}

export function startPomodoro(state, now = Date.now()) {
  if (state.isRunning) return state;
  const remaining = Math.max(0, Math.round(Number(state.remaining) || 0));
  return { ...state, isRunning: true, remaining, expiresAt: now + remaining * 1_000 };
}

export function remainingAt(state, now = Date.now()) {
  if (!state.isRunning || state.expiresAt == null) return state.remaining;
  return Math.max(0, Math.ceil((state.expiresAt - now) / 1_000));
}

export function pausePomodoro(state, now = Date.now()) {
  if (!state.isRunning) return state;
  return { ...state, isRunning: false, remaining: remainingAt(state, now), expiresAt: null };
}

export function advancePomodoro(state, now = Date.now()) {
  if (!state.isRunning) return state;
  const remaining = remainingAt(state, now);
  if (remaining > 0) return { ...state, remaining };

  const nextMode = state.mode === "focus" ? "break" : "focus";
  return {
    ...state,
    mode: nextMode,
    round: state.mode === "break" ? state.round + 1 : state.round,
    completed: state.mode === "focus" ? state.completed + 1 : state.completed,
    isRunning: false,
    remaining: (nextMode === "focus" ? state.focusMinutes : state.breakMinutes) * 60,
    expiresAt: null,
  };
}

export function skipPomodoro(state) {
  const nextMode = state.mode === "focus" ? "break" : "focus";
  return {
    ...state,
    mode: nextMode,
    round: state.mode === "break" ? state.round + 1 : state.round,
    isRunning: false,
    remaining: (nextMode === "focus" ? state.focusMinutes : state.breakMinutes) * 60,
    expiresAt: null,
  };
}

export function resetPomodoro(state) {
  return createPomodoroState({ focusMinutes: state.focusMinutes, breakMinutes: state.breakMinutes });
}

export function isPomodoroState(value) {
  return Boolean(
    value &&
    (value.mode === "focus" || value.mode === "break") &&
    Number.isInteger(value.round) && value.round >= 1 &&
    Number.isInteger(value.completed) && value.completed >= 0 &&
    Number.isFinite(value.focusMinutes) && value.focusMinutes >= MIN_MINUTES &&
    Number.isFinite(value.breakMinutes) && value.breakMinutes >= MIN_MINUTES &&
    typeof value.isRunning === "boolean" &&
    Number.isInteger(value.remaining) && value.remaining >= 0 &&
    (value.expiresAt == null || Number.isFinite(value.expiresAt)),
  );
}

