import { randomUUID } from 'node:crypto';

import type { Scene, SceneType, StageAggregate, WidgetType } from '../dsl/contract.ts';
import { DSL_VERSION } from '../dsl/version.ts';
import { composeSlideCanvas, readSlideOutline } from '../dsl/slide-canvas.ts';
import { composePblProject } from '../dsl/pbl-project.ts';

export const GENERATION_MODES = [
  'slide', 'quiz', 'interactive', 'pbl', 'simulation', 'diagram', 'code', 'game',
  'visualization3d', 'procedural-skill',
] as const;

export type GenerationMode = (typeof GENERATION_MODES)[number];

export function isGenerationMode(value: unknown): value is GenerationMode {
  return typeof value === 'string' && (GENERATION_MODES as readonly string[]).includes(value);
}

function id(prefix: string) {
  return `${prefix}_${randomUUID().replaceAll('-', '')}`;
}

function clipPrompt(prompt: string): string {
  const trimmed = prompt.trim();
  return trimmed.length > 200 ? trimmed.slice(0, 200) : trimmed;
}

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

const PRACTICE_REQUEST = /选择题|练习|测验|答题|自测|习题/;

function quizContent(title: string): Extract<Scene['content'], { type: 'quiz' }> {
  return {
    type: 'quiz',
    questions: [{ id: id('question'), type: 'single', question: `学习“${title}”时，应先做哪一步？`, options: [
      { label: '明确核心概念与适用条件', value: 'A' },
      { label: '跳过概念，直接背结论', value: 'B' },
      { label: '只记例题答案，不检查理由', value: 'C' },
    ], answer: ['A'], analysis: '先弄清概念及其适用条件，再用推导和例题检验理解。', points: 1 }],
  };
}

function authoredScene(stageId: string, order: number, title: string, content: Scene['content'], now: number): Scene {
  return { id: id('scene'), stageId, title, order, type: content.type, content, createdAt: now, updatedAt: now };
}

/** A generation-specific quality gate; prepareStage still validates the entire DSL. */
export function reviewGeneratedStage(raw: unknown, mode: GenerationMode, prompt: string): string[] {
  const scenes = isObject(raw) && Array.isArray(raw.scenes) ? raw.scenes : [];
  const issues: string[] = [];
  if (mode === 'slide') {
    for (const [index, purpose] of ['概念', '推导或例子'].entries()) {
      const scene = scenes[index];
      const content = isObject(scene) && isObject(scene.content) ? scene.content : {};
      const outline = readSlideOutline(content);
      const heading = index === 0 ? /概念|定义|原理/ : /推导|步骤|例子|示例|应用/;
      const explained = content.type === 'slide' && outline.sections.some((section) =>
        heading.test(section.heading) && section.bullets.some((line) => line.length >= 15));
      if (!explained) issues.push(`slide ${index + 1} needs a ${purpose} explanation section with substantive text`);
    }
  }
  const needsQuiz = mode === 'quiz' || PRACTICE_REQUEST.test(prompt);
  const quizzes = scenes.filter((scene) => isObject(scene) && scene.type === 'quiz');
  if (needsQuiz && quizzes.length === 0) issues.push('quiz scene is required for practice');
  for (const scene of quizzes) {
    const content = isObject(scene.content) ? scene.content : {};
    const questions = content.questions;
    if (!Array.isArray(questions) || questions.length === 0) {
      issues.push('quiz scene needs questions');
      continue;
    }
    for (const question of questions) {
      if (!isObject(question) || !['single', 'multiple', 'short_answer'].includes(String(question.type))
        || typeof question.question !== 'string' || !question.question.trim()
        || typeof question.analysis !== 'string' || !question.analysis.trim()
        || typeof question.points !== 'number' || !Number.isFinite(question.points) || question.points <= 0) {
        issues.push('quiz question needs a stem, analysis and positive points');
        continue;
      }
      if (question.type === 'short_answer') continue;
      const options = question.options;
      const answer = question.answer;
      if (!Array.isArray(options) || options.length < 3 || options.length > 6
        || !options.every((option) => isObject(option) && typeof option.label === 'string' && option.label.trim()
          && typeof option.value === 'string' && option.value.trim())
        || new Set(options.map((option) => option.value)).size !== options.length
        || !Array.isArray(answer) || answer.length < (question.type === 'multiple' ? 2 : 1)
        || (question.type === 'single' && answer.length !== 1)
        || answer.some((value) => !options.some((option) => option.value === value))
        || new Set(answer).size !== answer.length) {
        issues.push('quiz choice question needs 3-6 distinct options and matching answer values');
      }
    }
  }
  return issues;
}

