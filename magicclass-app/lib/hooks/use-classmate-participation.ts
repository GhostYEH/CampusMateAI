'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AgentConfig } from '@/lib/orchestration/registry/types';
import type { Scene } from '@/lib/types/stage';
import { getCurrentModelConfig } from '@/lib/utils/model-config';

export interface ClassmateParticipationState {
  messages: Record<string, string>;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
}

/** What classmates already said in this classroom, bounded and sent with the next page. */
interface ClassmateMemory {
  pages: string[];
  lines: { agentId: string; text: string }[];
  recentAgentIds: string[];
}

const IDLE: ClassmateParticipationState = { messages: {}, status: 'idle', error: null };
const EMPTY_MEMORY: ClassmateMemory = { pages: [], lines: [], recentAgentIds: [] };
const MEMORY_PREFIX = 'maic:classmate-memory:';
const USAGE_PREFIX = 'maic:classmate-usage:';
/**
 * A course-level guard against runaway spending, not a hard cap: when the
 * classroom has spent this many tokens on page reactions and direct answers,
 * classmates stop reacting automatically and the UI says so.
 */
export const CLASSROOM_TOKEN_BUDGET = 240_000;
const MAX_MEMORY_PAGES = 8;
const MAX_MEMORY_LINES = 12;
const MAX_MEMORY_PAGE_CHARS = 200;
const MAX_MEMORY_LINE_CHARS = 400;
const MEDIA_FIELDS = new Set([
  'src',
  'url',
  'audio',
  'audioUrl',
  'audioData',
  'imageBase64',
  'svg',
  'style',
  'theme',
  'fontName',
  'fontFamily',
  'color',
  'fill',
  'outline',
  'shadow',
  'thumbnail',
  'path',
]);

const memoryKey = (stageId?: string) => (stageId ? `${MEMORY_PREFIX}${stageId}` : '');
const usageKey = (stageId?: string) => (stageId ? `${USAGE_PREFIX}${stageId}` : '');

/**
 * Continuity memory scoped to this browser and this course: it keeps the class
 * from repeating itself page after page, survives reopening the classroom, and
 * never stores the student's own words. Durable learner-level memory belongs
 * to the learner profile, not here.
 */
function readClassmateMemory(stageId?: string): ClassmateMemory {
  const key = memoryKey(stageId);
  if (!key) return EMPTY_MEMORY;
  try {
    const raw = globalThis.localStorage?.getItem(key);
    if (!raw) return EMPTY_MEMORY;
    const value = JSON.parse(raw) as Partial<ClassmateMemory> | null;
    if (!value || typeof value !== 'object') return EMPTY_MEMORY;
    const pages = Array.isArray(value.pages)
      ? value.pages
          .filter((page): page is string => typeof page === 'string' && page.length > 0)
          .map((page) => page.slice(0, MAX_MEMORY_PAGE_CHARS))
          .slice(-MAX_MEMORY_PAGES)
      : [];
    const lines = Array.isArray(value.lines)
      ? value.lines
          .filter(
            (line): line is { agentId: string; text: string } =>
              !!line &&
              typeof line === 'object' &&
              typeof (line as { agentId?: unknown }).agentId === 'string' &&
              typeof (line as { text?: unknown }).text === 'string',
          )
          .map((line) => ({
            agentId: line.agentId,
            text: line.text.slice(0, MAX_MEMORY_LINE_CHARS),
          }))
          .slice(-MAX_MEMORY_LINES)
      : [];
    const recentAgentIds = Array.isArray(value.recentAgentIds)
      ? value.recentAgentIds
          .filter((id): id is string => typeof id === 'string' && id.length > 0)
          .slice(0, 7)
      : [];
    return { pages, lines, recentAgentIds };
  } catch {
    return EMPTY_MEMORY;
  }
}

function writeClassmateMemory(stageId: string | undefined, memory: ClassmateMemory): void {
  const key = memoryKey(stageId);
  if (!key) return;
  try {
    globalThis.localStorage?.setItem(key, JSON.stringify(memory));
  } catch {
    // A full or unavailable storage only costs continuity, never the lesson.
  }
}

/** Bound both text and structure so a large page still leaves room for every persona. */
function boundedContext(
  value: unknown,
  budget: { characters: number; nodes: number },
  depth = 0,
): unknown {
  if (depth > 16 || budget.nodes-- <= 0 || budget.characters <= 0) return undefined;
  if (typeof value === 'string') {
    const text = value.slice(0, Math.min(12_000, budget.characters));
    budget.characters -= text.length;
    return text;
  }
  if (Array.isArray(value)) {
    const children: unknown[] = [];
    for (const child of value) {
      if (budget.nodes <= 0 || budget.characters <= 0) break;
      const projected = boundedContext(child, budget, depth + 1);
      if (projected !== undefined) children.push(projected);
    }
    return children;
  }
  if (value && typeof value === 'object') {
    const entries: [string, unknown][] = [];
    for (const [key, child] of Object.entries(value)) {
      if (MEDIA_FIELDS.has(key) || key.length > 128) continue;
      if (budget.characters < key.length || budget.nodes <= 0) break;
      budget.characters -= key.length;
      const projected = boundedContext(child, budget, depth + 1);
      if (projected !== undefined) entries.push([key, projected]);
    }
    return Object.fromEntries(entries);
  }
  return value;
}

