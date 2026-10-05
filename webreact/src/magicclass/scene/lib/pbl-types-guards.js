/**
 * 移植自参考项目 `lib/pbl/v2/types.ts` 的**运行时判别子集**。
 *
 * `types.ts` 有 26KB，绝大部分是 TypeScript 类型（在 .jsx 目标项目里会被完全擦除）。
 * 这里只保留真正参与运行时的结构判别函数——它们是 `resolvePBLContent`
 * （pbl-renderer.jsx 用它决定走 v2 还是 legacy 升级路径）的判定依据。
 * 只擦除类型标注，判定逻辑逐字保留。
 */

function isNonArrayObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isObjectArray(value) {
  return Array.isArray(value) && value.every(isNonArrayObject);
}

/** Whether a persisted v2 value has every container the renderer and runtime
 *  contract require. */
export function hasPBLProjectV2Containers(value) {
  if (!isNonArrayObject(value)) return false;

  if (
    !isObjectArray(value.milestones) ||
    !isObjectArray(value.roles) ||
    !isObjectArray(value.submissions) ||
    !isObjectArray(value.evaluations) ||
    !isObjectArray(value.threads) ||
    !isObjectArray(value.engagementEvents)
  ) {
    return false;
  }

  if (value.milestones.some((milestone) => !isObjectArray(milestone.microtasks))) return false;
  if (value.threads.some((thread) => !isObjectArray(thread.messages))) return false;

  if (value.gains !== undefined && !Array.isArray(value.gains)) return false;
  if (value.runtimeEvents !== undefined && !isObjectArray(value.runtimeEvents)) return false;
  if (value.scenario !== undefined) {
    if (!isNonArrayObject(value.scenario)) return false;
    if (!isObjectArray(value.scenario.characters)) return false;
  }

  return true;
}

/** Whether a stored v2 payload has the minimum design structure the current
 *  workspace can turn into learner progress. Runtime normalization can repair
 *  status and create the Instructor thread, but it cannot synthesize the role
 *  id used to bind that thread, the microtask ids used by lookup/update paths,
 *  or the role/task labels rendered by the workspace and Instructor prompt.
 *  Other scalar leaves remain deliberately outside this structural predicate. */
export function isRunnablePBLProjectV2(value) {
  if (!hasPBLProjectV2Containers(value)) return false;

  const project = value;
  return (
    project.roles.some(
      (role) =>
        role.type === 'instructor' &&
        typeof role.id === 'string' &&
        role.id.trim().length > 0 &&
        typeof role.name === 'string',
    ) &&
    project.milestones.length > 0 &&
    project.milestones.every(
      (milestone) =>
        milestone.microtasks.length > 0 &&
        milestone.microtasks.every(
          (microtask) =>
            typeof microtask.id === 'string' &&
            microtask.id.trim().length > 0 &&
            typeof microtask.title === 'string',
        ),
    )
  );
}
