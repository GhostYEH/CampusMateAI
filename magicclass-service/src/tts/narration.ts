/**
 * 场景讲解稿（narration）—— 把一份场景正文变成**可朗读的讲稿**。
 *
 * 这是"讲课有声音"这条链路里唯一需要判断"读什么"的地方，因此它必须是纯叶子：
 * 不碰数据库、不碰网络、不读时钟。理由和 `dsl/slide-canvas.ts` 一样——讲稿的
 * 文案质量可以靠人听，但"讲稿是否为空、是否超长、是否带走了不该读的东西"
 * 必须能在 `node --test` 里直接钉住，不需要真的调用 MiMo。
 *
 * ## 为什么讲稿由服务端派生，而不是让客户端传文本
 *
 * 之前 Web 端的「生成语音」是让用户手打一段文字再去合成（见 `ProviderToolsPanel`），
 * 合成结果和任何一个场景都没有关系。那既不是讲课，也无法在切换场景时正确对应。
 * 讲稿必须**从当前场景的正文派生**，于是 "scene A 的音频" 与 "scene A 的内容"
 * 由同一份输入决定，二者不可能对不上。
 *
 * ## 为什么按场景类型分派
 *
 * 四类场景的正文形状完全不同。把 quiz 的选项当成讲解去读，或者把 PBL 的
 * 内部字段名读出来，都会产出"听起来像讲解、其实在念数据结构"的音频——这正是
 * 最该避免的失败模式。所以每类只读它**面向学生**的那部分字段。
 */

import { createHash } from 'node:crypto';

import { readSlideOutline } from '../dsl/slide-canvas.ts';
import type { Scene, SceneContent } from '../dsl/contract.ts';

/**
 * 单次合成的讲稿上限。
 *
 * MiMo 侧本身能接受更长的文本，限制在这里是因为：一段超过这个长度的音频没人会
 * 在课堂里边听边看，而它按字符计费。超长时**截断并如实标记**，而不是拒绝——
 * 拒绝会让一张内容很长的幻灯片完全点不动"生成讲解"。
 */
export const MAX_NARRATION_CHARS = 1200;

