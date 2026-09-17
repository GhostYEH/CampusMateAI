/**
 * P1-4 —— 课程切换的迟到回写防护。
 *
 * 真实场景：用户在 A 课程发起 status/plan/history/poll/composition 请求后立刻切到 B。
 * B 的 effect 会重新初始化，而 A 的响应可能**最后**才回来。
 * 修复前共用一个 `alive` 布尔量：B 的 effect 把它设回 true，A 的迟到响应于是被
 * 当成有效结果，覆盖 B 的界面（成功、错误、finally 三条路径都会中招）。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import "./helpers/setup-globals.mjs";
import { createEpochGuard } from "../src/data/epochGuard.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

/** 用 guard 模拟"一个异步任务出发 → 写回"的完整生命周期。 */
function makeTask(guard, label, log) {
  const myEpoch = guard.current;
  return {
    label,
    /** 模拟成功后写回 */
    succeed: () => guard.runIfCurrent(myEpoch, () => log.push(`${label}:success`)),
    /** 模拟失败后写回 */
    fail: () => guard.runIfCurrent(myEpoch, () => log.push(`${label}:error`)),
    /** 模拟 finally 里的清理 */
    settle: () => guard.runIfCurrent(myEpoch, () => log.push(`${label}:finally`)),
  };
}

test("切换课程后，A 的迟到成功结果不得写回", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log); // A 出发
  guard.next(); // 切到 B
  const b = makeTask(guard, "B", log); // B 出发

  b.succeed(); // B 先返回
  a.succeed(); // A 最后才返回
  assert.deepEqual(log, ["B:success"], "A 的迟到成功必须被丢弃");
});

test("切换课程后，A 的迟到错误结果不得写回", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log);
  guard.next();
  const b = makeTask(guard, "B", log);

  b.succeed();
  a.fail();
  assert.deepEqual(log, ["B:success"], "A 的迟到错误不得污染 B 的界面");
});

test("切换课程后，A 的迟到 finally 不得覆盖 B 的 loading 状态", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log);
  guard.next();
  const b = makeTask(guard, "B", log);

  b.succeed();
  a.settle(); // A 的 finally 若生效，会把 B 的 itemsLoading 置回 false 之外的状态
  assert.deepEqual(log, ["B:success"], "A 的迟到 finally 必须被丢弃");
});

test("连续快速切换 A→B→C，只有 C 的结果生效", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log);
  guard.next();
  const b = makeTask(guard, "B", log);
  guard.next();
  const c = makeTask(guard, "C", log);

  c.succeed();
  b.succeed();
  a.fail();
  a.settle();
  assert.deepEqual(log, ["C:success"]);
});

test("卸载（组件销毁）会作废所有在途请求", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log);
  guard.invalidate(); // 卸载
  a.succeed();
  a.fail();
  a.settle();
  assert.deepEqual(log, []);
});

test("同一作用域内的结果正常写回（没有误伤）", () => {
  const guard = createEpochGuard();
  const log = [];
  const a = makeTask(guard, "A", log);
  a.succeed();
  a.settle();
  assert.deepEqual(log, ["A:success", "A:finally"]);
});

test("runIfCurrent 返回是否真的执行", () => {
  const guard = createEpochGuard();
  const myEpoch = guard.current;
  assert.equal(guard.runIfCurrent(myEpoch, () => {}), true);
  guard.next();
  assert.equal(guard.runIfCurrent(myEpoch, () => {}), false);
});

// ===== 接线：面板必须真的用 epoch，而不是共享布尔量 =====

test("课程面板使用 epoch 守卫而不是共享 alive 布尔量", () => {
  const src = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(src, /createEpochGuard/);
  assert.match(src, /guard\.next\(\)/);
  assert.match(src, /guard\.invalidate\(\)/);
  assert.match(src, /isCurrent\(myEpoch\)/);
  assert.doesNotMatch(src, /alive\.current/, "不得再用共享 alive 布尔量");
});

test("切换课程时清空上一门课的全部状态", () => {
  const src = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  const effect = src.slice(src.indexOf("const myEpoch = guard.next()"));
  const body = effect.slice(0, effect.indexOf("}, [courseId"));
  for (const cleared of [
    "setSession(null)",
    "setComposition(null)",
    "setPlan(null)",
    "setItems([])",
    "setBrief(EMPTY_BRIEF)",
    "setError(\"\")",
    "setNotice(\"\")",
    "setPolling(false)",
    "stopPoll()",
  ]) {
    assert.ok(body.includes(cleared), `切换课程时必须清理: ${cleared}`);
  }
});

test("每个异步写回都经过 epoch 校验", () => {
  const src = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  // status / history / plan / composition / poll / generate 六条路径
  const checks = src.match(/isCurrent\(myEpoch\)/g) || [];
  assert.ok(checks.length >= 10, `epoch 校验点过少（${checks.length}），可能有路径漏检`);
});
