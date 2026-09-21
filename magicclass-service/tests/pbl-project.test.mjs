/**
 * PBL 项目合成器的契约测试。
 *
 * 与 `slide-canvas.test.mjs` 同一思路：**不调用模型**，把"渲染器到底认不认这份内容"
 * 变成可读可断言的规则。判定条件同步自前端移植层的 `isRunnablePBLProjectV2`
 * （`webreact/src/maic/scene/lib/pbl-types-guards.js`）——它是渲染器决定"显示项目"
 * 还是"显示占位面板"的唯一依据。
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { composePblProject, readPblOutline, upgradeLegacyPblProjects } from '../src/dsl/pbl-project.ts';
import { projectStoredDocument } from '../src/dsl/document-projection.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';

/** 渲染器可运行判定的镜像。改了这里就必须同时改前端那份，两边不能各自漂移。 */
function isRunnable(project) {
  const objectArray = (value) => Array.isArray(value) && value.every((item) => typeof item === 'object' && item !== null && !Array.isArray(item));
  if (typeof project !== 'object' || project === null || Array.isArray(project)) return false;
  for (const key of ['milestones', 'roles', 'submissions', 'evaluations', 'threads', 'engagementEvents']) {
    if (!objectArray(project[key])) return false;
  }
  if (project.milestones.some((milestone) => !objectArray(milestone.microtasks))) return false;
  if (project.threads.some((thread) => !objectArray(thread.messages))) return false;
  return (
    project.roles.some(
      (role) => role.type === 'instructor' && typeof role.id === 'string' && role.id.trim().length > 0 && typeof role.name === 'string',
    ) &&
    project.milestones.length > 0 &&
    project.milestones.every(
      (milestone) =>
        milestone.microtasks.length > 0 &&
        milestone.microtasks.every(
          (microtask) => typeof microtask.id === 'string' && microtask.id.trim().length > 0 && typeof microtask.title === 'string',
        ),
    )
  );
}

const NEW_SHAPE = {
  type: 'pbl',
  project: {
    title: '校园节能方案',
    description: '为一个真实场景提出可检验的节能方案。',
    milestones: [
      { title: '提出问题', description: '明确要解决什么。', tasks: [{ title: '定义问题', description: '写清约束。' }] },
      { title: '探索', description: '找依据。', tasks: [{ title: '收集数据' }, { title: '访谈使用者' }] },
    ],
  },
};

const LEGACY_SHAPE = {
  type: 'pbl',
  phases: [{ id: 'p1', title: '提出问题', tasks: [{ id: 't1', title: '定义问题' }] }],
};

test('both the new and the legacy content shape are readable', () => {
  const modern = readPblOutline(NEW_SHAPE);
  assert.equal(modern.title, '校园节能方案');
  assert.equal(modern.phases.length, 2);
  assert.equal(modern.phases[1].tasks.length, 2);
  // 旧形态没有描述：用标题兜底，不留空——空描述会让 Hero 出现大片空白。
  const legacy = readPblOutline(LEGACY_SHAPE);
  assert.equal(legacy.phases.length, 1);
  assert.equal(legacy.phases[0].tasks[0].description, '定义问题');
});

test('composed projects pass the renderer runnable check for both shapes', () => {
  for (const [label, content] of [['new', NEW_SHAPE], ['legacy', LEGACY_SHAPE]]) {
    const project = composePblProject(content, '项目式学习');
    assert.ok(isRunnable(project), `${label}: 合成结果必须能过渲染器的可运行判定`);
    assert.equal(project.uiPhase, 'hero', `${label}: 内容刚生成时应停在项目说明页`);
    assert.equal(project.language, 'zh-CN');
  }
});

test('a content-free PBL scene still composes into a runnable project', () => {
  // 判定要求 milestones.length > 0，所以"没有阶段"不能产出空项目——那等于白做，
  // 渲染器照样退回占位面板。
  for (const bad of [undefined, null, 7, 'text', {}, { phases: [] }, { phases: [{ tasks: [] }] }]) {
    const project = composePblProject(bad, '项目式学习');
    assert.ok(isRunnable(project), `畸形输入必须仍可运行：${JSON.stringify(bad)}`);
  }
});

