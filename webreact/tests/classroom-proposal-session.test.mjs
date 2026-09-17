/**
 * 阶段 P1-3 —— CPM 提案卡的跨提案 / 跨课程 / 跨账号状态隔离（真实行为测试）。
 *
 * 这些测试**驱动真正的编排器**（`classroomProposalSession`），用可控的
 * 假 API + 手动调度器复现"迟到响应"的真实时序，而不是对源码做字符串断言。
 *
 * 修复前的三个真实故障：
 *   1. 只用一个共享 `alive` 布尔量：新提案的 effect 把它设回 true，
 *      旧提案的迟到响应于是被写进新提案的界面（success / error / finally 全中招）。
 *   2. 恢复 key 只按 courseId：同一门课的第二个提案复用第一个提案的 jobId 与深链。
 *   3. 恢复 key 不绑身份：账号 A 的任务被账号 B 恢复出来。
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./helpers/setup-globals.mjs";
import {
  createProposalSession,
} from "../src/data/classroomProposalSession.js";
import {
  JOB_PHASE,
  proposalFingerprint,
  purgeOtherIdentityJobs,
  storageKey,
} from "../src/data/classroomJobMachine.js";

// ===== 假 API + 手动调度器 =====

function createFakeApi() {
  const calls = { create: [], get: [], decide: [] };
  const pending = [];
  const settle = () => new Promise((resolve) => setImmediate(resolve));

  const api = {
    createAgentJob(payload) {
      calls.create.push(payload);
      return new Promise((resolve, reject) => pending.push({ kind: "create", resolve, reject }));
    },
    getAgentJob(jobId) {
      calls.get.push(jobId);
      return new Promise((resolve, reject) => pending.push({ kind: "get", jobId, resolve, reject }));
    },
    decideAgentApproval(approvalId, decision, reason) {
      calls.decide.push({ approvalId, decision, reason });
      return new Promise((resolve, reject) =>
        pending.push({ kind: "decide", approvalId, decision, resolve, reject }),
      );
    },
  };

  function take(kind) {
    const index = pending.findIndex((item) => item.kind === kind);
    if (index < 0) return null;
    return pending.splice(index, 1)[0];
  }

  return {
    api,
    calls,
    pending,
    settle,
    resolveCreate(job) {
      const item = take("create");
      assert.ok(item, "没有待决的 create 请求");
      item.resolve(job);
      return settle();
    },
    rejectCreate(err) {
      const item = take("create");
      assert.ok(item, "没有待决的 create 请求");
      item.reject(err);
      return settle();
    },
    resolveGet(job) {
      const item = take("get");
      assert.ok(item, "没有待决的 get 请求");
      item.resolve(job);
      return settle();
    },
    rejectGet(err) {
      const item = take("get");
      assert.ok(item, "没有待决的 get 请求");
      item.reject(err);
      return settle();
    },
    resolveDecide(value = { status: "APPROVED" }) {
      const item = take("decide");
      assert.ok(item, "没有待决的 decide 请求");
      item.resolve(value);
      return settle();
    },
    rejectDecide(err) {
      const item = take("decide");
      assert.ok(item, "没有待决的 decide 请求");
      item.reject(err);
      return settle();
    },
  };
}

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
    pendingCount: () => tasks.size,
    /**
     * 跑一轮当前待触发的定时器。
     *
     * **不 await** 回调本身：真实世界里 timer 回调是"发射后不管"的，
     * 回调内部的 `await api.getAgentJob(...)` 会一直挂到测试显式 resolve。
     * 若这里 await，就会与"响应迟到"的用例互相死锁。
     */
    async step() {
      const entries = [...tasks.values()];
      tasks.clear();
      for (const fn of entries) {
        void fn();
      }
      await new Promise((resolve) => setImmediate(resolve));
      return entries.length;
    },
    async drain(limit = 30) {
      for (let i = 0; i < limit; i += 1) {
        if (tasks.size === 0) return i;
        await this.step();
      }
      return limit;
    },
  };
}

const JOB = (overrides = {}) => ({
  job_id: "job_1",
  status: "SUCCEEDED",
  input_ref: { session_id: "om_1", deep_link: "/courses/c1?tab=mentoring&session=om_1" },
  ...overrides,
});

