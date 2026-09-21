import { appendProficiencyUpdatedRuntimeEvent } from './pbl-runtime-events.js';

/**
 * 参考项目 `packages/@magicclass/generation/src/pbl/operations/kernel/proficiency.ts`
 * 的**必要子集**移植。
 *
 * 参考实现有 33KB：关键词/生物/前序场景检测、初始评估、EWMA 动态信号、tier 迁移
 * 决策等。本层只移植 hero 的预演练重校准路径真正触及的函数：
 *   DEFAULT_TIER / scoreToTier / analyzeQuizAccuracy / emptyAssessment /
 *   aggregateSignals / applySignal / ensureAssessment / applyQuizSnapshot
 * 其余检测器与决策函数（detectOutlineKeywords、processDynamicSignal、
 * commitTierSwitch、updateProjectAssessment …）未移植，因为它们的调用方
 * （Instructor agent、task/update 路由）不在本次移植范围内。已在报告中标注。
 *
 * 仅擦除 TypeScript 类型标注，算法与常量逐字保留。
 */

/** Exponential decay for the EWMA update. Each signal moves the
 *  score by at most `EWMA_ALPHA * direction * weight`. */
const EWMA_ALPHA = 0.2;

/** Per-signal confidence accrual factor. Each signal adds at most
 *  `weight * CONFIDENCE_GAIN` to confidence, capped at 1. */
const CONFIDENCE_GAIN = 0.5;

/** Hard ceiling on `assessment.signals` length to keep
 *  `scene.content` bounded. */
const MAX_SIGNAL_HISTORY = 50;

/** Tier bucket boundaries. A learner must cross the *outer*
 *  boundary to ENTER a tier, but only the *inner* boundary to
 *  LEAVE it — that's the hysteresis. */
const TIER_BOUNDS = {
  enterAdvanced: 0.5,
  leaveAdvanced: 0.2,
  enterBeginner: -0.33,
  leaveBeginner: -0.2,
};

const WEIGHT_CAPS = {
  outline_keyword: 0.5,
  prior_scene_difficulty: 0.4,
  user_bio: 0.5,
  user_level_explicit: 1,
  quiz_accuracy: 0.5,
  submission_score: 0.5,
  task_speed: 0.3,
  help_request: 0.35,
  concept_confusion: 0.45,
  self_correction: 0.4,
  force_advance: 0.3,
  closing_check_quality: 0.4,
};

export const DEFAULT_TIER = 'intermediate';

function clamp(x, lo, hi) {
  return Math.max(lo, Math.min(hi, x));
}

function nowIso() {
  return new Date().toISOString();
}

/** Map a continuous score to a tier bucket, respecting hysteresis. */
export function scoreToTier(score, currentTier) {
  const cur = currentTier === '' || !currentTier ? DEFAULT_TIER : currentTier;
  if (cur === 'beginner') {
    if (score > TIER_BOUNDS.leaveBeginner) return 'intermediate';
    return 'beginner';
  }
  if (cur === 'advanced') {
    if (score < TIER_BOUNDS.leaveAdvanced) return 'intermediate';
    return 'advanced';
  }
  // intermediate (current) — needs to cross the outer bound to move
  if (score > TIER_BOUNDS.enterAdvanced) return 'advanced';
  if (score < TIER_BOUNDS.enterBeginner) return 'beginner';
  return 'intermediate';
}

/** Aggregate quiz-accuracy across all prior quizzes. */
export function analyzeQuizAccuracy(results) {
  if (!results || results.length === 0) return null;
  let totalScored = 0;
  let totalCorrect = 0;
  for (const r of results) {
    const scored = r.correctCount + r.incorrectCount;
    if (scored <= 0) continue;
    totalScored += scored;
    totalCorrect += r.correctCount;
  }
  if (totalScored === 0) return null;
  const accuracy = totalCorrect / totalScored;
  // Map: 0% → -1 (strong beginner), 50% → 0, 100% → +1 (strong advanced).
  // Cap at ±1 just in case of rounding artefacts.
  const direction = clamp((accuracy - 0.5) * 2, -1, 1);
  return {
    kind: 'quiz_accuracy',
    direction,
    weight: WEIGHT_CAPS.quiz_accuracy,
    note: `${totalCorrect}/${totalScored} correct across ${results.length} quiz(es), accuracy ${(
      accuracy * 100
    ).toFixed(0)}%`,
    ts: nowIso(),
  };
}

