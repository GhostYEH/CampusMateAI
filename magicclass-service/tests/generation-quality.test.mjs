import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';

import { buildGeneratedStage, materializeGeneratedStage, reviewGeneratedStage } from '../src/generation/generator.ts';
import { generateStageDocument, ProviderError } from '../src/provider/client.ts';
import { buildSceneNarration } from '../src/tts/narration.ts';
import { prepareStage } from '../src/dsl/validate.ts';

const concept = { type: 'slide', slide: { title: '极限的概念', sections: [{ heading: '概念解释', bullets: ['极限描述自变量接近某点时函数值趋向的数值。'] }] } };
const example = { type: 'slide', slide: { title: '极限的例子', sections: [{ heading: '具体例子', bullets: ['当 x 接近 2 时，函数 x + 1 的值接近 3。'] }] } };
const quiz = { type: 'quiz', questions: [{ type: 'single', question: 'x 接近 2 时，x + 1 接近多少？', options: [{ label: '2', value: 'A' }, { label: '3', value: 'B' }, { label: '4', value: 'C' }], answer: ['B'], analysis: '把 x 趋近的 2 代入 x + 1，得到 3。', points: 1 }] };
const doc = (contents) => ({ stage: { name: '极限' }, scenes: contents.map((content, i) => ({ title: `第 ${i + 1} 页`, type: content.type, content })) });

test('generated lesson keeps readable explanation text after canvas composition and full validation', () => {
  const prepared = prepareStage(materializeGeneratedStage(doc([concept, example, quiz]))).document;
  assert.deepEqual(reviewGeneratedStage(prepared, 'slide', '讲解并练习极限'), []);
  for (const scene of prepared.scenes.slice(0, 2)) {
    assert.ok(scene.content.canvas.elements.length);
    assert.ok(buildSceneNarration(scene).text.length > 30);
  }
});

test('quality review rejects terse slides and quiz scenes without usable answer keys', () => {
  const terse = doc([{ type: 'slide', slide: { title: '极限', bullets: ['定义', '公式'] } }, example]);
  assert.ok(reviewGeneratedStage(terse, 'slide', '极限').length);
  assert.ok(reviewGeneratedStage(doc([concept, example]), 'slide', '极限选择题练习').some((item) => item.includes('quiz')));
  for (const change of [
    { answer: [] }, { answer: ['missing'] }, { analysis: '' }, { points: 0 },
    { options: [{ label: '2', value: 'A' }, { label: '3', value: 'B' }] },
  ]) {
    const broken = { ...quiz, questions: [{ ...quiz.questions[0], ...change }] };
    assert.ok(reviewGeneratedStage(doc([concept, example, broken]), 'slide', '极限练习').some((item) => item.includes('quiz')));
  }
  const shortAnswer = { type: 'quiz', questions: [{ type: 'short_answer', question: '什么是函数的极限？', analysis: '函数值随自变量趋近目标点而趋近的数。', points: 2 }] };
  assert.deepEqual(reviewGeneratedStage(doc([concept, example, shortAnswer]), 'slide', '极限测验'), []);
});

test('local slide generation has explanation, worked example, and a real quiz when practice is requested', () => {
  const stage = prepareStage(buildGeneratedStage('slide', '牛顿第二定律选择题练习')).document;
  assert.deepEqual(stage.scenes.map((scene) => scene.type), ['slide', 'slide', 'quiz']);
  assert.ok(stage.scenes.slice(0, 2).every((scene) => buildSceneNarration(scene).text.length > 30));
  assert.deepEqual(reviewGeneratedStage(stage, 'slide', '牛顿第二定律选择题练习'), []);
});

test('simulation mode preserves teaching slides and appends an interactive runtime when provider omits one', () => {
  const stage = prepareStage(materializeGeneratedStage(doc([concept, example]), { mode: 'simulation', prompt: '验证牛顿第二定律的实验' })).document;
  assert.equal(stage.scenes[0].type, 'slide');
  assert.equal(stage.scenes.at(-1).type, 'interactive');
  assert.equal(stage.scenes.at(-1).content.widgetType, 'simulation');
  assert.deepEqual(reviewGeneratedStage(stage, 'simulation', '验证牛顿第二定律的实验'), []);
});

test('provider retries a weak lesson with quality feedback before accepting the complete document', async () => {
  const requests = [];
  const server = createServer((request, response) => {
    let body = '';
    request.on('data', (chunk) => { body += chunk; });
    request.on('end', () => {
      requests.push(JSON.parse(body));
      response.setHeader('content-type', 'application/json');
      response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(requests.length === 1 ? doc([concept, example]) : doc([concept, example, quiz])) } }] }));
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    const result = await generateStageDocument({ baseUrl: `http://127.0.0.1:${port}`, apiKey: 'stub', model: 'stub', timeoutMs: 5000 }, { mode: 'slide', prompt: '极限选择题练习' });
    assert.equal(requests.length, 2);
    assert.match(requests[1].messages[1].content, /quiz/);
    assert.equal(result.scenes[2].type, 'quiz');
  } finally {
    server.close();
  }
});

test('provider refuses two incomplete drafts instead of persisting an unanswerable lesson', async () => {
  const server = createServer((request, response) => {
    request.resume();
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(doc([concept, example])) } }] }));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    await assert.rejects(
      generateStageDocument({ baseUrl: `http://127.0.0.1:${port}`, apiKey: 'stub', model: 'stub', timeoutMs: 5000 }, { mode: 'slide', prompt: '极限选择题' }),
      (error) => error instanceof ProviderError && error.code === 'provider_invalid_response',
    );
  } finally {
    server.close();
  }
});
