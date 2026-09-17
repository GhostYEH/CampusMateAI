/**
 * CPM 互动课堂生成的**真实**异步状态机。
 *
 * 为什么需要它：真实时序是
 *
 *   POST /agent-jobs  → 立刻返回 status=QUEUED, pending_approval_id=null
 *   Worker 稍后执行   → GET /agent-jobs/{id} 才变成 AWAITING_APPROVAL + pending_approval_id
 *
 * 修复前的实现把首个 QUEUED 当成 RUNNING，`refresh` 又不处理后来才出现的
 * `pending_approval_id`，于是页面永远到不了"批准"按钮；而"批准"的实现是
 * **再创建一个携带旧 approval_id 的新 Job** —— 既是功能故障，也是安全漏洞。
 *
 * 现在：状态机是纯函数（可无 DOM 单测），批准只调用审批接口，由后端续跑**原 Run**。
 */

export const JOB_PHASE = {
  IDLE: "IDLE",
  CREATING_JOB: "CREATING_JOB",
  QUEUED: "QUEUED",
  AWAITING_APPROVAL: "AWAITING_APPROVAL",
  APPROVING: "APPROVING",
  RUNNING: "RUNNING",
  SUCCEEDED: "SUCCEEDED",
  FAILED: "FAILED",
  REJECTED: "REJECTED",
  EXPIRED: "EXPIRED",
};

/** 需要继续轮询的阶段。 */
const POLLING_PHASES = new Set([
  JOB_PHASE.QUEUED,
  JOB_PHASE.RUNNING,
  JOB_PHASE.AWAITING_APPROVAL,
]);

export const TERMINAL_PHASES = new Set([
  JOB_PHASE.SUCCEEDED,
  JOB_PHASE.FAILED,
  JOB_PHASE.REJECTED,
  JOB_PHASE.EXPIRED,
]);

export const initialState = () => ({
  phase: JOB_PHASE.IDLE,
  jobId: null,
  runId: null,
  approvalId: null,
  sessionId: null,
  deepLink: null,
  status: null,
  message: "",
  error: "",
  // 是否已经发起过创建请求（用于恢复时避免重复创建）
  created: false,
});

/** 后端 job/run 状态 → 前端阶段。 */
export function phaseFromJob(job) {
  if (!job) return JOB_PHASE.QUEUED;
  const status = String(job.status || "").toUpperCase();
  const pending = job.pending_approval_id || null;
  if (pending) return JOB_PHASE.AWAITING_APPROVAL;
  if (status === "SUCCEEDED" || status === "PARTIAL") return JOB_PHASE.SUCCEEDED;
  if (status === "CANCELLED") return JOB_PHASE.REJECTED;
  if (status === "FAILED") return JOB_PHASE.FAILED;
  if (status === "RUNNING") return JOB_PHASE.RUNNING;
  if (status === "AWAITING_APPROVAL") return JOB_PHASE.AWAITING_APPROVAL;
  return JOB_PHASE.QUEUED;
}

/** 从 job 的 input_ref 里取出续跑/完成信息（后端把 handler 输出回填到这里）。 */
export function outcomeFromJob(job) {
  const ref = (job && (job.input_ref || job.input_ref_json)) || {};
  if (typeof ref === "string") return {};
  return {
    sessionId: ref.session_id || null,
    deepLink: ref.deep_link || null,
    classroomId: ref.classroom_id || null,
  };
}

export function needsPolling(state) {
  return POLLING_PHASES.has(state.phase);
}

export function canConfirm(state) {
  // 已经成功创建过任务（或从存储里恢复出 jobId）时不得再显示"确认生成"，
  // 否则一次确认会变成两次上游生成。
  if (state.created) return false;
  return state.phase === JOB_PHASE.IDLE || state.phase === JOB_PHASE.FAILED;
}

export function canApprove(state) {
  return state.phase === JOB_PHASE.AWAITING_APPROVAL && Boolean(state.approvalId);
}

/** 已成功但还没有内部深链时（后端还没回填）——继续轮询而不是提前宣布完成。 */
export function awaitingOutcome(state) {
  return state.phase === JOB_PHASE.SUCCEEDED && !state.deepLink;
}

