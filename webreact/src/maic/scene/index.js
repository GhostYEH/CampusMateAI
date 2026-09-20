/**
 * MACI 场景层入口。
 *
 * 移植自参考项目 `components/stage/scene-renderer.tsx` 及其
 * `components/scene-renderers/` 下的各个渲染器。
 *
 * 分发器本体在 `./scene-renderer.jsx`（必须是 `.jsx`：目标项目的 vite 只对
 * `.jsx` 启用 JSX 语法），这里把它连同各个渲染器、PBL 卡片与必要 helper 一起
 * 导出，调用方只需要 `import { MaicSceneRenderer } from <maic/scene/index.js>`。
 */

export { MaicSceneRenderer } from './scene-renderer.jsx';

// ─── 各个场景渲染器 ─────────────────────────────────────────────────────────

export { QuizView, setQuizGradeModelConfig } from './quiz-view.jsx';
export { QuizRenderer } from './quiz-renderer.jsx';
export { InteractiveRenderer } from './interactive-renderer.jsx';
export { InteractiveIframeHost } from './InteractiveIframeHost.jsx';
export { PBLRenderer } from './pbl-renderer.jsx';
export { ClassroomCompletePage, ClassroomCompletePageConnected } from './classroom-complete.jsx';

// ─── PBL 展示层 ─────────────────────────────────────────────────────────────

export { MarkdownText } from './pbl/markdown-text.jsx';
export { StarRating } from './pbl/eval-cards/star-rating.jsx';
export { CompletionCtaCard } from './pbl/eval-cards/completion-cta-card.jsx';
export { TaskEvaluationCard } from './pbl/eval-cards/task-evaluation-card.jsx';
export {
  MilestoneCard,
  milestoneHandoverCtaState,
  stripFinalMilestoneContinueGuidance,
} from './pbl/eval-cards/milestone-card.jsx';
export { PBLV2Hero } from './pbl/hero.jsx';
export {
  PBLV2Completion,
  buildCompletionReportViewModel,
  cleanCompletionIntro,
} from './pbl/completion.jsx';
export { SceneBackdrop } from './pbl/scene-backdrop.jsx';

// ─── 小 helper ──────────────────────────────────────────────────────────────

export { computeFitScale } from './pbl/fit-scale.js';
export { rectsEqual } from './pbl/host-rect.js';
export {
  TASK_DIVIDER_PREFIX,
  MILESTONE_DIVIDER_PREFIX,
  stripEmbeddedDividerMarkers,
  isStandaloneDividerMessage,
} from './pbl/protocol-markers.js';
export { sanitizeSceneVisual } from './pbl/scene-types.js';

// ─── 调用方可能需要的底层能力 ───────────────────────────────────────────────

export { setLatexRenderer, renderQuizMathText } from './lib/quiz-math-text.js';
export { useInteractiveIframePool, IFRAME_POOL_CAP } from './lib/interactive-iframe-pool.js';
export { useWidgetIframeStore } from './lib/widget-iframe-store.js';
export { useSceneRuntimeErrors } from './lib/scene-runtime-errors.js';
export { useStageStore } from './lib/stage-store.js';
export { patchHtmlForIframe } from './lib/iframe.js';
export { computeCompletionStats } from './lib/completion-stats.js';
export { normalizeStars, normalizeScore, stripEvaluationTail } from './lib/eval-tail-parser.js';
export {
  quizAttemptId,
  loadQuizAttemptState,
  createQuizAttemptWriter,
  recordQuizAttempt,
} from './lib/quiz-runtime.js';
export { gradeChoiceQuestions, answerIncludesOption } from './lib/quiz-grading.js';
export {
  resolvePBLContent,
  upgradeLegacyPBLConfigToProjectV2,
} from './lib/pbl-legacy-read.js';
export {
  hasStartedProject,
  resetProjectProgress,
  normalizeProjectRuntime,
  PBL_SIMULATOR_AGENT_ID,
} from './lib/pbl-progress.js';
export { transitionProjectUiPhase } from './lib/pbl-runtime-events.js';
