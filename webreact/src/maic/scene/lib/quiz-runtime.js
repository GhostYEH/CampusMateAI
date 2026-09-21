import {
  clearDraftRecovery,
  readLegacyQuizStateSnapshot,
  clearLegacyQuizStateSnapshot,
} from './quiz-persistence.js';

/**
 * 移植自参考项目 `lib/quiz/runtime.ts` 的**等价替换**。
 *
 * 参考实现把 quiz 生命周期事实追加到一个 learner 分区的 `@magicclass/storage`
 * RuntimeStore（IndexedDB / 服务端 KV）里，再做 session 折叠与并发 CAS。目标项目
 * 没有这套存储层，所以这里把同一份语义落到 localStorage：
 *
 *   - attemptId 的构造与参考实现逐字一致：
 *     `quiz-attempt:<encodeURIComponent(stageId)>:<encodeURIComponent(sceneId)>:<learnerKey>`
 *   - 重试滚动的 id 规则一致：`<root>:retry:<n>`；`startNewAttempt: true` 时把该
 *     scene 的「当前 attempt」向前滚一格，之后的写入都落在新的 attempt 上
 *     （对应参考实现的 session rollover 语义）。
 *   - 每个 attempt 保存一条**只追加**的事实日志（phase/answers/results），
 *     读取时取最后一条 —— 与参考实现的 fold 语义相同
 *   - `loadQuizAttemptState` 返回同样的 `{ attemptId, state }`
 *   - `createQuizAttemptWriter` 逐字保留（去抖、串行 tail、先冲刷草稿再写 phase）
 *
 * 保持这些签名是刻意的：quiz-view.jsx / pbl 的 quiz 快照 / classroom-complete
 * 都按原样调用，不需要改写调用点。
 *
 * 被弱化的能力（已在报告中标注）：
 *   - 没有跨标签页锁（参考实现用 navigator.locks + store CAS），
 *     `QuizRetryProgressedError` 因此永远不会被抛出（类仍导出以保持 API 完整）。
 */

const PHASE_ORDER = {
  draft: 0,
  submitted: 1,
  reviewed: 2,
};

const RECORD_KEY_PREFIX = 'maic:quiz:attempt:';
const CURRENT_KEY_PREFIX = 'maic:quiz:current:';
/** 单机本地 learner 分区键；参考实现从 learner-key 服务解析。 */
const LOCAL_LEARNER_KEY = 'local';

export class QuizRetryProgressedError extends Error {
  constructor(sessionId) {
    super(`Quiz retry ${JSON.stringify(sessionId)} already progressed in another tab`);
    this.name = 'QuizRetryProgressedError';
  }
}

const queues = new Map();
const writerTails = new Map();

async function awaitQueuedWriterLineage(attemptId) {
  let queueKey = attemptId;
  while (true) {
    while (true) {
      const pending = writerTails.get(queueKey);
      if (!pending?.size) break;
      await Promise.all(pending);
    }
    const parent = queueKey.replace(/:retry:\d+$/, '');
    if (parent === queueKey) return;
    queueKey = parent;
  }
}

async function awaitQueuedAttemptLineage(attemptId) {
  let queueKey = attemptId;
  while (true) {
    const queued = queues.get(queueKey);
    if (queued) await queued;
    const parent = queueKey.replace(/:retry:\d+$/, '');
    if (parent === queueKey) return;
    queueKey = parent;
  }
}

/**
 * Coalesce draft snapshots and serialize every phase through one local chain.
 * `recordPhase` synchronously queues a pending draft first, so submitted and
 * reviewed can never overtake the latest answers even though UI callers remain
 * fire-and-forget.
 */
export function createQuizAttemptWriter(options = {}) {
  const debounceMs = options.debounceMs ?? 500;
  const write =
    options.write ??
    (async (input) => {
      await recordQuizAttempt(input);
      clearDraftRecovery(input.sceneId, input.attemptId, input.answers);
    });
  const onError = options.onError ?? (() => {});
  let pendingDraft;
  let timer;
  let tail = Promise.resolve();

  const clearTimer = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  };

  const run = (input) => {
    const operation = tail.then(() => write(input));
    void operation.catch(onError);
    const settled = operation.catch(() => {});
    tail = settled;
    let attemptTails = writerTails.get(input.attemptId);
    if (!attemptTails) {
      attemptTails = new Set();
      writerTails.set(input.attemptId, attemptTails);
    }
    attemptTails.add(settled);
    void settled.finally(() => {
      attemptTails.delete(settled);
      if (attemptTails.size === 0 && writerTails.get(input.attemptId) === attemptTails) {
        writerTails.delete(input.attemptId);
      }
    });
    return operation;
  };

  const flushDraft = () => {
    clearTimer();
    if (!pendingDraft) return tail;
    const input = pendingDraft;
    pendingDraft = undefined;
    return run({ ...input, phase: 'draft' });
  };

  return {
    scheduleDraft(input) {
      pendingDraft = input;
      clearTimer();
      timer = setTimeout(() => {
        void flushDraft();
      }, debounceMs);
    },
    flushDraft,
    recordPhase(input) {
      void flushDraft();
      return run(input);
    },
    cancelDraft() {
      clearTimer();
      pendingDraft = undefined;
    },
  };
}

