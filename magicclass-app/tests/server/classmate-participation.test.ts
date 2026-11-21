import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import {
  buildClassmateAnswerPrompt,
  buildClassmatePrompt,
  buildClassmateRoutingPrompt,
  classmateTokens,
  parseClassmateAnswer,
  validateClassmateQuestion,
  CLASSMATE_ROUTING,
  ClassmateRequestError,
  fallbackClassmates,
  MAX_CLASSMATE_BODY_BYTES,
  parseClassmateMessages,
  parseClassmateRouting,
  readClassmateBody,
  selectClassmates,
  validateClassmateRequest,
} from '@/lib/server/classmate-participation';

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), call: vi.fn(), requiresKey: vi.fn() }));
vi.mock('@/lib/server/resolve-model', () => ({ resolveModelFromRequest: mocks.resolve }));
vi.mock('@/lib/ai/llm', () => ({ callLLM: mocks.call }));
vi.mock('@/lib/ai/providers', () => ({ isProviderKeyRequired: mocks.requiresKey }));

import { POST } from '@/app/api/chat/classmates/route';
import { POST as ASK_POST } from '@/app/api/chat/classmates/ask/route';

const agents = [
  { id: 'curious', name: '小问', role: 'student', persona: 'Curious, asks concrete questions.' },
  {
    id: 'helper',
    name: '小助',
    role: 'assistant',
    persona: 'Practical, connects ideas to examples.',
  },
];

function body(patch: Record<string, unknown> = {}) {
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
    ...patch,
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

const routingReply = (scores: { agentId: string; score: number }[], needs = 0.9) => ({
  text: JSON.stringify({ needs, scores, reason: 'page fit' }),
});
const speakingReply = (value: unknown[] = messages) => ({
  text: JSON.stringify({ messages: value }),
});

/** Every page request now asks twice: who speaks, then what they say. */
function answerAs(routing: ReturnType<typeof routingReply>, speaking = speakingReply()) {
  mocks.call.mockResolvedValueOnce(routing).mockResolvedValueOnce(speaking);
}

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
});

