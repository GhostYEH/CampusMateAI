import { transitionProjectUiPhase } from './pbl-runtime-events.js';

/**
 * 移植自参考项目 `lib/pbl/v2/operations/runtime/workspace-launch.ts`。
 * 仅擦除 TypeScript 类型标注，逻辑逐字保留。
 */

/** Invalidate an async Hero launch before a different scene can reuse it. */
export function invalidatePendingWorkspaceLaunch(epoch, setLaunching) {
  epoch.current += 1;
  setLaunching(false);
}

/** Reject async launch work after either a newer launch or a scene render. */
export function isCurrentWorkspaceLaunch(epoch, currentEpoch, sceneId, currentSceneId) {
  return epoch === currentEpoch.current && sceneId === currentSceneId.current;
}

/** Prepare the project state written by the Hero when the learner starts.
 *
 * The Workspace mounts immediately; its Chat consumes
 * `pendingOpenTaskPriorQuizResults` to start the first `/open-task` stream,
 * then clears that transient payload before the request begins.
 */
export function prepareWorkspaceLaunchProject(project, priorQuizResults) {
  const next = transitionProjectUiPhase(project, 'workspace');
  if (priorQuizResults.length > 0) {
    next.pendingOpenTaskPriorQuizResults = priorQuizResults;
  } else {
    delete next.pendingOpenTaskPriorQuizResults;
  }
  return next;
}

/** Apply a delayed launch to the latest project rendered for the scene. */
export function prepareCurrentWorkspaceLaunchProject(currentProject, priorQuizResults) {
  return prepareWorkspaceLaunchProject(currentProject.current, priorQuizResults);
}
