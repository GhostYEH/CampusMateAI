/**
 * 一个"提案作用域"的互动课堂会话编排器（纯 JS，无 React 依赖，可无 DOM 单测）。
 *
 * 为什么需要它：修复前 `ClassroomProposalCard` 用一个共享的 `alive` 布尔量保护
 * 异步回写，并把恢复 key 只按 courseId 存。真实故障：
 *
 *   1. A 提案未完成时切到 B：B 的 effect 把 `alive` 立刻设回 true，
 *      A 的迟到响应（success / error / finally / 递归 poll）于是被当成有效结果写进 B。
 *   2. 同一门课的第二个提案：`courseId` 没变 → 恢复 effect 不重跑 →
 *      卡片继续显示第一个提案的 job、审批按钮与深链。
 *   3. 账号 A 退出、账号 B 登录：key 只按 courseId → B 恢复出 A 的任务。
 *
 * 现在：每个提案有稳定 fingerprint，每次切换都递增 epoch；
 * **所有**异步分支（success / error / finally / 递归 poll）先校验
 * `epoch` 与 `jobId` 才允许写状态。仅靠 `alive` 是拦不住迟到响应的。
 */
import {
  JOB_PHASE,
  TERMINAL_PHASES,
  canApprove,
  canConfirm,
  clearPersistedJob,
  initialState,
  persistJob,
  phaseFromJob,
  pollDelayMs,
  proposalFingerprint,
  readPersistedJob,
  reduce,
} from "./classroomJobMachine.js";

/** 这些阶段必须停止轮询（学生主动取消 / 审批过期）。 */
const STOP_POLLING_PHASES = new Set([JOB_PHASE.REJECTED, JOB_PHASE.EXPIRED]);

function defaultSchedule(fn, ms) {
  return setTimeout(fn, ms);
}

function defaultCancelSchedule(handle) {
  clearTimeout(handle);
}

