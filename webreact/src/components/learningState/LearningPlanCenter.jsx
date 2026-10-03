import { EmptyState, Spinner, ErrorBar } from './shared.jsx';
import { useMemo } from 'react';
import { useAsyncResource as useAsync } from '../../hooks/useAsyncResource.js';
import * as api from '../../data/learnerStateApi.js';

const PLAN_STATUS_LABEL = {
  PROPOSED: "待确认",
  ACCEPTED: "已接受",
  REJECTED: "已拒绝",
  EXECUTED: "已执行",
  PARTIALLY_EXECUTED: "部分执行",
  UNDONE: "已撤销",
  EXPIRED: "已过期",
};

function LearningPlanCenter({ plans, onAction, busy }) {
  const current = plans?.items?.find((p) => p.status === "PROPOSED" || p.status === "ACCEPTED" || p.status === "EXECUTED");
  if (!current) return <EmptyState text="暂时没有行动计划" />;
  return (
    <section className="ls-section ls-plan" aria-label="行动计划中心">
      <div className="ls-plan__header">
        <h3>当前行动计划</h3>
        <span className={`ls-plan__status ls-plan__status--${(current.status || "").toLowerCase()}`}>{PLAN_STATUS_LABEL[current.status] || current.status}</span>
      </div>
      {current.warning_codes?.length > 0 && (
        <div className="ls-plan__warnings">
          {current.warning_codes.map((w) => <p key={w} className="ls-warning">{WARNING_LABEL[w] || w}</p>)}
        </div>
      )}
      {current.items?.map((item) => (
        <div key={item.item_id} className="ls-plan-item">
          <p className="ls-plan-item__type">{ITEM_TYPE_LABEL[item.item_type] || item.item_type}</p>
          <p className="ls-plan-item__time">预计 {item.estimated_minutes || 0} 分钟</p>
          {item.explanation_codes?.map((e) => <span key={e} className="ls-plan-item__reason">{e}</span>)}
        </div>
      ))}
      <div className="ls-plan__actions">
        {current.status === "PROPOSED" && (
          <>
            <button className="ls-btn ls-btn--primary" onClick={() => onAction("accept", current.plan_id)} disabled={busy}>接受计划</button>
            <button className="ls-btn" onClick={() => onAction("reject", current.plan_id)} disabled={busy}>拒绝</button>
          </>
        )}
        {current.status === "ACCEPTED" && (
          <button className="ls-btn ls-btn--primary" onClick={() => onAction("execute", current.plan_id)} disabled={busy}>创建个人任务</button>
        )}
        {current.status === "EXECUTED" && (
          <>
            <button className="ls-btn" onClick={() => onAction("undo", current.plan_id)} disabled={busy}>撤销</button>
            <button className="ls-btn" onClick={() => onAction("replan", current.plan_id)} disabled={busy}>重新规划</button>
          </>
        )}
        {current.status === "EXPIRED" && (
          <p className="ls-warning">计划已过有效期</p>
        )}
      </div>
    </section>
  );
}

const ITEM_TYPE_LABEL = {
  TASK_FOCUS: "专注任务",
  CREATE_PERSONAL_TASK: "创建学习任务",
  SCHEDULE_REVIEW: "日程回顾",
  DEADLINE_REMINDER: "截止提醒",
};

const WARNING_LABEL = {
  INPUT_TRUNCATED: "部分输入数据被截断",
  CORE_QUALITY_DEGRADED: "核心状态数据质量降级",
  STALE_CORE_STATE: "核心状态已过期",
  PLAN_STALE: "依据已变化，请重新规划",
};

function PlanEvaluation({ evaluation }) {
  if (!evaluation) return null;
  return (
    <section className="ls-section ls-evaluation" aria-label="计划效果观察">
      <p className="ls-evaluation__disclaimer">这里展示计划之后观察到的学习记录，不代表计划与结果之间存在因果关系。</p>
      <div className="ls-evaluation__grid">
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.planned_item_count || 0}</span><span>计划项</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.executed_item_count || 0}</span><span>已执行</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.completed_plan_task_count || 0}</span><span>完成任务</span></div>
        <div className="ls-eval-stat"><span className="ls-eval-stat__num">{evaluation.followup_practice_count || 0}</span><span>后续练习</span></div>
      </div>
      {evaluation.warning_codes?.length > 0 && evaluation.warning_codes.map((w) => (
        <p key={w} className="ls-warning">{WARNING_LABEL[w] || w}</p>
      ))}
    </section>
  );
}

function PlanEvaluationSection({ plans }) {
  const executedPlan = useMemo(() => {
    const items = plans?.items || [];
    return items.find((p) => p.status === "EXECUTED" || p.status === "PARTIALLY_EXECUTED") || null;
  }, [plans]);
  const evaluation = useAsync(
    () => (executedPlan ? api.getPlanEvaluation(executedPlan.plan_id) : Promise.resolve(null)),
    [executedPlan?.plan_id],
  );
  if (!executedPlan) return null;
  if (evaluation.loading) return <Spinner label="加载效果观察" />;
  if (evaluation.error) return <ErrorBar error={evaluation.error} />;
  return <PlanEvaluation evaluation={evaluation.data} />;
}

export { LearningPlanCenter, PlanEvaluationSection };