describe('classmate page context and roster', () => {
  it('preserves custom classroom roles and their personas', () => {
    const request = validateClassmateRequest({
      ...body(),
      agents: [{ ...agents[0], role: 'skeptic' }, agents[1]],
    });
    expect(request.agents[0].role).toBe('skeptic');
    expect(buildClassmatePrompt(request).prompt).toContain('skeptic');
    expect(buildClassmateRoutingPrompt(request).prompt).toContain('skeptic');
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
    expect(prompt.system).toContain('listed below');
    expect(prompt.system).toContain('one or two');
    expect(prompt.system).toContain('Staying quiet is normal');
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
      for (const prompt of [buildClassmatePrompt(request), buildClassmateRoutingPrompt(request)]) {
        expect(prompt.prompt).toContain('Measure friction');
        expect(prompt.prompt).toContain('Compare material surfaces');
        expect(prompt.prompt).not.toContain('private-code');
        expect(prompt.prompt).not.toContain('private-style');
      }
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
    const routing = buildClassmateRoutingPrompt(request);
    expect(prompt.prompt).toContain('Which point');
    expect(prompt.prompt).toContain('Highest point');
    expect(prompt.prompt).not.toContain('SECRET');
    expect(routing.prompt).not.toContain('SECRET');
    expect(prompt.system).toContain('Never solve a question');
    expect(prompt.system).toContain('encouragement or general problem-solving methods ONLY');
    expect(routing.system).toContain('Nobody may solve it');
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

describe('classmate memory', () => {
  it('carries bounded memory into both prompts and drops unknown classmates', () => {
    const request = validateClassmateRequest({
      ...body(),
      memory: {
        pages: ['Page 0'],
        lines: [
          { agentId: 'curious', text: 'Half of the cake is gone.' },
          { agentId: 'stranger', text: 'Not in this roster.' },
        ],
        recentAgentIds: ['curious', 'stranger'],
      },
    });
    expect(request.memory.lines).toEqual([
      { agentId: 'curious', text: 'Half of the cake is gone.' },
    ]);
    expect(request.memory.recentAgentIds).toEqual(['curious']);
    const prompt = buildClassmatePrompt(request);
    expect(prompt.prompt).toContain('Half of the cake is gone.');
    expect(prompt.prompt).not.toContain('Not in this roster.');
    expect(JSON.parse(buildClassmateRoutingPrompt(request).prompt).spokeLastPage).toEqual([
      'curious',
    ]);
  });

  it.each([
    { memory: 'invalid' },
    { memory: { pages: Array(9).fill('page') } },
    { memory: { pages: ['x'.repeat(201)] } },
    { memory: { lines: Array(13).fill({ agentId: 'curious', text: 'hi' }) } },
    { memory: { lines: [{ agentId: 'curious', text: ' ' }] } },
    { memory: { recentAgentIds: ['x'.repeat(129)] } },
  ])('rejects unbounded memory: %j', (patch) => {
    expect(() => validateClassmateRequest({ ...body(), ...patch })).toThrow(ClassmateRequestError);
  });
});

describe('classmate routing', () => {
  it('reads tolerant JSON and clamps unknown, malformed and duplicate scores', () => {
    const parsed = parseClassmateRouting(
      '```json\n' +
        JSON.stringify({
          needs: 1.4,
          scores: [
            { agentId: 'curious', score: 0.4 },
            { agentId: 'curious', score: 0.9 },
            { agentId: 'stranger', score: 1 },
            { agentId: 'helper', score: 'high' },
          ],
        }) +
        '\n```',
      agents,
    );
    expect(parsed).toEqual({
      needs: 1,
      scores: [{ agentId: 'curious', score: 0.9 }],
      reason: null,
    });
  });

  it.each(['not JSON', '[]', JSON.stringify({ scores: 'x' }), JSON.stringify({ needs: 1 })])(
    'returns null when the routing output is unusable: %s',
    (text) => {
      expect(parseClassmateRouting(text, agents)).toBeNull();
    },
  );

  it('selects at most two speakers and honours the need gate', () => {
    const request = validateClassmateRequest({
      ...body(),
      agents: [...agents, { id: 'note', name: '小记', role: 'student', persona: 'Takes notes.' }],
    });
    const all = [
      { agentId: 'curious', score: 0.95 },
      { agentId: 'helper', score: 0.8 },
      { agentId: 'note', score: 0.7 },
    ];
    expect(selectClassmates(request, { needs: 0.9, scores: all })).toEqual(['curious', 'helper']);
    // Nobody needs to speak, and no single classmate is a clear pick.
    expect(
      selectClassmates(request, {
        needs: 0.2,
        scores: [
          { agentId: 'curious', score: 0.7 },
          { agentId: 'helper', score: 0.65 },
        ],
      }),
    ).toEqual([]);
    // A clear pick answers even when the page says it needs nobody in general.
    expect(
      selectClassmates(request, {
        needs: 0.2,
        scores: [{ agentId: 'curious', score: CLASSMATE_ROUTING.clearPick }],
      }),
    ).toEqual(['curious']);
  });

  it('penalizes a classmate who spoke on the page just left', () => {
    const request = validateClassmateRequest({
      ...body(),
      memory: { pages: ['Page 0'], lines: [], recentAgentIds: ['curious'] },
    });
    const scores = [
      { agentId: 'curious', score: 0.8 },
      { agentId: 'helper', score: 0.65 },
    ];
    expect(selectClassmates(request, { needs: 0.9, scores })).toEqual(['helper']);
    // A clearly better reason still wins over the penalty.
    expect(
      selectClassmates(request, {
        needs: 0.9,
        scores: [
          { agentId: 'curious', score: 1 },
          { agentId: 'helper', score: 0.5 },
        ],
      }),
    ).toEqual(['curious']);
  });

  it('rotates the fallback voice by page and avoids the previous speaker', () => {
    const two = validateClassmateRequest(body());
    expect(fallbackClassmates(two)).toEqual(['curious']);
    const second = validateClassmateRequest({
      ...body(),
      memory: { pages: ['Page 0'], lines: [], recentAgentIds: ['curious'] },
    });
    expect(fallbackClassmates(second)).toEqual(['helper']);
  });
});

describe('tolerant classmate output', () => {
  it('returns every spoken classmate in roster order and trims text', () => {
    const text =
      '```json\n' +
      JSON.stringify({ messages: [messages[1], { ...messages[0], text: ' Hi. ' }] }) +
      '\n```';
    expect(parseClassmateMessages(text, agents)).toEqual([
      { agentId: 'curious', text: 'Hi.' },
      messages[1],
    ]);
  });

  it('accepts a page where only one classmate speaks', () => {
    expect(parseClassmateMessages(JSON.stringify({ messages: [messages[0]] }), agents)).toEqual([
      messages[0],
    ]);
  });

  it.each([
    ['an empty text', [{ agentId: 'curious', text: ' ' }]],
    ['the silence sentinel', [{ agentId: 'curious', text: 'NO_REPLY' }]],
    ['a pass sentinel', [{ agentId: 'curious', text: '**pass**' }]],
    ['an unknown classmate', [{ agentId: 'teacher', text: 'Hi' }]],
    ['a non-textual reply', [{ agentId: 'curious', text: 123 }]],
    ['an oversized reply', [{ agentId: 'curious', text: 'x'.repeat(1201) }]],
  ])('drops %s without failing the page', (_label, value) => {
    expect(parseClassmateMessages(JSON.stringify({ messages: value }), agents)).toEqual([]);
  });

  it('keeps the first line when a classmate is repeated', () => {
    expect(
      parseClassmateMessages(JSON.stringify({ messages: [messages[0], messages[0]] }), agents),
    ).toEqual([messages[0]]);
  });

  it.each([
    'not JSON',
    'prefix ' + JSON.stringify({ messages }),
    'x'.repeat(20_001),
    JSON.stringify({ messages: 'nope' }),
    JSON.stringify({ nope: [] }),
  ])('still rejects an unusable envelope: %s', (text) => {
    expect(() => parseClassmateMessages(text, agents)).toThrow();
  });
});

describe('classmate endpoint', () => {
  it('routes first, then speaks only for the selected classmates', async () => {
    const request = req();
    answerAs(
      routingReply([
        { agentId: 'curious', score: 0.92 },
        { agentId: 'helper', score: 0.55 },
      ]),
    );
    const response = await POST(request);
    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload).toMatchObject({
      success: true,
      messages: [messages[0]],
      routed: { selected: ['curious'], needs: 0.9, by: 'router' },
    });
    expect(mocks.resolve).toHaveBeenCalledWith(request, body(), 'chat-adapter');
    expect(mocks.call).toHaveBeenCalledTimes(2);
    expect(mocks.call.mock.calls[0][0]).toMatchObject({
      model: 'resolved-model',
      maxOutputTokens: 600,
      maxRetries: 0,
    });
    expect(mocks.call.mock.calls[0][0].system).toContain('You decide which AI classmates');
    expect(mocks.call.mock.calls[1][0].system).toContain('Continue the classroom');
    // The speaking step only sees the classmate it was asked about.
    expect(mocks.call.mock.calls[1][0].prompt).toContain('curious');
    expect(mocks.call.mock.calls[1][0].prompt).not.toContain('helper');
    expect(mocks.call.mock.calls[1][3]).toEqual({ mode: 'enabled', effort: 'high' });
  });

  it('says nothing, and calls no model twice, when the page needs nobody', async () => {
    answerAs(
      routingReply(
        [
          { agentId: 'curious', score: 0.3 },
          { agentId: 'helper', score: 0.2 },
        ],
        0.1,
      ),
    );
    const response = await POST(req());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      success: true,
      messages: [],
      routed: { selected: [], needs: 0.1, by: 'silence' },
    });
    expect(mocks.call).toHaveBeenCalledTimes(1);
  });

  it('keeps the page when the speaking step returns a silent classmate', async () => {
    answerAs(
      routingReply([
        { agentId: 'curious', score: 0.9 },
        { agentId: 'helper', score: 0.9 },
      ]),
      speakingReply([messages[0], { agentId: 'helper', text: '' }]),
    );
    const response = await POST(req());
    expect(await response.json()).toMatchObject({ success: true, messages: [messages[0]] });
  });

  it('falls back to the rotation when routing fails, without inventing words', async () => {
    mocks.call.mockRejectedValueOnce(new Error('Router unavailable'));
    mocks.call.mockResolvedValueOnce(speakingReply([messages[0]]));
    const response = await POST(req());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      success: true,
      messages: [messages[0]],
      routed: { selected: ['curious'], needs: null, by: 'fallback' },
    });
    expect(mocks.call).toHaveBeenCalledTimes(2);
  });

  it('falls back when routing output is unusable instead of failing the page', async () => {
    mocks.call.mockResolvedValueOnce({ text: 'not JSON' });
    mocks.call.mockResolvedValueOnce(speakingReply([messages[0]]));
    const response = await POST(req());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ routed: { by: 'fallback' } });
  });

  it('passes the resolved stage thinking config instead of overwriting it', async () => {
    mocks.resolve.mockResolvedValue({
      model: 'routed-model',
      providerId: 'custom',
      apiKey: 'key',
      thinkingConfig: { mode: 'disabled' },
    });
    answerAs(routingReply([{ agentId: 'curious', score: 0.9 }]));
    await POST(req());
    expect(mocks.call.mock.calls[0][3]).toEqual({ mode: 'disabled' });
    expect(mocks.call.mock.calls[1][3]).toEqual({ mode: 'disabled' });
  });

  it('avoids inference when there are no peers', async () => {
    const response = await POST(req({ ...body(), agents: [{ id: 'teacher', role: 'teacher' }] }));
    expect(await response.json()).toEqual({
      success: true,
      messages: [],
      routed: { selected: [], needs: null, by: 'silence' },
      usage: { tokens: 0 },
    });
    expect(mocks.resolve).not.toHaveBeenCalled();
    expect(mocks.call).not.toHaveBeenCalled();
  });

  it('rejects missing required provider key while allowing keyless local providers', async () => {
    mocks.resolve.mockResolvedValue({ model: 'local-model', providerId: 'local', apiKey: '' });
    expect((await POST(req())).status).toBe(401);
    expect(mocks.call).not.toHaveBeenCalled();
    mocks.requiresKey.mockReturnValue(false);
    answerAs(routingReply([{ agentId: 'curious', score: 0.9 }]));
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
    mocks.call.mockResolvedValueOnce(routingReply([{ agentId: 'curious', score: 0.9 }]));
    mocks.call.mockRejectedValueOnce(new Error('Provider unavailable'));
    response = await POST(req());
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ success: false, error: 'Provider unavailable' });
    mocks.call.mockResolvedValueOnce(routingReply([{ agentId: 'curious', score: 0.9 }]));
    mocks.call.mockResolvedValueOnce({ text: 'not JSON' });
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

