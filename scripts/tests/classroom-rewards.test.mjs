import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const canonical = path.join(root, 'android/app/src/main/assets/classroom-rewards.js');
const iosCopy = path.join(root, 'ios/CampusMate/Resources/classroom-rewards.js');
const fixturePath = path.join(root, 'android/app/src/test/resources/classroom-rewards-events.json');

const require = createRequire(import.meta.url);
const rules = require(canonical);
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));

test('Android and iOS reward scripts are byte-identical', () => {
  assert.equal(readFileSync(canonical, 'utf8'), readFileSync(iosCopy, 'utf8'));
});

test('script constants match the shared fixture contract', () => {
  assert.equal(rules.VISIT_XP, 12);
  assert.equal(rules.CORRECT_XP, 6);
  assert.equal(rules.PERFECT_BONUS, 20);
  assert.equal(rules.COMBO_BONUS, 12);
  assert.equal(rules.LEVEL_STEP, 100);
  assert.deepEqual(
    [...rules.ACHIEVEMENT_IDS].sort(),
    ['combo_3', 'combo_5', 'finish_route', 'first_scene', 'half_route', 'perfect_quiz'],
  );
});

test('shared event fixture drives the web rules', () => {
  let state = rules.empty();
  fixture.events.forEach((event, index) => {
    const result = event.type === 'visit'
      ? rules.visit(state, event.scene, fixture.scenes, '2026-11-21T00:00:00Z')
      : rules.grade(state, event.scene, event.correct, event.total, fixture.scenes, '2026-11-21T00:00:00Z');
    assert.equal(result.awardedXp, event.expect.awardedXp, `event ${index} awardedXp`);
    assert.equal(result.state.xp, event.expect.xp, `event ${index} xp`);
    assert.equal(result.combo, event.expect.combo, `event ${index} combo`);
    assert.deepEqual([...result.unlocked].sort(), [...event.expect.unlocked].sort(), `event ${index} unlocked`);
    state = result.state;
  });

  const final = fixture.final;
  assert.equal(state.xp, final.xp);
  assert.equal(Object.keys(state.visited).length, final.visited);
  assert.equal(Object.keys(state.quiz).length, final.quizCount);
  assert.equal(state.combo, final.combo);
  assert.equal(state.bestCombo, final.bestCombo);
  assert.deepEqual([...state.achievements].sort(), [...final.achievements].sort());
  const level = rules.levelOf(state.xp);
  assert.equal(level.level, final.level);
  assert.equal(level.inLevel, final.inLevel);
});

test('redo does not award twice and non-perfect breaks the combo', () => {
  let state = rules.empty();
  let outcome = rules.grade(state, 'q-redo', 2, 2, 4, 't');
  assert.equal(outcome.awardedXp, 32);
  state = outcome.state;

  outcome = rules.grade(state, 'q-redo', 2, 2, 4, 't');
  assert.equal(outcome.awardedXp, 0, '同一场景重做不再结算');

  outcome = rules.grade(state, 'q-miss', 0, 2, 4, 't');
  assert.equal(outcome.awardedXp, 0);
  assert.equal(outcome.combo, 0, '答错清零连击');
});

test('quiz payload applies only after submit/review and uses results length', () => {
  let state = rules.empty();
  const draft = rules.gradeFromAttempt(state, 'q-draft', {
    state: { phase: 'draft', results: [] },
  }, 4, 't');
  assert.equal(draft.applied, false);

  const reviewed = rules.gradeFromAttempt(state, 'q-payload', {
    state: {
      phase: 'reviewed',
      results: [{ correct: true }, { correct: true }, { correct: null }],
    },
  }, 4, 't');
  assert.equal(reviewed.applied, true);
  assert.equal(reviewed.awardedXp, 12, '2/3 正确：2×6 分，无满分奖励');
  assert.equal(reviewed.combo, 1);
});
