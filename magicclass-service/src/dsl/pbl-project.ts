/**
 * PBL（项目式学习）场景内容的合成器。
 *
 * ## 为什么需要它
 *
 * 参考项目的播放器只认一种 PBL 内容：`content.projectV2`（一个带 `roles` /
 * `milestones` / `microtasks` / `threads` 的项目），或历史遗留的
 * `content.projectConfig`。两者都没有时，渲染器如实地显示
 * “PBL 项目尚未生成，请通过课程生成创建”——**这不是渲染缺陷，是内容形态不匹配**。
 *
 * 本服务此前产出的正是后者：`{ phases: [{ title, tasks: [{ title }] }] }`，既不是
 * projectV2 也不是 projectConfig。于是每个 PBL 场景在课堂里都是一个占位面板。
 *
 * ## 职责切分与幻灯片一致
 *
 * 模型只出**内容**（标题、描述、阶段与任务），服务端把它合成渲染器要求的形状。
 * 与 `slide-canvas.ts` 同样刻意保持**纯函数且确定性**：不注入时间戳（渲染器自己
 * 会补 `updatedAt`），否则读时投影每次都会得到新对象，幂等性和"没变就不重写"的
 * 判断都会失效。
 */

const INSTRUCTOR_ROLE_ID = 'role_instructor';

export interface PblTask {
  title: string;
  description: string;
}

export interface PblPhase {
  title: string;
  description: string;
  tasks: PblTask[];
}

