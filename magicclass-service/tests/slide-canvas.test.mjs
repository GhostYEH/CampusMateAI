/**
 * 幻灯片画布合成器的几何与形状契约。
 *
 * 这些断言的价值在于**不需要调用模型**：合成是纯函数，所以"元素越界""标题与正文
 * 重叠""id 重复""形状缺 viewBox"这类只在渲染后才看得见的错误，可以在几毫秒内
 * 被钉死。模型侧的失败模式因此收窄成"内容为空/字段类型不对"。
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  SLIDE_CANVAS_HEIGHT,
  SLIDE_CANVAS_WIDTH,
  composeSlideCanvas,
  readSlideOutline,
  slideLayoutOf,
  upgradeLegacySlideCanvases,
} from '../src/dsl/slide-canvas.ts';
import { buildGeneratedStage, materializeGeneratedStage } from '../src/generation/generator.ts';
import { prepareStage } from '../src/dsl/validate.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';

const BASE_FIELDS = ['id', 'left', 'top', 'width', 'height', 'rotate'];

function outline(overrides = {}) {
  return { type: 'slide', slide: { title: '进程与线程', ...overrides } };
}

/** 每个元素必须能被渲染层直接读：基础字段 + 类型专属字段齐全。 */
function assertRenderable(canvas, label) {
  assert.ok(Array.isArray(canvas.elements), `${label}: elements 必须是数组`);
  assert.ok(canvas.elements.length > 0, `${label}: 至少要有一个元素，否则课堂是一块空白`);

  const ids = new Set();
  for (const element of canvas.elements) {
    for (const field of BASE_FIELDS) {
      assert.ok(element[field] !== undefined, `${label}: 元素缺少必填字段 ${field}`);
      if (field !== 'id') assert.equal(typeof element[field], 'number', `${label}: ${field} 必须是数字`);
    }
    assert.ok(!ids.has(element.id), `${label}: 元素 id 重复（${element.id}）`);
    ids.add(element.id);

    assert.ok(['text', 'shape'].includes(element.type), `${label}: 未支持的元素类型 ${element.type}`);
    if (element.type === 'text') {
      assert.equal(typeof element.content, 'string', `${label}: 文本元素必须有 content`);
      assert.equal(typeof element.defaultColor, 'string', `${label}: 文本元素必须有 defaultColor`);
      assert.equal(typeof element.defaultFontName, 'string', `${label}: 文本元素必须有 defaultFontName`);
      // 字号走内联样式，渲染结果才不依赖宿主页面是否注入了排版 CSS。
      assert.match(element.content, /font-size:\d+px/, `${label}: 文本必须自带内联字号`);
    }
    if (element.type === 'shape') {
      assert.ok(Array.isArray(element.viewBox) && element.viewBox.length === 2, `${label}: 形状必须有 viewBox`);
      assert.equal(typeof element.path, 'string', `${label}: 形状必须有 path`);
      assert.match(element.path, /^M /, `${label}: path 必须是有效的 SVG 路径`);
      assert.equal(typeof element.fill, 'string', `${label}: 形状必须有 fill`);
    }
  }
}

/** 任何元素都不许越出画布——越界的内容用户既看不到也点不到。 */
function assertInsideCanvas(canvas, label) {
  for (const element of canvas.elements) {
    assert.ok(element.left >= 0, `${label}: ${element.id} left 为负（${element.left}）`);
    assert.ok(element.top >= 0, `${label}: ${element.id} top 为负（${element.top}）`);
    assert.ok(
      element.left + element.width <= SLIDE_CANVAS_WIDTH + 0.01,
      `${label}: ${element.id} 右侧越界（${element.left + element.width} > ${SLIDE_CANVAS_WIDTH}）`,
    );
    assert.ok(
      element.top + element.height <= SLIDE_CANVAS_HEIGHT + 0.01,
      `${label}: ${element.id} 底部越界（${element.top + element.height} > ${SLIDE_CANVAS_HEIGHT}）`,
    );
  }
}

test('the layout follows the content shape, deterministically', () => {
  assert.equal(slideLayoutOf(outline()), 'title');
  assert.equal(slideLayoutOf(outline({ bullets: ['a', 'b'] })), 'bullets');
  assert.equal(
    slideLayoutOf(outline({ sections: [{ heading: '甲', bullets: ['a'] }] })),
    'sections',
  );
  // sections 比 bullets 更具体：两者都给时按 sections 排版，而不是悄悄丢掉分组。
  assert.equal(
    slideLayoutOf(outline({ bullets: ['a'], sections: [{ heading: '甲', bullets: ['b'] }] })),
    'sections',
  );
  assert.equal(slideLayoutOf(outline({ layout: 'cover', subtitle: '课程导览' })), 'cover');
  assert.equal(slideLayoutOf(outline({ layout: 'toc', toc: ['第一章', '第二章'] })), 'toc');
  assert.equal(
    slideLayoutOf(outline({ layout: 'comparison', comparison: { left: { heading: '旧', bullets: ['a'] }, right: { heading: '新', bullets: ['b'] } } })),
    'comparison',
  );
  assert.equal(slideLayoutOf(outline({ layout: 'conclusion', bullets: ['a'], conclusion: '记住这一点' })), 'conclusion');
});

