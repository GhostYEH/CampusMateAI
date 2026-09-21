import {
  appendRuntimeEvent,
  appendStatusChangedRuntimeEvent,
  mintRuntimeEventId,
  normalizationRepairEventId,
} from './pbl-runtime-events.js';

/**
 * 移植自参考项目
 * `packages/@magicclass/generation/src/pbl/operations/kernel/progress.ts`
 * 的**必要子集**（参考项目通过 `lib/pbl/v2/operations/kernel/progress.ts`
 * 的 barrel 再导出）。
 *
 * 本层需要的成员：
 *   PBL_SIMULATOR_AGENT_ID / currentMilestone / currentMicrotask /
 *   normalizeProjectRuntime / hasStartedProject / resetProjectProgress /
 *   findMicrotask / normalizeScenario
 * 未移植的推进函数（startMicrotask / advanceMicrotask / completeRoleplayAct /
 * continueAfterHandover / appendTaskDividerMessage / appendMilestoneDividerMessage）
 * 由 Instructor agent 与 `/api/pbl/v2/task/update` 路由调用，不在本次移植范围内；
 * 它们依赖的 engagement / task-completion 内核同理未移植。已在报告中标注。
 *
 * 仅擦除 TypeScript 类型标注，逻辑逐字保留。
 */

export const MILESTONE_DIVIDER_PREFIX = '[MILESTONE_DIVIDER]';
export const TASK_DIVIDER_PREFIX = '[TASK_DIVIDER]';

/** SCENARIO ONLY. Synthetic agent id for the Simulator's own chat
 *  thread. It is NOT a `roles[]` record — the cast lives as data on
 *  `project.scenario.characters`. A dedicated thread keeps the
 *  role-play conversation isolated from the Instructor's teaching
 *  history (so neither prompt pollutes the other). Absent on all
 *  ordinary projects. */
export const PBL_SIMULATOR_AGENT_ID = 'simulator';

export function currentMilestone(project) {
  return project.milestones.find((m) => m.status === 'active');
}

export function currentMicrotask(project) {
  const ms = currentMilestone(project);
  if (!ms) return undefined;
  const mt = ms.microtasks.find((t) => t.status === 'todo' || t.status === 'in_progress');
  if (!mt) return undefined;
  return { milestone: ms, microtask: mt };
}

/**
 * Normalize runtime-only state that the UI and Instructor API both
 * require after a project is generated or reloaded. Planner tools
 * build the project structure, but the runtime contract is stricter:
 * there must be one Instructor thread, one active milestone, and one
 * current microtask. Keep this small and deterministic so normal
 * generation and local test generation share the same behavior.
 */
export function normalizeProjectRuntime(project) {
  let changed = false;

  // Run the scenario skeleton repair on EVERY load (not just at generation):
  // it deterministically fixes any milestone whose `scenarioStage` the planner
  // left missing/invalid — which otherwise makes a middle act render as the
  // Instructor (prep) thread instead of the live scene. Idempotent + a no-op
  // for ordinary (non-scenario) projects, so it is safe to call here.
  if (normalizeScenario(project)) changed = true;

  const instructor = project.roles.find((r) => r.type === 'instructor');
  if (instructor && !project.threads.some((t) => t.agentId === instructor.id)) {
    project.threads.push({ agentId: instructor.id, messages: [] });
    changed = true;
  }

  // SCENARIO ONLY. Role-play projects get an extra Simulator thread so
  // the in-character conversation is stored apart from the Instructor's
  // prep/wrapup teaching thread. Gated on `project.scenario`; ordinary
  // projects never grow this thread and their runtime is byte-identical.
  if (project.scenario && !project.threads.some((t) => t.agentId === PBL_SIMULATOR_AGENT_ID)) {
    project.threads.push({ agentId: PBL_SIMULATOR_AGENT_ID, messages: [] });
    changed = true;
  }

  if (project.pendingHandover && !project.pendingHandover.consumed) {
    if (changed) {
      project.updatedAt = new Date().toISOString();
    }
    return changed;
  }

  if (project.status !== 'completed' && project.milestones.length > 0) {
    let active = project.milestones.find((m) => m.status === 'active');
    if (!active) {
      active =
        project.milestones.find((m) => m.status !== 'completed') ??
        project.milestones[project.milestones.length - 1];
      if (active && active.status !== 'active') {
        const from = active.status;
        active.status = 'active';
        appendStatusChangedRuntimeEvent(project, {
          id: normalizationRepairEventId(project, 'milestone', active.id, from, active.status),
          entityType: 'milestone',
          entityId: active.id,
          from,
          to: active.status,
          milestoneId: active.id,
        });
        changed = true;
      }
    }

    const current = active?.microtasks.find(
      (t) => t.status === 'todo' || t.status === 'in_progress',
    );
    const taskToOpen =
      current ?? active?.microtasks.find((t) => t.status !== 'completed' && t.status !== 'skipped');
    if (taskToOpen && taskToOpen.status !== 'in_progress') {
      const from = taskToOpen.status;
      taskToOpen.status = 'in_progress';
      appendStatusChangedRuntimeEvent(project, {
        id: normalizationRepairEventId(
          project,
          'microtask',
          taskToOpen.id,
          from,
          taskToOpen.status,
        ),
        entityType: 'microtask',
        entityId: taskToOpen.id,
        from,
        to: taskToOpen.status,
        microtaskId: taskToOpen.id,
        milestoneId: active?.id,
      });
      changed = true;
    }
  }

  if (changed) {
    project.updatedAt = new Date().toISOString();
  }
  return changed;
}