const PROPOSAL = (overrides = {}) => ({
  id: "interactive-classroom",
  proposal_id: "icp_aaa",
  course_id: "c1",
  course_name: "高等数学",
  mode: "review",
  mode_label: "考前复习",
  available: true,
  requires_confirmation: true,
  job_kind: "interactive_classroom",
  ...overrides,
});

function setup({ proposal = PROPOSAL(), identity = "user_a", storage } = {}) {
  const fake = createFakeApi();
  const scheduler = createScheduler();
  const store = storage || globalThis.localStorage;
  const session = createProposalSession({
    proposal,
    identity,
    api: fake.api,
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancel,
    pollFallbackMs: 1500,
  });
  // 用真实的 localStorage 语义（key 里已经含身份与指纹）
  return { fake, scheduler, session, store };
}

test.beforeEach(() => globalThis.localStorage.clear());

// ===== 1. 不同提案得到不同指纹 / 不同恢复 key =====

test("不同提案、不同课程、不同模式、不同账号都得到不同的恢复 key", () => {
  const a = storageKey({
    identity: "u1",
    courseId: "c1",
    fingerprint: proposalFingerprint({ identity: "u1", proposal: PROPOSAL() }),
  });
  const sameProposalOtherAccount = storageKey({
    identity: "u2",
    courseId: "c1",
    fingerprint: proposalFingerprint({ identity: "u2", proposal: PROPOSAL() }),
  });
  const otherCourse = storageKey({
    identity: "u1",
    courseId: "c2",
    fingerprint: proposalFingerprint({
      identity: "u1",
      proposal: PROPOSAL({ course_id: "c2" }),
    }),
  });
  const otherMode = storageKey({
    identity: "u1",
    courseId: "c1",
    fingerprint: proposalFingerprint({
      identity: "u1",
      proposal: PROPOSAL({ mode: "quiz" }),
    }),
  });
  const secondProposal = storageKey({
    identity: "u1",
    courseId: "c1",
    fingerprint: proposalFingerprint({
      identity: "u1",
      proposal: PROPOSAL({ proposal_id: "icp_bbb" }),
    }),
  });
  const keys = new Set([a, sameProposalOtherAccount, otherCourse, otherMode, secondProposal]);
  assert.equal(keys.size, 5, "五种维度必须两两隔离");
});

// ===== 2. A 未完成时切到 B：A 的迟到响应不得写进 B =====

test("A 提案未完成时切到 B，A 的迟到成功响应不得写进 B", async () => {
  const { fake, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();

  // 切到 B（同一门课、不同提案）
  session.update(PROPOSAL({ proposal_id: "icp_B" }), "user_a");
  assert.equal(session.getState().phase, JOB_PHASE.IDLE, "新提案必须重置状态");

  // A 的创建响应此刻才回来
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));

  assert.equal(session.getState().jobId, null, "A 的 jobId 不得写进 B");
  assert.equal(session.getState().phase, JOB_PHASE.IDLE);
});

