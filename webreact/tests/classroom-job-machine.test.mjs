/**
 * P1-3 —— CPM 互动课堂生成的真实异步状态机。
 *
 * 真实时序：POST /agent-jobs 立刻返回 QUEUED + pending_approval_id=null；
 * Worker 稍后执行，GET /agent-jobs/{id} 才变成 AWAITING_APPROVAL + pending_approval_id。
 *
 * 修复前的两个真实故障：
 *  ① 把首个 QUEUED 当成 RUNNING、refresh 不处理后来出现的 pending_approval_id
 *     → 页面永远到不了"批准"按钮；
 *  ② "批准"的实现是再创建一个携带旧 approval_id 的新 Job
 *     → 既是功能故障，也是跨请求复用审批的漏洞入口。
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import "./helpers/setup-globals.mjs";
import * as M from "../src/data/classroomJobMachine.js";

const here = dirname(fileURLToPath(import.meta.url));
const read = (rel) => readFileSync(resolve(here, "..", rel), "utf8");

const job = (overrides = {}) => ({
  job_id: "job_1",
  status: "QUEUED",
  pending_approval_id: null,
  input_ref: { course_id: "c1", mode: "review" },
  ...overrides,
});

const run = (actions) => actions.reduce((state, action) => M.reduce(state, action), M.initialState());

// ===== A. 真实时序 =====

test("创建接口先返回 QUEUED 且没有 approval_id", () => {
  const state = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
  ]);
  assert.equal(state.phase, M.JOB_PHASE.QUEUED);
  assert.equal(state.approvalId, null);
  assert.equal(state.jobId, "job_1");
  assert.equal(M.canApprove(state), false, "QUEUED 阶段不得显示批准按钮");
});

test("后续轮询才进入 AWAITING_APPROVAL 并出现批准按钮", () => {
  const state = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
  ]);
  assert.equal(state.phase, M.JOB_PHASE.AWAITING_APPROVAL);
  assert.equal(state.approvalId, "apv_1");
  assert.equal(M.canApprove(state), true);
});

test("批准后回到排队并继续订阅同一个 job", () => {
  const before = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
    { type: "APPROVE_REQUESTED" },
  ]);
  assert.equal(before.phase, M.JOB_PHASE.APPROVING);

  const after = M.reduce(before, { type: "APPROVE_DONE", job: job({ status: "QUEUED" }) });
  assert.equal(after.phase, M.JOB_PHASE.QUEUED);
  assert.equal(after.jobId, "job_1", "必须继续订阅同一个 job");
  assert.equal(after.approvalId, null);
});

test("终态成功后从 input_ref 读出 session_id 与内部深链", () => {
  const state = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
    { type: "APPROVE_DONE", job: job({ status: "QUEUED" }) },
    {
      type: "POLL_RESULT",
      job: job({
        status: "SUCCEEDED",
        input_ref: { session_id: "om_1", deep_link: "/courses/c1?tab=mentoring&session=om_1" },
      }),
    },
  ]);
  assert.equal(state.phase, M.JOB_PHASE.SUCCEEDED);
  assert.equal(state.sessionId, "om_1");
  assert.equal(state.deepLink, "/courses/c1?tab=mentoring&session=om_1");
  assert.equal(M.awaitingOutcome(state), false);
});

test("已成功但后端还没回填深链时不得提前宣布完成", () => {
  const state = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "SUCCEEDED" }) },
  ]);
  assert.equal(state.phase, M.JOB_PHASE.SUCCEEDED);
  assert.equal(M.awaitingOutcome(state), true, "缺深链时必须继续等待，而不是说已完成");
});

// ===== B. 安全与幂等 =====

test("重复点击确认只创建一次（状态机层面拒绝）", () => {
  const once = run([{ type: "CONFIRM_REQUESTED" }]);
  const twice = M.reduce(once, { type: "CONFIRM_REQUESTED" });
  assert.equal(twice, once, "非 IDLE/FAILED 阶段不得再次发起创建");
});

test("重复点击批准只发起一次（状态机层面拒绝）", () => {
  const awaiting = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
    { type: "APPROVE_REQUESTED" },
  ]);
  const twice = M.reduce(awaiting, { type: "APPROVE_REQUESTED" });
  assert.equal(twice, awaiting);
});

test("批准后轮询返回旧快照不得把状态回退成等审批", () => {
  const running = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
    { type: "APPROVE_DONE", job: job({ status: "QUEUED" }) },
    { type: "POLL_RESULT", job: job({ status: "RUNNING" }) },
  ]);
  assert.equal(running.phase, M.JOB_PHASE.RUNNING);

  const stale = M.reduce(running, {
    type: "POLL_RESULT",
    job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }),
  });
  assert.equal(stale.phase, M.JOB_PHASE.RUNNING, "不得回退成等待审批");
});

test("拒绝与过期都收口到明确的非成功状态", () => {
  const awaiting = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "AWAITING_APPROVAL", pending_approval_id: "apv_1" }) },
  ]);
  assert.equal(M.reduce(awaiting, { type: "APPROVE_REJECTED" }).phase, M.JOB_PHASE.REJECTED);
  assert.equal(
    M.reduce(awaiting, { type: "APPROVE_FAILED", expired: true }).phase,
    M.JOB_PHASE.EXPIRED,
  );
  assert.equal(
    M.reduce(awaiting, { type: "APPROVE_FAILED", error: "网络错误" }).phase,
    M.JOB_PHASE.AWAITING_APPROVAL,
    "普通失败应回到可重试的等待态",
  );
});

test("网络抖动只记录原因，不改变已确定的阶段", () => {
  const running = run([
    { type: "CONFIRM_REQUESTED" },
    { type: "JOB_CREATED", job: job() },
    { type: "POLL_RESULT", job: job({ status: "RUNNING" }) },
  ]);
  const after = M.reduce(running, { type: "POLL_FAILED", error: "网络断开" });
  assert.equal(after.phase, M.JOB_PHASE.RUNNING);
  assert.match(after.error, /网络断开/);
});

// ===== C. 恢复与轮询策略 =====

test("恢复时沿用同一个 jobId，绝不重新创建", () => {
  const restored = M.reduce(M.initialState(), {
    type: "RESTORED",
    state: { jobId: "job_9", created: true },
  });
  assert.equal(restored.jobId, "job_9");
  assert.equal(restored.created, true);
  assert.equal(M.canConfirm(restored), false, "已创建过的任务不得再显示『确认生成』");
});

test("轮询间隔尊重后端并设下限", () => {
  assert.equal(M.pollDelayMs({ poll_interval_ms: 5000 }), 5000);
  assert.equal(M.pollDelayMs({ poll_interval_ms: 100 }), 1500);
  assert.equal(M.pollDelayMs({ poll_interval_ms: 999999 }), 30000);
  assert.equal(M.pollDelayMs(null), 3000);
});

test("持久化 key 同时按身份 / 课程 / 提案指纹隔离，并且只保存 jobId", () => {
  const scope = (identity, courseId, fingerprint) => ({ identity, courseId, fingerprint });
  const a = scope("u1", "c1", "fp1");
  const otherCourse = scope("u1", "c2", "fp1");
  const otherAccount = scope("u2", "c1", "fp1");
  const otherProposal = scope("u1", "c1", "fp2");

  const keys = [a, otherCourse, otherAccount, otherProposal].map(M.storageKey);
  assert.equal(new Set(keys).size, 4, "身份/课程/提案任一不同都必须隔离");

  M.persistJob(a, { jobId: "job_1", phase: "QUEUED" });
  assert.equal(M.readPersistedJob(a).jobId, "job_1");
  assert.equal(M.readPersistedJob(otherCourse), null, "不同课程不得共享恢复记录");
  assert.equal(M.readPersistedJob(otherAccount), null, "不同账号不得共享恢复记录");
  assert.equal(M.readPersistedJob(otherProposal), null, "不同提案不得共享恢复记录");
  M.clearPersistedJob(a);
  assert.equal(M.readPersistedJob(a), null);
});

test("proposalFingerprint 绑定身份 + 提案 nonce + 课程 + 模式", () => {
  const base = {
    id: "interactive-classroom",
    proposal_id: "icp_1",
    course_id: "c1",
    mode: "review",
  };
  const fp = (identity, overrides) =>
    M.proposalFingerprint({ identity, proposal: { ...base, ...overrides } });

  assert.equal(fp("u1"), fp("u1"), "同输入必须稳定（重挂载才能继续同一个 job）");
  assert.notEqual(fp("u1"), fp("u2"), "身份必须参与指纹");
  assert.notEqual(fp("u1"), fp("u1", { course_id: "c2" }), "课程必须参与指纹");
  assert.notEqual(fp("u1"), fp("u1", { mode: "quiz" }), "模式必须参与指纹");
  assert.notEqual(
    fp("u1"),
    fp("u1", { proposal_id: "icp_2" }),
    "服务端 nonce 必须参与指纹（否则同课同模式的第二个提案会复用第一个）",
  );
});

test("logout 清理只删除其他身份的课堂恢复记录", () => {
  const mine = { identity: "u1", courseId: "c1", fingerprint: "fp" };
  const theirs = { identity: "u2", courseId: "c1", fingerprint: "fp" };
  M.persistJob(mine, { jobId: "job_mine", phase: "QUEUED" });
  M.persistJob(theirs, { jobId: "job_theirs", phase: "QUEUED" });
  globalThis.localStorage.setItem("campus_session", "{}");

  const removed = M.purgeOtherIdentityJobs("u1");
  assert.equal(removed, 1);
  assert.equal(M.readPersistedJob(mine).jobId, "job_mine", "自己身份的记录必须保留");
  assert.equal(M.readPersistedJob(theirs), null, "他人身份的记录必须清除");
  assert.equal(globalThis.localStorage.getItem("campus_session"), "{}", "不得误删其他应用数据");
});

test("阶段集合语义正确", () => {
  assert.equal(M.needsPolling({ phase: M.JOB_PHASE.QUEUED }), true);
  assert.equal(M.needsPolling({ phase: M.JOB_PHASE.RUNNING }), true);
  assert.equal(M.needsPolling({ phase: M.JOB_PHASE.AWAITING_APPROVAL }), true);
  assert.equal(M.needsPolling({ phase: M.JOB_PHASE.SUCCEEDED }), false);
  for (const p of ["SUCCEEDED", "FAILED", "REJECTED", "EXPIRED"]) {
    assert.equal(M.TERMINAL_PHASES.has(p), true, p);
  }
});

// ===== D. 批准路径不得再创建 Job =====
//
// 行为层面的完整覆盖在 `classroom-proposal-session.test.mjs`
// （"审批成功后继续订阅同一个 job（不产生第二个 job）" 等）。
// 这里保留一条结构性护栏：审批分支里不能出现创建动作。

test("批准路径不调用 createAgentJob（杜绝携带旧 approval 的新 Job）", () => {
  const src = read("src/data/classroomProposalSession.js");
  const approveBody = src.slice(
    src.indexOf("async function approve()"),
    src.indexOf("async function reject()"),
  );
  assert.match(approveBody, /decideAgentApproval/);
  assert.doesNotMatch(approveBody, /createAgentJob/, "批准时绝不能创建第二个 Job");
  assert.match(approveBody, /poll\(jobId\)/, "批准后必须继续订阅同一个 job");
  // 审批响应丢失时必须靠查询同一 job 恢复，而不是重新创建任务
  assert.match(approveBody, /查询同一个 job/);
});

test("卡片把并发防护委托给作用域会话，不自己管 alive 布尔量", () => {
  const src = read("src/components/interactive/ClassroomProposalCard.jsx");
  assert.match(src, /createProposalSession/);
  assert.match(src, /canApprove\(state\)/);
  assert.match(src, /canConfirm\(state\)/);
  assert.doesNotMatch(
    src,
    /const alive = useRef/,
    "共享 alive 布尔量挡不住新提案覆盖旧提案的迟到响应",
  );
});
