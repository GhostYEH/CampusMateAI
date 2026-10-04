// @vitest-environment jsdom
import { createElement, act, useEffect } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentConfig } from '@/lib/orchestration/registry/types';
import type { Scene } from '@/lib/types/stage';

vi.mock('@/lib/utils/model-config', () => ({
  getCurrentModelConfig: () => ({
    modelString: 'mock:test',
    apiKey: '',
    baseUrl: '',
    providerType: 'openai',
  }),
}));

import {
  classmateRequestBody,
  requestClassmateParticipation,
  useClassmateParticipation,
} from '@/lib/hooks/use-classmate-participation';

const agents = [
  { id: 'curious', name: 'Curious', role: 'student', persona: 'Ask why' },
  { id: 'practical', name: 'Practical', role: 'student', persona: 'Try examples' },
] as AgentConfig[];
const scene = {
  id: 'page-a',
  stageId: 'course-a',
  title: 'Fractions',
  type: 'slide',
  content: {
    type: 'slide',
    canvas: {
      elements: [
        { type: 'text', content: '<p>1/2</p>' },
        { type: 'image', src: 'data:image/png;base64,MEDIA' },
      ],
    },
  },
  actions: [{ type: 'speech', text: 'One half is a fraction.', audioUrl: 'private-audio' }],
} as unknown as Scene;
const successful = (a = 'Why halves?', b = 'Try dividing a cake.') =>
  new Response(
    JSON.stringify({
      success: true,
      messages: [
        { agentId: 'curious', text: a },
        { agentId: 'practical', text: b },
      ],
    }),
    { status: 200 },
  );

describe('classmate participation', () => {
  let root: Root;
  let container: HTMLDivElement;
  let output: ReturnType<typeof useClassmateParticipation>;
  let props: Parameters<typeof useClassmateParticipation>[0];
  const fetchMock = vi.fn<typeof fetch>();
  function Probe() {
    const state = useClassmateParticipation(props);
    useEffect(() => {
      output = state;
    });
    return createElement('div', null, JSON.stringify(state));
  }
  async function render() {
    await act(async () => {
      root.render(createElement(Probe));
    });
  }

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
    props = { scene, agents, language: 'en-US', enabled: true, started: false };
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  it('keeps actual lesson and personas while removing media and teacher agents', () => {
    const body = classmateRequestBody(
      scene,
      [...agents, { id: 'teacher', role: 'teacher' } as AgentConfig],
      'en-US',
    );
    expect(body).toContain('One half is a fraction.');
    expect(body).toContain('Ask why');
    expect(body).toContain('<p>1/2</p>');
    expect(body).not.toContain('MEDIA');
    expect(body).not.toContain('private-audio');
    expect(JSON.parse(body).agents.map((a: AgentConfig) => a.id)).toEqual(['curious', 'practical']);
  });

  it('starts with playback and caches completed reactions across pause/resume', async () => {
    fetchMock.mockResolvedValue(successful());
    await render();
    expect(fetchMock).not.toHaveBeenCalled();
    props = { ...props, started: true };
    await render();
    expect(output.status).toBe('ready');
    expect(output.messages.practical).toBe('Try dividing a cake.');
    props = { ...props, started: false };
    await render();
    props = { ...props, started: true };
    await render();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('keeps a large multibyte page within the server byte limit for all seven classmates', async () => {
    const roster = Array.from({ length: 7 }, (_, i) => ({
      ...agents[0],
      id: `peer-${i}`,
      persona: '中文人设'.repeat(3000),
    }));
    const largeScene = {
      ...scene,
      content: {
        type: 'slide',
        elements: Array.from({ length: 3000 }, () => ({ content: '中文课文'.repeat(3000) })),
      },
      actions: Array.from({ length: 300 }, () => ({
        type: 'speech',
        text: '中文讲解'.repeat(3000),
      })),
    } as unknown as Scene;
    const body = classmateRequestBody(largeScene, roster);
    const request = JSON.parse(body);
    expect(request.agents).toHaveLength(7);
    expect(request.scene.content.type).toBe('slide');
    expect(body).toContain('中文课文');
    const { MAX_CLASSMATE_BODY_BYTES, validateClassmateRequest } =
      await import('@/lib/server/classmate-participation');
    expect(new TextEncoder().encode(body).byteLength).toBeLessThan(MAX_CLASSMATE_BODY_BYTES);
    expect(validateClassmateRequest(request).agents).toHaveLength(7);
  });

  it('aborts a previous page and discards its late result after switching pages', async () => {
    let finishOld!: (response: Response) => void;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        }),
    );
    fetchMock.mockResolvedValueOnce(successful('Current page question', 'Current example'));
    props = { ...props, started: true };
    await render();
    const oldSignal = fetchMock.mock.calls[0][1]?.signal;
    props = { ...props, scene: { ...scene, id: 'page-b', title: 'Decimals' } as Scene };
    await render();
    expect(oldSignal?.aborted).toBe(true);
    expect(output.messages.curious).toBe('Current page question');
    await act(async () => {
      finishOld(successful('STALE', 'STALE'));
    });
    expect(output.messages.curious).toBe('Current page question');
  });

  it('shows a real failure and retries without invented dialogue', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: false, error: 'Provider unavailable' }), {
        status: 503,
      }),
    );
    fetchMock.mockResolvedValueOnce(successful());
    props = { ...props, started: true };
    await render();
    expect(output).toMatchObject({ status: 'error', error: 'Provider unavailable', messages: {} });
    await act(async () => output.retry());
    expect(output.status).toBe('ready');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('clears reactions when the roster changes or participation is disabled', async () => {
    fetchMock.mockResolvedValue(successful());
    props = { ...props, started: true };
    await render();
    props = { ...props, agents: [], started: false };
    await render();
    expect(output).toMatchObject({ status: 'idle', messages: {} });
    props = { ...props, agents, enabled: false };
    await render();
    expect(output).toMatchObject({ status: 'idle', messages: {} });
  });

  it.each(
    [
      [{ agentId: 'unknown', text: 'Wrong person' }],
      [
        { agentId: 'curious', text: 'Same' },
        { agentId: 'curious', text: 'Duplicate' },
      ],
      [{ agentId: 'curious', text: 'Only one' }],
      [
        { agentId: 'curious', text: ' ' },
        { agentId: 'practical', text: 'Example' },
      ],
    ].map((messages) => ({ messages })),
  )('rejects incomplete or misattributed output: %j', async ({ messages }) => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ success: true, messages }), { status: 200 }),
    );
    await expect(
      requestClassmateParticipation(
        classmateRequestBody(scene, agents),
        new AbortController().signal,
      ),
    ).rejects.toThrow(/classmate response/);
  });
});
