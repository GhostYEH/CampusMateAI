import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import {
  buildClassmatePrompt,
  ClassmateRequestError,
  MAX_CLASSMATE_BODY_BYTES,
  parseClassmateMessages,
  readClassmateBody,
  validateClassmateRequest,
} from '@/lib/server/classmate-participation';

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), call: vi.fn(), requiresKey: vi.fn() }));
vi.mock('@/lib/server/resolve-model', () => ({ resolveModelFromRequest: mocks.resolve }));
vi.mock('@/lib/ai/llm', () => ({ callLLM: mocks.call }));
vi.mock('@/lib/ai/providers', () => ({ isProviderKeyRequired: mocks.requiresKey }));

import { POST } from '@/app/api/chat/classmates/route';

const agents = [
  { id: 'curious', name: '小问', role: 'student', persona: 'Curious, asks concrete questions.' },
  {
    id: 'helper',
    name: '小助',
    role: 'assistant',
    persona: 'Practical, connects ideas to examples.',
  },
];

function body() {
  return {
    scene: {
      id: 'page-1',
      title: 'Energy conservation',
      type: 'slide',
      content: {
        type: 'slide',
        canvas: {
          elements: [{ type: 'text', content: '<p>Kinetic energy becomes potential energy.</p>' }],
          src: 'data:image/png;base64,private-media',
        },
      },
      actions: [{ type: 'speech', text: 'Consider a pendulum at its highest point.' }],
    },
    agents,
    language: 'zh-CN',
    thinkingConfig: { mode: 'enabled', effort: 'high' },
  };
}

function req(value: unknown = body(), signal?: AbortSignal) {
  return new NextRequest('http://localhost/api/chat/classmates', {
    method: 'POST',
    body: JSON.stringify(value),
    headers: {
      'Content-Type': 'application/json',
      'x-model': 'provider/custom-model',
      'x-api-key': 'test-key',
      'x-base-url': 'https://example.com/v1',
      'x-provider-type': 'openai-compatible',
    },
    signal,
  });
}

const messages = [
  { agentId: 'curious', text: 'Where is the kinetic energy largest in this pendulum?' },
  { agentId: 'helper', text: 'I will compare the highest and lowest points to track the energy.' },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
  mocks.resolve.mockResolvedValue({
    model: 'resolved-model',
    providerId: 'custom',
    apiKey: 'resolved-key',
    thinkingConfig: { mode: 'enabled', effort: 'high' },
  });
  mocks.requiresKey.mockReturnValue(true);
  mocks.call.mockResolvedValue({ text: JSON.stringify({ messages }) });
});