test('every layout produces renderable elements inside the canvas', () => {
  const cases = [
    ['title', outline()],
    ['title+subtitle', outline({ subtitle: '从零开始理解' })],
    ['bullets', outline({ bullets: ['一个进程可以有多个线程', '线程共享进程的地址空间', '切换线程比切换进程便宜'] })],
    ['sections', outline({
      sections: [
        { heading: '进程', bullets: ['独立地址空间', '切换开销大'] },
        { heading: '线程', bullets: ['共享地址空间', '切换开销小'] },
      ],
    })],
    ['three sections', outline({
      sections: [
        { heading: '甲', bullets: ['a', 'b'] },
        { heading: '乙', bullets: ['c'] },
        { heading: '丙', bullets: ['d'] },
      ],
    })],
    ['cover', outline({ layout: 'cover', subtitle: '课程副标题' })],
    ['toc', outline({ layout: 'toc', toc: ['概念', '推导', '练习'] })],
    ['comparison', outline({ layout: 'comparison', comparison: {
      left: { heading: '进程', bullets: ['独立地址空间', '切换开销大'] },
      right: { heading: '线程', bullets: ['共享地址空间', '切换开销小'] },
    } })],
    ['conclusion', outline({ layout: 'conclusion', bullets: ['先理解概念'], conclusion: '能用自己的话解释' })],
  ];
  for (const [label, content] of cases) {
    const canvas = composeSlideCanvas(content);
    assert.equal(canvas.width, SLIDE_CANVAS_WIDTH, label);
    assert.equal(canvas.height, SLIDE_CANVAS_HEIGHT, label);
    assertRenderable(canvas, label);
    assertInsideCanvas(canvas, label);
  }
});

test('new layouts expose their defining content with unique ids and bounded geometry', () => {
  const cases = [
    outline({ layout: 'toc', toc: ['第一章', '第二章'] }),
    outline({ layout: 'comparison', comparison: { left: { heading: 'A', bullets: ['左侧'] }, right: { heading: 'B', bullets: ['右侧'] } } }),
    outline({ layout: 'conclusion', bullets: ['要点'], conclusion: '结论条' }),
  ];
  for (const content of cases) {
    const canvas = composeSlideCanvas(content);
    assertRenderable(canvas, slideLayoutOf(content));
    assertInsideCanvas(canvas, slideLayoutOf(content));
    const ids = canvas.elements.map((element) => element.id);
    assert.equal(new Set(ids).size, ids.length);
    assert.match(JSON.stringify(canvas.elements), /第一章|左侧|结论条/);
  }
});

test('the header never overlaps the body', () => {
  // 标题被正文压住是最容易发生、也最难在代码里看出来的排版事故。
  const canvas = composeSlideCanvas(
    outline({ bullets: ['a', 'b', 'c'] }),
  );
  const title = canvas.elements.find((element) => element.id === 'el_title');
  const accent = canvas.elements.find((element) => element.id === 'el_accent');
  const body = canvas.elements.find((element) => element.id === 'el_body');
  assert.ok(title && accent && body);
  assert.ok(title.top + title.height <= body.top, '标题与正文重叠');
  assert.ok(accent.top >= title.top + title.height, '强调线与标题重叠');
  assert.ok(accent.top + accent.height <= body.top, '强调线与正文重叠');
});

test('the canvas carries its own theme and background', () => {
  const canvas = composeSlideCanvas(outline({ bullets: ['a'] }));
  assert.equal(canvas.background.type, 'solid');
  assert.equal(typeof canvas.background.color, 'string');
  assert.equal(typeof canvas.theme.fontColor, 'string');
  assert.equal(typeof canvas.theme.fontName, 'string');
});

test('composing is a pure function of the content', () => {
  const content = outline({ bullets: ['a', 'b'] });
  assert.deepEqual(composeSlideCanvas(content), composeSlideCanvas(content));
});