/** Bootstrap assessment for a project with no evidence yet: a neutral score
 *  at the no-evidence DEFAULT_TIER, with low confidence. */
export function emptyAssessment() {
  return {
    tier: DEFAULT_TIER,
    score: 0,
    confidence: 0.1,
    source: 'planner',
    signals: [],
    lastUpdatedAt: nowIso(),
    transitions: [],
    dynamicSignalsSinceRetier: 0,
    turnsSinceRetier: 0,
  };
}

/** Build an assessment from a fresh batch of signals. */
export function aggregateSignals(signals, source) {
  if (!signals || signals.length === 0) {
    return { ...emptyAssessment(), source };
  }
  const SHRINK_K = 0.7;
  let weightedSum = 0;
  let weightTotal = 0;
  for (const s of signals) {
    weightedSum += s.direction * s.weight;
    weightTotal += s.weight;
  }
  const rawDirection = weightTotal === 0 ? 0 : weightedSum / weightTotal;
  const shrink = weightTotal / (weightTotal + SHRINK_K);
  const score = clamp(rawDirection * shrink, -1, 1);
  const confidence = clamp(shrink, 0, 1);
  const tier = scoreToTier(score, DEFAULT_TIER);
  return {
    tier,
    score,
    confidence,
    source,
    signals: signals.slice(-MAX_SIGNAL_HISTORY),
    lastUpdatedAt: signals[signals.length - 1]?.ts ?? nowIso(),
    transitions: [],
    dynamicSignalsSinceRetier: 0,
    turnsSinceRetier: 0,
  };
}

/** Fold one new signal into the EWMA score. Pure: returns a new
 *  assessment, does not mutate. */
export function applySignal(current, signal) {
  const contribution = signal.direction * signal.weight;
  const newScore = clamp(EWMA_ALPHA * contribution + (1 - EWMA_ALPHA) * current.score, -1, 1);
  const newConfidence = clamp(current.confidence + signal.weight * CONFIDENCE_GAIN, 0, 1);
  return {
    ...current,
    score: newScore,
    confidence: newConfidence,
    signals: [...current.signals, signal].slice(-MAX_SIGNAL_HISTORY),
    lastUpdatedAt: signal.ts,
    dynamicSignalsSinceRetier: current.dynamicSignalsSinceRetier + 1,
  };
}

/** Glue used by Stage 2 / pre-play recalibration: applies a fresh
 *  quiz snapshot to an existing assessment, preserving the planner-time
 *  history but bumping the source to `'pre-play'`. */
export function applyQuizSnapshot(current, results) {
  const quizSignal = analyzeQuizAccuracy(results);
  if (!quizSignal) return current;
  const next = applySignal(current, quizSignal);
  const newTier = scoreToTier(next.score, current.tier);
  if (newTier === next.tier) {
    return { ...next, source: 'pre-play' };
  }
  // Pre-play recalibration is allowed to skip the dynamic gates —
  // quiz results are a high-quality measured behaviour, not noise.
  const ts = nowIso();
  return {
    ...next,
    tier: newTier,
    source: 'pre-play',
    transitions: [
      ...next.transitions,
      { from: current.tier, to: newTier, ts, reason: 'pre-play quiz recalibration' },
    ],
    dynamicSignalsSinceRetier: 0,
    turnsSinceRetier: 0,
    lastUpdatedAt: ts,
  };
}

/** Ensure `project.proficiencyAssessment` exists and is in sync with
 *  `project.proficiency`. Used as a safety net when older v2 projects
 *  (pre-adaptive-engine) are read back. */
export function ensureAssessment(project) {
  if (project.proficiencyAssessment) {
    return project.proficiencyAssessment;
  }
  const seed = {
    ...emptyAssessment(),
    tier: project.proficiency === '' ? DEFAULT_TIER : project.proficiency,
  };
  project.proficiencyAssessment = seed;
  return seed;
}

export { appendProficiencyUpdatedRuntimeEvent };
