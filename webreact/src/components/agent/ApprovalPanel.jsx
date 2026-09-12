import {
  approvalStatusLabel,
  riskLevelLabel,
  isSafeToAct,
  canResolveApproval,
  isTerminalApprovalStatus,
} from "../../data/agentContracts.js";

/**
 * ApprovalPanel — 显示审批请求与决策入口。
 *
 * 关键约束：
 * - MANUAL_ONLY 只展示手动引导，不提供"执行"按钮（isSafeToAct=false）。
 * - CONFIRM_REQUIRED 提供"同意/拒绝"按钮，决策带 Idempotency-Key（由调用方保存）。
 * - 终态或未知 approval 禁止操作（canResolveApproval）。
 * - 风险等级用文字 + 图标表达，不只靠颜色。
 * - 不展示 prompt、chain-of-thought 或敏感 trace。
 */
export default function ApprovalPanel({
  approval,
  onApprove,
  onReject,
  onOpenManual,
  resolving = false,
  error = null,
  idempotencyKey,
}) {
  if (!approval) return null;

  const status = approval.status;
  const riskLevel = approval.risk_level;
  const canAct = canResolveApproval(status);
  const terminal = isTerminalApprovalStatus(status);
  const allowExecute = isSafeToAct(riskLevel);
  const isManual = riskLevel === "MANUAL_ONLY";

  return (
    <section className="agent-approval-panel" aria-labelledby="approval-title">
      <h3 id="approval-title">需要你确认</h3>

      <dl className="approval-meta">
        <dt>状态</dt>
        <dd>{approvalStatusLabel(status)}</dd>
        <dt>风险等级</dt>
        <dd className={`risk-${riskLevel || "unknown"}`}>{riskLevelLabel(riskLevel)}</dd>
        {approval.action_summary && (
          <>
            <dt>待确认动作</dt>
            <dd>{approval.action_summary}</dd>
          </>
        )}
        {approval.expires_at && (
          <>
            <dt>有效期至</dt>
            <dd>{formatTime(approval.expires_at)}</dd>
          </>
        )}
      </dl>

      {error && (
        <p className="approval-error" role="alert">
          {error.message || error}
        </p>
      )}

      {terminal && (
        <p className="approval-terminal-note">该确认已结束，无法再次操作。</p>
      )}

      {isManual && !terminal && (
        <div className="approval-manual-guide" role="note">
          <p>该动作需要你手动完成（例如登录教务系统、提交作业、支付费用）。这里仅提供步骤引导，不会代你执行。</p>
          {onOpenManual && (
            <button className="button button-secondary" type="button" onClick={onOpenManual}>
              查看操作指引
            </button>
          )}
        </div>
      )}

      {!isManual && canAct && !terminal && (
        <div className="approval-actions">
          <button
            className="button button-primary approval-approve-btn"
            type="button"
            onClick={() => onApprove?.(idempotencyKey)}
            disabled={resolving}
            aria-label="同意该动作"
          >
            {resolving ? "处理中…" : "同意"}
          </button>
          <button
            className="button button-secondary approval-reject-btn"
            type="button"
            onClick={() => onReject?.(idempotencyKey)}
            disabled={resolving}
            aria-label="拒绝该动作"
          >
            拒绝
          </button>
        </div>
      )}

      {allowExecute && canAct && !terminal && onApprove && (
        <p className="approval-safe-note">该动作可安全自动执行，确认后将立即生效。</p>
      )}
    </section>
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