export function reduce(state, action) {
  switch (action.type) {
    case "RESET":
      return initialState();

    case "CONFIRM_REQUESTED":
      if (!canConfirm(state)) return state;
      return { ...state, phase: JOB_PHASE.CREATING_JOB, created: true, error: "" };

    case "JOB_CREATED": {
      const job = action.job || {};
      const outcome = outcomeFromJob(job);
      return {
        ...state,
        jobId: job.job_id || state.jobId,
        runId: job.latest_run_id || state.runId,
        approvalId: job.pending_approval_id || null,
        status: job.status || state.status,
        phase: phaseFromJob(job),
        sessionId: outcome.sessionId || state.sessionId,
        deepLink: outcome.deepLink || state.deepLink,
        error: "",
      };
    }

    case "CREATE_FAILED":
      // 创建失败要允许重试：清掉 created 标记，否则按钮会被永久禁用。
      return {
        ...state,
        phase: JOB_PHASE.FAILED,
        created: false,
        error: action.error || "提交失败，请稍后重试",
      };

    case "POLL_RESULT": {
      const job = action.job || {};
      const outcome = outcomeFromJob(job);
      const phase = phaseFromJob(job);
      // 轮询结果只允许让阶段**前进**，不能把已批准的状态回退成"等审批"：
      // 后端在续跑期间会短暂返回旧快照。
      const regressed =
        state.phase === JOB_PHASE.RUNNING && phase === JOB_PHASE.AWAITING_APPROVAL;
      return {
        ...state,
        jobId: job.job_id || state.jobId,
        runId: job.latest_run_id || state.runId,
        approvalId: regressed ? state.approvalId : job.pending_approval_id || null,
        status: job.status || state.status,
        phase: regressed ? state.phase : phase,
        sessionId: outcome.sessionId || state.sessionId,
        deepLink: outcome.deepLink || state.deepLink,
      };
    }

    case "POLL_FAILED":
      // 网络抖动不改变已确定的阶段，只记录可读原因（SSE/轮询会自动重试）
      return { ...state, error: action.error || "进度查询失败，正在重试" };

    case "APPROVE_REQUESTED":
      if (!canApprove(state)) return state;
      return { ...state, phase: JOB_PHASE.APPROVING, error: "" };

    case "APPROVE_DONE": {
      // 批准后回到 QUEUED：后端已把**原 Run** 重新排队，继续订阅同一个 job。
      const job = action.job || {};
      const phase = phaseFromJob(job);
      return {
        ...state,
        phase: phase === JOB_PHASE.AWAITING_APPROVAL ? JOB_PHASE.QUEUED : phase,
        approvalId: null,
        jobId: job.job_id || state.jobId,
        status: job.status || state.status,
        error: "",
      };
    }

    case "APPROVE_REJECTED":
      return {
        ...state,
        phase: JOB_PHASE.REJECTED,
        approvalId: null,
        error: action.error || "已拒绝，本次不会生成课堂",
      };

    case "APPROVE_FAILED":
      // 审批接口本身失败（网络/409/410）→ 回到可重试的等待态并给出原因
      return {
        ...state,
        phase: action.expired ? JOB_PHASE.EXPIRED : JOB_PHASE.AWAITING_APPROVAL,
        error: action.error || "确认失败，请重试",
      };

    case "RESTORED":
      return { ...state, ...(action.state || {}) };

    default:
      return state;
  }
}

/** 轮询间隔：尊重后端的 poll_interval_ms，并设下限避免打爆后端。 */
export function pollDelayMs(job, fallback = 3000) {
  const raw = Number(job && job.poll_interval_ms);
  if (!Number.isFinite(raw) || raw <= 0) return fallback;
  return Math.max(1500, Math.min(raw, 30000));
}

/**
 * 恢复用的持久化 key。
 *
 * **必须**同时绑定"身份 + 课程 + 提案指纹"三件套：
 * - 只按 courseId 时，账号 A 退出、账号 B 登录后会恢复出 A 的任务；
 * - 同一门课的第二个提案（不同 mode / 不同 nonce）会复用第一个提案的 jobId，
 *   于是"新提案"直接显示上一节课的深链。
 */
export function storageKey({ identity, courseId, fingerprint } = {}) {
  return [
    "campus_classroom_job",
    identity || "anon",
    courseId || "default",
    fingerprint || "none",
  ].join(":");
}

/** 提案指纹：身份 + 提案唯一身份（服务端 nonce）+ 课程 + 模式 + 动作 id。 */
export function proposalFingerprint({ identity, proposal } = {}) {
  const p = proposal || {};
  return [
    identity || "anon",
    p.course_id || p.courseId || "",
    p.mode || "adaptive",
    p.id || "interactive-classroom",
    p.proposal_id || p.proposalId || "",
  ].join("|");
}

export function persistJob(scope, state) {
  try {
    if (!state?.jobId) return;
    globalThis.localStorage?.setItem(
      storageKey(scope),
      JSON.stringify({ jobId: state.jobId, phase: state.phase }),
    );
  } catch {
    // 存储不可用时只是失去恢复能力，不影响主流程
  }
}

export function readPersistedJob(scope) {
  try {
    const raw = globalThis.localStorage?.getItem(storageKey(scope));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.jobId ? parsed : null;
  } catch {
    return null;
  }
}

export function clearPersistedJob(scope) {
  try {
    globalThis.localStorage?.removeItem(storageKey(scope));
  } catch {
    // 忽略
  }
}

/**
 * 清除**其他身份**遗留的课堂恢复记录。
 *
 * 登录账号切换时调用：既保证 B 不会恢复 A 的任务，也避免陈旧的 jobId 长期留在
 * 浏览器里。只删本模块前缀的键，不触碰其他应用数据。
 */
export function purgeOtherIdentityJobs(identity, storage = globalThis.localStorage) {
  if (!storage) return 0;
  const prefix = "campus_classroom_job:";
  const keep = `${prefix}${identity || "anon"}:`;
  let removed = 0;
  try {
    const keys = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key && key.startsWith(prefix) && !key.startsWith(keep)) keys.push(key);
    }
    keys.forEach((key) => {
      storage.removeItem(key);
      removed += 1;
    });
  } catch {
    // 忽略
  }
  return removed;
}
