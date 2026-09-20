import { gradeChoiceQuestions } from './quiz-grading.js';

/**
 * 移植自参考项目 `lib/classroom/complete-summary.ts`。
 * 仅擦除 TypeScript 类型标注，逻辑逐字保留。
 */

export function pendingCompleteSummary(scenes) {
  return {
    countsByType: scenes.reduce((counts, scene) => {
      counts[scene.type] = (counts[scene.type] ?? 0) + 1;
      return counts;
    }, {}),
    quiz: null,
  };
}

/** Never render a completed summary produced for a different scenes snapshot. */
export function completeSummaryForScenes(scenes, resolved) {
  return resolved.scenes === scenes ? resolved.summary : pendingCompleteSummary(scenes);
}

/** Skip malformed legacy scenes before opening their RuntimeStore partition. */
export async function readSceneQuizAnswers(scene, load) {
  if (!scene?.stageId) return undefined;
  const { state } = await load({ stageId: scene.stageId, sceneId: scene.id });
  return state?.answers ?? {};
}

export async function summarizeScenes(scenes, readAnswers) {
  const countsByType = {};
  for (const scene of scenes) {
    countsByType[scene.type] = (countsByType[scene.type] ?? 0) + 1;
  }

  let correct = 0;
  let total = 0;
  for (const scene of scenes) {
    if (scene.type !== 'quiz') continue;
    const questions = scene.content.questions ?? [];
    let answers;
    try {
      answers = await readAnswers(scene.id);
    } catch {
      continue;
    }
    if (answers === undefined) continue;
    const results = gradeChoiceQuestions(questions, answers);
    for (const r of results) {
      total += 1;
      if (r.correct === true) correct += 1;
    }
  }

  const quiz = total > 0 ? { correct, total, pct: Math.round((correct / total) * 100) } : null;

  return { countsByType, quiz };
}