test('composing is deterministic and carries no clock', () => {
  // 读时投影靠"没变就不重写"来避免触碰存量字节；一旦注入时间戳，这条判断永久失效。
  const input = JSON.parse(JSON.stringify(NEW_SHAPE));
  assert.deepEqual(composePblProject(input, 'x'), composePblProject(input, 'x'));
  const serialized = JSON.stringify(composePblProject(input, 'x'));
  assert.doesNotMatch(serialized, /20\d\d-\d\d-\d\dT/, '合成结果不得包含时间戳');
});

test('the projection fills only what is missing and is idempotent', () => {
  const document = {
    stage: { id: 'stage_1', name: 'x' },
    scenes: [
      { id: 's1', title: '校园节能', type: 'pbl', content: LEGACY_SHAPE },
      { id: 's2', title: '已有项目', type: 'pbl', content: { type: 'pbl', projectV2: composePblProject(NEW_SHAPE, 'x') } },
      { id: 's3', title: '历史配置', type: 'pbl', content: { type: 'pbl', projectConfig: { issueboard: { issues: [{ id: 'i1', index: 0, title: 't' }] } } } },
    ],
  };

  const projected = upgradeLegacyPblProjects(document);
  assert.notEqual(projected, document, '有改动时必须返回新对象');
  assert.ok(isRunnable(projected.scenes[0].content.projectV2), '缺 projectV2 的场景必须被补上');
  // 渲染器的一等公民与它自己会升级的历史形态都不许被抢着改写。
  assert.equal(projected.scenes[1], document.scenes[1], '已有 projectV2 的场景必须原样保留');
  assert.equal(projected.scenes[2], document.scenes[2], '有 issueboard 的 projectConfig 必须交给渲染器自己升级');

  const twice = upgradeLegacyPblProjects(projected);
  assert.equal(twice, projected, '第二次投影必须检测到"没有改动"');
});

test('the projection leaves unrelated documents untouched', () => {
  for (const value of [undefined, null, 7, 'text', {}, { scenes: 'nope' }, { scenes: [] }]) {
    assert.equal(upgradeLegacyPblProjects(value), value, `无关输入必须原样返回：${JSON.stringify(value)}`);
  }
});

test('slide and PBL projections compose into one document pass', () => {
  // 两个投影由 `projectStoredDocument` 串起来；任一环节改过都必须反映到结果里。
  const document = {
    stage: { id: 'stage_1', name: 'x' },
    scenes: [
      { id: 's1', title: '极限', type: 'slide', content: { type: 'slide', canvas: { title: '极限', body: '先看数列。' } } },
      { id: 's2', title: '项目', type: 'pbl', content: LEGACY_SHAPE },
    ],
  };
  const projected = projectStoredDocument(document);
  assert.ok(projected.scenes[0].content.canvas.elements.length > 0, '幻灯片必须被合成');
  assert.ok(isRunnable(projected.scenes[1].content.projectV2), 'PBL 必须被合成');
  assert.equal(projectStoredDocument(projected), projected, '串起来之后仍然幂等');
});

test('the repository serves composed PBL projects without rewriting stored bytes', () => {
  const database = new ServiceDatabase(':memory:');
  const repository = new WorkspaceRepository(database);
  const workspace = repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '节能' });
  const stored = JSON.stringify({
    dslVersion: '0.3.0',
    stage: { id: 'stage_1', name: '节能' },
    scenes: [{ id: 'scene_1', stageId: 'stage_1', title: '校园节能', order: 0, type: 'pbl', content: LEGACY_SHAPE }],
  });

  const created = repository.createStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    title: '校园节能',
    document: JSON.parse(stored),
    dslVersion: '0.3.0',
  });
  const read = repository.getStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    stageId: created.id,
  });

  const served = JSON.parse(read.document);
  assert.ok(isRunnable(served.scenes[0].content.projectV2), '读取必须返回可运行的 PBL 项目');

  const storedRow = database.raw.prepare('SELECT document FROM stages WHERE id = ?').get(created.id);
  assert.equal(storedRow.document, stored, '存量字节不得被读取路径改写');
});
