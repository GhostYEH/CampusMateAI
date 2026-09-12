import { itemsOf } from "../../data/contracts.js";
import {
  noticeWorkflowStatusLabel,
  noticeActionStatusLabel,
  riskLevelLabel,
  isSafeToAct,
  canResolveApproval,
} from "../../data/agentContracts.js";

/**
 * NoticeWorkflowView — 展示通知流程状态与动作清单。
 *
 * 关键约束：
 * - AUTO_SAFE 动作可由后端自动执行，前端展示"已自动执行"。
 * - CONFIRM_REQUIRED 动作展示"同意/拒绝"入口。
 * - MANUAL_ONLY 动作只展示引导，不提供执行按钮。
 * - 不展示 prompt、chain-of-thought 或敏感 trace。
 */
export default function NoticeWorkflowView({
  workflow,
  onDecideAction,
  onExecuteAction,
  onOpenManual,
  resolvingActionId = null,
  error = null,
}) {
  if (!workflow) {
    return (
      <section className="notice-workflow-view state-card empty-state">
        <p>提交通知后将展示流程与待办动作。</p>
      </section>
    );
  }

  const actions = itemsOf(workflow.actions);

  return (
    <section className="notice-workflow-view" aria-labelledby="nw-view-title">
      <h3 id="nw-view-title">流程详情</h3>
      {error && <p className="form-error" role="alert">{error.message || error}</p>}

      <dl className="workflow-meta">
        <dt>流程状态</dt>
        <dd>{noticeWorkflowStatusLabel(workflow.status)}</dd>
        {workflow.source_label && (
          <>
            <dt>来源</dt>
            <dd>{workflow.source_label}</dd>
          </>
        )}
        {workflow.created_at && (
          <>
            <dt>创建时间</dt>
            <dd>{formatTime(workflow.created_at)}</dd>
          </>
        )}
      </dl>

      {actions.length === 0 ? (
        <p className="workflow-empty">暂无待办动作。</p>
      ) : (
        <ol className="action-list" aria-label="动作清单">
          {actions.map((action) => (
            <li key={action.action_id || action.id} className={`action-item risk-${action.risk_level || "unknown"}`}>
              <div className="action-head">
                <span className="action-summary">{action.action_summary || action.title || "未命名动作"}</span>
                <span className="action-status">{noticeActionStatusLabel(action.status)}</span>
              </div>
              {action.risk_level && (
                <span className={`action-risk risk-${action.risk_level}`}>
                  风险：{riskLevelLabel(action.risk_level)}
                </span>
              )}
              <ActionControls
                action={action}
                onDecideAction={onDecideAction}
                onExecuteAction={onExecuteAction}
                onOpenManual={onOpenManual}
                resolving={resolvingActionId === (action.action_id || action.id)}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function ActionControls({ action, onDecideAction, onExecuteAction, onOpenManual, resolving }) {
  const id = action.action_id || action.id;
  const status = action.status;
  const risk = action.risk_level;
  const canDecide = canResolveApproval(status) || status === "PROPOSED";
  const allowExecute = isSafeToAct(risk);

  if (status === "DONE" || status === "REJECTED" || status === "EXPIRED" || status === "FAILED") {
    return null;
  }

  if (risk === "MANUAL_ONLY") {
    return (
      <div className="action-manual" role="note">
        <p>需手动完成（如登录教务系统、提交作业）。仅提供指引，不会代你执行。</p>
        {onOpenManual && (
          <button className="button button-secondary" type="button" onClick={() => onOpenManual(action)}>
            查看指引
          </button>
        )}
      </div>
    );
  }

  if (!canDecide) return null;

  return (
    <div className="action-controls">
      {allowExecute && onExecuteAction && (
        <button
          className="button button-primary"
          type="button"
          disabled={resolving}
          onClick={() => onExecuteAction(id)}
        >
          {resolving ? "处理中…" : "执行"}
        </button>
      )}
      {onDecideAction && (
        <>
          <button
            className="button button-secondary"
            type="button"
            disabled={resolving}
            onClick={() => onDecideAction(id, "APPROVED")}
            aria-label={`同意：${action.action_summary || ""}`}
          >
            同意
          </button>
          <button
            className="button button-secondary"
            type="button"
            disabled={resolving}
            onClick={() => onDecideAction(id, "REJECTED")}
            aria-label={`拒绝：${action.action_summary || ""}`}
          >
            拒绝
          </button>
        </>
      )}
    </div>
  );
}

function formatTime(value) {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return String(value);
  }
}