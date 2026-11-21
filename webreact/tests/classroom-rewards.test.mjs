/**
 * 课堂游戏化结算契约。
 *
 * 这里钉的是"分数与成就什么时候算"：重复翻页不能重复加分、重做测验不能刷新
 * 连击、坏存档不能把整份进度清零。界面文案不在这里断言。
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  emptyRewards,
  gradeScene,
  levelOf,
  normalizeRewards,
  readRewards,
  rewardsKey,
  sceneMap,
  unlockedAchievements,
  visitScene,
  writeRewards,
  XP_COMBO_BONUS,
  XP_PER_CORRECT,
  XP_PER_SCENE,
  XP_PERFECT_BONUS,
} from "../src/features/magicclass/rewardsModel.js";

test("levelOf 从 1 级开始，满 100 XP 升一级", () => {
  assert.deepEqual(levelOf(0), { level: 1, xp: 0, inLevel: 0, toNext: 100, progress: 0 });
  assert.equal(levelOf(99).level, 1);
  assert.equal(levelOf(100).level, 2);
  assert.equal(levelOf(260).level, 3);
  assert.equal(levelOf(260).inLevel, 60);
  assert.equal(levelOf(-5).level, 1);
});

test("首次访问某页只加一次 XP，重复访问不再结算", () => {
  const seeded = emptyRewards();
  const first = visitScene(seeded, "scene-1", { totalScenes: 4 });
  assert.equal(first.awarded, XP_PER_SCENE);
  assert.equal(first.state.xp, XP_PER_SCENE);
  assert.equal(first.state.visited["scene-1"], true);

  const again = visitScene(first.state, "scene-1", { totalScenes: 4 });
  assert.equal(again.awarded, 0);
  assert.equal(again.state.xp, XP_PER_SCENE);
});

test("同一个场景重复交卷不重复加分，也不刷新连击", () => {
  const visited = visitScene(emptyRewards(), "q1", { totalScenes: 2 }).state;
  const first = gradeScene(visited, { sceneId: "q1", correct: 2, total: 2 }, { totalScenes: 2 });
  assert.equal(first.awarded, 2 * XP_PER_CORRECT + XP_PERFECT_BONUS);
  assert.equal(first.combo, 1);

  const second = gradeScene(first.state, { sceneId: "q1", correct: 2, total: 2 }, { totalScenes: 2 });
  assert.equal(second.awarded, 0);
  assert.equal(second.combo, 1);
  assert.equal(second.state.xp, first.state.xp);
});

test("答对累加连击并给连击奖励，答错清零", () => {
  let state = emptyRewards();
  state = gradeScene(state, { sceneId: "q1", correct: 1, total: 2 }, { totalScenes: 3 }).state;
  assert.equal(state.combo, 1);

  const second = gradeScene(state, { sceneId: "q2", correct: 2, total: 2 }, { totalScenes: 3 });
  assert.equal(second.combo, 2);
  assert.equal(second.awarded, 2 * XP_PER_CORRECT + XP_PERFECT_BONUS + XP_COMBO_BONUS);
  state = second.state;
  assert.equal(state.bestCombo, 2);

  const failed = gradeScene(state, { sceneId: "q3", correct: 0, total: 2 }, { totalScenes: 3 });
  assert.equal(failed.combo, 0);
  assert.equal(failed.awarded, 0);
  assert.equal(failed.state.bestCombo, 2);
});

test("成就按真实进度解锁，重复计算不会重复写", () => {
  const state = { ...emptyRewards(), visited: { a: true, b: true }, bestCombo: 3, quiz: { q: { correct: 2, total: 2, perfect: true } } };
  const unlocked = unlockedAchievements(state, { totalScenes: 4 });
  assert.deepEqual(new Set(unlocked), new Set(["first_scene", "half_route", "combo_3", "perfect_quiz"]));

  const withAll = { ...state, visited: { a: true, b: true, c: true, d: true }, achievements: unlocked };
  assert.deepEqual(unlockedAchievements(withAll, { totalScenes: 4 }), ["finish_route"]);
});

test("坏存档只丢坏字段，不把整份进度清零", () => {
  const normalized = normalizeRewards({
    xp: "80",
    visited: { keep: true, drop: false },
    quiz: { ok: { correct: 3, total: 3, perfect: true }, bad: null },
    combo: -2,
    achievements: ["combo_3", "unknown"],
  });
  assert.equal(normalized.xp, 80);
  assert.deepEqual(normalized.visited, { keep: true });
  assert.deepEqual(Object.keys(normalized.quiz), ["ok"]);
  assert.equal(normalized.combo, 0);
  assert.deepEqual(normalized.achievements, ["combo_3"]);
});

test("关卡地图合并播放计划与本地完成记录", () => {
  const state = { ...emptyRewards(), visited: { s1: true }, quiz: { s2: { correct: 1, total: 1, perfect: true } } };
  const map = sceneMap(state, [{ id: "s1" }, { id: "s2" }, { id: "s3" }], 1);
  assert.equal(map.length, 3);
  assert.equal(map[0].visited, true);
  assert.equal(map[1].quizzed, true);
  assert.equal(map[1].current, true);
  assert.equal(map[2].title, "第 3 页");
});

test("localStorage 不可用时读成空进度、写入返回 false", () => {
  const key = rewardsKey({ courseId: "c", workspaceId: "w", stageId: "s" });
  assert.match(key, /^campusmate:classroom-rewards:v1:c:w:s$/);
  assert.equal(readRewards(null, key).xp, 0);
  assert.equal(writeRewards(null, key, emptyRewards()), false);
});
