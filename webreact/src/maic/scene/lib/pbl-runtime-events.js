/**
 * 移植自参考项目 `packages/@openmaic/generation/src/pbl/operations/kernel/runtime-events.ts`
 * （参考项目通过 `lib/pbl/v2/operations/kernel/runtime-events.ts` 的 barrel 再导出）。
 *
 * 仅擦除 TypeScript 类型标注。运行时事件是 PBL 进度账本，`transitionProjectUiPhase`
 * 被 pbl-renderer / hero / workspace-launch 直接调用，必须逐字保留。
 */

export const MAX_RUNTIME_EVENTS = 500;

export function mintRuntimeEventId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function appendRuntimeEvent(project, event) {
  project.runtimeEvents ??= [];
  const existing = project.runtimeEvents.find((candidate) => candidate.id === event.id);
  if (existing) {
    capRuntimeEvents(project);
    return existing;
  }
  project.runtimeEvents.push(event);
  capRuntimeEvents(project);
  return event;
}

function capRuntimeEvents(project) {
  if (!project.runtimeEvents) return;
  if (project.runtimeEvents.length > MAX_RUNTIME_EVENTS) {
    project.runtimeEvents.splice(0, project.runtimeEvents.length - MAX_RUNTIME_EVENTS);
  }
}

export function runtimeEventEpoch(project) {
  return project.runtimeResetEpoch ?? 0;
}

export function milestoneIdForMicrotask(project, microtaskId) {
  if (!microtaskId) return undefined;
  return project.milestones.find((milestone) =>
    milestone.microtasks.some((microtask) => microtask.id === microtaskId),
  )?.id;
}

export function normalizationRepairEventId(project, entityType, entityId, from, to) {
  return `norm:${runtimeEventEpoch(project)}:${entityType}:${entityId}:${from}:${to}`;
}

export function patchStatusChangedRuntimeEventId(project, entityType, entityId, from, to) {
  return `patch:${runtimeEventEpoch(project)}:${entityType}:${entityId}:${from}:${to}`;
}

export function appendStatusChangedRuntimeEvent(project, args) {
  if (args.from === args.to) return undefined;
  return appendRuntimeEvent(project, {
    id: args.id ?? mintRuntimeEventId(),
    kind: 'status_changed',
    actorType: args.actorType ?? 'system',
    actorRoleId: args.actorRoleId,
    entityType: args.entityType,
    entityId: args.entityId,
    from: args.from,
    to: args.to,
    ts: new Date().toISOString(),
    microtaskId: args.microtaskId,
    milestoneId: args.milestoneId,
  });
}

export function appendProficiencyUpdatedRuntimeEvent(project) {
  const assessment = project.proficiencyAssessment;
  if (!assessment) return undefined;
  return appendRuntimeEvent(project, {
    id: mintRuntimeEventId(),
    kind: 'proficiency_updated',
    actorType: 'system',
    tier: assessment.tier,
    score: assessment.score,
    confidence: assessment.confidence,
    ts: new Date().toISOString(),
  });
}

export function transitionProjectUiPhase(project, uiPhase) {
  const next = {
    ...project,
    runtimeEvents: project.runtimeEvents ? [...project.runtimeEvents] : undefined,
    uiPhase,
  };
  appendStatusChangedRuntimeEvent(next, {
    actorType: 'user',
    entityType: 'ui_phase',
    entityId: 'project',
    from: project.uiPhase,
    to: uiPhase,
  });
  return next;
}
