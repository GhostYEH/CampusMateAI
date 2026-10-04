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

const IDLE: ClassmateParticipationState = { messages: {}, status: 'idle', error: null };
const MEDIA_FIELDS = new Set(['src', 'url', 'audio', 'audioUrl', 'audioData', 'imageBase64']);

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
        stageId: scene.stageId,
        title: scene.title,
        type: scene.type,
        content: scene.content,
        actions: (scene.actions || [])
          .filter((action) => action.type === 'speech')
          .map((action) => ({ type: action.type, text: action.text })),
      },
      agents: agents
        .filter((agent) => agent.role !== 'teacher' && agent.role !== 'user')
        .map(({ id, name, role, persona }) => ({ id, name, role, persona })),
      language,
    },
    (key, value: unknown) => {
      if (MEDIA_FIELDS.has(key)) return undefined;
      return typeof value === 'string' ? value.slice(0, 12_000) : value;
    },
  );
}

export async function requestClassmateParticipation(
  body: string,
  signal: AbortSignal,
): Promise<Record<string, string>> {
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
    body: JSON.stringify({ ...payload, thinkingConfig: config.thinkingConfig }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(65_000)]),
  });
  const data = await response.json();
  if (!response.ok || data.success !== true) {
    throw new Error(data.error || `Classmate generation failed (${response.status})`);
  }
  if (!Array.isArray(data.messages)) throw new Error('Invalid classmate response');
  const expectedIds = new Set(payload.agents.map((agent) => agent.id));
  const messages: Record<string, string> = Object.create(null);
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
  if (Object.keys(messages).length !== expectedIds.size) {
    throw new Error('Incomplete classmate response');
  }
  return messages;
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
  const [result, setResult] = useState<{ key: string | null; state: ClassmateParticipationState }>({
    key: null,
    state: IDLE,
  });
  const [retryCount, setRetryCount] = useState(0);
  const retry = useCallback(() => {
    if (body) cache.current.delete(body);
    setRetryCount((count) => count + 1);
  }, [body]);

  useEffect(() => {
    if (!enabled || !body) return;
    if (started) startedPages.current.add(body);
    if (!startedPages.current.has(body)) return;
    const cached = cache.current.get(body);
    if (cached) {
      setResult({ key: body, state: { messages: cached, status: 'ready', error: null } });
      return;
    }
    const controller = new AbortController();
    setResult({ key: body, state: { messages: {}, status: 'loading', error: null } });
    void requestClassmateParticipation(body, controller.signal).then(
      (messages) => {
        if (controller.signal.aborted) return;
        cache.current.set(body, messages);
        if (cache.current.size > 32) cache.current.delete(cache.current.keys().next().value!);
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
  }, [enabled, body, started, retryCount]);

  return { ...(enabled && result.key === body ? result.state : IDLE), retry };
}