test('the legacy canvas shape still composes instead of rendering blank', () => {
  // 历史数据与既有夹具用的是 { canvas: { title, body } }。它必须仍然得到一张
  // 真实画布，否则老课堂会在升级后突然变成空白页。
  const legacy = { type: 'slide', canvas: { title: '极限', body: '先看数列。\n再看函数。' } };
  assert.equal(slideLayoutOf(legacy), 'bullets');

  const parsed = readSlideOutline(legacy);
  assert.equal(parsed.title, '极限');
  assert.deepEqual(parsed.bullets, ['先看数列。', '再看函数。']);

  const canvas = composeSlideCanvas(legacy);
  assertRenderable(canvas, 'legacy');
  assertInsideCanvas(canvas, 'legacy');
  assert.match(JSON.stringify(canvas.elements), /极限/, '标题必须出现在画布里');
});

test('model-supplied text is escaped, never injected as markup', () => {
  const canvas = composeSlideCanvas(
    outline({
      title: '<img src=x onerror=alert(1)>',
      bullets: ['<script>alert(2)</script>'],
    }),
  );
  const html = canvas.elements.map((element) => String(element.content ?? '')).join('');
  assert.doesNotMatch(html, /<script/i, '注入的 script 标签必须被转义');
  assert.doesNotMatch(html, /<img/i, '注入的 img 标签必须被转义');
  assert.match(html, /&lt;script&gt;/, '原文应以转义形式保留，而不是被丢弃');
});

test('malformed content degrades to a title slide, never to a crash', () => {
  for (const bad of [undefined, null, 42, 'text', {}, { type: 'slide' }, { slide: { bullets: 'nope' } }]) {
    const canvas = composeSlideCanvas(bad);
    assertRenderable(canvas, `malformed: ${JSON.stringify(bad)}`);
    assertInsideCanvas(canvas, `malformed: ${JSON.stringify(bad)}`);
  }
});

test('over-long lists are bounded so one page cannot overflow its box', () => {
  const canvas = composeSlideCanvas(outline({ bullets: Array.from({ length: 40 }, (_, index) => `要点 ${index}`) }));
  const body = canvas.elements.find((element) => element.id === 'el_body');
  const items = (body.content.match(/<li/g) ?? []).length;
  assert.ok(items <= 8, `要点必须被截断到上限，实际 ${items}`);
});

// ===== 与生成流程的集成：任何 slide 都不许"不带元素"地到达浏览器 =====

test('the local template emits a real canvas, not a title stub', () => {
  // 未配置 provider 时的降级路径。如果它只出 { title, body }，课堂就只能走标题
  // 兜底——用户看到的是"功能坏了"，而不是"没配模型"。
  const stage = buildGeneratedStage('slide', '函数的极限');
  const content = stage.scenes[0].content;
  assert.equal(content.type, 'slide');
  const canvas = content.canvas;
  assertRenderable(canvas, 'local template');
  assertInsideCanvas(canvas, 'local template');
  assert.match(JSON.stringify(canvas.elements), /函数的极限/);
});

test('model output is composed into a canvas before it is persisted', () => {
  const raw = {
    dslVersion: '0.3.0',
    stage: { name: '进程与线程' },
    scenes: [
      { title: '进程与线程', type: 'slide', content: outline({ bullets: ['进程有独立地址空间', '线程共享地址空间'] }) },
      { title: '复习', type: 'slide', content: { type: 'slide', canvas: { title: '复习', body: '先看概念。\n再做练习。' } } },
    ],
  };
  const aggregate = materializeGeneratedStage(raw);
  for (const scene of aggregate.scenes) {
    assert.equal(scene.type, 'slide');
    // 这是前端渲染分发的判据：有非空 elements 才走真实画布，否则退化。
    assert.ok(
      Array.isArray(scene.content.canvas.elements) && scene.content.canvas.elements.length > 0,
      `${scene.title}: 持久化的 canvas 必须带元素，否则课堂只能渲染兜底`,
    );
    assertRenderable(scene.content.canvas, scene.title);
    assertInsideCanvas(scene.content.canvas, scene.title);
  }
});

test('a composed canvas survives the write path (migrate -> sanitize -> validate)', () => {
  // 合成结果必须真的能落库：校验器只要求 canvas 是对象，sanitize 只截断字符串，
  // 但这条链一旦改动就可能悄悄把元素剥掉。所以按真实写入路径走一遍。
  const raw = materializeGeneratedStage({
    stage: { name: '进程与线程' },
    scenes: [{ title: '进程与线程', type: 'slide', content: outline({ sections: [{ heading: '进程', bullets: ['独立地址空间'] }] }) }],
  });
  const prepared = prepareStage(raw);
  const canvas = prepared.document.scenes[0].content.canvas;
  assert.ok(Array.isArray(canvas.elements) && canvas.elements.length > 0, '写入路径不得剥掉画布元素');
  assert.ok(canvas.elements.some((element) => element.type === 'shape'), '卡片形状必须留下');
  assert.ok(canvas.elements.some((element) => element.type === 'text'), '文本元素必须留下');
});