describe('classmate page context and roster', () => {
  it('preserves custom classroom roles and their personas', () => {
    const request = validateClassmateRequest({
      ...body(),
      agents: [{ ...agents[0], role: 'skeptic' }, agents[1]],
    });
    expect(request.agents[0].role).toBe('skeptic');
    expect(buildClassmatePrompt(request).prompt).toContain('skeptic');
    expect(parseClassmateMessages(JSON.stringify({ messages }), request.agents)).toEqual(messages);
  });
  it('includes actual slide text, narration, each persona and language, excluding media', () => {
    const prompt = buildClassmatePrompt(validateClassmateRequest(body()));
    expect(prompt.prompt).toContain('Kinetic energy becomes potential energy');
    expect(prompt.prompt).toContain('pendulum at its highest point');
    expect(prompt.prompt).toContain(agents[0].persona);
    expect(prompt.prompt).toContain(agents[1].persona);
    expect(prompt.prompt).toContain('zh-CN');
    expect(prompt.prompt).not.toContain('private-media');
    expect(prompt.system).toContain('EVERY');
    expect(prompt.system).toContain('one or two');
  });

  it('keeps interactive visible text and PBL goals while omitting scripts/styles', () => {
    for (const type of ['interactive', 'pbl']) {
      const value = body();
      const request = validateClassmateRequest({
        ...value,
        scene: {
          ...value.scene,
          type,
          content: {
            type,
            html: '<style>private-style</style><script>private-code()</script><h1>Measure friction</h1>',
            projectV2: { objectives: ['Compare material surfaces'] },
          },
        },
      });
      const { prompt } = buildClassmatePrompt(request);
      expect(prompt).toContain('Measure friction');
      expect(prompt).toContain('Compare material surfaces');
      expect(prompt).not.toContain('private-code');
      expect(prompt).not.toContain('private-style');
    }
  });

  it('whitelists quiz questions and excludes answers, analysis, grading guidance and all speech', () => {
    const value = body();
    const request = validateClassmateRequest({
      ...value,
      scene: {
        ...value.scene,
        type: 'quiz',
        content: {
          type: 'quiz',
          analysis: 'TOP_LEVEL_SECRET',
          questions: [
            {
              question: 'Which point has greatest potential energy?',
              type: 'single',
              options: [{ label: 'Highest point', value: 'A', answer: 'OPTION_SECRET' }],
              answer: ['ANSWER_SECRET'],
              analysis: 'ANALYSIS_SECRET',
              commentPrompt: 'GRADE_SECRET',
            },
          ],
        },
        actions: [{ type: 'speech', text: 'SPEECH_SECRET: the answer is A' }],
      },
    });
    const prompt = buildClassmatePrompt(request);
    expect(prompt.prompt).toContain('Which point');
    expect(prompt.prompt).toContain('Highest point');
    expect(prompt.prompt).not.toContain('SECRET');
    expect(prompt.system).toContain('Never solve a question');
    expect(prompt.system).toContain('encouragement or general problem-solving methods ONLY');
  });

  it('filters teacher/user and accepts exactly seven assistant/student peers', () => {
    const peers = Array.from({ length: 7 }, (_, i) => ({ ...agents[0], id: `s-${i}` }));
    expect(
      validateClassmateRequest({
        ...body(),
        agents: [...peers, { id: 't', role: 'teacher' }, { id: 'u', role: 'user' }],
      }).agents,
    ).toEqual(peers);
    expect(() =>
      validateClassmateRequest({
        ...body(),
        agents: [...peers, { ...agents[0], id: 's-7' }],
      }),
    ).toThrow('seven');
  });

  it.each([
    { agents: [agents[0], agents[0]] },
    { agents: [{ ...agents[0], role: '' }] },
    { agents: [{ ...agents[0], persona: '' }] },
    { agents: [{ ...agents[0], id: 'x'.repeat(129) }] },
    { agents: [{ ...agents[0], name: 'x'.repeat(121) }] },
    { agents: [{ ...agents[0], persona: 'x'.repeat(12_001) }] },
    { language: 'x'.repeat(201) },
    { scene: { ...body().scene, type: 'quiz' } },
    { scene: { ...body().scene, actions: 'invalid' } },
  ])('rejects invalid input before inference: %j', (patch) => {
    expect(() => validateClassmateRequest({ ...body(), ...patch })).toThrow(ClassmateRequestError);
  });

  it('bounds per-page context even when many text fields are supplied', () => {
    const value = body();
    const request = validateClassmateRequest({
      ...value,
      scene: {
        ...value.scene,
        content: { type: 'slide', paragraphs: Array(12).fill('x'.repeat(12_000)) },
      },
    });
    expect(JSON.parse(buildClassmatePrompt(request).prompt).page.content.length).toBe(24_000);
  });
});

describe('strict classmate output', () => {
  it('returns every classmate in selected order and trims text', () => {
    const text =
      '```json\n' +
      JSON.stringify({ messages: [messages[1], { ...messages[0], text: ' Hi. ' }] }) +
      '\n```';
    expect(parseClassmateMessages(text, agents)).toEqual([
      { agentId: 'curious', text: 'Hi.' },
      messages[1],
    ]);
  });

  it.each([
    'not JSON',
    JSON.stringify({ messages: [messages[0]] }),
    JSON.stringify({ messages: [messages[0], messages[0]] }),
    JSON.stringify({ messages: [messages[0], { agentId: 'unknown', text: 'Hi' }] }),
    JSON.stringify({ messages: [messages[0], { agentId: 'teacher', text: 'Hi' }] }),
    JSON.stringify({ messages: [messages[0], { agentId: 'helper', text: ' ' }] }),
    JSON.stringify({ messages: [messages[0], { agentId: 'helper', text: 123 }] }),
    JSON.stringify({ messages: [messages[0], { agentId: 'helper', text: 'x'.repeat(1201) }] }),
    'prefix ' + JSON.stringify({ messages }),
    'x'.repeat(20_001),
  ])('rejects malformed or incomplete replies without invented fallback: %s', (text) => {
    expect(() => parseClassmateMessages(text, agents)).toThrow();
  });
});

