/**
 * Stage/Scene/Action DSL tests.
 *
 * The ported contract is the foundation the workspace, editor and player all
 * read, so these tests pin the *mechanism* (version ladder, cross-line guard,
 * write path ordering) rather than only the happy path: a silently mis-migrated
 * document is far more expensive than a rejected one.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ACTION_TYPES,
  DSL_LIMITS,
  DSL_MIGRATIONS,
  DSL_VERSION,
  DSL_VERSION_KEY,
  DslLimitError,
  DslValidationError,
  DslVersionError,
  INITIAL_DSL_VERSION,
  RUNTIME_DSL_MIGRATIONS,
  RUNTIME_DSL_VERSION,
  RUNTIME_DSL_VERSION_KEY,
  SCENE_TYPES,
  UNVERSIONED_DSL_VERSION,
  WIDGET_TYPES,
  compareVersions,
  depthBeyond,
  migrate,
  migrateRuntime,
  needsMigration,
  prepareStage,
  sanitizeInteractiveHtml,
  sanitizeText,
  sanitizeUrl,
  validateStage,
  versionOf,
} from '../src/dsl/index.ts';

// ===== fixtures =====

function slideScene(overrides = {}) {
  return {
    id: 'scene-1',
    stageId: 'stage-1',
    type: 'slide',
    title: '开场',
    order: 0,
    content: { type: 'slide', canvas: { elements: [] } },
    ...overrides,
  };
}

function aggregate(overrides = {}) {
  return {
    dslVersion: DSL_VERSION,
    stage: { id: 'stage-1', name: '演示课堂', createdAt: 1, updatedAt: 2 },
    scenes: [slideScene()],
    ...overrides,
  };
}

// ===== version comparison =====

test('compareVersions treats a missing segment as zero and orders numerically', () => {
  assert.equal(compareVersions('1.0', '1.0.0'), 0);
  assert.equal(compareVersions('0.9.0', '0.10.0'), -1, 'numeric, not lexicographic');
  assert.equal(compareVersions('0.10.0', '0.9.0'), 1);
  assert.equal(compareVersions('2.0.0', '1.99.99'), 1);
});

// ===== cross-line guard =====

test('versionOf applies the cross-line guard instead of guessing', () => {
  const docKey = DSL_VERSION_KEY;
  const otherKey = RUNTIME_DSL_VERSION_KEY;

  // own stamp present
  assert.equal(versionOf({ [docKey]: '0.2.0' }, docKey, otherKey, UNVERSIONED_DSL_VERSION), '0.2.0');
  // neither stamp: the document line has a legacy epoch
  assert.equal(versionOf({}, docKey, otherKey, UNVERSIONED_DSL_VERSION), UNVERSIONED_DSL_VERSION);
  // neither stamp on a line with no unversioned epoch
  assert.throws(() => versionOf({}, otherKey, docKey, null), (error) => {
    assert.ok(error instanceof DslVersionError);
    assert.equal(error.code, 'no_runtime_epoch');
    return true;
  });
  // sibling stamp only: neither silent answer is safe
  assert.throws(() => versionOf({ [otherKey]: '0.1.0' }, docKey, otherKey, UNVERSIONED_DSL_VERSION), (error) => {
    assert.equal(error.code, 'cross_line');
    return true;
  });
  // malformed own stamp
  assert.throws(() => versionOf({ [docKey]: 'v1' }, docKey, otherKey, UNVERSIONED_DSL_VERSION), (error) => {
    assert.equal(error.code, 'malformed_version');
    return true;
  });
});

test('a runtime aggregate is never lifted from an unstamped envelope', () => {
  assert.throws(() => migrateRuntime({ id: 'session-1' }), (error) => {
    assert.equal(error.code, 'no_runtime_epoch');
    return true;
  });
  const stamped = migrateRuntime({ [RUNTIME_DSL_VERSION_KEY]: RUNTIME_DSL_VERSION, id: 's' });
  assert.equal(stamped[RUNTIME_DSL_VERSION_KEY], RUNTIME_DSL_VERSION);
});

// ===== migration ladder integrity =====

test('the ladder is contiguous, pinned and terminates at the current version', () => {
  assert.ok(DSL_MIGRATIONS.length > 0);
  assert.equal(DSL_MIGRATIONS[0].from, UNVERSIONED_DSL_VERSION);
  assert.equal(DSL_MIGRATIONS[0].to, INITIAL_DSL_VERSION);
  for (let index = 1; index < DSL_MIGRATIONS.length; index += 1) {
    assert.equal(DSL_MIGRATIONS[index].from, DSL_MIGRATIONS[index - 1].to, 'ladder must be contiguous');
  }
  assert.equal(DSL_MIGRATIONS[DSL_MIGRATIONS.length - 1].to, DSL_VERSION);

  // Endpoints are pinned literals: re-pointing one would retroactively rewrite
  // the meaning of documents already stamped with it.
  const literals = DSL_MIGRATIONS.flatMap((entry) => [entry.from, entry.to]);
  assert.deepEqual(literals, [
    UNVERSIONED_DSL_VERSION,
    INITIAL_DSL_VERSION,
    INITIAL_DSL_VERSION,
    '0.2.0',
    '0.2.0',
    DSL_VERSION,
  ]);
});

test('the runtime ladder ships empty because the runtime line has no unversioned epoch', () => {
  assert.deepEqual(RUNTIME_DSL_MIGRATIONS, []);
});

// ===== migrate =====

test('migrate stamps an unversioned document and is idempotent', () => {
  const legacy = { stage: { id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2 }, scenes: [] };
  assert.equal(needsMigration(legacy), true);
  const once = migrate(legacy);
  assert.equal(once[DSL_VERSION_KEY], DSL_VERSION);
  const twice = migrate(once);
  assert.equal(twice, once, 'a current document is returned by identity');
  assert.equal(needsMigration(once), false);
});

test('migrate leaves a document written ahead of us untouched', () => {
  const ahead = { [DSL_VERSION_KEY]: '9.9.9', stage: { id: 's' }, scenes: [] };
  assert.equal(migrate(ahead), ahead);
  assert.equal(needsMigration(ahead), false);
});

test('migrate returns non-objects unchanged', () => {
  for (const value of [null, 42, 'x', []]) assert.equal(migrate(value), value);
});

test('a gap in the ladder is a loud failure, not a silent pass-through', () => {
  const broken = { ...aggregate(), [DSL_VERSION_KEY]: '0.0.1' };
  assert.throws(() => migrate(broken), (error) => {
    assert.equal(error.code, 'no_path');
    return true;
  });
});

// ===== legacy line geometry =====

test('the 0.2.0→0.3.0 step strips stray line geometry from every slide surface', () => {
  const dirtyLine = { type: 'line', left: 1, top: 2, width: 3, rotate: 45, height: 9, start: [0, 0], end: [1, 1] };
  const legacy = {
    [DSL_VERSION_KEY]: '0.2.0',
    stage: { id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2, whiteboard: [{ elements: [dirtyLine] }] },
    scenes: [
      slideScene({ content: { type: 'slide', canvas: { elements: [dirtyLine] } } }),
      slideScene({ id: 'scene-2', order: 1, whiteboards: [{ elements: [dirtyLine] }] }),
    ],
  };

  const migrated = migrate(legacy);
  const canvasLine = migrated.scenes[0].content.canvas.elements[0];
  assert.equal(canvasLine.rotate, undefined);
  assert.equal(canvasLine.height, undefined);
  assert.equal(canvasLine.left, 1, 'geometry that stays is preserved');
  assert.equal(migrated.scenes[1].whiteboards[0].elements[0].rotate, undefined);
  assert.equal(migrated.stage.whiteboard[0].elements[0].rotate, undefined);
  assert.equal(migrated[DSL_VERSION_KEY], DSL_VERSION);
  // input untouched
  assert.equal(legacy.scenes[0].content.canvas.elements[0].rotate, 45);
});

test('a clean document is returned by identity and other scene kinds are out of scope', () => {
  const clean = {
    [DSL_VERSION_KEY]: '0.2.0',
    stage: { id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2 },
    scenes: [
      slideScene(),
      { id: 'q', stageId: 'stage-1', type: 'quiz', title: 't', order: 1, content: { type: 'quiz', questions: [] } },
    ],
  };
  const migrated = migrate(clean);
  assert.equal(migrated.scenes[0], clean.scenes[0], 'clean slide shares by reference');
  assert.equal(migrated.scenes[1], clean.scenes[1], 'quiz passes through');
});

// ===== limits =====

test('depthBeyond stops at the first breaching depth and reports it', () => {
  assert.equal(depthBeyond({ a: 1 }, 5), null);
  assert.equal(depthBeyond({ a: { b: { c: 1 } } }, 2), 3);
  assert.equal(depthBeyond([[[]]], 1), 2);
});

// ===== sanitization =====

test('sanitizeText removes control characters and bounds length', () => {
  assert.equal(sanitizeText('a\u0000b\u0007c'), 'abc');
  assert.equal(sanitizeText('a\nb\tc'), 'a\nb\tc', 'tab and newline survive');
  assert.equal(sanitizeText('abcdef', 3), 'abc');
});

test('sanitizeUrl accepts only credential-free http(s)', () => {
  assert.equal(sanitizeUrl('https://example.com/a'), 'https://example.com/a');
  for (const bad of [
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'file:///etc/passwd',
    'blob:https://example.com/x',
    'https://user:pass@example.com/',
    'not a url',
  ]) {
    assert.equal(sanitizeUrl(bad), null, bad);
  }
});

test('sanitizeInteractiveHtml keeps scripts but removes frame-hijacking tags', () => {
  const html = '<html><head><base href="https://evil.example/"><meta http-equiv="refresh" content="0;url=https://evil.example/"></head><body><script>1</script></body></html>';
  const cleaned = sanitizeInteractiveHtml(html);
  assert.doesNotMatch(cleaned, /<base/i);
  assert.doesNotMatch(cleaned, /http-equiv/i);
  assert.match(cleaned, /<script>/, 'an interactive scene without scripts is not interactive');
});

test('sanitizeInteractiveHtml refuses an oversize payload', () => {
  assert.equal(sanitizeInteractiveHtml('x'.repeat(DSL_LIMITS.maxInlineHtmlBytes + 1)), null);
});

// ===== validation =====

test('a well-formed aggregate validates', () => {
  const result = validateStage(aggregate());
  assert.deepEqual(result.issues, []);
  assert.equal(result.ok, true);
});

test('the scene type must agree with its content discriminant', () => {
  const document = aggregate({ scenes: [slideScene({ content: { type: 'quiz', questions: [] } })] });
  const result = validateStage(document);
  assert.ok(result.issues.some((item) => item.code === 'content_type_mismatch'));
  assert.ok(result.issues.some((item) => item.path === 'scenes[0].content.type'));
});

test('an unknown scene type is rejected rather than passed to the renderer', () => {
  const document = aggregate({ scenes: [slideScene({ type: 'simulation' })] });
  const result = validateStage(document);
  assert.ok(result.issues.some((item) => item.code === 'scene_type_invalid'));
  // 3D/导图/编程 are widget types, not scene types
  assert.deepEqual([...SCENE_TYPES], ['slide', 'quiz', 'interactive', 'pbl']);
  assert.ok(WIDGET_TYPES.includes('visualization3d'));
});

test('scene order must be unique within a stage', () => {
  const document = aggregate({ scenes: [slideScene(), slideScene({ id: 'scene-2' })] });
  const result = validateStage(document);
  assert.ok(result.issues.some((item) => item.code === 'scene_order_duplicate'));
});

test('a scene whose stageId disagrees with its parent is rejected', () => {
  const document = aggregate({ scenes: [slideScene({ stageId: 'other' })] });
  assert.ok(validateStage(document).issues.some((item) => item.code === 'scene_stage_mismatch'));
});

test('an interactive scene needs a payload and a valid widget type', () => {
  const empty = aggregate({
    scenes: [slideScene({ type: 'interactive', content: { type: 'interactive' } })],
  });
  assert.ok(validateStage(empty).issues.some((item) => item.code === 'interactive_payload_missing'));

  const badWidget = aggregate({
    scenes: [slideScene({
      type: 'interactive',
      content: { type: 'interactive', html: '<b>x</b>', widgetType: 'hologram' },
    })],
  });
  assert.ok(validateStage(badWidget).issues.some((item) => item.code === 'widget_type_invalid'));

  const badUrl = aggregate({
    scenes: [slideScene({
      type: 'interactive',
      content: { type: 'interactive', url: 'javascript:alert(1)' },
    })],
  });
  assert.ok(validateStage(badUrl).issues.some((item) => item.code === 'interactive_url_rejected'));
});

test('unknown action types are rejected, including widget action casing', () => {
  const document = aggregate({
    scenes: [slideScene({
      actions: [
        { id: 'a1', type: 'speech', text: 'hi' },
        { id: 'a2', type: 'teleport' },
      ],
    })],
  });
  const issues = validateStage(document).issues;
  assert.ok(issues.some((item) => item.code === 'action_type_invalid'));
  assert.ok(ACTION_TYPES.includes('widget_setState'), 'camelCase widget action is part of the contract');
});

test('a speech action without text is rejected', () => {
  const document = aggregate({ scenes: [slideScene({ actions: [{ id: 'a1', type: 'speech' }] })] });
  assert.ok(validateStage(document).issues.some((item) => item.code === 'speech_text_missing'));
});

test('scene and agent counts are bounded', () => {
  const tooManyScenes = aggregate({
    scenes: Array.from({ length: DSL_LIMITS.maxScenes + 1 }, (_value, index) =>
      slideScene({ id: `s${index}`, order: index })),
  });
  assert.ok(validateStage(tooManyScenes).issues.some((item) => item.code === 'scenes_too_many'));

  const tooManyAgents = aggregate({
    stage: {
      id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2,
      agentIds: Array.from({ length: DSL_LIMITS.maxAgents + 1 }, (_v, i) => `a${i}`),
    },
  });
  assert.ok(validateStage(tooManyAgents).issues.some((item) => item.code === 'stage_agents_too_many'));
});

test('a document deeper than the limit is rejected before anything walks it', () => {
  let deep = {};
  const root = deep;
  for (let index = 0; index < DSL_LIMITS.maxDepth + 2; index += 1) {
    deep.child = {};
    deep = deep.child;
  }
  const document = aggregate({ stage: { id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2, style: root } });
  assert.ok(validateStage(document).issues.some((item) => item.code === 'document_too_deep'));
});

// ===== write path =====

test('prepareStage migrates, sanitizes and stamps in one pass', () => {
  const legacy = {
    stage: { id: 'stage-1', name: '演示\u0000课堂', createdAt: 1, updatedAt: 2 },
    scenes: [slideScene({ title: '标题\u0007', content: { type: 'slide', canvas: { elements: [] } } })],
  };
  const { document, migrated } = prepareStage(legacy);
  assert.equal(migrated, true);
  assert.equal(document[DSL_VERSION_KEY], DSL_VERSION);
  assert.equal(document.stage.name, '演示课堂');
  assert.equal(document.scenes[0].title, '标题');
});

test('prepareStage refuses an oversize document instead of truncating it', () => {
  const huge = aggregate({ stage: { id: 's', name: 'x'.repeat(DSL_LIMITS.maxDocumentBytes + 10), createdAt: 1, updatedAt: 2 } });
  assert.throws(() => prepareStage(huge), (error) => {
    assert.ok(error instanceof DslLimitError);
    assert.equal(error.limit, 'maxDocumentBytes');
    return true;
  });
});

test('prepareStage refuses an oversize inline html payload by name', () => {
  const document = aggregate({
    scenes: [slideScene({
      type: 'interactive',
      content: { type: 'interactive', html: 'x'.repeat(DSL_LIMITS.maxInlineHtmlBytes + 1) },
    })],
  });
  assert.throws(() => prepareStage(document), (error) => {
    assert.equal(error.limit, 'maxInlineHtmlBytes');
    return true;
  });
});

test('prepareStage surfaces every validation issue at once', () => {
  const document = aggregate({
    scenes: [slideScene({ stageId: 'other', content: { type: 'quiz', questions: [] } })],
  });
  assert.throws(() => prepareStage(document), (error) => {
    assert.ok(error instanceof DslValidationError);
    assert.ok(error.issues.length >= 2, 'a caller should not have to fix one field per round trip');
    return true;
  });
});

test('prepareStage strips frame-hijacking tags from inline html', () => {
  const { document } = prepareStage(aggregate({
    scenes: [slideScene({
      type: 'interactive',
      content: { type: 'interactive', html: '<meta http-equiv="refresh" content="0"><b>ok</b>' },
    })],
  }));
  assert.doesNotMatch(document.scenes[0].content.html, /http-equiv/i);
  assert.match(document.scenes[0].content.html, /<b>ok<\/b>/);
});

test('a prepared document survives a second pass unchanged', () => {
  const first = prepareStage(aggregate()).document;
  const second = prepareStage(first);
  assert.equal(second.migrated, false);
  assert.deepEqual(second.document, first);
});