test("A 提案未完成时切到 B，A 的迟到错误响应不得写进 B", async () => {
  const { fake, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();
  session.update(PROPOSAL({ proposal_id: "icp_B" }), "user_a");

  await fake.rejectCreate({ response: { data: { message: "A 的失败" } } });
  assert.equal(session.getState().phase, JOB_PHASE.IDLE, "B 不得显示 A 的错误");
  assert.equal(session.getState().error, "");
});

test("A 的迟到轮询结果不得写进 B（同一门课，不同提案）", async () => {
  const { fake, scheduler, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step(); // 触发 A 的第一次 poll

  // A 的 get 还在途，切到 B
  session.update(PROPOSAL({ proposal_id: "icp_B" }), "user_a");
  await fake.resolveGet(JOB({ job_id: "job_A" }));
  await scheduler.drain();

  const state = session.getState();
  assert.equal(state.jobId, null, "B 不得继承 A 的 jobId");
  assert.equal(state.deepLink, null, "B 不得继承 A 的深链");
  assert.equal(state.phase, JOB_PHASE.IDLE);
});

test("A 成功后再收到 B：B 必须干净，不显示旧 job / 旧错误 / 旧深链", async () => {
  const { fake, scheduler, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step();
  await fake.resolveGet(JOB({ job_id: "job_A" }));
  await scheduler.drain();

  const done = session.getState();
  assert.equal(done.phase, JOB_PHASE.SUCCEEDED);
  assert.match(done.deepLink, /session=om_1/);

  session.update(PROPOSAL({ proposal_id: "icp_B", mode: "quiz" }), "user_a");
  const fresh = session.getState();
  assert.equal(fresh.phase, JOB_PHASE.IDLE);
  assert.equal(fresh.jobId, null);
  assert.equal(fresh.deepLink, null);
  assert.equal(fresh.error, "");
  assert.equal(fresh.created, false, "新提案必须能再次确认");
});

// ===== 3. 同一个 proposal 重挂载 → 继续同一个 job =====

test("同一个提案重挂载：恢复同一个 job，且绝不重新创建", async () => {
  const { fake, scheduler, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step();

  // 组件重挂载：同一个提案对象（或同内容的新对象）
  const createdBefore = fake.calls.create.length;
  session.update(PROPOSAL({ proposal_id: "icp_A" }), "user_a");
  assert.equal(fake.calls.create.length, createdBefore, "同一提案不得重复创建任务");
  assert.equal(session.getState().jobId, "job_A", "必须继续同一个 job");
});

test("页面刷新（新会话对象）后按已保存的 jobId 恢复，不重新创建", async () => {
  const { fake, scheduler, session } = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step();

  // 刷新 = 新的会话对象，但 localStorage 仍在
  const second = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }) });
  second.session.restore();
  assert.equal(second.fake.calls.create.length, 0, "恢复不得创建新任务");
  await second.scheduler.step();
  assert.deepEqual(second.fake.calls.get, ["job_A"], "必须订阅同一个 job");
});

// ===== 4. 跨账号隔离 =====

test("账号 A 的任务不会被账号 B 恢复", async () => {
  const { fake, scheduler, session } = setup({
    proposal: PROPOSAL({ proposal_id: "icp_A" }),
    identity: "user_a",
  });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step();

  // B 登录后拿到**同样内容**的提案
  const b = setup({ proposal: PROPOSAL({ proposal_id: "icp_A" }), identity: "user_b" });
  b.session.restore();
  assert.equal(b.session.getState().jobId, null, "B 不得恢复 A 的 job");
  assert.equal(b.fake.calls.get.length, 0);
});

test("logout 后清除其他身份遗留的恢复记录", async () => {
  const { fake, scheduler, session } = setup({ identity: "user_a" });
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_A", status: "QUEUED", input_ref: {} }));
  await scheduler.step();
  assert.ok(globalThis.localStorage.getItem(storageKey(session.getScope())), "应已持久化");

  const removed = purgeOtherIdentityJobs("user_b");
  assert.equal(removed, 1);
  assert.equal(globalThis.localStorage.getItem(storageKey(session.getScope())), null);
});

// ===== 5. 终态与轮询 =====

test("终态必须停止轮询", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_1", status: "QUEUED", input_ref: {} }));

  await scheduler.step();
  await fake.resolveGet(JOB({ job_id: "job_1" })); // SUCCEEDED + deep_link
  await scheduler.drain();

  assert.equal(session.getState().phase, JOB_PHASE.SUCCEEDED);
  assert.equal(scheduler.pendingCount(), 0, "终态后不得再安排轮询");
  const before = fake.calls.get.length;
  await scheduler.drain();
  assert.equal(fake.calls.get.length, before, "终态后不得再发起查询");
});

test("学生拒绝后必须停止轮询", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(
    JOB({ job_id: "job_1", status: "AWAITING_APPROVAL", pending_approval_id: "apv_1", input_ref: {} }),
  );
  session.reject();
  await fake.settle();
  await fake.resolveDecide({ status: "REJECTED" });
  await scheduler.drain();

  assert.equal(session.getState().phase, JOB_PHASE.REJECTED);
  assert.equal(scheduler.pendingCount(), 0, "拒绝后不得继续轮询");
});

test("轮询失败后继续重试，直到终态", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(JOB({ job_id: "job_1", status: "QUEUED", input_ref: {} }));

  await scheduler.step();
  await fake.rejectGet(new Error("网络抖动"));
  assert.equal(session.getState().jobId, "job_1", "网络抖动不得改变 job 归属");
  await scheduler.step();
  await fake.resolveGet(JOB({ job_id: "job_1" }));
  await scheduler.drain();
  assert.equal(session.getState().phase, JOB_PHASE.SUCCEEDED);
});

// ===== 6. 快速重复点击 =====

