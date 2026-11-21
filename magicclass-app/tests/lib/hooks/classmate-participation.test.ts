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
  CLASSROOM_TOKEN_BUDGET,
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
      routed: { selected: ['curious', 'practical'], needs: 0.8, by: 'router' },
    }),
    { status: 200 },
  );
const quiet = () => new Response(JSON.stringify({ success: true, messages: [] }), { status: 200 });

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
    localStorage.clear();
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

  it('accepts a page where only one classmate speaks', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ success: true, messages: [{ agentId: 'curious', text: 'Why halves?' }] }),
        { status: 200 },
      ),
    );
    props = { ...props, started: true };
    await render();
    expect(output).toMatchObject({ status: 'ready', messages: { curious: 'Why halves?' } });
    expect(output.messages.practical).toBeUndefined();
  });

  it('accepts a page that needs nobody', async () => {
    fetchMock.mockResolvedValue(quiet());
    props = { ...props, started: true };
    await render();
    expect(output).toMatchObject({ status: 'ready', messages: {} });
  });

  it.each([
    { problem: 'unknown speaker', messages: [{ agentId: 'unknown', text: 'Wrong person' }] },
    {
      problem: 'duplicate speaker',
      messages: [
        { agentId: 'curious', text: 'Same' },
        { agentId: 'curious', text: 'Duplicate' },
      ],
    },
    { problem: 'blank message', messages: [{ agentId: 'curious', text: ' ' }] },
  ])('rejects $problem without inventing dialogue', async ({ messages }) => {
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

  it('carries what the class already said into the next page in this browser', async () => {
    fetchMock.mockResolvedValueOnce(successful());
    fetchMock.mockResolvedValueOnce(successful('Second page question', 'Second page example'));
    props = { ...props, started: true };
    await render();
    props = { ...props, scene: { ...scene, id: 'page-b', title: 'Decimals' } as Scene };
    await render();
    const sent = JSON.parse(String(fetchMock.mock.calls[1][1]?.body)) as {
      memory?: { pages: string[]; lines: { agentId: string }[]; recentAgentIds: string[] };
    };
    expect(sent.memory?.pages).toEqual(['Fractions']);
    expect(sent.memory?.lines.map((line) => line.agentId)).toEqual(['curious', 'practical']);
    expect(sent.memory?.recentAgentIds).toEqual(['curious', 'practical']);
    const stored = JSON.parse(String(localStorage.getItem('maic:classmate-memory:course-a')));
    expect(stored.lines).toHaveLength(4);
    expect(stored.pages).toEqual(['Fractions', 'Decimals']);
  });

  it('restores continuity memory when the classroom is reopened', async () => {
    localStorage.setItem(
      'maic:classmate-memory:course-a',
      JSON.stringify({
        pages: ['Fractions'],
        lines: [{ agentId: 'curious', text: 'Why halves?' }],
        recentAgentIds: ['curious'],
      }),
    );
    fetchMock.mockResolvedValue(quiet());
    props = { ...props, started: true };
    await render();
    const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as {
      memory?: { pages: string[] };
    };
    expect(sent.memory?.pages).toEqual(['Fractions']);
  });

  it('asks one classmate directly, remembers the answer and counts its tokens', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          success: true,
          message: { agentId: 'curious', text: 'Because the cake splits into halves.' },
          usage: { tokens: 700 },
        }),
        { status: 200 },
      ),
    );
    await render();
    let answer = '';
    await act(async () => {
      answer = await output.ask('curious', '  Why halves?  ');
    });
    expect(answer).toBe('Because the cake splits into halves.');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/chat/classmates/ask');
    const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as {
      question: string;
      agents: AgentConfig[];
    };
    expect(sent.question).toBe('Why halves?');
    expect(sent.agents.map((agent) => agent.id)).toEqual(['curious']);
    expect(localStorage.getItem('maic:classmate-usage:course-a')).toBe('700');
    const memory = JSON.parse(String(localStorage.getItem('maic:classmate-memory:course-a'))) as {
      lines: { agentId: string; text: string }[];
    };
    expect(memory.lines).toEqual([
      { agentId: 'curious', text: 'Because the cake splits into halves.' },
    ]);
  });

  it('refuses to ask a teacher or an unknown person, and surfaces a failed answer', async () => {
    await render();
    await expect(output.ask('teacher', 'Why?')).rejects.toThrow(/Unknown classmate/);
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ success: false, error: 'provider down' }), { status: 502 }),
    );
    await expect(output.ask('curious', 'Why?')).rejects.toThrow(/provider down/);
  });

  it('stops automatic reactions once the course budget is spent', async () => {
    localStorage.setItem('maic:classmate-usage:course-a', String(CLASSROOM_TOKEN_BUDGET));
    fetchMock.mockResolvedValue(successful());
    props = { ...props, started: true };
    await render();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(output.budgetLimited).toBe(true);
    expect(output.status).toBe('idle');
    await expect(output.ask('curious', 'Why?')).rejects.toThrow(/budget/);

    props = { ...props, scene: { ...scene, id: 'page-b', title: 'Decimals' } as Scene };
    await render();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('crosses the budget in the middle of a lesson and stops the next page', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          success: true,
          messages: [{ agentId: 'curious', text: 'Why halves?' }],
          usage: { tokens: CLASSROOM_TOKEN_BUDGET },
        }),
        { status: 200 },
      ),
    );
    props = { ...props, started: true };
    await render();
    expect(output.status).toBe('ready');
    expect(output.budgetLimited).toBe(true);
    props = { ...props, scene: { ...scene, id: 'page-b', title: 'Decimals' } as Scene };
    await render();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