/**
 * Whether the learner has actually entered the project at least once.
 * Drives the Hero's "Start project" vs "Continue project" button.
 *
 * NOTE: an `in_progress` microtask does NOT count — `normalizeProjectRuntime`
 * opens the first task on a brand-new project too. The reliable signals
 * are learner-produced or Instructor-delivered: a thread message (the
 * GREETING opener), a submission / evaluation / engagement event, a
 * terminal microtask, a completed milestone, a pending handover, or a
 * finished project.
 */
export function hasStartedProject(project) {
  if (project.uiPhase === 'completed' || project.status === 'completed') return true;
  if (project.submissions.length > 0) return true;
  if (project.evaluations.length > 0) return true;
  if (project.engagementEvents.length > 0) return true;
  if (project.pendingHandover) return true;
  if (project.threads.some((thread) => thread.messages.length > 0)) return true;
  return project.milestones.some(
    (milestone) =>
      milestone.status === 'completed' ||
      milestone.microtasks.some(
        (microtask) => microtask.status === 'completed' || microtask.status === 'skipped',
      ),
  );
}

/**
 * Wipe all learner PBL progress and return a fresh `hero`-phase project,
 * equivalent to one that was just generated and never played. The
 * project STRUCTURE (roles, milestone / microtask definitions, title,
 * language, …) is preserved; only the runtime learning state is reset.
 *
 * Proficiency state (`proficiency` / `proficiencyAssessment`) is NOT
 * touched: it belongs to the learner model, not PBL progress, and is
 * owned by a separate runtime layer (PBL content vs learner runtime are
 * being decoupled). Clearing it here would couple reset to profile /
 * proficiency re-initialization and regress an intermediate/advanced
 * learner back to the beginner tier on restart.
 *
 * Pure: returns a new project, does not mutate the input.
 */
export function resetProjectProgress(project) {
  const reset = {
    ...project,
    runtimeEvents: project.runtimeEvents ? [...project.runtimeEvents] : undefined,
    runtimeResetEpoch: (project.runtimeResetEpoch ?? 0) + 1,
    uiPhase: 'hero',
    status: 'active',
    submissions: [],
    evaluations: [],
    engagementEvents: [],
    pendingHandover: undefined,
    pendingTaskCompletion: undefined,
    threads: project.threads.map((thread) => ({ agentId: thread.agentId, messages: [] })),
    milestones: project.milestones.map((milestone, index) => ({
      ...milestone,
      status: index === 0 ? 'active' : 'locked',
      internalAssessment: undefined,
      microtasks: milestone.microtasks.map((microtask) => ({
        ...microtask,
        status: 'todo',
        internalAssessment: undefined,
        completionReason: undefined,
        engagement: undefined,
      })),
    })),
    updatedAt: new Date().toISOString(),
  };
  appendRuntimeEvent(reset, {
    id: mintRuntimeEventId(),
    kind: 'project_reset',
    actorType: 'user',
    ts: reset.updatedAt,
  });
  appendStatusChangedRuntimeEvent(reset, {
    actorType: 'user',
    entityType: 'ui_phase',
    entityId: 'project',
    from: project.uiPhase,
    to: reset.uiPhase,
  });
  appendStatusChangedRuntimeEvent(reset, {
    actorType: 'user',
    entityType: 'project',
    entityId: 'project',
    from: project.status,
    to: reset.status,
  });
  project.milestones.forEach((milestone, milestoneIndex) => {
    const resetMilestone = reset.milestones[milestoneIndex];
    if (!resetMilestone) return;
    appendStatusChangedRuntimeEvent(reset, {
      actorType: 'user',
      entityType: 'milestone',
      entityId: resetMilestone.id,
      from: milestone.status,
      to: resetMilestone.status,
      milestoneId: resetMilestone.id,
    });
    milestone.microtasks.forEach((microtask, microtaskIndex) => {
      const resetMicrotask = resetMilestone.microtasks[microtaskIndex];
      if (!resetMicrotask) return;
      appendStatusChangedRuntimeEvent(reset, {
        actorType: 'user',
        entityType: 'microtask',
        entityId: resetMicrotask.id,
        from: microtask.status,
        to: resetMicrotask.status,
        microtaskId: resetMicrotask.id,
        milestoneId: resetMilestone.id,
      });
    });
  });
  return reset;
}

