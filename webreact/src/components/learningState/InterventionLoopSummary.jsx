import { describeInterventionDecision, describeAdoption, describeObservedOutcome, describeInterventionScope, DECISION_STATE } from '../../data/interventionDecisionView.js';
import { formatTime } from './shared.jsx';

function InterventionLoopSummary({ intervention, outcome, loading, error, onRetry }) {
  if (!intervention) return null;
  const decision = describeInterventionDecision({ outcome, loading, error });
  const adoption = describeAdoption(outcome?.adoption);
  const observed = describeObservedOutcome(decision.observedOutcome);
  const scope = describeInterventionScope(intervention.scope_type);
  return <section className="ls-section" aria-label="当前干预闭环">
    <div className="ls-section__heading"><h2>当前干预闭环</h2><span className="ls-section__hint">基于可追溯证据，不作因果断言</span></div>
    <article className="ls-state-card">
      <p><strong>当前策略：</strong>{intervention.strategy_code}</p>
      <p><strong>选择依据：</strong>{intervention.rationale_codes?.join("、") || "状态证据有限"}</p>
      <p data-intervention-scope={scope.scope}><strong>归因范围：</strong>{scope.label}</p>
      <p className="ls-hint">{scope.detail}</p>
      <p><strong>执行采纳：</strong>{adoption}</p>
      <p><strong>观测结果：</strong>{observed}</p>
      <p>
        <strong>系统决定：</strong>
        <span
          className={`ls-decision ls-decision--${decision.tone}`}
          data-decision-state={decision.state}
          data-decision-status={decision.decisionStatus ?? ""}
          data-plan-switched={String(decision.applied)}
        >
          {decision.label}
        </span>
        {decision.state === DECISION_STATE.PENDING && decision.detail ? `（${decision.detail}）` : ""}
        {intervention.observation_due_at ? `（观测截至 ${formatTime(intervention.observation_due_at)}）` : ""}
      </p>
      {decision.state === DECISION_STATE.DECIDED && decision.detail && <p className="ls-hint">
        {decision.detail}
      </p>}
      {decision.state === DECISION_STATE.UNAVAILABLE && <p className="ls-error" role="alert">
        <span>{decision.detail || "系统决定暂时读不到，页面不会按状态差值推测决定。"}</span>
        {onRetry && <button onClick={onRetry} className="ls-retry-btn">重试</button>}
      </p>}
      {decision.reasonCodes.length > 0 && <p><strong>决定依据：</strong>{decision.reasonCodes.join("、")}</p>}
      {decision.adjustments.length > 0 && <p><strong>调整项：</strong>{decision.adjustments.join("、")}</p>}
      {intervention.supersedes_intervention_id && <p>来源干预：{intervention.supersedes_intervention_id}</p>}
    </article>
  </section>;
}

export { InterventionLoopSummary };