export function createProposalSession({
  proposal = null,
  identity = "anon",
  api,
  schedule = defaultSchedule,
  cancelSchedule = defaultCancelSchedule,
  pollFallbackMs = 3000,
  onChange = () => {},
} = {}) {
  let currentProposal = proposal;
  let currentIdentity = identity;
  let fingerprint = proposalFingerprint({ identity: currentIdentity, proposal: currentProposal });
  let courseId = currentProposal?.course_id || "";
  let machine = initialState();
  let epoch = 0;
  let timer = null;
  // `active` 而不是一次性的 `disposed`：React 18 StrictMode 在开发环境会
  // mount → cleanup → mount 双调用 effect。若 cleanup 里把会话永久置为"已销毁"，
  // 第二次 mount 拿到的就是一个死会话 —— 按钮点了没反应，且没有任何报错。
  let active = true;

  const scope = () => ({ identity: currentIdentity, courseId, fingerprint });

  function emit() {
    onChange(machine, { fingerprint, courseId, epoch });
  }

  /** 唯一的写状态入口：先校验 epoch 与 jobId，再落状态并处理持久化。 */
  function apply(action, guard) {
    const guardEpoch = guard?.epoch === undefined ? epoch : guard.epoch;
    if (!isCurrent(guardEpoch, guard?.jobId)) return false;
    const next = reduce(machine, action);
    if (next === machine) return false;
    machine = next;
    if (machine.jobId) persistJob(scope(), machine);
    if (TERMINAL_PHASES.has(machine.phase)) {
      stopTimer();
      clearPersistedJob(scope());
    }
    emit();
    return true;
  }

  /**
   * 迟到响应防护：`epoch` 必须仍是当前代次，且（若给了 jobId）仍是当前 job。
   * 两者缺一不可 —— 只看 jobId 挡不住"新提案恰好复用了同一个 jobId"，
   * 只看 epoch 挡不住"同一提案里旧 job 的迟到响应"。
   */
  function isCurrent(myEpoch, jobId) {
    if (!active) return false;
    if (myEpoch !== epoch) return false;
    if (jobId && machine.jobId && jobId !== machine.jobId) return false;
    return true;
  }

  function stopTimer() {
    if (timer !== null) {
      cancelSchedule(timer);
      timer = null;
    }
  }

  function poll(jobId) {
    const myEpoch = epoch;
    stopTimer();
    if (!jobId) return;
    timer = schedule(async () => {
      timer = null;
      if (!isCurrent(myEpoch, jobId)) return;
      let job = null;
      try {
        job = await api.getAgentJob(jobId);
      } catch (err) {
        if (!isCurrent(myEpoch, jobId)) return;
        apply(
          {
            type: "POLL_FAILED",
            error: err?.response?.data?.message || err?.message || "进度查询失败",
          },
          { epoch: myEpoch, jobId },
        );
        // 网络抖动 / SSE 断开后继续重试，直到终态
        poll(jobId);
        return;
      }
      if (!isCurrent(myEpoch, jobId)) return;
      apply({ type: "POLL_RESULT", job }, { epoch: myEpoch, jobId });

      const status = String(job?.status || "").toUpperCase();
      const hasOutcome = Boolean(job?.input_ref?.deep_link);
      const settled = (status === "SUCCEEDED" || status === "PARTIAL") && hasOutcome;
      const terminalFailure = ["FAILED", "CANCELLED"].includes(status);
      // 学生已拒绝 / 审批已过期 → 无论如何都不再轮询
      if (STOP_POLLING_PHASES.has(machine.phase)) return;
      if (!settled && !terminalFailure) poll(jobId);
    }, pollDelayMs({ poll_interval_ms: pollFallbackMs }, pollFallbackMs));
  }

  /** 用已保存的 jobId 重新订阅**同一个** Job，绝不重新创建。 */
  function restore() {
    const persisted = readPersistedJob(scope());
    if (!persisted?.jobId) return false;
    apply(
      { type: "RESTORED", state: { jobId: persisted.jobId, created: true } },
      { epoch },
    );
    poll(persisted.jobId);
    return true;
  }

  /**
   * 切换到新提案 / 新身份。
   *
   * 同一个 fingerprint（组件重挂载、父组件重渲染）→ 保持同一个 job，不重复生成。
   * 新 fingerprint → 停旧 timer、作废旧在途请求（epoch+1）、重置状态、
   * 换新的幂等上下文。
   */
  function update(nextProposal, nextIdentity = currentIdentity) {
    const nextFingerprint = proposalFingerprint({
      identity: nextIdentity,
      proposal: nextProposal,
    });
    const nextCourseId = nextProposal?.course_id || "";
    if (nextFingerprint === fingerprint && nextCourseId === courseId) {
      // 同一个提案：只刷新展示用数据，绝不重置 job / 轮询 / 幂等上下文
      currentProposal = nextProposal;
      return false;
    }
    stopTimer();
    epoch += 1; // 作废所有旧的在途请求与旧 timer
    currentProposal = nextProposal;
    currentIdentity = nextIdentity;
    fingerprint = nextFingerprint;
    courseId = nextCourseId;
    machine = initialState();
    emit();
    if (active && nextProposal && nextCourseId) restore();
    return true;
  }

  async function confirm() {
    if (!currentProposal || !courseId) return;
    if (!canConfirm(machine)) return;
    const myEpoch = epoch;
    const myFingerprint = fingerprint;
    apply({ type: "CONFIRM_REQUESTED" }, { epoch: myEpoch });
    try {
      const job = await api.createAgentJob({
        job_kind: "interactive_classroom",
        input_ref: { course_id: courseId, mode: currentProposal.mode || "adaptive" },
      });
      // 身份/提案在等待期间变了 → 丢弃结果，绝不写进新提案
      if (!active || myEpoch !== epoch || myFingerprint !== fingerprint) return;
      apply({ type: "JOB_CREATED", job }, { epoch: myEpoch });
      if (job?.job_id) poll(job.job_id);
    } catch (err) {
      if (!active || myEpoch !== epoch || myFingerprint !== fingerprint) return;
      apply(
        {
          type: "CREATE_FAILED",
          error: err?.response?.data?.message || err?.message || "提交失败，请稍后重试",
        },
        { epoch: myEpoch },
      );
    }
  }

  async function approve() {
    if (!canApprove(machine)) return;
    const myEpoch = epoch;
    const jobId = machine.jobId;
    const approvalId = machine.approvalId;
    apply({ type: "APPROVE_REQUESTED" }, { epoch: myEpoch, jobId });
    try {
      await api.decideAgentApproval(approvalId, "APPROVED");
      if (!isCurrent(myEpoch, jobId)) return;
      apply(
        { type: "APPROVE_DONE", job: { job_id: jobId, status: "QUEUED" } },
        { epoch: myEpoch, jobId },
      );
      // 后端已把原 Run 重新排队 —— 继续订阅**同一个** job。
      poll(jobId);
    } catch (err) {
      if (!isCurrent(myEpoch, jobId)) return;
      const status = err?.response?.status;
      apply(
        {
          type: "APPROVE_FAILED",
          expired: status === 410,
          error:
            err?.response?.data?.message ||
            (status === 410 ? "审批已过期，请重新发起" : "确认失败，请重试"),
        },
        { epoch: myEpoch, jobId },
      );
      if (status !== 410) {
        // 审批响应丢失（超时/断网）：**查询同一个 job** 来恢复真实状态，
        // 绝不重新创建任务 —— 否则一次确认会变成两次上游生成。
        poll(jobId);
      }
    }
  }

  async function reject() {
    if (!canApprove(machine)) return;
    const myEpoch = epoch;
    const jobId = machine.jobId;
    const approvalId = machine.approvalId;
    try {
      await api.decideAgentApproval(approvalId, "REJECTED", "学生取消");
    } catch {
      // 拒绝失败也要收口到 REJECTED，避免学生卡在等待态
    }
    if (!isCurrent(myEpoch, jobId)) return;
    stopTimer();
    apply({ type: "APPROVE_REJECTED" }, { epoch: myEpoch, jobId });
  }

  /**
   * 挂载生命周期（可逆）。
   *
   * `activate()` / `deactivate()` 而不是一次性的销毁：StrictMode 的
   * mount → cleanup → mount 必须能回到可用状态，否则开发环境下卡片直接失灵。
   * 两者都会递增 epoch，从而作废上一轮所有在途请求与 timer。
   */
  function activate() {
    active = true;
    epoch += 1;
  }

  function deactivate() {
    active = false;
    stopTimer();
    epoch += 1;
  }

  return {
    getState: () => machine,
    getFingerprint: () => fingerprint,
    getScope: scope,
    update,
    restore,
    confirm,
    approve,
    reject,
    activate,
    deactivate,
    /** 兼容别名：等同于 deactivate（挂载生命周期可逆，见 activate） */
    dispose: deactivate,
    /** 仅测试/调试用：当前代次 */
    getEpoch: () => epoch,
  };
}

export { phaseFromJob, pollDelayMs, JOB_PHASE };
export default createProposalSession;
