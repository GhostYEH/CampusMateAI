/**
 * NoticeWorkflowPage — 通知事务 Agent 工作台。
 *
 * 流程：粘贴文本 → POST /notices/manual（得 notice_id）→ POST /notices/:id/workflow → 订阅 → 决策。
 *
 * 关键约束（任务 §6）：
 * - 保留当前 NoticeCenter（不修改、不删除其直接建任务能力）。
 * - 用户粘贴文本时先登记 server notice，再创建 workflow。
 * - 不把旧的"提取后直接 createTask"偷偷作为自动执行路径。
 * - AUTO_SAFE 动作由后端执行；CONFIRM_REQUIRED 提供决策入口；MANUAL_ONLY 仅引导。
 * - 稳定 Idempotency-Key 保存在组件状态。
 */
import { useCallback, useEffect, useState } from "react";
import { PageFrame, Panel, SectionHeading, BackLink } from "../components/Primitives.jsx";
import AgentErrorBoundary from "../components/agent/ErrorBoundary.jsx";
import RunProgress from "../components/agent/RunProgress.jsx";
import NoticeWorkflowForm from "../components/noticeWorkflow/NoticeWorkflowForm.jsx";
import NoticeWorkflowView from "../components/noticeWorkflow/NoticeWorkflowView.jsx";
import { useAgentRun } from "../hooks/useAgentRun.js";
import * as api from "../data/agentRuntimeApi.js";
import { createIdempotencyKey } from "../data/agentContracts.js";

export default function NoticeWorkflowPage() {
  const [workflow, setWorkflow] = useState(null);
  const [activeRunId, setActiveRunId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [resolvingActionId, setResolvingActionId] = useState(null);
  const [actionKeys, setActionKeys] = useState(() => ({}));

  const run = useAgentRun({ runId: activeRunId });

  const handleSubmit = useCallback(async ({ content, source_label, manual_key, workflow_key }) => {
    setSubmitting(true);
    setError(null);
    setWorkflow(null);
    try {
      const notice = await api.createManualNotice({
        title: source_label || content.slice(0, 64),
        content,
        source_name: source_label || null,
      }, manual_key);
      if (!notice?.notice_id) throw new Error("未收到服务端通知 ID，请重试");
      const created = await api.createNoticeWorkflow(notice.notice_id, { idempotency_key: workflow_key }, workflow_key);
      setWorkflow(created);
      if (created?.run_id) setActiveRunId(created.run_id);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }, []);

  const refreshWorkflow = useCallback(async (workflowId) => {
    if (!workflowId) return;
    try {
      const data = await api.getNoticeWorkflow(workflowId);
      setWorkflow(data);
    } catch { /* 忽略轮询错误 */ }
  }, []);

  useEffect(() => {
    if (!workflow?.workflow_id) return;
    const timer = setInterval(() => refreshWorkflow(workflow.workflow_id), 8000);
    return () => clearInterval(timer);
  }, [workflow?.workflow_id, refreshWorkflow]);

  const getActionKey = useCallback((actionId) => {
    setActionKeys((prev) => {
      if (prev[actionId]) return prev;
      return { ...prev, [actionId]: createIdempotencyKey(`notice_action_${actionId}`) };
    });
  }, []);

  const handleDecideAction = useCallback(async (actionId, decision) => {
    getActionKey(actionId);
    setResolvingActionId(actionId);
    setError(null);
    try {
      const key = actionKeys[actionId] || createIdempotencyKey(`notice_action_${actionId}`);
      await api.decideNoticeWorkflowAction(actionId, decision, "用户决策", key);
      if (workflow?.workflow_id) await refreshWorkflow(workflow.workflow_id);
    } catch (err) {
      setError(err);
    } finally {
      setResolvingActionId(null);
    }
  }, [actionKeys, getActionKey, workflow, refreshWorkflow]);

  const handleExecuteAction = useCallback(async (actionId) => {
    getActionKey(actionId);
    setResolvingActionId(actionId);
    setError(null);
    try {
      const key = actionKeys[actionId] || createIdempotencyKey(`notice_action_${actionId}`);
      await api.executeNoticeWorkflowAction(actionId, key);
      if (workflow?.workflow_id) await refreshWorkflow(workflow.workflow_id);
    } catch (err) {
      setError(err);
    } finally {
      setResolvingActionId(null);
    }
  }, [actionKeys, getActionKey, workflow, refreshWorkflow]);

  return (
    <PageFrame
      eyebrow="Agent 工作台"
      title="通知事务"
      description="把校园通知变成安全的可跟踪流程，外部动作需你手动完成。"
      actions={<BackLink to="/notifications">返回通知中心</BackLink>}
    >
      <AgentErrorBoundary>
        <div className="agent-workspace notice-workflow-workspace">
          <Panel className="workspace-main">
            <SectionHeading title="新建流程" detail="先登记通知，再生成受控流程。" />
            <NoticeWorkflowForm onSubmit={handleSubmit} submitting={submitting} error={error} />
          </Panel>

          <Panel className="workspace-side">
            <SectionHeading title="流程与动作" />
            <NoticeWorkflowView
              workflow={workflow}
              onDecideAction={handleDecideAction}
              onExecuteAction={handleExecuteAction}
              resolvingActionId={resolvingActionId}
              error={error}
            />
            {activeRunId && (
              <RunProgress
                run={run.run}
                events={run.events}
                streamStatus={run.streamStatus}
                streamStatusLabel={run.streamStatusLabel}
                loading={run.loading}
                error={run.error}
                onCancel={() => run.cancel(createIdempotencyKey("notice_cancel"))}
              />
            )}
          </Panel>
        </div>
      </AgentErrorBoundary>
    </PageFrame>
  );
}