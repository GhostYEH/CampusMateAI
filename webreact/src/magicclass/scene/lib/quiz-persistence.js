/**
 * 移植自参考项目 `lib/quiz/persistence.ts`。
 *
 * 仅擦除 TypeScript 类型标注（type / interface / 泛型 / `as`）。所有行为——
 * 四个 legacy localStorage key 的读取、按值比对后再清理的语义——逐字保留。
 *
 * One-time compatibility reader for quiz state written before RuntimeStore.
 *
 * Four legacy keys may coexist:
 *
 *   quizDraft:<sceneId>
 *   quizAnswers:<sceneId>
 *   quizResults:<sceneId>
 *   quizAttemptId:<sceneId>
 *
 * RuntimeStore is the only live read source. The draft key also acts as a
 * synchronous crash-recovery journal while an async RuntimeStore write is in
 * flight; `loadQuizAttemptState` consumes it, commits the strongest valid state
 * to the current learner partition, then deletes all four keys.
 */

export const DRAFT_KEY_PREFIX = 'quizDraft:';
export const ANSWERS_KEY_PREFIX = 'quizAnswers:';
export const RESULTS_KEY_PREFIX = 'quizResults:';
export const ATTEMPT_ID_KEY_PREFIX = 'quizAttemptId:';

function isQuizAnswers(value) {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every(
      (answer) =>
        typeof answer === 'string' ||
        (Array.isArray(answer) && answer.every((item) => typeof item === 'string')),
    )
  );
}

export function hasLegacyQuizState(sceneId) {
  return [DRAFT_KEY_PREFIX, ANSWERS_KEY_PREFIX, RESULTS_KEY_PREFIX, ATTEMPT_ID_KEY_PREFIX].some(
    (prefix) => safeGet(prefix + sceneId) !== null,
  );
}

function safeGet(key) {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, value);
  } catch {
    // Best-effort recovery journal; RuntimeStore remains the authority.
  }
}

function safeRemove(key) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

/** Parse legacy post-submit state: answers + optional graded results. */
export function readSubmittedState(sceneId) {
  const rawA = safeGet(ANSWERS_KEY_PREFIX + sceneId);
  const rawR = safeGet(RESULTS_KEY_PREFIX + sceneId);
  return parseSubmittedState(rawA, rawR);
}

function parseSubmittedState(rawA, rawR) {
  if (!rawA) return null;
  try {
    const answers = JSON.parse(rawA);
    if (!isQuizAnswers(answers)) return null;
    if (rawR) {
      const results = JSON.parse(rawR);
      if (Array.isArray(results)) {
        return { kind: 'reviewing', answers, results };
      }
    }
    return { kind: 'answering', answers };
  } catch {
    return null;
  }
}

export function readDraftState(sceneId) {
  const raw = safeGet(DRAFT_KEY_PREFIX + sceneId);
  return parseDraftState(raw);
}

function parseDraftState(raw) {
  if (!raw) return null;
  try {
    const answers = JSON.parse(raw);
    return isQuizAnswers(answers) ? answers : null;
  } catch {
    return null;
  }
}

/** Read the legacy attempt pointer only to order one-time migration snapshots. */
export function readLegacyAttemptId(sceneId) {
  const attemptId = safeGet(ATTEMPT_ID_KEY_PREFIX + sceneId);
  return attemptId && attemptId.trim().length > 0 ? attemptId : null;
}

/** Capture one coherent cleanup token for a one-time legacy migration. */
export function readLegacyQuizStateSnapshot(sceneId) {
  const rawDraft = safeGet(DRAFT_KEY_PREFIX + sceneId);
  const rawAnswers = safeGet(ANSWERS_KEY_PREFIX + sceneId);
  const rawResults = safeGet(RESULTS_KEY_PREFIX + sceneId);
  const rawAttemptId = safeGet(ATTEMPT_ID_KEY_PREFIX + sceneId);
  return {
    hasState: [rawDraft, rawAnswers, rawResults, rawAttemptId].some((value) => value !== null),
    draft: parseDraftState(rawDraft),
    submitted: parseSubmittedState(rawAnswers, rawResults),
    attemptId: rawAttemptId && rawAttemptId.trim().length > 0 ? rawAttemptId : null,
    rawDraft,
    rawAnswers,
    rawResults,
    rawAttemptId,
  };
}

/** Synchronously journal the latest draft before its async RuntimeStore write. */
export function writeDraftRecovery(sceneId, attemptId, answers) {
  safeSet(DRAFT_KEY_PREFIX + sceneId, JSON.stringify(answers));
  safeSet(ATTEMPT_ID_KEY_PREFIX + sceneId, attemptId);
}

/** Retire only the recovery snapshot proven durable by this exact write. */
export function clearDraftRecovery(sceneId, attemptId, answers) {
  if (safeGet(ATTEMPT_ID_KEY_PREFIX + sceneId) !== attemptId) return;
  if (safeGet(DRAFT_KEY_PREFIX + sceneId) !== JSON.stringify(answers)) return;
  safeRemove(DRAFT_KEY_PREFIX + sceneId);
  safeRemove(ATTEMPT_ID_KEY_PREFIX + sceneId);
}

/** Retire only the legacy values captured by one completed migration. */
export function clearLegacyQuizStateSnapshot(sceneId, snapshot) {
  const draftKey = DRAFT_KEY_PREFIX + sceneId;
  const attemptKey = ATTEMPT_ID_KEY_PREFIX + sceneId;
  if (safeGet(draftKey) === snapshot.rawDraft && safeGet(attemptKey) === snapshot.rawAttemptId) {
    safeRemove(draftKey);
    safeRemove(attemptKey);
  }

  const answersKey = ANSWERS_KEY_PREFIX + sceneId;
  const resultsKey = RESULTS_KEY_PREFIX + sceneId;
  if (safeGet(answersKey) === snapshot.rawAnswers && safeGet(resultsKey) === snapshot.rawResults) {
    safeRemove(answersKey);
    safeRemove(resultsKey);
  }
}

/** Retire every legacy key after migration or during stage deletion. */
export function clearAllForScene(sceneId) {
  safeRemove(DRAFT_KEY_PREFIX + sceneId);
  safeRemove(ANSWERS_KEY_PREFIX + sceneId);
  safeRemove(RESULTS_KEY_PREFIX + sceneId);
  safeRemove(ATTEMPT_ID_KEY_PREFIX + sceneId);
}