export function findMicrotask(project, microtaskId) {
  for (const ms of project.milestones) {
    const mt = ms.microtasks.find((t) => t.id === microtaskId);
    if (mt) return { milestone: ms, microtask: mt };
  }
  return undefined;
}

function genScenarioCharId() {
  return 'char_' + Math.random().toString(16).slice(2, 8) + Math.random().toString(16).slice(2, 8);
}

/**
 * SCENARIO ONLY. Idempotent safety net that keeps the role-play
 * scenario data structurally coherent, degrading to a plain project
 * (never crashing) when persisted / legacy / hand-edited data is
 * incoherent. No-op for ordinary projects (no `scenario`, no `scene`).
 *
 * Returns true if it mutated the project.
 */
export function normalizeScenario(project) {
  let changed = false;
  const stagedMilestones = project.milestones.filter((m) => m.scenarioStage !== undefined);

  // No cast → any `scenarioStage` marker is an orphan. Clear it so the
  // project is a clean ordinary project. (Also covers ordinary projects
  // with no stage markers at all: the loop simply does nothing.)
  if (!project.scenario) {
    for (const m of stagedMilestones) {
      delete m.scenarioStage;
      changed = true;
    }
    if (changed) project.updatedAt = new Date().toISOString();
    return changed;
  }

  const scenario = project.scenario;

  // Drop structurally-broken characters (need name + persona); assign
  // missing ids to the survivors.
  const validChars = (scenario.characters ?? []).filter(
    (c) =>
      !!c &&
      typeof c.name === 'string' &&
      c.name.trim().length > 0 &&
      typeof c.persona === 'string' &&
      c.persona.trim().length > 0,
  );
  if (validChars.length !== (scenario.characters?.length ?? 0)) {
    scenario.characters = validChars;
    changed = true;
  }
  for (const c of scenario.characters) {
    if (!c.id) {
      c.id = genScenarioCharId();
      changed = true;
    }
  }

  const degradeToPlainProject = () => {
    delete project.scenario;
    delete project.schemaVersion;
    for (const m of stagedMilestones) delete m.scenarioStage;
    changed = true;
  };

  // Cast unusable (no valid characters) → degrade.
  if (scenario.characters.length === 0) {
    degradeToPlainProject();
    if (changed) project.updatedAt = new Date().toISOString();
    return changed;
  }

  // SCENARIO SKELETON REPAIR (deterministic; runs on every load → fixes new
  // AND already-generated projects). The skeleton is FIXED: prep → roleplay(s)
  // → wrapup. The planner occasionally omits or mangles a MIDDLE milestone's
  // `scenarioStage`, leaving it undefined. At runtime an undefined-stage
  // milestone is treated as non-roleplay (Instructor thread), so entering it
  // mid-scene wrongly shows the prep briefing instead of the live scene (the
  // act-transition bug). Coerce any milestone with a missing/invalid stage by
  // position: first → prep, last → wrapup, everything in between → roleplay.
  const allMs = project.milestones;
  allMs.forEach((m, i) => {
    if (
      m.scenarioStage === 'prep' ||
      m.scenarioStage === 'roleplay' ||
      m.scenarioStage === 'wrapup'
    ) {
      return;
    }
    m.scenarioStage = i === 0 ? 'prep' : i === allMs.length - 1 ? 'wrapup' : 'roleplay';
    changed = true;
  });

  // Need at least one immersive roleplay stage to host the cast; otherwise
  // the cast has nowhere to appear → degrade (keeps the single gate
  // "`project.scenario` present = scenario project" honest). Read fresh after
  // the skeleton repair above.
  const hasRoleplay = allMs.some((m) => m.scenarioStage === 'roleplay');
  if (!hasRoleplay) {
    degradeToPlainProject();
    if (changed) project.updatedAt = new Date().toISOString();
    return changed;
  }

  // Coherent scenario.
  if (changed) project.updatedAt = new Date().toISOString();
  return changed;
}
