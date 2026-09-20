import { loadQuizAttemptState } from './quiz-runtime.js';
import { createLogger } from './logger.js';
import { applyQuizSnapshot, ensureAssessment } from './pbl-proficiency.js';
import { appendProficiencyUpdatedRuntimeEvent } from './pbl-runtime-events.js';

/**
 * 移植自参考项目 `lib/pbl/v2/operations/runtime/quiz-snapshot.ts`。
 * 仅擦除 TypeScript 类型标注，逻辑逐字保留。
 *
 * PBL v2 — Pre-PBL quiz snapshot helpers.
 *
 * The adaptive proficiency engine's Stage 2 (`source: 'pre-play'`)
 * recalibration consumes the learner's prior-quiz results so the
 * Instructor starts with a more accurate proficiency tier than the
 * Planner-time static signals alone could produce.
 */

const log = createLogger('PBLQuizSnapshot');

/** Build a `PriorQuizResult[]` from the scenes preceding the PBL
 *  scene. Reads the current learner's RuntimeStore partition.
 *
 *  - Only scenes the learner has actually submitted contribute;
 *    drafts/submissions without review and never-opened quizzes do
 *    not move the signal.
 *  - Short-answer questions without `hasAnswer` are counted as
 *    `unscoredCount` rather than wrong — the engine excludes them
 *    from the accuracy denominator. */
export async function buildQuizSnapshot(scenesBeforePbl) {
  const out = [];
  for (const scene of scenesBeforePbl) {
    if (scene.type !== 'quiz' || scene.content.type !== 'quiz' || !scene.stageId) continue;
    let state;
    try {
      ({ state } = await loadQuizAttemptState({ stageId: scene.stageId, sceneId: scene.id }));
    } catch (error) {
      log.warn(`Failed to load quiz snapshot for scene ${scene.id}:`, error);
      continue;
    }
    if (state?.phase !== 'reviewed') continue;
    // `reviewed` means the learner has submitted AND seen the
    // graded results — that's the only case where we have a
    // trustworthy correctness signal.
    const questions = scene.content.questions ?? [];
    if (questions.length === 0) continue;

    let correct = 0;
    let incorrect = 0;
    let unscored = 0;
    for (const r of state.results ?? []) {
      // `correct === null` for short-answer / non-auto-gradable
      // questions: count as unscored, do not penalise.
      if (r.correct === null) {
        unscored++;
      } else if (r.correct) {
        correct++;
      } else {
        incorrect++;
      }
    }
    const scored = correct + incorrect;
    const accuracy = scored === 0 ? null : correct / scored;
    out.push({
      sceneId: scene.id,
      sceneTitle: scene.title,
      totalQuestions: questions.length,
      correctCount: correct,
      incorrectCount: incorrect,
      unscoredCount: unscored,
      accuracy,
    });
  }
  return out;
}

/** Server-side entry point: apply a freshly built quiz snapshot to
 *  the project's proficiency assessment. Mutates the assessment in
 *  place (and `project.proficiency` if the tier changes); returns
 *  the assessment after the update for caller logging. No-op when
 *  the snapshot is empty or no question was auto-graded.
 *
 *  移植说明：参考实现的这个函数只在 `/api/pbl/v2/open-task` 路由里被调用
 *  （服务端）。目标项目没有该路由，因此本函数保留在库中但当前没有调用点，
 *  以便后续接入自己的服务端时行为一致。 */
export function applyQuizSignalsToProject(project, results) {
  if (!results || results.length === 0) {
    return { updated: false, tierChanged: false };
  }
  const before = ensureAssessment(project);
  const next = applyQuizSnapshot(before, results);
  if (next === before) {
    // applyQuizSnapshot returns the same reference when no scored
    // questions were present.
    return { updated: false, tierChanged: false };
  }
  project.proficiencyAssessment = next;
  const tierChanged = next.tier !== before.tier;
  if (tierChanged) {
    project.proficiency = next.tier;
  }
  appendProficiencyUpdatedRuntimeEvent(project);
  project.updatedAt = next.lastUpdatedAt;
  return { updated: true, tierChanged };
}
