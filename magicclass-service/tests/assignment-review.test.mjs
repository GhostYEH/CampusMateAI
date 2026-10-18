import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { ServiceDatabase } from '../src/db/database.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { JobRepository } from '../src/jobs/repository.ts';
import { createProviderJobWorker } from '../src/provider/worker.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { reviewGeneratedStage } from '../src/generation/generator.ts';
import { buildSceneNarration } from '../src/tts/narration.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const spec = { question_count: 2 };
const question = (source, role, n = 1) => ({
  type: 'single', question: `原题${source}的${role}练习${n}：x=${n}时x+1是多少？`,
  options: [{ label: String(n + 1), value: 'A' }, { label: String(n + 2), value: 'B' }],
  answer: ['A'], analysis: `AI参考解析：将${n}代入x+1得到${n + 1}，另一选项多加了1。`, points: 1,
  sourceQuestionNumber: source, exerciseRole: role, hints: ['先识别已知量和要求的量。', '把已知量代入题目给定的表达式。'],
});
function lesson() {
  return { stage: { name: '函数自主练习' }, scenes: [
    { title: '原题重做', type: 'quiz', content: { type: 'quiz', questions: [question(1, 'retry'), question(2, 'retry')] } },
    { title: '变式练习', type: 'quiz', content: { type: 'quiz', questions: [question(1, 'transfer', 2), question(2, 'transfer', 2), question(1, 'transfer', 3)] } },
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