function enqueue(attemptId, work) {
  const prior = queues.get(attemptId) ?? Promise.resolve();
  const current = prior.catch(() => {}).then(work);
  const settled = current.then(
    () => undefined,
    () => undefined,
  );
  queues.set(attemptId, settled);
  void settled.finally(() => {
    if (queues.get(attemptId) === settled) queues.delete(attemptId);
  });
  return current;
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
    // Best-effort; a private-mode quota error must not break the quiz UI.
  }
}

function asQuizPayload(record) {
  if (!record || typeof record.payload !== 'object' || record.payload === null) return undefined;
  const payload = record.payload;
  if (
    payload.payloadVersion !== 1 ||
    (payload.phase !== 'draft' && payload.phase !== 'submitted' && payload.phase !== 'reviewed') ||
    typeof payload.answers !== 'object' ||
    payload.answers === null ||
    Array.isArray(payload.answers)
  ) {
    return undefined;
  }
  return payload;
}

function attemptIdSegment(value) {
  return encodeURIComponent(value);
}

export function quizAttemptId(stageId, sceneId, learnerKey) {
  return [
    'quiz-attempt',
    attemptIdSegment(stageId),
    attemptIdSegment(sceneId),
    attemptIdSegment(learnerKey),
  ].join(':');
}

function currentKey(stageId, sceneId) {
  return `${CURRENT_KEY_PREFIX}${stageId}:${sceneId}`;
}

function rootAttemptId(attemptId) {
  return attemptId.replace(/(?::retry:\d+)+$/, '');
}

/** The attempt new writes land on: the root id, or its latest retry rollover. */
function readCurrentAttemptId(stageId, sceneId) {
  const fallback = quizAttemptId(stageId, sceneId, LOCAL_LEARNER_KEY);
  const stored = safeGet(currentKey(stageId, sceneId));
  if (!stored) return fallback;
  if (rootAttemptId(stored) !== fallback) return fallback;
  return stored;
}

function rollCurrentAttemptId(stageId, sceneId) {
  const current = readCurrentAttemptId(stageId, sceneId);
  const root = rootAttemptId(current);
  const suffix = /:retry:(\d+)$/.exec(current);
  const next = rolloverAttemptId(root, suffix ? Number(suffix[1]) + 1 : 1);
  safeSet(currentKey(stageId, sceneId), next);
  return next;
}