describe('classmate endpoint', () => {
  it('reuses standard header/body model resolution and returns one real batch', async () => {
    const request = req();
    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true, messages });
    expect(mocks.resolve).toHaveBeenCalledWith(request, body(), 'chat-adapter');
    expect(mocks.call).toHaveBeenCalledTimes(1);
    expect(mocks.call).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'resolved-model',
        abortSignal: expect.any(AbortSignal),
        maxRetries: 0,
      }),
      'chat-adapter',
      undefined,
      { mode: 'enabled', effort: 'high' },
    );
  });

  it('passes the resolved stage thinking config instead of overwriting it', async () => {
    mocks.resolve.mockResolvedValue({
      model: 'routed-model',
      providerId: 'custom',
      apiKey: 'key',
      thinkingConfig: { mode: 'disabled' },
    });
    await POST(req());
    expect(mocks.call.mock.calls[0][3]).toEqual({ mode: 'disabled' });
  });

  it('avoids inference when there are no peers', async () => {
    const response = await POST(req({ ...body(), agents: [{ id: 'teacher', role: 'teacher' }] }));
    expect(await response.json()).toEqual({ success: true, messages: [] });
    expect(mocks.resolve).not.toHaveBeenCalled();
    expect(mocks.call).not.toHaveBeenCalled();
  });

  it('rejects missing required provider key while allowing keyless local providers', async () => {
    mocks.resolve.mockResolvedValue({ model: 'local-model', providerId: 'local', apiKey: '' });
    expect((await POST(req())).status).toBe(401);
    expect(mocks.call).not.toHaveBeenCalled();
    mocks.requiresKey.mockReturnValue(false);
    expect((await POST(req())).status).toBe(200);
  });

  it('returns validation failures before resolving a model', async () => {
    const response = await POST(req({ ...body(), agents: [{ ...agents[0], persona: '' }] }));
    expect(response.status).toBe(400);
    expect(mocks.resolve).not.toHaveBeenCalled();
  });

  it('enforces body byte limits with and without content-length', async () => {
    const declared = req();
    declared.headers.set('content-length', String(MAX_CLASSMATE_BODY_BYTES + 1));
    expect((await POST(declared)).status).toBe(413);
    const actual = req({ value: '中'.repeat(MAX_CLASSMATE_BODY_BYTES / 2) });
    expect((await POST(actual)).status).toBe(413);
    expect(mocks.resolve).not.toHaveBeenCalled();
  });

  it('returns 400 for malformed JSON', async () => {
    const request = new NextRequest('http://localhost/api/chat/classmates', {
      method: 'POST',
      body: '{',
    });
    expect((await POST(request)).status).toBe(400);
    expect(mocks.call).not.toHaveBeenCalled();
  });

  it('returns real upstream/config/parse failures, never fabricated messages', async () => {
    mocks.resolve.mockRejectedValueOnce(new Error('No model could be resolved'));
    let response = await POST(req());
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({
      success: false,
      error: 'No model could be resolved',
    });
    mocks.call.mockRejectedValueOnce(new Error('Provider unavailable'));
    response = await POST(req());
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ success: false, error: 'Provider unavailable' });
    mocks.call.mockResolvedValueOnce({ text: JSON.stringify({ messages: [messages[0]] }) });
    response = await POST(req());
    expect(response.status).toBe(502);
    expect(await response.json()).not.toHaveProperty('messages');
  });

  it('propagates client cancellation to inference', async () => {
    const controller = new AbortController();
    mocks.call.mockImplementationOnce(async ({ abortSignal }) => {
      controller.abort();
      expect(abortSignal.aborted).toBe(true);
      abortSignal.throwIfAborted();
    });
    expect((await POST(req(body(), controller.signal))).status).toBe(499);
  });

  it('enforces the server timeout and reports it as a failure', async () => {
    const controller = new AbortController();
    const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(controller.signal);
    mocks.call.mockImplementationOnce(async ({ abortSignal }) => {
      controller.abort(new DOMException('Timed out', 'TimeoutError'));
      abortSignal.throwIfAborted();
    });
    const response = await POST(req());
    expect(timeout).toHaveBeenCalledWith(55_000);
    expect(response.status).toBe(504);
    expect(await response.json()).toMatchObject({
      success: false,
      error: 'Classmate generation timed out',
    });
  });

  it('does not read an already cancelled request', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(readClassmateBody(req(body(), controller.signal))).rejects.toThrow();
  });

  it('cancels a pending body read when the request timeout expires', async () => {
    const controller = new AbortController();
    const cancelled = vi.fn();
    const request = {
      headers: new Headers(),
      body: new ReadableStream({ cancel: cancelled }),
      signal: new AbortController().signal,
    } as Request;
    const read = readClassmateBody(request, controller.signal);
    controller.abort(new DOMException('Timed out', 'TimeoutError'));
    await expect(read).rejects.toThrow('Timed out');
    expect(cancelled).toHaveBeenCalledOnce();
  });
});
