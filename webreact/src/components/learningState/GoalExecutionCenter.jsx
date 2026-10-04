import { formatRelativeTime } from "../../utils/date.js";
import { useState, useEffect } from 'react';
import { EmptyState } from './shared.jsx';

const CANDIDATE_CLAIM_LABEL = {
  PRIORITIZE_NEAR_DEADLINE: "优先处理临近截止",
  USE_SHORT_SESSION: "拆成短时段学习",
  DATA_QUALITY_PARTIAL: "部分数据质量受限",
};

const CANDIDATE_REASON_LABEL = {
  canary_feature_flag_disabled: "金丝雀展示未开启",
  candidate_model_not_configured: "候选模型未配置",
  model_shadow_paused_for_user: "你已暂停模型影子评测",
  no_promotion_decision: "候选模型尚未通过评测",
  quality_gates_failed: "候选模型未通过质量门控",
  circuit_breaker_open: "候选模型暂时熔断",
  MODEL_RATE_LIMITED: "本次未命中采样",
  MODEL_TIMEOUT: "候选模型响应超时",
  MODEL_SCHEMA_INVALID: "候选模型输出格式不合法",
  MODEL_POLICY_VIOLATION: "候选模型输出违反安全策略",
  MODEL_DISABLED: "候选模型未启用",
  MODEL_UNAVAILABLE: "候选模型不可用",
  candidate_invocation_failed: "候选模型调用失败",
  no_eligible_feature_input: "当前计划没有可用的结构化特征",
};

function CandidateAnnotation({ annotation }) {
  const available = Boolean(annotation?.available);
  return (
    <div className="ls-candidate" data-available={available ? "true" : "false"} aria-label="候选模型只读注解">
      <strong>{available ? "候选模型建议（只读）" : "候选模型建议不可用"}</strong>
      {available ? (
        <>
          <p className="ls-candidate__text">{annotation.summary}</p>
          {annotation.claim_codes?.length > 0 && (
            <small>依据：{annotation.claim_codes.map((code) => CANDIDATE_CLAIM_LABEL[code] || code).join("、")}</small>
          )}
          <small>来源：{annotation.model_key} · 提示版本 {annotation.prompt_version}</small>
        </>
      ) : (
        <small>已回退到确定性结果：{CANDIDATE_REASON_LABEL[annotation?.reason] || annotation?.reason || "不可用"}</small>
      )}
      <small className="ls-candidate__note">这是候选模型的只读展示，不会修改你的状态、计划或待办。</small>
    </div>
  );
}

function GoalExecutionCenter({ goals, plans, jobs, summary, activeRun, onGenerate, onControl, busy }) {
  const activeGoals = goals?.items || [];
  const [goalId, setGoalId] = useState(activeGoals[0]?.goal_id || "");
  const [minutes, setMinutes] = useState(60);
  useEffect(() => {
    if (!goalId && activeGoals[0]?.goal_id) setGoalId(activeGoals[0].goal_id);
  }, [activeGoals, goalId]);
  const currentPlan = plans?.items?.find((p) => p.status !== "REJECTED" && p.status !== "SUPERSEDED") || null;

  return (
    <section className="ls-section ls-goal-execution" aria-label="AI学习目标执行中心">
      <div className="ls-section__heading">
        <h2>AI 学习目标执行中心</h2>
        <span className="ls-section__hint">目标 → 计划 → 待办 → 跟进 → 重规划</span>
      </div>
      <form className="ls-goal-create" onSubmit={(event) => {
        event.preventDefault();
        if (goalId) onGenerate(goalId, Number(minutes));
      }}>
        <select aria-label="选择学习目标" value={goalId} onChange={(event) => setGoalId(event.target.value)} disabled={busy || activeGoals.length === 0}>
          {activeGoals.length === 0 && <option value="">先创建一个学习目标</option>}
          {activeGoals.map((goal) => <option key={goal.goal_id} value={goal.goal_id}>{goal.name || goal.goal_id}</option>)}
        </select>
        <input aria-label="每日可用分钟" type="number" min="1" max="1440" value={minutes} onChange={(event) => setMinutes(event.target.value)} />
        <button className="ls-btn ls-btn--primary ls-btn--sm" disabled={busy || !goalId}>生成计划草案</button>
      </form>
      {currentPlan && summary && (
        <div className="ls-goal-execution__summary" aria-label="阶段总结">
          <strong>{summary.headline}</strong>
          <span>完成度 {summary.completion_percent}% · {summary.executed_item_count}/{summary.planned_item_count} 项</span>
          <span>下一步：{summary.next_action}</span>
          {summary.recommendations?.map((item) => <small key={item}>{item}</small>)}
          <small className="ls-goal-execution__note">
            确认计划后，系统会在观测窗结束后自动核对执行情况；只有证据支持时才会调整计划。
          </small>
          {summary.candidate_annotation && <CandidateAnnotation annotation={summary.candidate_annotation} />}
        </div>
      )}
      <div className="ls-goal-execution__runs" aria-label="任务执行记录">
        {(jobs || []).filter((job) => job.job_kind === "learning_goal").slice(0, 5).map((job) => {
          const runId = job.latest_run_id;
          const status = activeRun?.run_id === runId ? activeRun.status : job.status;
          return (
            <article key={job.job_id} className="ls-goal-execution__run">
              <div><strong>{job.input_ref?.plan_id ? "学习计划" : "目标计划"}</strong><span aria-live="polite">{status}</span></div>
              <small>{job.updated_at ? formatRelativeTime(job.updated_at) : ""}</small>
              {activeRun?.run_id === runId && activeRun.error?.message && <small>{activeRun.error.message}</small>}
              {runId && <div className="ls-goal-execution__actions">
                {(status === "RUNNING" || status === "QUEUED") && <button className="ls-btn ls-btn--sm" onClick={() => onControl("pause", runId)} disabled={busy}>暂停</button>}
                {status === "PAUSED" && <button className="ls-btn ls-btn--sm" onClick={() => onControl("resume", runId)} disabled={busy}>恢复</button>}
                {(["FAILED", "PARTIAL", "CANCELLED"].includes(status)) && <button className="ls-btn ls-btn--sm" onClick={() => onControl("retry", runId)} disabled={busy}>重试</button>}
              </div>}
            </article>
          );
        })}
        {(!jobs || !jobs.some((job) => job.job_kind === "learning_goal")) && <EmptyState text="还没有目标执行记录" />}
      </div>
    </section>
  );
}

export { GoalExecutionCenter };
