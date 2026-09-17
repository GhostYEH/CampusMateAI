import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../data/api.js";
import {
  JOB_PHASE,
  awaitingOutcome,
  canApprove,
  canConfirm,
  initialState,
  needsPolling,
} from "../../data/classroomJobMachine.js";
import { createProposalSession } from "../../data/classroomProposalSession.js";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";

/**
 * CPM 的互动课堂提案确认卡。
 *
 * 真实时序（这是修复的重点）：
 *   POST /agent-jobs → 立刻返回 status=QUEUED、pending_approval_id=null
 *   Worker 稍后执行   → GET /agent-jobs/{id} 才变成 AWAITING_APPROVAL + pending_approval_id
 *   学生批准          → 只调用审批接口；后端把**原 Run** 重新排队并继续执行
 *   继续订阅同一个 Job → 终态后从 input_ref 读取 session_id / deep_link
 *
 * 四条硬约束：
 * 1. 绝不创建"携带旧 approval_id 的第二个 Job"（那是跨请求复用漏洞）；
 * 2. 没有真正进入 AWAITING_APPROVAL 之前，不显示"批准"按钮；
 * 3. 不用"已提交"冒充"已生成完成" —— 只有拿到真实深链才说完成；
 * 4. 所有异步回写都必须绑定**当前提案的 epoch 与 jobId**（见 classroomProposalSession）：
 *    仅靠一个共享的 `alive` 布尔量挡不住"新提案覆盖旧提案"的迟到响应。
 *
 * 组件本身只做渲染 + 把用户动作转给作用域会话，状态机与并发防护全在纯 JS 模块里，
 * 因此可以脱离 DOM 做真正的行为测试。
 */
export default function ClassroomProposalCard({
  proposal,
  identity = "anon",
  onOpenClassroom = null,
}) {
  const [state, setState] = useState(initialState);
  const sessionRef = useRef(null);
  if (sessionRef.current === null) {
    sessionRef.current = createProposalSession({
      proposal,
      identity,
      api,
      onChange: (next) => setState(next),
    });
  }
  const session = sessionRef.current;

  // 提案或身份变化 → 作用域会话自己决定"继续同一个 job"还是"作废旧代次"。
  useEffect(() => {
    session.update(proposal, identity);
  }, [session, proposal, identity]);

  // 页面刷新 / 组件重挂载：按已保存的 jobId 重新订阅同一个 Job，绝不重新创建。
  // 生命周期可逆（activate/deactivate）：React StrictMode 的
  // mount → cleanup → mount 必须能回到可用状态，否则开发环境卡片直接失灵。
  useEffect(() => {
    session.activate();
    session.restore();
    return () => session.deactivate();
  }, [session]);

  const confirm = useCallback(() => {
    session.confirm();
  }, [session]);
  const approve = useCallback(() => {
    session.approve();
  }, [session]);
  const reject = useCallback(() => {
    session.reject();
  }, [session]);

  if (!proposal || !proposal.course_id) return null;
  const available = proposal.available !== false;
  const intentNote =
    proposal.intent_note ||
    "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。";

  const busy = state.phase === JOB_PHASE.CREATING_JOB || state.phase === JOB_PHASE.APPROVING;

  return (
    <div className="classroom-proposal" role="region" aria-label="互动课堂建议">
      <span className="classroom-proposal-icon">
        <Icon name="PhGraduationCap" size={20} />
      </span>
      <div className="classroom-proposal-body">
        <strong>{proposal.label || `生成一节「${proposal.mode_label}」互动课堂`}</strong>
        <small>
          {proposal.course_name || proposal.course_id} · {proposal.mode_label}
        </small>
        <p className="classroom-proposal-note">{intentNote}</p>

        {!available ? (
          <p className="classroom-proposal-warn">
            互动课堂暂不可用{proposal.reason ? `：${proposal.reason}` : ""}。你仍然可以继续用文字提问。
          </p>
        ) : null}

        {state.phase === JOB_PHASE.CREATING_JOB ? (
          <p className="classroom-proposal-note">正在提交生成请求…</p>
        ) : null}
        {state.phase === JOB_PHASE.QUEUED || state.phase === JOB_PHASE.RUNNING ? (
          <p className="classroom-proposal-note">
            已排队，正在准备这节课。生成需要一点时间，可以留在本页等待。
          </p>
        ) : null}
        {state.phase === JOB_PHASE.AWAITING_APPROVAL ? (
          <p className="classroom-proposal-warn">
            已准备好，需要你确认后才会真正开始生成（会调用外部服务并产生费用）。
          </p>
        ) : null}
        {state.phase === JOB_PHASE.APPROVING ? (
          <p className="classroom-proposal-note">正在确认…</p>
        ) : null}
        {state.phase === JOB_PHASE.SUCCEEDED && !state.deepLink ? (
          <p className="classroom-proposal-note">课堂已生成，正在获取打开入口…</p>
        ) : null}
        {state.phase === JOB_PHASE.SUCCEEDED && state.deepLink ? (
          <p className="classroom-proposal-note">
            课堂已生成。
            {onOpenClassroom ? (
              <button
                type="button"
                className="text-button"
                onClick={() => onOpenClassroom(state.deepLink)}
              >
                去课程详情查看
              </button>
            ) : null}
          </p>
        ) : null}
        {state.phase === JOB_PHASE.REJECTED ? (
          <p className="classroom-proposal-note">已取消，本次不会生成课堂。</p>
        ) : null}
        {state.phase === JOB_PHASE.FAILED ? (
          <p className="classroom-proposal-error">生成失败，可以重新发起。</p>
        ) : null}
        {state.phase === JOB_PHASE.EXPIRED ? (
          <p className="classroom-proposal-error">确认已过期，请重新发起。</p>
        ) : null}
        {state.error && state.phase !== JOB_PHASE.FAILED ? (
          <p className="classroom-proposal-error">{state.error}</p>
        ) : null}

        <div className="classroom-proposal-actions">
          {canConfirm(state) ? (
            <Button variant="quiet" icon="PhPlay" disabled={!available || busy} onClick={confirm}>
              {state.phase === JOB_PHASE.FAILED ? "重新发起" : "确认生成"}
            </Button>
          ) : null}
          {canApprove(state) ? (
            <>
              <Button variant="quiet" icon="PhCheck" onClick={approve} disabled={busy}>
                批准并开始生成
              </Button>
              <Button variant="quiet" onClick={reject} disabled={busy}>
                不用了
              </Button>
            </>
          ) : null}
          {needsPolling(state) || awaitingOutcome(state) ? (
            <span className="classroom-proposal-note" role="status" aria-live="polite">
              {state.phase === JOB_PHASE.AWAITING_APPROVAL ? "等待你确认…" : "处理中…"}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