/** Send lesson text, not the lesson's potentially large media assets. */
export function classmateRequestBody(
  scene: Scene,
  agents: AgentConfig[],
  language?: string,
): string {
  return JSON.stringify(
    {
      scene: {
        id: scene.id,
        title: scene.title.slice(0, 1000),
        type: scene.type,
        content: {
          ...(boundedContext(scene.content, { characters: 16_000, nodes: 512 }) as Record<
            string,
            unknown
          >),
          type: scene.type,
        },
        actions: boundedContext(
          (scene.actions || [])
            .filter((action) => action.type === 'speech')
            .map((action) => ({ type: action.type, text: action.text })),
          { characters: 8000, nodes: 128 },
        ),
      },
      agents: agents
        .filter((agent) => agent.role !== 'teacher' && agent.role !== 'user')
        .map(({ id, name, role, persona }) => ({
          id,
          name,
          role,
          persona: persona.slice(0, 2000),
        })),
      language,
    },
    (key, value: unknown) => {
      if (MEDIA_FIELDS.has(key)) return undefined;
      return typeof value === 'string' ? value.slice(0, 12_000) : value;
    },
  );
}

/** Tokens this course already spent on classmate calls; unknown or corrupt values count as zero. */
function readClassmateUsage(stageId?: string): number {
  const key = usageKey(stageId);
  if (!key) return 0;
  try {
    const value = Number(globalThis.localStorage?.getItem(key));
    return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
  } catch {
    return 0;
  }
}

function addClassmateUsage(stageId: string | undefined, tokens: number): number {
  const key = usageKey(stageId);
  const total = readClassmateUsage(stageId) + (Number.isFinite(tokens) ? Math.max(0, tokens) : 0);
  if (!key) return total;
  try {
    globalThis.localStorage?.setItem(key, String(total));
  } catch {
    // Quota or private mode: keep the in-memory count, the budget still applies this session.
  }
  return total;
}

export async function requestClassmateParticipation(
  body: string,
  signal: AbortSignal,
  memory?: ClassmateMemory,
): Promise<{ messages: Record<string, string>; tokens: number }> {
  const config = getCurrentModelConfig();
  const payload = JSON.parse(body) as { agents: { id: string }[] };
  const response = await fetch('/api/chat/classmates', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-model': config.modelString,
      'x-api-key': config.apiKey,
      'x-base-url': config.baseUrl,
      'x-provider-type': config.providerType || '',
    },
    body: JSON.stringify({
      ...payload,
      ...(memory ? { memory } : {}),
      thinkingConfig: config.thinkingConfig,
    }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(65_000)]),
  });
  const data = await response.json();
  if (!response.ok || data.success !== true) {
    throw new Error(data.error || `Classmate generation failed (${response.status})`);
  }
  if (!Array.isArray(data.messages)) throw new Error('Invalid classmate response');
  const expectedIds = new Set(payload.agents.map((agent) => agent.id));
  const messages: Record<string, string> = Object.create(null);
  // Fewer messages are legitimate: a classmate may stay quiet, or the page may
  // not need anyone. Only misattributed or duplicated output is rejected.
  for (const message of data.messages) {
    if (
      typeof message?.agentId !== 'string' ||
      !expectedIds.has(message.agentId) ||
      typeof message.text !== 'string' ||
      !message.text.trim() ||
      Object.hasOwn(messages, message.agentId)
    ) {
      throw new Error('Invalid classmate response');
    }
    messages[message.agentId] = message.text.trim();
  }
  return { messages, tokens: Number(data.usage?.tokens) || 0 };
}