// ===== 读取时投影：历史文档里的旧版画布 =====

function legacyDocument() {
  return {
    dslVersion: '0.3.0',
    stage: { id: 'stage_1', name: '极限' },
    scenes: [
      { id: 'scene_1', stageId: 'stage_1', title: '极限', order: 0, type: 'slide', content: { type: 'slide', canvas: { title: '极限', body: '先看数列。\n再看函数。' } } },
      { id: 'scene_2', stageId: 'stage_1', title: '练习', order: 1, type: 'quiz', content: { type: 'quiz', questions: [] } },
    ],
  };
}

test('the read-time projection composes legacy canvases and reports that it changed', () => {
  const source = legacyDocument();
  const projected = upgradeLegacySlideCanvases(source);
  assert.notEqual(projected, source, '有改动时必须返回新对象');
  const canvas = projected.scenes[0].content.canvas;
  assertRenderable(canvas, 'projected legacy');
  assertInsideCanvas(canvas, 'projected legacy');
  assert.match(JSON.stringify(canvas.elements), /极限/, '旧版标题必须进入画布');
  // 非 slide 场景逐字保持：投影不该顺手改动别的场景。
  assert.equal(projected.scenes[1], source.scenes[1], '非 slide 场景必须原样保留');
});

test('the projection leaves real canvases and unrelated documents untouched', () => {
  // 1) 已经有元素的画布：必须**同一个引用**返回，否则"没变"只能靠比内容。
  const modern = {
    stage: { id: 'stage_1', name: 'x' },
    scenes: [{ id: 's1', type: 'slide', content: { type: 'slide', canvas: composeSlideCanvas(outline({ bullets: ['a'] })) } }],
  };
  assert.equal(upgradeLegacySlideCanvases(modern), modern, '真实画布不得被重写');

  // 2) 与幻灯片无关的文档、以及畸形输入：原样返回，不抛错。
  for (const value of [undefined, null, 7, 'text', {}, { scenes: 'nope' }, { scenes: [] }]) {
    assert.equal(upgradeLegacySlideCanvases(value), value, `无关输入必须原样返回：${JSON.stringify(value)}`);
  }
});

test('the projection is idempotent: projecting twice changes nothing more', () => {
  const once = upgradeLegacySlideCanvases(legacyDocument());
  const twice = upgradeLegacySlideCanvases(once);
  assert.equal(twice, once, '第二次投影必须检测到"没有改动"并返回同一引用');
});

test('the repository serves composed documents without rewriting stored bytes', () => {
  // 这条是整套投影的**中心断言**：调用方拿到的是可渲染的文档，而数据库里躺着的
  // 仍是用户当初写入的字节。把两件事同时钉住，才排除"其实偷偷改了存量数据"。
  const database = new ServiceDatabase(':memory:');
  const repository = new WorkspaceRepository(database);
  const workspace = repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '极限' });
  const legacy = JSON.stringify(legacyDocument());

  const created = repository.createStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    title: '极限',
    document: JSON.parse(legacy),
    dslVersion: '0.3.0',
  });

  const read = repository.getStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    stageId: created.id,
  });
  const served = JSON.parse(read.document);
  const canvas = served.scenes[0].content.canvas;
  assert.ok(
    Array.isArray(canvas.elements) && canvas.elements.length > 0,
    '读取必须返回已合成的画布，否则课堂只能渲染标题兜底',
  );

  const storedRow = database.raw
    .prepare('SELECT document FROM stages WHERE id = ?')
    .get(created.id);
  assert.equal(storedRow.document, legacy, '存量字节不得被读取路径改写');
});

test('the repository does not touch stages that already have real canvases', () => {
  const database = new ServiceDatabase(':memory:');
  const repository = new WorkspaceRepository(database);
  const workspace = repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '极限' });
  const modern = JSON.stringify({
    dslVersion: '0.3.0',
    stage: { id: 'stage_1', name: '极限' },
    scenes: [{ id: 'scene_1', stageId: 'stage_1', title: '极限', order: 0, type: 'slide', content: { type: 'slide', canvas: composeSlideCanvas(outline({ bullets: ['a'] })) } }],
  });
  const created = repository.createStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    title: '极限',
    document: JSON.parse(modern),
    dslVersion: '0.3.0',
  });
  const read = repository.getStage({
    userId: 'user-1',
    courseId: 'course-1',
    workspaceId: workspace.id,
    stageId: created.id,
  });
  // 没有改动时必须逐字节返回存储原样（含键顺序与数字写法）。
  assert.equal(read.document, modern, '已有真实画布的文档必须逐字节原样返回');
});


