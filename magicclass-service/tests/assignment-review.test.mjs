import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { ServiceDatabase } from '../src/db/database.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { JobRepository } from '../src/jobs/repository.ts';
import { createProviderJobWorker } from '../src/provider/worker.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { reviewGeneratedStage } from '../src/generation/generator.ts';
import { assignmentReviewGuide } from '../src/generation/assignment-review.ts';
import { buildSceneNarration } from '../src/tts/narration.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const spec = { question_count: 2 };
const wrongSpec = {
  question_count: 2,
  source_numbers: [2, 5],
  source_stems: ['解方程2x+3=7，求x。', '一个三角形底6厘米、高4厘米，面积是多少？'],
  retry_required: false,
};
const originalOne = '当x=2时，x+1的值是多少？';
const originalTwo = '一件商品原价100元，打八折后的价格是多少元？';
const transferOne = '某班有3组学生，每组4人，另有2名老师，总人数是多少人？';
const transferTwo = '一辆汽车3小时行驶180千米，按同样速度5小时能行驶多少千米？';
const transferThree = '一个长方形长6厘米、宽4厘米，它的周长是多少厘米？';
const question = (source, role, text, n = 1) => ({
  type: 'single', question: text,
  options: [{ label: String(n + 1), value: 'A' }, { label: String(n + 2), value: 'B' }],
  answer: ['A'], analysis: `AI参考解析：先整理已知条件，再按${role === 'retry' ? '原题' : '变式'}条件独立推导。`, points: 1,
  sourceQuestionNumber: source, exerciseRole: role, hints: ['先识别已知量和要求的量。', '把已知量代入题目给定的关系。'],
});
function lesson() {
  return { stage: { name: '函数自主练习' }, scenes: [
    { title: '原题重做', type: 'quiz', content: { type: 'quiz', questions: [question(1, 'retry', originalOne), question(2, 'retry', originalTwo)] } },
    { title: '变式练习', type: 'quiz', content: { type: 'quiz', questions: [
      question(1, 'transfer', transferOne), question(2, 'transfer', transferTwo), question(1, 'transfer', transferThree, 3),
    ] } },
  ] };
}
function wrongLesson() {
  return { stage: { name: '作业错题变式讲解' }, scenes: [
    { title: '错题变式', type: 'quiz', content: { type: 'quiz', questions: [
      question(2, 'transfer', '某数的3倍减去5等于16，求这个数。'), question(5, 'transfer', '一块平行四边形底8厘米、高5厘米，面积是多少？'),
    ] } },
    { title: '再练一题', type: 'quiz', content: { type: 'quiz', questions: [
      question(2, 'transfer', '某数的4倍加上7等于31，求这个数。', 3),
    ] } },
  ] };
}

test('assignment quality gate checks practice balance, complete coverage and progressive hints', () => {
  assert.deepEqual(reviewGeneratedStage(lesson(), 'quiz', '', spec), []);
  for (const [change, expected] of [
    [(doc) => doc.scenes.unshift({ type: 'slide', content: { type: 'slide' } }), /start with a quiz/],
    [(doc) => doc.scenes.push(...Array.from({ length: 3 }, () => ({ type: 'slide' }))), /two-thirds/],
    [(doc) => doc.scenes[0].content.questions.pop(), /cover every original/],
    [(doc) => doc.scenes[1].content.questions.pop(), /at least 3 transfer/],
    [(doc) => { doc.scenes[0].content.questions[0].hints = ['直接给答案']; }, /progressive hints/],
    [(doc) => { doc.scenes[0].actions = [{ type: 'speech', text: '自动讲答案' }]; }, /leave narration/],
  ]) {
    const doc = lesson(); change(doc);
    assert.match(reviewGeneratedStage(doc, 'quiz', '', spec).join(';'), expected);
  }
});

test('assignment quality gate rejects transfer questions that copy or merely renumber originals', () => {
  const copied = lesson();
  copied.scenes[1].content.questions[0].question = originalOne;
  assert.match(
    reviewGeneratedStage(copied, 'quiz', '', spec).join(';'),
    /transfer practice must not copy an original question/,
  );

  const renumbered = lesson();
  renumbered.scenes[1].content.questions[0].question = '当x=7时，x+1的值是多少？';
  assert.match(
    reviewGeneratedStage(renumbered, 'quiz', '', spec).join(';'),
    /transfer practice must change more than numbers, names or punctuation/,
  );

  const paraphrased = lesson();
  paraphrased.scenes[1].content.questions[0].question = '当x=8时，x+1的结果是多少？';
  assert.match(
    reviewGeneratedStage(paraphrased, 'quiz', '', spec).join(';'),
    /transfer practice is too similar to an original question/,
  );
});

