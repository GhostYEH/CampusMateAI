import { randomUUID } from 'node:crypto';

import type { Scene, SceneType, StageAggregate, WidgetType } from '../dsl/contract.ts';
import { DSL_VERSION } from '../dsl/version.ts';
import { composeSlideCanvas } from '../dsl/slide-canvas.ts';
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
      canvas: composeSlideCanvas({
        slide: {
          title,
          subtitle: `围绕“${title}”开始学习。`,
          bullets: [`${title}的核心问题`, `关键概念与相互关系`, `如何检验自己的理解`],
        },
      }),
    },
    createdAt: now,
    updatedAt: now,
  };

  if (mode === 'quiz') {
    type = 'quiz';
    content = {
      type: 'quiz',
      questions: [{ id: id('question'), type: 'single', question: `关于“${title}”，最重要的第一步是什么？`, options: [
        { label: '先梳理关键概念', value: 'concepts' },
        { label: '跳过基础直接背答案', value: 'answers' },
      ], answer: ['concepts'], analysis: '先建立概念结构，再进行练习。', points: 1 }],
    };
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
    scenes: [scene],
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
    result.content = { type: 'slide', canvas: composeSlideCanvas(content) };
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