function readRecords(attemptId) {
  const raw = safeGet(RECORD_KEY_PREFIX + attemptId);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function appendRecord(attemptId, record) {
  const records = readRecords(attemptId);
  records.push(record);
  safeSet(RECORD_KEY_PREFIX + attemptId, JSON.stringify(records));
}

function mintRecordId() {
  const suffix =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `quiz-record:${suffix}`;
}

function latestPayloadForAttempt(attemptId) {
  const records = readRecords(attemptId);
  return asQuizPayload(records[records.length - 1]);
}

function readLatestQuizAttemptState(input) {
  const attemptId = readCurrentAttemptId(input.stageId, input.sceneId);
  const payload = latestPayloadForAttempt(attemptId);
  if (!payload) return undefined;
  return {
    sessionId: attemptId,
    status: 'active',
    phase: payload.phase,
    answers: payload.answers,
    ...(payload.phase === 'reviewed'
      ? { results: Array.isArray(payload.results) ? payload.results : [] }
      : {}),
  };
}

function sameAnswers(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function rolloverAttemptId(attemptId, index) {
  return `${attemptId}:retry:${index}`;
}

/**
 * One-time compatibility migration for the four legacy localStorage keys. The
 * phase-ordering / payload-comparison rules mirror the reference implementation;
 * the legacy values are deleted only after the runtime write succeeds.
 */
async function migrateLegacyQuizState(input) {
  const legacySnapshot = readLegacyQuizStateSnapshot(input.sceneId);
  if (!legacySnapshot.hasState) return;

  const existing = readLatestQuizAttemptState(input);
  const { submitted, draft, attemptId: legacyAttemptId } = legacySnapshot;
  const legacyPhase =
    submitted?.kind === 'reviewing'
      ? 'reviewed'
      : submitted?.kind === 'answering'
        ? 'submitted'
        : draft
          ? 'draft'
          : undefined;
  const legacyPointsToNewAttempt =
    legacyAttemptId !== null &&
    (!existing ||
      (existing.sessionId !== legacyAttemptId &&
        !existing.sessionId.startsWith(`${legacyAttemptId}:retry:`)));
  const legacyPayloadMatchesExisting =
    existing !== undefined &&
    legacyPhase === existing.phase &&
    (legacyPhase === 'reviewed' && submitted?.kind === 'reviewing'
      ? sameAnswers(submitted.answers, existing.answers) &&
        JSON.stringify(submitted.results) === JSON.stringify(existing.results ?? [])
      : legacyPhase === 'submitted' && submitted?.kind === 'answering'
        ? sameAnswers(submitted.answers, existing.answers)
        : legacyPhase === 'draft' && draft !== null
          ? sameAnswers(draft, existing.answers)
          : false);
  const shouldMigrate =
    legacyPointsToNewAttempt ||
    (legacyPhase !== undefined &&
      (!existing ||
        PHASE_ORDER[legacyPhase] > PHASE_ORDER[existing.phase] ||
        (PHASE_ORDER[legacyPhase] === PHASE_ORDER[existing.phase] &&
          !legacyPayloadMatchesExisting)));

  if (shouldMigrate) {
    const attemptId =
      (legacyPointsToNewAttempt ? legacyAttemptId : existing?.sessionId) ??
      quizAttemptId(input.stageId, input.sceneId, LOCAL_LEARNER_KEY);
    if (legacyPointsToNewAttempt && legacyAttemptId) {
      safeSet(currentKey(input.stageId, input.sceneId), legacyAttemptId);
    }
    if (submitted?.kind === 'reviewing') {
      await recordQuizAttempt({
        ...input,
        attemptId,
        phase: 'reviewed',
        answers: submitted.answers,
        results: submitted.results,
      });
    } else if (submitted?.kind === 'answering') {
      await recordQuizAttempt({
        ...input,
        attemptId,
        phase: 'submitted',
        answers: submitted.answers,
      });
    } else if (draft) {
      await recordQuizAttempt({ ...input, attemptId, phase: 'draft', answers: draft });
    } else if (legacyPointsToNewAttempt) {
      await recordQuizAttempt({ ...input, attemptId, phase: 'draft', answers: {} });
    }
  }

  clearLegacyQuizStateSnapshot(input.sceneId, legacySnapshot);
}

/** Load the learner's latest quiz state, migrating legacy localStorage once. */
export async function loadQuizAttemptState(input) {
  const attemptId = readCurrentAttemptId(input.stageId, input.sceneId);
  // A UI transition can expose the next consumer while its fire-and-forget
  // writer is still queued. Wait for both the writer tail and the store queue
  // before opening a read.
  await awaitQueuedWriterLineage(attemptId);
  await awaitQueuedAttemptLineage(attemptId);
  await migrateLegacyQuizState(input);
  const state = readLatestQuizAttemptState(input);
  return {
    attemptId: state ? state.sessionId : readCurrentAttemptId(input.stageId, input.sceneId),
    state,
  };
}

/**
 * Append one immutable quiz lifecycle fact. Calls for one attempt are serialized
 * so rapid draft writes cannot overtake submit or review writes.
 *
 * `startNewAttempt` rolls the scene's current attempt forward to
 * `<root>:retry:<n>` and lands this write there — the same net effect as the
 * reference implementation's session rollover.
 */
export async function recordQuizAttempt(input) {
  return enqueue(input.attemptId, async () => {
    const targetAttemptId = input.startNewAttempt
      ? rollCurrentAttemptId(input.stageId, input.sceneId)
      : readCurrentAttemptId(input.stageId, input.sceneId);
    const payload = {
      payloadVersion: 1,
      phase: input.phase,
      answers: input.answers,
      ...(input.phase === 'reviewed' ? { results: input.results ?? [] } : {}),
    };
    const records = readRecords(targetAttemptId);
    const last = asQuizPayload(records[records.length - 1]);
    if (last && JSON.stringify(last) === JSON.stringify(payload)) {
      // Replaying the same fact is an idempotent no-op (the reference repair
      // path relies on this).
      return;
    }
    appendRecord(targetAttemptId, {
      id: mintRecordId(),
      sessionId: targetAttemptId,
      sceneId: input.sceneId,
      payload,
      ts: new Date().toISOString(),
    });
  });
}

/** Retire every stored fact for one scene (used on classroom deletion). */
export function clearQuizRuntimeForScene(stageId, sceneId) {
  if (typeof window === 'undefined') return;
  const attemptIds = [
    quizAttemptId(stageId, sceneId, LOCAL_LEARNER_KEY),
    ...Array.from({ length: 32 }, (_unused, index) =>
      rolloverAttemptId(quizAttemptId(stageId, sceneId, LOCAL_LEARNER_KEY), index + 1),
    ),
  ];
  for (const attemptId of attemptIds) {
    try {
      localStorage.removeItem(RECORD_KEY_PREFIX + attemptId);
    } catch {
      // ignore
    }
  }
  try {
    localStorage.removeItem(currentKey(stageId, sceneId));
  } catch {
    // ignore
  }
}
