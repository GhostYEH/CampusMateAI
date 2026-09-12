/**
 * FinalReviewPage — 期末复习 Agent 工作台。
 *
 * 流程：创建活动 → 生成计划（run）→ 审批激活 → 查看今日日程。
 * - 用 useAgentRun 订阅生成/调整 run 的 SSE。
 * - 稳定 Idempotency-Key 保存在组件状态，重复点击/重挂载不重复写入。
 * - 不把旧 LearningStatePage 的学习计划当成 Agent 版本计划（任务 §4）。
 * - 复用 Primitives 与共享 agent 组件。
 * - 可访问、响应式（≥320px）、键盘可达、prefers-reduced-motion 由 CSS 媒体查询处理。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageFrame, Panel, SectionHeading, Button, AsyncState } from "../components/Primitives.jsx";
import AgentErrorBoundary from "../components/agent/ErrorBoundary.jsx";
import RunProgress from "../components/agent/RunProgress.jsx";
import ApprovalPanel from "../components/agent/ApprovalPanel.jsx";
import ArtifactViewer from "../components/agent/ArtifactViewer.jsx";
import FinalReviewCampaignForm from "../components/finalReview/FinalReviewCampaignForm.jsx";
import FinalReviewPlanView from "../components/finalReview/FinalReviewPlanView.jsx";
import { useAgentRun } from "../hooks/useAgentRun.js";
import * as api from "../data/agentRuntimeApi.js";
import { itemsOf } from "../data/contracts.js";
import { createIdempotencyKey } from "../data/agentContracts.js";

export default function FinalReviewPage() {
  const [exams, setExams] = useState([]);
  const [examsLoading, setExamsLoading] = useState(true);
  const [campaign, setCampaign] = useState(null);
  const [planVersions, setPlanVersions] = useState([]);
  const [todayAgenda, setTodayAgenda] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState(null);
  const [activeRunId, setActiveRunId] = useState(null);
  const [approval, setApproval] = useState(null);
  const [resolveKey, setResolveKey] = useState(() => createIdempotencyKey("fr_resolve"));

  const run = useAgentRun({ runId: activeRunId });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getFinalReviewCampaigns();
        const list = itemsOf(data);
        if (!cancelled && list.length > 0) {
          setCampaign(list[0]);
          await refreshCampaignDetail(list[0].campaign_id);
        }
      } catch { /* 首次无活动属正常 */ } finally {
        if (!cancelled) setExamsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await import("../data/api.js").then((m) => m.getExams());
        if (!cancelled) setExams(data);
      } catch { /* 考试可选 */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const refreshCampaignDetail = useCallback(async (campaignId) => {
    try {
      const [versions, agenda] = await Promise.allSettled([
        api.getFinalReviewPlanVersions(campaignId),
        api.getTodayAgenda(campaignId),
      ]);
      if (versions.status === "fulfilled") setPlanVersions(versions.value);
      if (agenda.status === "fulfilled") setTodayAgenda(agenda.value);
    } catch { /* 忽略次要加载错误 */ }
  }, []);

  const handleCreateCampaign = useCallback(async (body) => {
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createFinalReviewCampaign(body, body.idempotency_key);
      setCampaign(created);
      await refreshCampaignDetail(created.campaign_id);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }, [refreshCampaignDetail]);

  const handleGenerate = useCallback(async (campaignId, body) => {
    setGenerating(true);
    setError(null);
    try {
      const result = await api.generateFinalReviewPlan(campaignId, body, body.idempotency_key);
      setActiveRunId(result.run_id);
    } catch (err) {
      setError(err);
    } finally {
      setGenerating(false);
    }
  }, []);

  const handleActivate = useCallback(async (campaignId, idempotencyKey) => {
    setActivating(true);
    setError(null);
    try {
      await api.activateFinalReviewCampaign(campaignId, idempotencyKey);
      await refreshCampaignDetail(campaignId);
    } catch (err) {
      setError(err);
    } finally {
      setActivating(false);
    }
  }, [refreshCampaignDetail]);

  useEffect(() => {
    if (!run.run) return;
    if (run.run.artifact_ids?.length && !artifact) {
      (async () => {
        try {
          const art = await api.getAgentArtifact(run.run.artifact_ids[0]);
          setArtifact(art);
        } catch { /* 忽略 */ }
      })();
    }
    const lastApproval = [...run.events].reverse().find((e) => e.approval_id);
    if (lastApproval?.approval_id) {
      setApproval((prev) => prev && prev.approval_id === lastApproval.approval_id ? prev : {
        approval_id: lastApproval.approval_id,
        status: "PENDING",
        risk_level: run.run.risk_level,
        action_summary: lastApproval.summary,
      });
    }
  }, [run.run, run.events, artifact]);

  const handleApprove = useCallback(async (idempotencyKey) => {
    if (!approval) return;
    try {
      await api.resolveAgentApproval(approval.approval_id, "APPROVED", "用户确认激活", idempotencyKey || resolveKey);
      setApproval((prev) => ({ ...prev, status: "APPROVED" }));
      if (campaign) await refreshCampaignDetail(campaign.campaign_id);
    } catch (err) {
      setError(err);
    }
  }, [approval, resolveKey, campaign, refreshCampaignDetail]);

  const handleReject = useCallback(async (idempotencyKey) => {
    if (!approval) return;
    try {
      await api.resolveAgentApproval(approval.approval_id, "REJECTED", "用户拒绝", idempotencyKey || resolveKey);
      setApproval((prev) => ({ ...prev, status: "REJECTED" }));
    } catch (err) {
      setError(err);
    }
  }, [approval, resolveKey]);

  const handleDownload = useCallback(async (art) => {
    if (!art?.download_url) return;
    const { client } = await import("../data/api.js");
    const response = await client.get(art.download_url, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `final-review-plan-v${art.version || 1}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <PageFrame eyebrow="Agent 工作台" title="期末复习" description="创建版本化复习计划，按日跟进并安全调整。">
      <AgentErrorBoundary>
        <div className="agent-workspace final-review-workspace">
          <Panel className="workspace-main">
            <SectionHeading title="活动与计划" detail="计划版本不可变，调整由后端裁决并生成新版本。" />
            <AsyncState loading={examsLoading} empty={examsLoading ? null : null}>
              {!campaign ? (
                <FinalReviewCampaignForm
                  exams={exams}
                  onSubmit={handleCreateCampaign}
                  submitting={submitting}
                  error={error}
                />
              ) : (
                <FinalReviewPlanView
                  campaign={campaign}
                  planVersions={planVersions}
                  todayAgenda={todayAgenda}
                  onGenerate={handleGenerate}
                  onActivate={handleActivate}
                  generating={generating}
                  activating={activating}
                  error={error}
                />
              )}
            </AsyncState>
          </Panel>

          <Panel className="workspace-side">
            <SectionHeading title="运行状态" />
            <RunProgress
              run={run.run}
              events={run.events}
              streamStatus={run.streamStatus}
              streamStatusLabel={run.streamStatusLabel}
              loading={run.loading}
              error={run.error}
              onCancel={() => run.cancel(createIdempotencyKey("fr_cancel"))}
            />
            {approval && approval.status === "PENDING" && (
              <ApprovalPanel
                approval={approval}
                onApprove={handleApprove}
                onReject={handleReject}
                idempotencyKey={resolveKey}
              />
            )}
            {artifact && <ArtifactViewer artifact={artifact} onDownload={handleDownload} />}
          </Panel>
        </div>
      </AgentErrorBoundary>
    </PageFrame>
  );
}