/** Invariants for the replayable functional patch layer. */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { applyFeatureText, restoreFeatureText } from '../magicclass-brand.mjs';
import { FEATURE_ADDED_FILES, FEATURE_EDITS } from '../magicclass-feature.patch.mjs';

test('functional feature edits are explicitly reversible exact-text replacements', () => {
  const edit = {
    file: 'app/classroom/page.tsx',
    from: 'const state = "upstream";',
    to: 'const state = "approved-feature";',
  };
  const upstream = 'before\nconst state = "upstream";\nafter\n';
  const applied = applyFeatureText(upstream, edit);

  assert.equal(applied.changed, true);
  assert.equal(applied.text, 'before\nconst state = "approved-feature";\nafter\n');
  assert.equal(applyFeatureText(applied.text, edit).changed, false, 'apply must be idempotent');
  assert.equal(restoreFeatureText(applied.text, edit), upstream, 'inverse must recover original bytes');
});

test('functional feature edits reject partial or ambiguous states', () => {
  const edit = { file: 'app/classroom/page.tsx', from: 'old()', to: 'new()' };
  assert.throws(() => applyFeatureText('old() new()', edit), /状态不明确/);
  assert.throws(() => applyFeatureText('old() old()', edit), /状态不明确/);
  assert.throws(() => restoreFeatureText('new() old()', edit), /状态不明确/);
});

test('the checked in functional patch list uses normalized app paths and exact replacements', () => {
  for (const edit of FEATURE_EDITS) {
    assert.equal(typeof edit.file, 'string');
    assert.ok(edit.file.length > 0);
    assert.equal(edit.file.includes('\\'), false, `${edit.file} must use forward slashes`);
    assert.equal(edit.file.startsWith('/'), false, `${edit.file} must be app relative`);
    assert.equal(typeof edit.from, 'string');
    assert.ok(edit.from.length > 0);
    assert.equal(typeof edit.to, 'string');
    assert.ok(edit.to.length > 0);
    assert.notEqual(edit.from, edit.to);
  }
  for (const entry of FEATURE_ADDED_FILES) {
    assert.equal(typeof entry.file, 'string');
    assert.ok(entry.file.length > 0);
    assert.equal(entry.file.includes('\\'), false, `${entry.file} must use forward slashes`);
    assert.equal(entry.file.startsWith('/'), false, `${entry.file} must be app relative`);
    assert.equal(typeof entry.content, 'string');
    assert.ok(entry.content.length > 0);
  }
});