export interface PblOutline {
  title: string;
  description: string;
  phases: PblPhase[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * 归一成 outline。同时接受模型的新形态与历史形态：
 * - 新：`{ project: { title, description, milestones: [{ title, description, tasks }] } }`
 * - 旧：`{ phases: [{ title, tasks: [{ title }] }] }`
 *
 * 旧形态没有描述，用标题兜底而不是留空——空描述会让 Hero 与工作台出现大片空白。
 */
export function readPblOutline(content: unknown): PblOutline {
  const source = isObject(content) ? content : {};
  const project = isObject(source.project) ? source.project : undefined;

  if (project) {
    const rawPhases = Array.isArray(project.milestones) ? project.milestones : [];
    const phases = rawPhases
      .map((phase) => {
        if (!isObject(phase)) return null;
        const title = text(phase.title);
        const rawTasks = Array.isArray(phase.tasks) ? phase.tasks : [];
        const tasks = rawTasks
          .map((task) => {
            if (!isObject(task)) return null;
            const taskTitle = text(task.title);
            if (!taskTitle) return null;
            return { title: taskTitle, description: text(task.description) || taskTitle };
          })
          .filter((task): task is PblTask => task !== null)
          .slice(0, 6);
        if (!title && !tasks.length) return null;
        return {
          title: title || tasks[0].title,
          description: text(phase.description) || title,
          tasks: tasks.length ? tasks : [{ title: title || '任务', description: title || '任务' }],
        };
      })
      .filter((phase): phase is PblPhase => phase !== null)
      .slice(0, 6);

    return {
      title: text(project.title),
      description: text(project.description),
      phases,
    };
  }

  const rawPhases = Array.isArray(source.phases) ? source.phases : [];
  const phases = rawPhases
    .map((phase) => {
      if (!isObject(phase)) return null;
      const title = text(phase.title);
      const rawTasks = Array.isArray(phase.tasks) ? phase.tasks : [];
      const tasks = rawTasks
        .map((task) => {
          if (!isObject(task)) return null;
          const taskTitle = text(task.title);
          if (!taskTitle) return null;
          return { title: taskTitle, description: text(task.description) || taskTitle };
        })
        .filter((task): task is PblTask => task !== null)
        .slice(0, 6);
      if (!title && !tasks.length) return null;
      return {
        title: title || '阶段',
        description: text(phase.description) || title,
        tasks: tasks.length ? tasks : [{ title: title || '任务', description: title || '任务' }],
      };
    })
    .filter((phase): phase is PblPhase => phase !== null)
    .slice(0, 6);

  return { title: '', description: '', phases };
}

/**
 * 合成 `projectV2`。
 *
 * 结构上满足渲染器的 `isRunnablePBLProjectV2` 判定（同步自
 * `webreact/src/maic/scene/lib/pbl-types-guards.js`）：
 * 六个容器数组齐全、每个 milestone 至少一个 microtask、microtask 有非空 id 与
 * 字符串 title、至少一个 `type: 'instructor'` 且 id 非空的角色。
 *
 * 没有阶段时也**必须**产出至少一个 milestone：判定要求 `milestones.length > 0`，
 * 否则渲染器会退回占位面板，合成等于白做。
 */
export function composePblProject(content: unknown, fallbackTitle = '项目式学习'): Record<string, unknown> {
  const outline = readPblOutline(content);
  const title = outline.title || fallbackTitle;
  const phases = outline.phases.length
    ? outline.phases
    : [{ title: '提出问题', description: `围绕“${title}”明确要解决的问题。`, tasks: [{ title: `定义“${title}”要解决的问题`, description: `围绕“${title}”明确要解决的问题。` }] }];

  const instructor = {
    id: INSTRUCTOR_ROLE_ID,
    type: 'instructor',
    name: '指导老师',
    description: '陪你拆解问题、推进阶段并复盘成果。',
  };

  const milestones = phases.map((phase, phaseIndex) => ({
    id: `ms_${phaseIndex + 1}`,
    title: phase.title,
    description: phase.description,
    // 第一段是"当前在做"的，其余按顺序等待：Hero 与工作台据此显示进度。
    status: phaseIndex === 0 ? 'active' : 'todo',
    order: phaseIndex,
    microtasks: phase.tasks.map((task, taskIndex) => ({
      id: `mt_${phaseIndex + 1}_${taskIndex + 1}`,
      title: task.title,
      description: task.description,
      status: phaseIndex === 0 && taskIndex === 0 ? 'in_progress' : 'todo',
      assignee: 'user',
      hints: [],
      order: taskIndex,
    })),
    documents: [],
    briefing: phase.description || phase.title,
    completionCriteria: '完成本阶段任务，并能说清结论与依据。',
    debrief: '回看本阶段：哪些判断有证据支撑，哪些还需要补充。',
  }));

  return {
    // 一定是 hero：内容刚生成，学员还没开始，直接进 workspace 会跳过项目说明。
    uiPhase: 'hero',
    title,
    description: outline.description || `围绕“${title}”展开的项目式学习。`,
    proficiency: '',
    language: 'zh-CN',
    tags: [],
    status: 'active',
    roles: [instructor],
    milestones,
    submissions: [],
    evaluations: [],
    threads: [{ agentId: instructor.id, messages: [] }],
    engagementEvents: [],
  };
}

/**
 * 读取时投影：把历史 PBL 场景的内容补成渲染器认得的 `projectV2`。
 *
 * 与幻灯片投影同一条边界：
 * - **已经有 `projectV2` 或可用的 `projectConfig` 就不动。** 前者是渲染器的一等
 *   公民；后者是渲染器自己会升级的合法历史形态，抢着改写只会覆盖它的升级逻辑。
 * - **无改动时返回同一引用**，调用方据此跳过序列化。
 */
export function upgradeLegacyPblProjects(document: unknown): unknown {
  if (!isObject(document)) return document;
  const scenes = document.scenes;
  if (!Array.isArray(scenes)) return document;

  let changed = false;
  const upgraded = scenes.map((scene) => {
    if (!isObject(scene) || scene.type !== 'pbl') return scene;
    const content = isObject(scene.content) ? scene.content : undefined;
    if (!content || content.type !== 'pbl') return scene;
    if (isObject(content.projectV2)) return scene;

    const legacyConfig = content.projectConfig;
    const hasLegacyIssues = isObject(legacyConfig)
      && isObject(legacyConfig.issueboard)
      && Array.isArray(legacyConfig.issueboard.issues)
      && legacyConfig.issueboard.issues.length > 0;
    if (hasLegacyIssues) return scene;

    const sceneTitle = text(scene.title);
    changed = true;
    return {
      ...scene,
      content: { ...content, projectV2: composePblProject(content, sceneTitle || '项目式学习') },
    };
  });

  return changed ? { ...document, scenes: upgraded } : document;
}