/** Classmate reactions run separately from the teacher's playback/live chat state. */
export function useClassmateParticipation({
  scene,
  agents,
  language,
  enabled,
  started,
}: {
  scene: Scene | null;
  agents: AgentConfig[];
  language?: string;
  enabled: boolean;
  started: boolean;
}) {
  const body = useMemo(
    () => (scene && agents.length > 0 ? classmateRequestBody(scene, agents, language) : null),
    [scene, agents, language],
  );
  const cache = useRef(new Map<string, Record<string, string>>());
  const startedPages = useRef(new Set<string>());
  const stageId = scene?.stageId;
  const memory = useRef<ClassmateMemory>(readClassmateMemory(stageId));
  const memoryStage = useRef<string | undefined>(stageId);
  const [result, setResult] = useState<{ key: string | null; state: ClassmateParticipationState }>({
    key: null,
    state: IDLE,
  });
  const [retryCount, setRetryCount] = useState(0);
  const retry = useCallback(() => {
    if (body) cache.current.delete(body);
    setRetryCount((count) => count + 1);
  }, [body]);
  const [budget, setBudget] = useState(() => ({
    stageId,
    limited: readClassmateUsage(stageId) >= CLASSROOM_TOKEN_BUDGET,
  }));
  // A stage switch reads its own stored spend during render, so no effect has to reset state.
  const budgetLimited =
    budget.stageId === stageId
      ? budget.limited
      : readClassmateUsage(stageId) >= CLASSROOM_TOKEN_BUDGET;
  const recordUsage = useCallback(
    (tokens: number) => {
      const total = addClassmateUsage(stageId, tokens);
      setBudget({ stageId, limited: total >= CLASSROOM_TOKEN_BUDGET });
    },
    [stageId],
  );

  useEffect(() => {
    if (memoryStage.current === stageId) return;
    memoryStage.current = stageId;
    memory.current = readClassmateMemory(stageId);
  }, [stageId]);

  useEffect(() => {
    if (!enabled || !body) return;
    const alreadyStarted = startedPages.current.has(body);
    if (started) startedPages.current.add(body);
    // Spend stops new pages, not the page that just finished and is still on screen.
    if (budgetLimited && !alreadyStarted) return;
    if (!startedPages.current.has(body)) return;
    const cached = cache.current.get(body);
    if (cached) {
      setResult({ key: body, state: { messages: cached, status: 'ready', error: null } });
      return;
    }
    const controller = new AbortController();
    setResult({ key: body, state: { messages: {}, status: 'loading', error: null } });
    void requestClassmateParticipation(body, controller.signal, memory.current).then(
      ({ messages, tokens }) => {
        if (controller.signal.aborted) return;
        recordUsage(tokens);
        cache.current.set(body, messages);
        if (cache.current.size > 32) cache.current.delete(cache.current.keys().next().value!);
        const pageTitle = (scene?.title ?? '').slice(0, MAX_MEMORY_PAGE_CHARS);
        memory.current = {
          pages: [...memory.current.pages, pageTitle]
            .filter((page) => page.length > 0)
            .slice(-MAX_MEMORY_PAGES),
          lines: [
            ...memory.current.lines,
            ...Object.entries(messages).map(([agentId, text]) => ({
              agentId,
              text: text.slice(0, MAX_MEMORY_LINE_CHARS),
            })),
          ].slice(-MAX_MEMORY_LINES),
          // Who spoke on the page just left: the router leans away from them next.
          recentAgentIds: Object.keys(messages).slice(0, 7),
        };
        writeClassmateMemory(stageId, memory.current);
        setResult({ key: body, state: { messages, status: 'ready', error: null } });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({
          key: body,
          state: {
            messages: {},
            status: 'error',
            error: error instanceof Error ? error.message : 'Classmate generation failed',
          },
        });
      },
    );
    return () => controller.abort();
  }, [enabled, body, started, retryCount, scene?.title, stageId, budgetLimited, recordUsage]);

  /**
   * The student named one classmate. The answer is page-scoped and one-shot;
   * it is remembered like any other line so later pages stop repeating it.
   */
  const ask = useCallback(
    async (agentId: string, question: string): Promise<string> => {
      if (!scene) throw new Error('No page to ask on');
      const agent = agents.find(
        (candidate) =>
          candidate.id === agentId && candidate.role !== 'teacher' && candidate.role !== 'user',
      );
      if (!agent) throw new Error('Unknown classmate');
      if (budgetLimited) throw new Error('Class participation budget reached');
      const trimmed = question.trim().slice(0, 600);
      if (!trimmed) throw new Error('Question is empty');
      const payload = JSON.parse(classmateRequestBody(scene, [agent], language)) as Record<
        string,
        unknown
      >;
      const config = getCurrentModelConfig();
      const response = await fetch('/api/chat/classmates/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-model': config.modelString,
          'x-api-key': config.apiKey,
          'x-base-url': config.baseUrl,
          'x-provider-type': config.providerType || '',
        },
        body: JSON.stringify({
          ...payload,
          question: trimmed,
          memory: memory.current,
          thinkingConfig: config.thinkingConfig,
        }),
        signal: AbortSignal.timeout(50_000),
      });
      const data = await response.json();
      if (!response.ok || data.success !== true) {
        throw new Error(data.error || `Classmate answer failed (${response.status})`);
      }
      const message = data.message;
      if (
        !message ||
        message.agentId !== agentId ||
        typeof message.text !== 'string' ||
        !message.text.trim()
      ) {
        throw new Error('Invalid classmate answer');
      }
      recordUsage(Number(data.usage?.tokens) || 0);
      const answer = message.text.trim();
      memory.current = {
        ...memory.current,
        lines: [
          ...memory.current.lines,
          { agentId, text: answer.slice(0, MAX_MEMORY_LINE_CHARS) },
        ].slice(-MAX_MEMORY_LINES),
      };
      writeClassmateMemory(stageId, memory.current);
      return answer;
    },
    [scene, agents, language, budgetLimited, recordUsage, stageId],
  );

  return {
    ...(enabled && result.key === body ? result.state : IDLE),
    retry,
    ask,
    budgetLimited,
  };
}