test('wrong-question review is transfer-only, covers selected numbers, and checks against original stems', () => {
  assert.deepEqual(reviewGeneratedStage(wrongLesson(), 'quiz', '', wrongSpec), []);
  assert.match(assignmentReviewGuide(wrongSpec), /错题原题2、5/);
  assert.match(assignmentReviewGuide(wrongSpec), /不得出现retry/);
  assert.match(assignmentReviewGuide(wrongSpec), /全部为transfer/);

  const retry = wrongLesson();
  retry.scenes[0].content.questions[0].exerciseRole = 'retry';
  assert.match(reviewGeneratedStage(retry, 'quiz', '', wrongSpec).join(';'), /must not include original retry/);

  const missing = wrongLesson();
  missing.scenes[0].content.questions.pop();
  assert.match(reviewGeneratedStage(missing, 'quiz', '', wrongSpec).join(';'), /cover every wrong original/);

  const copied = wrongLesson();
  copied.scenes[0].content.questions[0].question = '解方程2x+3=7，求x。';
  assert.match(reviewGeneratedStage(copied, 'quiz', '', wrongSpec).join(';'), /must not copy an original question/);

  const renumbered = wrongLesson();
  renumbered.scenes[0].content.questions[0].question = '解方程5x+3=18，求x。';
  assert.match(reviewGeneratedStage(renumbered, 'quiz', '', wrongSpec).join(';'), /change more than numbers/);

  assert.match(reviewGeneratedStage(wrongLesson(), 'quiz', '', { ...wrongSpec, source_stems: undefined }).join(';'), /requires the original stems/);
});

test('authenticated review job uses the dedicated prompt, repairs weak drafts and persists student-led quiz metadata', async () => {
  const requests = [];
  const upstream = createServer((request, response) => {
    let body = '';
    request.on('data', (chunk) => { body += chunk; });
    request.on('end', () => {
      requests.push(JSON.parse(body));
      const doc = lesson();
      if (requests.length === 1) doc.scenes[1].content.questions = [];
      response.setHeader('content-type', 'application/json');
      response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(doc) } }] }));
    });
  });
  await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve));
  const database = new ServiceDatabase(':memory:');
  try {
    const provider = { baseUrl: `http://127.0.0.1:${upstream.address().port}`, apiKey: 'stub', model: 'stub', timeoutMs: 5000 };
    const workspaces = new WorkspaceRepository(database);
    const identity = { userId: 'user-1', courseId: 'course-1' };
    const workspace = workspaces.createWorkspace({ ...identity, name: '作业复习' });
    const jobs = new JobRepository(database);
    const worker = createProviderJobWorker({ database, jobs, workspaces, provider });
    const { server } = createHarness({ database, routes: createGenerationRoutes({ database, provider }) });
    await withServer(server, async (base) => {
      const body = { mode: 'quiz', prompt: '重做两道原题并练习变式', assignment_review: spec };
      const send = async (key, value = body) => fetch(`${base}/internal/courses/course-1/workspaces/${workspace.id}/generate`, {
        method: 'POST', headers: { 'content-type': 'application/json', 'idempotency-key': key,
          'x-campusmate-service-assertion': mintAssertion({ scopes: ['generation:write', 'workspace:write', 'job:write'] }) }, body: JSON.stringify(value),
      });
      const response = await send('review-1');
      assert.equal(response.status, 201);
      const first = await response.json();
      assert.equal(await worker.tick(), true);
      assert.equal(jobs.get({ ...identity, jobId: first.job.id }).status, 'completed');
      assert.equal(requests.length, 2);
      assert.match(requests[0].messages[0].content, /学生掌握选题/);
      assert.doesNotMatch(requests[0].messages[0].content, /slide→at least two/);
      assert.match(requests[1].messages[1].content, /cover every original|at least 3 transfer/);
      const stages = workspaces.listStages({ ...identity, workspaceId: workspace.id }).items;
      assert.equal(stages.length, 1);
      const document = JSON.parse(stages[0].document);
      assert.equal(document.scenes[0].content.learningProfile, 'assignment_review');
      assert.equal(document.scenes[0].content.questions[0].hints.length, 2);
      assert.deepEqual(document.scenes[0].actions, []);
      assert.equal(document.scenes[0].multiAgent.enabled, false);
      assert.doesNotMatch(buildSceneNarration(document.scenes[0]).text, /AI参考解析|另一选项/);
      assert.equal((await (await send('review-1')).json()).job.status, 'completed');
      assert.equal((await send('bad-profile', { ...body, assignment_review: { question_count: 0 } })).status, 400);
    });
  } finally {
    database.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
});