export interface NarrationDraft {
  /** 派生出的讲稿正文。可能因超长被截断。 */
  text: string;
  /** 讲稿是否被截断（用于向学生如实说明，不伪装成完整讲解）。 */
  truncated: boolean;
  /** 原始（未截断）长度，便于诊断。 */
  originalLength: number;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function textList(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(text).filter(Boolean).slice(0, limit);
}

/** 去掉会让 TTS 读错的 Markdown / 控制字符，并压平空白。 */
function clean(value: string): string {
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .replace(/[*_~>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * 把一句话收尾成可朗读的句子（补句号，避免两句连读时粘连）。
 *
 * 只有标点、没有可发音字符的输入返回空串——否则一个孤零零的"。"会被当成一段
 * 讲稿送去合成，产出几毫秒的静音音频冒充"这一页有讲解"。判据是"清洗后是否还剩
 * 字母/数字/汉字/假名/谚文"，而不是简单的 `!cleaned`。
 */
function sentence(value: string): string {
  const cleaned = clean(value);
  if (!cleaned) return '';
  if (!/[\p{L}\p{N}]/u.test(cleaned)) return '';
  return /[。！？.!?；;：:]$/.test(cleaned) ? cleaned : `${cleaned}。`;
}

function paragraphs(parts: string[]): string {
  return parts.filter(Boolean).map(sentence).filter(Boolean).join('');
}

/**
 * 标题是否值得读出来。
 *
 * 只看"非空"不够：DSL 允许的标题可能是"。"或"—"这类纯标点，把它拼进
 * "这一页讲的是……"会得到一句没有信息的话，却让上层以为这一页有讲解。
 */
function readableTitle(value: string): boolean {
  return /[\p{L}\p{N}]/u.test(clean(value));
}

/** slide：标题 + 副标题 + 要点 + 小节，都是面向学生的正文。 */
function slideNarration(content: SceneContent, sceneTitle: string): string {
  const outline = readSlideOutline(content);
  const parts: string[] = [];
  const title = outline.title || sceneTitle;
  if (readableTitle(title)) parts.push(`这一页讲的是${title}`);
  if (outline.subtitle) parts.push(outline.subtitle);
  for (const bullet of outline.bullets) parts.push(bullet);
  for (const section of outline.sections) {
    if (section.heading) parts.push(section.heading);
    for (const bullet of section.bullets) parts.push(bullet);
  }
  // New generated slides keep the authoritative rendered copy in canvas
  // elements. Older narration only inspected the structured outline, so a
  // slide with detailed text elements was incorrectly reported as empty.
  if (isObject(content) && isObject(content.canvas) && Array.isArray(content.canvas.elements)) {
    for (const element of content.canvas.elements.slice(0, 20)) {
      if (!isObject(element) || element.type !== 'text' || element.id === 'el_title') continue;
      const value = text(element.text) || text(element.value) || text(element.label) || text(element.content);
      if (value) parts.push(value);
    }
  }
  return paragraphs(parts);
}

/**
 * quiz：只读题干与解析，**不读选项、不读答案**。
 *
 * 把答案读出来等于在讲解之前先把答案念给正在自测的学生，那会直接破坏这个场景
 * 的教学用途。所以这里刻意不碰 `answer`。
 */
function quizNarration(content: SceneContent, sceneTitle: string): string {
  const questions = isObject(content) && Array.isArray(content.questions) ? content.questions : [];
  const parts: string[] = [];
  const header = readableTitle(sceneTitle) ? `这一页是${sceneTitle}的自测` : '这一页是自测';
  parts.push(header);
  for (const entry of questions.slice(0, 5)) {
    if (!isObject(entry)) continue;
    const question = text(entry.question);
    if (question) parts.push(question);
    const analysis = text(entry.analysis);
    if (analysis) parts.push(analysis);
  }
  return paragraphs(parts);
}

/**
 * interactive：读运行时可给出的说明文案，不读 `html` 原文。
 *
 * `html` 里是标签与脚本，直接朗读会变成念代码；`widgetConfig` 是内部配置，
 * 字段名同样不该进耳朵。只有 `title` / `prompt` 这类**本来就是文案**的字段可读。
 */
function interactiveNarration(content: SceneContent, sceneTitle: string): string {
  const parts: string[] = [];
  const title = (isObject(content) && text(content.title)) || sceneTitle;
  if (readableTitle(title)) parts.push(`这一页是一个互动环节：${title}`);
  if (isObject(content)) {
    const config = isObject(content.widgetConfig) ? content.widgetConfig : undefined;
    const prompt = text(config?.prompt) || text(config?.title);
    if (prompt) parts.push(prompt);
    const description = text(content.description);
    if (description) parts.push(description);
  }
  return paragraphs(parts);
}

/** pbl：项目式学习的公开说明字段；其余内部字段一律不读。 */
function pblNarration(content: SceneContent, sceneTitle: string): string {
  const parts: string[] = [];
  const source = isObject(content) ? content : {};
  const project = isObject(source.project) ? source.project : source;
  const title = text(project.title) || sceneTitle;
  if (readableTitle(title)) parts.push(`这一页是一个项目任务：${title}`);
  const goal = text(project.goal) || text(project.objective) || text(project.description);
  if (goal) parts.push(goal);
  for (const step of textList(project.steps, 6)) parts.push(step);
  return paragraphs(parts);
}

/**
 * 从场景派生讲解稿。
 *
 * 返回 `text: ''` 是**合法结果**，不是错误：一张只有图片、没有文字的幻灯片确实
 * 没什么可讲的。调用方据此如实告诉学生"这一页没有可讲解的文字"，而不是合成
 * 一段空音频冒充有讲解。
 */
export function buildSceneNarration(scene: Pick<Scene, 'type' | 'title' | 'content'>): NarrationDraft {
  const title = text(scene?.title);
  const content = scene?.content;
  let body = '';
  switch (scene?.type) {
    case 'slide': body = slideNarration(content, title); break;
    case 'quiz': body = quizNarration(content, title); break;
    case 'interactive': body = interactiveNarration(content, title); break;
    case 'pbl': body = pblNarration(content, title); break;
    default: body = sentence(title);
  }
  // 兜底：某类场景派生出空讲稿但有标题时，至少把标题读出来，而不是判成"无内容"。
  if (!body && title) body = sentence(title);
  const originalLength = body.length;
  const truncated = originalLength > MAX_NARRATION_CHARS;
  return {
    text: truncated ? body.slice(0, MAX_NARRATION_CHARS) : body,
    truncated,
    originalLength,
  };
}

/**
 * 讲稿指纹。用它对同一场景的重复生成做去重：讲稿没变就不必再付一次 TTS。
 * 与 `workspace/repository.ts` 的 `hashRequest` 同构（sha256 十六进制）。
 */
export function narrationFingerprint(sceneId: string, text: string): string {
  return createHash('sha256').update(`${sceneId}\u0000${text}`, 'utf8').digest('hex');
}