describe('named classmate answers', () => {
  const questionBody = (patch: Record<string, unknown> = {}) => ({
    ...body(),
    agents: [agents[0]],
    question: 'Where is the kinetic energy largest?',
    ...patch,
  });

  it('validates one classmate and a bounded question', () => {
    const question = validateClassmateQuestion(questionBody());
    expect(question.agent.id).toBe('curious');
    expect(question.question).toContain('kinetic');
    expect(() => validateClassmateQuestion(questionBody({ question: '   ' }))).toThrow(
      ClassmateRequestError,
    );
    expect(() => validateClassmateQuestion(questionBody({ question: 'x'.repeat(601) }))).toThrow(
      /600/,
    );
    expect(() => validateClassmateQuestion({ ...questionBody(), agents })).toThrow(/Exactly one/);
  });

  it('grounds the answer in the page, persona and question, and keeps quiz solutions out', () => {
    const prompt = buildClassmateAnswerPrompt(validateClassmateQuestion(questionBody()));
    expect(prompt.prompt).toContain('Curious');
    expect(prompt.prompt).toContain('Kinetic energy becomes potential energy');
    expect(prompt.prompt).toContain('Where is the kinetic energy largest?');
    expect(prompt.system).toContain('Return ONLY the answer text');

    const quiz = validateClassmateQuestion(
      questionBody({
        scene: {
          id: 'quiz-1',
          title: 'Check yourself',
          type: 'quiz',
          content: {
            type: 'quiz',
            questions: [
              { question: 'Which point has the most kinetic energy?', options: [{ label: 'A' }] },
            ],
          },
        },
      }),
    );
    const quizPrompt = buildClassmateAnswerPrompt(quiz);
    expect(quizPrompt.system).toContain('Never solve a question');
    expect(quizPrompt.prompt).toContain('Which point has the most kinetic energy?');
    expect(quizPrompt.prompt).not.toContain('answer:');
  });

  it('parses a plain answer and refuses silence', () => {
    expect(parseClassmateAnswer('  ```text\nGravity pulls it down.\n```  ')).toBe(
      'Gravity pulls it down.',
    );
    expect(() => parseClassmateAnswer('   ')).toThrow(/empty/);
    expect(() => parseClassmateAnswer('NO_REPLY')).toThrow(/empty/);
    expect(parseClassmateAnswer('y'.repeat(2500))).toHaveLength(2000);
  });

  it('counts tokens from total usage, split usage or nothing', () => {
    expect(classmateTokens({ usage: { totalTokens: 120 } })).toBe(120);
    expect(classmateTokens({ totalUsage: { inputTokens: 10, outputTokens: 5 } })).toBe(15);
    expect(classmateTokens({})).toBe(0);
  });

  it('answers the student as the classmate shown and reports its tokens', async () => {
    mocks.call.mockResolvedValueOnce({
      text: 'At the lowest point the kinetic energy is largest.',
      usage: { totalTokens: 1400 },
    });
    const response = await ASK_POST(req(questionBody()));
    expect(await response.json()).toEqual({
      success: true,
      message: { agentId: 'curious', text: 'At the lowest point the kinetic energy is largest.' },
      usage: { tokens: 1400 },
    });
    expect(mocks.call.mock.calls[0][0].system).toContain('小问');
  });

  it('rejects a question asked of several classmates', async () => {
    const response = await ASK_POST(req({ ...questionBody(), agents }));
    expect(response.status).toBe(400);
    expect(mocks.call).not.toHaveBeenCalled();
  });

  it('does not call the model without a provider key', async () => {
    mocks.resolve.mockResolvedValueOnce({
      model: 'm',
      providerId: 'custom',
      apiKey: undefined,
      thinkingConfig: {},
    });
    const response = await ASK_POST(req(questionBody()));
    expect(response.status).toBe(401);
    expect(mocks.call).not.toHaveBeenCalled();
  });

  it('reports a failed or empty answer instead of inventing one', async () => {
    mocks.call.mockRejectedValueOnce(new Error('boom'));
    expect((await ASK_POST(req(questionBody()))).status).toBe(502);

    mocks.call.mockResolvedValueOnce({ text: 'NO_REPLY' });
    expect((await ASK_POST(req(questionBody()))).status).toBe(502);
  });

  it('adds routing and speaking tokens to the page response', async () => {
    mocks.call
      .mockResolvedValueOnce({
        ...routingReply([{ agentId: 'curious', score: 0.95 }]),
        usage: { inputTokens: 10, outputTokens: 20 },
      })
      .mockResolvedValueOnce({
        ...speakingReply([messages[0]]),
        usage: { totalTokens: 300 },
      });
    const payload = await (await POST(req())).json();
    expect(payload.usage).toEqual({ tokens: 330 });
  });
});