test("快速双击确认只创建一个 job", async () => {
  const { fake, session } = setup();
  session.confirm();
  session.confirm();
  session.confirm();
  await fake.settle();
  assert.equal(fake.calls.create.length, 1, "双击不得创建两个 job");
});

// ===== 7. 审批 =====

test("审批响应丢失时通过查询同一个 job 恢复，绝不重新创建", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(
    JOB({ job_id: "job_1", status: "AWAITING_APPROVAL", pending_approval_id: "apv_1", input_ref: {} }),
  );
  assert.equal(session.getState().phase, JOB_PHASE.AWAITING_APPROVAL);

  session.approve();
  await fake.settle();
  await fake.rejectDecide(new Error("timeout")); // 审批响应丢失
  await fake.settle();

  assert.equal(fake.calls.create.length, 1, "审批丢失绝不能重新创建任务");
  assert.equal(session.getState().jobId, "job_1", "必须继续同一个 job");

  // 恢复路径：查询同一个 job 得知审批其实已生效
  await scheduler.step();
  await fake.resolveGet(JOB({ job_id: "job_1" }));
  await scheduler.drain();
  assert.equal(session.getState().phase, JOB_PHASE.SUCCEEDED);
  assert.match(session.getState().deepLink, /session=om_1/);
});

test("审批成功后继续订阅同一个 job（不产生第二个 job）", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(
    JOB({ job_id: "job_1", status: "AWAITING_APPROVAL", pending_approval_id: "apv_1", input_ref: {} }),
  );
  session.approve();
  await fake.settle();
  await fake.resolveDecide();
  await scheduler.step();
  await fake.resolveGet(JOB({ job_id: "job_1" }));
  await scheduler.drain();

  assert.equal(fake.calls.create.length, 1);
  assert.deepEqual(fake.calls.decide.map((c) => c.approvalId), ["apv_1"]);
  assert.equal(session.getState().phase, JOB_PHASE.SUCCEEDED);
});

test("审批过期（410）不再轮询且不显示为已批准", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  await fake.resolveCreate(
    JOB({ job_id: "job_1", status: "AWAITING_APPROVAL", pending_approval_id: "apv_1", input_ref: {} }),
  );
  session.approve();
  await fake.settle();
  await fake.rejectDecide({ response: { status: 410, data: { message: "审批已过期" } } });
  await scheduler.drain();

  assert.equal(session.getState().phase, JOB_PHASE.EXPIRED);
  assert.equal(scheduler.pendingCount(), 0, "过期后不得继续轮询");
});

// ===== 8. 卸载 =====

test("卸载后所有迟到响应都被丢弃", async () => {
  const { fake, scheduler, session } = setup();
  session.confirm();
  await fake.settle();
  session.dispose();

  await fake.resolveCreate(JOB({ job_id: "job_1", status: "QUEUED", input_ref: {} }));
  await scheduler.drain();
  assert.equal(session.getState().jobId, null, "卸载后不得再写状态");
  assert.equal(scheduler.pendingCount(), 0, "卸载后不得再安排轮询");
});

test("StrictMode 双调用（mount → cleanup → mount）后会话仍然可用", async () => {
  const { fake, scheduler, session } = setup();
  // React 18 StrictMode 在开发环境会 mount → cleanup → mount
  session.activate();
  session.restore();
  session.deactivate(); // cleanup
  session.activate(); // 第二次 mount
  session.restore();

  session.confirm();
  await fake.settle();
  assert.equal(fake.calls.create.length, 1, "双调用后确认按钮必须仍然有效");
  await fake.resolveCreate(JOB({ job_id: "job_1", status: "QUEUED", input_ref: {} }));
  await scheduler.step();
  assert.equal(session.getState().jobId, "job_1");
  await fake.resolveGet(JOB({ job_id: "job_1" }));
  await scheduler.drain();
  assert.equal(session.getState().phase, JOB_PHASE.SUCCEEDED);
});

test("deactivate 之前的在途响应在 activate 之后仍必须被丢弃", async () => {
  const { fake, session } = setup();
  session.confirm();
  await fake.settle();
  session.deactivate();
  session.activate(); // 新的一轮挂载
  await fake.resolveCreate(JOB({ job_id: "job_stale", status: "QUEUED", input_ref: {} }));
  assert.equal(session.getState().jobId, null, "上一轮的响应不得写进新的一轮");
});
