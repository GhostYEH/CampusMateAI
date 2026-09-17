/**
 * 课程详情"停止查看"后的轮询竞态。
 *
 * 真实故障：`stopPoll()` 只 `clearTimeout`。学生点"停止查看"时，
 * 一次 `getInteractiveClassroomJob` 可能已经在途；它返回时课程 epoch 没变，
 * 于是又 `schedulePoll(...)` 把轮询重新点着 —— 学生说不看了，后台还在打后端。
 *
 * 修复：轮询有自己的 token。"停止查看"递增 token；在途响应在**写状态之前**
 * 与**重新安排之前**都要确认 token 仍有效。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import "./helpers/setup-globals.mjs";
import { createPollScope } from "../src/data/pollScope.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

const flush = () => new Promise((resolve) => setImmediate(resolve));

function createScheduler() {
  let nextId = 1;
  const tasks = new Map();
  return {
    schedule(fn) {
      const id = nextId;
      nextId += 1;
      tasks.set(id, fn);
      return id;
    },
    cancel(id) {
      tasks.delete(id);
    },
    pending: () => tasks.size,
    /** 触发当前已安排的定时器，但**不 await** 回调（回调里可能还在等网络）。 */
    fire() {
      const entries = [...tasks.values()];
      tasks.clear();
      entries.forEach((fn) => {
        void fn();
      });
      return entries.length;
    },
  };
}

function makeScope(scheduler) {
  return createPollScope({ schedule: scheduler.schedule, cancel: scheduler.cancel });
}

/**
 * 模拟一轮真实的轮询：出发 → 请求在途 → （可能被停止）→ 响应返回。
 * 返回 { release }，由测试决定"响应什么时候回来"。
 */
function startRound(scope, scheduler, log) {
  const myToken = scope.begin();
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const armed = scope.arm(async () => {
    scope.disarm();
    if (!scope.isCurrent(myToken)) return;
    log.push("fetch");
    await gate; // 网络在途
    if (!scope.isCurrent(myToken)) return;
    log.push("apply");
    scope.arm(async () => log.push("fetch-again"), 1000, myToken);
    log.push("rearmed");
  }, 1000, myToken);
  assert.equal(armed, true);
  return { release, token: myToken };
}

test("停止查看后，在途轮询响应不得写状态、也不得重新安排轮询", async () => {
  const scheduler = createScheduler();
  const scope = makeScope(scheduler);
  const log = [];

  const { release } = startRound(scope, scheduler, log);
  scheduler.fire(); // 定时器触发，请求发出
  await flush();
  assert.deepEqual(log, ["fetch"], "应当已经发出一次请求");

  scope.stop(); // 学生点"停止查看"
  release(); // 响应此刻才回来
  await flush();

  assert.deepEqual(log, ["fetch"], "停止查看后不得写状态，更不得重新安排轮询");
  assert.equal(scheduler.pending(), 0, "不得留下任何已安排的轮询");
  assert.equal(scope.armed, false);
});

test("停止查看会取消尚未触发的定时器", () => {
  const scheduler = createScheduler();
  const scope = makeScope(scheduler);
  scope.arm(() => {}, 1000);
  assert.equal(scope.armed, true);
  assert.equal(scheduler.pending(), 1);

  scope.stop();

  assert.equal(scope.armed, false);
  assert.equal(scheduler.pending(), 0, "已安排的定时器必须被真正取消");
});

test("未停止时轮询正常继续（保护不能把正常路径也拦掉）", async () => {
  const scheduler = createScheduler();
  const scope = makeScope(scheduler);
  const log = [];

  const { release } = startRound(scope, scheduler, log);
  scheduler.fire();
  await flush();
  release();
  await flush();

  assert.deepEqual(log, ["fetch", "apply", "rearmed"]);
  assert.equal(scheduler.pending(), 1, "未终态时应继续轮询");
});

test("arm 在 token 失效时拒绝安排（双保险）", () => {
  const scheduler = createScheduler();
  const scope = makeScope(scheduler);
  const stale = scope.begin();
  scope.stop();

  assert.equal(scope.arm(() => {}, 1000, stale), false, "过期 token 不得安排轮询");
  assert.equal(scope.armed, false);
  assert.equal(scheduler.pending(), 0);
});

test("课程详情面板使用轮询作用域，停止查看会作废在途响应", () => {
  const src = read("src/components/interactive/InteractiveClassroomPanel.jsx");
  assert.match(src, /createPollScope/);
  // 不得再用裸 clearTimeout 冒充"停止"
  assert.doesNotMatch(src, /pollTimer/);
  assert.match(src, /pollScope\.stop\(\)/);
  // 在途响应写状态前必须校验 token
  assert.match(src, /pollScope\.isCurrent\(myToken\)/);
  assert.match(src, /onStopViewing=\{\(\) => \{\s*stopPoll\(\);/);
});