function widgetContent(mode: GenerationMode, title: string): { type: 'interactive'; html: string; widgetType?: WidgetType; widgetConfig?: Record<string, unknown> } {
  const widgetType = mode === 'interactive' ? undefined : mode as WidgetType;
  if (mode === 'simulation') {
    return {
      type: 'interactive',
      widgetType,
      widgetConfig: {
        type: 'simulation',
        title,
        resultLabel: '加速度',
        formula: 'force / mass',
        parameters: [
          { id: 'force', label: '力', min: 0, max: 100, step: 1, value: 20, unit: 'N' },
          { id: 'mass', label: '质量', min: 1, max: 20, step: 1, value: 5, unit: 'kg' },
        ],
      },
      html: `<main><h1>${escapeHtml(title)}</h1><p>调整力和质量，观察加速度的变化。</p></main>`,
    };
  }
  return {
    type: 'interactive',
    ...(widgetType ? { widgetType, widgetConfig: { type: widgetType, prompt: title } } : {}),
    // This is a bounded, inert local starter surface. It is always rendered in
    // the player sandbox, never inserted into trusted DOM.
    html: `<main><h1>${escapeHtml(title)}</h1><p>这是 ${escapeHtml(widgetType ?? 'interactive')} 学习活动的可编辑起点。</p></main>`,
  };
}

