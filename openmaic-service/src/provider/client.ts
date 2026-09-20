import type { ProviderConfig, RenderConfig, TtsConfig } from '../config.ts';
import { GENERATION_MODES, reviewGeneratedStage } from '../generation/generator.ts';
import type { GenerationMode } from '../generation/generator.ts';
import { DSL_VERSION } from '../dsl/version.ts';

/**
 * Redacted failure codes a job can end with. Messages never carry the API
 * key, the raw upstream body, or student content: they must be safe to show
 * and to log.
 */
export type ProviderErrorCode =
  | 'provider_timeout'
  | 'provider_request_failed'
  | 'provider_rejected'
  | 'provider_invalid_response'
  | 'internal_error';

export class ProviderError extends Error {
  readonly code: ProviderErrorCode;

  constructor(code: ProviderErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

/** One round trip against an OpenAI-compatible `chat/completions` endpoint. */
async function chatCompletion(
  endpoint: { baseUrl: string; apiKey: string; model: string; timeoutMs: number },
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  let response: Awaited<ReturnType<typeof fetch>>;
  try {
    response = await fetch(`${endpoint.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { authorization: `Bearer ${endpoint.apiKey}`, 'content-type': 'application/json' },
      body: JSON.stringify({ model: endpoint.model, ...body }),
      signal: AbortSignal.timeout(endpoint.timeoutMs),
    });
  } catch (error) {
    const name = error instanceof Error ? error.name : '';
    if (name === 'TimeoutError' || name === 'AbortError') {
      throw new ProviderError('provider_timeout', 'provider did not answer in time');
    }
    throw new ProviderError('provider_request_failed', 'provider could not be reached');
  }
  if (!response.ok) {
    // The status code is safe; the body may echo keys, quotas, or prompts.
    throw new ProviderError('provider_rejected', `provider rejected the request with HTTP ${response.status}`);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ProviderError('provider_invalid_response', 'provider returned malformed JSON');
  }
  if (typeof payload !== 'object' || payload === null || !Array.isArray((payload as Record<string, unknown>).choices)) {
    throw new ProviderError('provider_invalid_response', 'provider response is missing choices');
  }
  return payload as Record<string, unknown>;
}

function firstMessageContent(payload: Record<string, unknown>): string {
  const choices = payload.choices as Array<Record<string, unknown>>;
  const message = choices[0]?.message as Record<string, unknown> | undefined;
  const content = message?.content;
  if (typeof content !== 'string' || !content.trim()) {
    throw new ProviderError('provider_invalid_response', 'provider returned an empty message');
  }
  return content;
}

/** Providers like to wrap JSON in markdown fences; peel them off. */
function parseJsonContent(content: string): unknown {
  const fenced = /```(?:json)?\s*([\s\S]*?)```/.exec(content);
  const candidate = (fenced ? fenced[1] : content).trim();
  const start = candidate.indexOf('{');
  const end = candidate.lastIndexOf('}');
  if (start === -1 || end <= start) {
    throw new ProviderError('provider_invalid_response', 'provider content does not contain a JSON object');
  }
  try {
    return JSON.parse(candidate.slice(start, end + 1));
  } catch {
    throw new ProviderError('provider_invalid_response', 'provider content is not valid JSON');
  }
}

const MODE_SCENE_GUIDE = [
  "You produce learning content for an in-house Stage/Scene DSL. Reply with ONE JSON object and nothing else — no prose, no markdown fences.",
  'Shape: {"dslVersion": string, "stage": {"name": string, "description": string}, "scenes": [scene, ...]}.',
  `Set "dslVersion" to exactly "${DSL_VERSION}". Do not invent scene or stage ids; the server assigns them.`,
  `Available generation modes: ${GENERATION_MODES.join(', ')}.`,
  'Scene objects: {"title": string, "order": number, "type": "slide"|"quiz"|"interactive"|"pbl", "content": ...}.',
  'Mode mapping: slide→at least two teaching slides; quiz→quiz; pbl→pbl; every other mode→"interactive" with "widgetType" set to the mode name. If the user asks for 选择题/练习/测验/答题, include a real quiz scene after the teaching slides regardless of mode.',
  'slide content: {"type": "slide", "slide": {"title": string, "subtitle": string, "sections": [{"heading": string, "bullets": [string]}]}} — 排版由服务端生成，不给坐标。第 1 页用“概念解释”小节以完整句说明定义、适用条件及意义；第 2 页用“推导步骤”或“具体例子”小节展开至少一个可核对的步骤或实例。不要只有关键词/提纲；正文会直接作为课堂讲解稿。每条小节正文应具体、有信息量，避免空泛教学指令。',
  'quiz content: {"type": "quiz", "questions": [{"type": "single"|"multiple"|"short_answer", "question": string, "options": [{"label": string, "value": string}], "answer": [string], "analysis": string, "points": number}]} — 选择题每题 3–6 个不同选项，answer 必须是正确选项的 value（single 恰好一个，multiple 至少两个）；简答题无选项，用 analysis 给参考答案。每题题干明确、analysis 非空、points > 0；quiz 场景真正让学生作答，不能把题目写成 slide。',
  'pbl content: {"type": "pbl", "project": {"title": string, "description": string, "milestones": [{"title": string, "description": string, "tasks": [{"title": string, "description": string}]}]}} — 项目结构与阶段状态由服务端生成，你只给内容，绝不要给 id、状态或角色。2 到 5 个阶段，每阶段 1 到 5 个任务；描述都用一句话讲清"这一步要产出什么"。',
  'interactive content: {"type": "interactive", "html": string, "widgetType": string} — html is a self-contained inert fragment (headings, paragraphs, lists, inline SVG; no scripts) up to 20000 chars.',
  'Produce 2 to 8 scenes for slide mode (plus a quiz when practice is requested); quiz/pbl may have 1 to 3 scenes. All text in Chinese, academically accurate for university students.',
].join('\n');

/** Ask the provider for a full stage document; the caller still runs prepareStage. */
export async function generateStageDocument(
  provider: ProviderConfig,
  input: { mode: string; prompt: string },
): Promise<unknown> {
  const userRequest = `生成模式：${input.mode}\n内容要求：${input.prompt}`;
  let issues: string[] = [];
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const payload = await chatCompletion(provider, {
      messages: [
        { role: 'system', content: MODE_SCENE_GUIDE },
        { role: 'user', content: attempt === 0 ? userRequest : `${userRequest}\n上一稿未达到以下要求，请重新生成完整 JSON 文档并补全：${issues.join('；')}` },
      ],
      temperature: 0.4,
    });
    const document = parseJsonContent(firstMessageContent(payload));
    issues = reviewGeneratedStage(document, input.mode as GenerationMode, input.prompt);
    if (issues.length === 0) return document;
  }
  throw new ProviderError('provider_invalid_response', 'provider returned incomplete learning content');
}

const MAX_AUDIO_BYTES = 25 * 1024 * 1024;

/**
 * MiMo V2.5 TTS: the target text rides in an `assistant` message, an optional
 * style instruction in a `user` message, and `audio.voice` selects a preset
 * voice. Returns WAV bytes.
 */
export async function synthesizeSpeech(
  tts: TtsConfig,
  input: { text: string; instruction?: string; voice?: string },
): Promise<Buffer> {
  const messages: Array<{ role: string; content: string }> = [];
  if (input.instruction && input.instruction.trim()) {
    messages.push({ role: 'user', content: input.instruction.trim() });
  }
  messages.push({ role: 'assistant', content: input.text });
  const payload = await chatCompletion(tts, {
    messages,
    audio: { format: 'wav', voice: input.voice?.trim() || tts.voice },
  });
  const choices = payload.choices as Array<Record<string, unknown>>;
  const message = choices[0]?.message as Record<string, unknown> | undefined;
  const audio = message?.audio as Record<string, unknown> | undefined;
  const data = audio?.data;
  if (typeof data !== 'string' || !data) {
    throw new ProviderError('provider_invalid_response', 'provider response carries no audio');
  }
  let wav: Buffer;
  try {
    wav = Buffer.from(data, 'base64');
  } catch {
    throw new ProviderError('provider_invalid_response', 'provider audio payload is not valid base64');
  }
  const isWav = wav.length > 44 && wav.subarray(0, 4).toString('ascii') === 'RIFF' && wav.subarray(8, 12).toString('ascii') === 'WAVE';
  if (!isWav) throw new ProviderError('provider_invalid_response', 'provider audio payload is not a WAV file');
  if (wav.length > MAX_AUDIO_BYTES) {
    throw new ProviderError('provider_invalid_response', 'provider audio exceeds the supported size');
  }
  return wav;
}

export interface DiscussionMessage {
  agent: string;
  content: string;
}

/** Bounded multi-agent roundtable: N distinct voices discussing one prompt. */
export async function runDiscussion(
  provider: ProviderConfig,
  input: { prompt: string },
): Promise<DiscussionMessage[]> {
  const payload = await chatCompletion(provider, {
    messages: [
      {
        role: 'system',
        content: [
          'You orchestrate a multi-agent classroom roundtable. Reply with ONE JSON object and nothing else.',
          'Shape: {"messages": [{"agent": string, "content": string}, ...]}.',
          'Use 2 to 4 distinct agent personas (e.g. 主讲人, 追问者, 总结者); 4 to 10 messages total; each content is 1 to 4 sentences of Chinese, academically accurate; the last message summarises the discussion.',
        ].join('\n'),
      },
      { role: 'user', content: input.prompt },
    ],
    temperature: 0.6,
  });
  const parsed = parseJsonContent(firstMessageContent(payload));
  const messages = (parsed as Record<string, unknown>)?.messages;
  if (!Array.isArray(messages) || messages.length < 2 || messages.length > 12) {
    throw new ProviderError('provider_invalid_response', 'provider discussion payload has no usable messages');
  }
  return messages.map((entry) => {
    const agent = typeof (entry as Record<string, unknown>)?.agent === 'string' ? String((entry as Record<string, unknown>).agent).slice(0, 40) : '';
    const content = typeof (entry as Record<string, unknown>)?.content === 'string' ? String((entry as Record<string, unknown>).content).slice(0, 4000) : '';
    if (!content.trim()) throw new ProviderError('provider_invalid_response', 'provider discussion message is empty');
    return { agent: agent || '讨论者', content };
  });
}

const MAX_VIDEO_BYTES = 100 * 1024 * 1024;

/** Call the private render-service; its response is opaque MP4 bytes. */
export async function renderStageToMp4(render: RenderConfig, document: unknown): Promise<Buffer> {
  let response: Awaited<ReturnType<typeof fetch>>;
  try {
    response = await fetch(`${render.baseUrl}/internal/render`, {
      method: 'POST',
      headers: { 'x-render-service-token': render.token, 'content-type': 'application/json' },
      body: JSON.stringify({ document }),
      signal: AbortSignal.timeout(render.timeoutMs),
    });
  } catch (error) {
    const name = error instanceof Error ? error.name : '';
    throw new ProviderError(name === 'TimeoutError' || name === 'AbortError' ? 'provider_timeout' : 'provider_request_failed', 'render service could not be reached');
  }
  if (!response.ok) throw new ProviderError('provider_rejected', `render service rejected the request with HTTP ${response.status}`);
  const mediaType = (response.headers.get('content-type') ?? '').split(';', 1)[0].trim().toLowerCase();
  if (mediaType !== 'video/mp4') throw new ProviderError('provider_invalid_response', 'render service returned an unsupported media type');
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length === 0 || bytes.length > MAX_VIDEO_BYTES) throw new ProviderError('provider_invalid_response', 'render service returned an invalid video size');
  return bytes;
}