export function buildGeneratedStage(
  mode: GenerationMode,
  prompt: string,
  now = Date.now(),
  options: { agentIds?: string[] } = {},
): StageAggregate & { dslVersion: string } {
  const title = clipPrompt(prompt) || '未命名学习内容';
  const stageId = id('stage');
  const sceneId = id('scene');
  let type: SceneType = 'slide';
  let content: Scene['content'];
  const scene: Scene = {
    id: sceneId,
    stageId,
    title,
    order: 0,
    type,
    // 本地模板（未配置 provider 时的降级路径）也走同一套画布合成：它必须和模型
    // 产出的幻灯片**同形状**，否则"没配模型"与"配了模型"在课堂里会渲染成两种
    // 完全不同的东西，而前者看起来就像功能坏了。
    content: {
      type: 'slide',
      slide: {
        title: `理解${title}`,
        sections: [{ heading: '概念解释', bullets: [`先明确“${title}”讨论的对象、定义和适用条件，再说明它解决什么问题。`] }],
      },
      canvas: composeSlideCanvas({
        slide: {
          title: `理解${title}`,
          sections: [{ heading: '概念解释', bullets: [`先明确“${title}”讨论的对象、定义和适用条件，再说明它解决什么问题。`] }],
        },
      }),
    },
    createdAt: now,
    updatedAt: now,
  };

  if (mode === 'quiz') {
    type = 'quiz';
    content = quizContent(title);
  } else if (mode === 'pbl') {
    type = 'pbl';
    // 本地模板也必须产出渲染器认得的形状，理由同幻灯片：否则"没配模型"看起来
    // 就像 PBL 功能坏了。
    content = {
      type: 'pbl',
      projectV2: composePblProject({
        project: {
          title,
          description: `围绕“${title}”展开的项目式学习。`,
          milestones: [
            { title: '提出问题', description: `明确“${title}”要解决的问题。`, tasks: [{ title: `定义“${title}”要解决的问题` }] },
            { title: '拆解与探索', description: '找出需要的事实、资料与判断依据。', tasks: [{ title: '列出需要的资料与判断依据' }] },
            { title: '形成方案', description: '把结论组织成可以被检验的方案。', tasks: [{ title: '给出可检验的结论' }] },
          ],
        },
      }, title),
    };
  } else if (mode !== 'slide') {
    type = 'interactive';
    content = widgetContent(mode, title);
  } else {
    content = scene.content;
  }
  scene.type = type;
  scene.content = content;
  if (type === 'interactive' && content.type === 'interactive' && mode === 'simulation') {
    scene.whiteboards = [{ id: id('board'), title: '推导草稿', elements: [] }];
  }

  return {
    dslVersion: DSL_VERSION,
    stage: {
      id: stageId,
      name: title,
      description: `由本地受管生成流程创建：${title}`,
      createdAt: now,
      updatedAt: now,
      ...(options.agentIds?.length ? { agentIds: options.agentIds } : {}),
    },
    scenes: mode === 'slide' ? [
      scene,
      authoredScene(stageId, 1, `${title}：推导与例子`, {
        type: 'slide',
        slide: { title: `${title}：推导与例子`, sections: [{ heading: '推导步骤', bullets: ['从概念的适用条件出发，逐步写出已知量、使用的关系和得到的结论。'] }, { heading: '具体例子', bullets: ['选择一个满足条件的具体情境，代入已知量，再检查结论是否符合原概念。'] }] },
        canvas: composeSlideCanvas({ slide: { title: `${title}：推导与例子`, sections: [{ heading: '推导步骤', bullets: ['从概念的适用条件出发，逐步写出已知量、使用的关系和得到的结论。'] }, { heading: '具体例子', bullets: ['选择一个满足条件的具体情境，代入已知量，再检查结论是否符合原概念。'] }] } }),
      }, now),
      ...(PRACTICE_REQUEST.test(prompt) ? [authoredScene(stageId, 2, `${title}：自测`, quizContent(title), now)] : []),
    ] : [scene],
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function assignContentIds(scene: Record<string, unknown>): Record<string, unknown> {
  const result = { ...scene };
  const content = isObject(result.content) ? result.content : undefined;
  if (content?.type === 'slide') {
    // 模型只出结构化内容（title/subtitle/bullets/sections），**排版由服务端合成**：
    // 把绝对坐标交给模型，得到的是重叠与越界，而且只有渲染出来才看得见。
    // 这里同时兜住历史的 `canvas: { title, body }` 形态，老数据不会变成空白页。
    result.content = { type: 'slide', slide: readSlideOutline(content), canvas: composeSlideCanvas(content) };
  }
  if (content?.type === 'quiz' && Array.isArray(content.questions)) {
    result.content = {
      ...content,
      questions: content.questions.map((question) => (isObject(question) ? { ...question, id: id('question') } : question)),
    };
  }
  if (content?.type === 'pbl') {
    // 与幻灯片同理：模型出阶段/任务的内容，服务端合成渲染器唯一认得的
    // `projectV2`。此前产出的 `{ phases: [...] }` 既不是 projectV2 也不是历史
    // 的 projectConfig，渲染器只能显示"项目尚未生成"的占位面板。
    result.content = {
      type: 'pbl',
      projectV2: composePblProject(content, typeof result.title === 'string' ? result.title : '项目式学习'),
    };
  }
  if (Array.isArray(result.actions)) {
    result.actions = result.actions.map((action) => (isObject(action) ? { ...action, id: id('action') } : action));
  }
  return result;
}

/**
 * Turn a model-authored document into a complete aggregate. The model writes
 * content and never identities or timestamps (the prompt forbids it), so the
 * service owns the ids, ordering and clock before the validator runs.
 */
export function materializeGeneratedStage(raw: unknown, options: { agentIds?: string[] } = {}): StageAggregate & { dslVersion: string } {
  const now = Date.now();
  const stageId = id('stage');
  const source = isObject(raw) ? raw : {};
  const stageInput = isObject(source.stage) ? source.stage : {};
  const scenesInput = Array.isArray(source.scenes) ? source.scenes : [];
  const scenes = scenesInput.map((scene, index) => {
    const input = isObject(scene) ? scene : {};
    return {
      ...assignContentIds(input),
      id: id('scene'),
      stageId,
      order: index,
      createdAt: now,
      updatedAt: now,
    } as unknown as Scene;
  });
  return {
    dslVersion: DSL_VERSION,
    stage: {
      ...stageInput,
      id: stageId,
      createdAt: now,
      updatedAt: now,
      ...(options.agentIds?.length ? { agentIds: options.agentIds } : {}),
    } as unknown as StageAggregate['stage'],
    scenes,
  };
}
