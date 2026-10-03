import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as api from '../data/learnerStateApi.js';
import * as runtimeApi from '../data/agentRuntimeApi.js';
import { useAgentRun } from './useAgentRun.js';
import { useAsyncResource as useAsync } from './useAsyncResource.js';

/** Own data loading and mutations for the learning state page. */
export function useLearningState() {
  const [evidenceSnapshot, setEvidenceSnapshot] = useState(null);
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const toastTimer = useRef(null);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const snapshots = useAsync(() => api.getLearnerStateSnapshots({ pageSize: 50 }), [refreshKey]);
  const worldSnapshots = useAsync(() => api.getLearnerStateSnapshots({ pageSize: 50, projectionKind: "WORLD" }), [refreshKey]);
  const changes = useAsync(() => api.getLearnerStateChanges({ pageSize: 20 }), [refreshKey]);
  const forecasts = useAsync(() => api.getForecasts({ horizonDays: 7, pageSize: 30 }), [refreshKey]);
  const goals = useAsync(() => api.getStudentGoals({ status: "active" }), [refreshKey]);
  const plans = useAsync(() => api.getLearningPlans(1, 10), [refreshKey]);
  const interventions = useAsync(() => api.getAdaptiveInterventions(1, 5), [refreshKey]);
  const currentIntervention = interventions.data?.items?.find((item) => item.status !== "SUPERSEDED") || null;
  const interventionOutcome = useAsync(
    () => (currentIntervention ? api.getAdaptiveInterventionOutcome(currentIntervention.intervention_id) : Promise.resolve(null)),
    [currentIntervention?.intervention_id, refreshKey],
  );
  const runtimeJobs = useAsync(() => runtimeApi.listAgentJobs(1, 20), [refreshKey]);
  const currentPlanId = useMemo(
    () => plans.data?.items?.find((plan) => !["REJECTED", "SUPERSEDED"].includes(plan.status))?.plan_id || null,
    [plans.data],
  );
  const planSummary = useAsync(
    () => (currentPlanId ? api.getPlanSummary(currentPlanId) : Promise.resolve(null)),
    [currentPlanId, refreshKey],
  );
  const controls = useAsync(() => api.getDataControls(), [refreshKey]);
  const summary = useAsync(() => api.getDataSummary(), [refreshKey]);
  const corrections = useAsync(() => api.getCorrections(1, 20), [refreshKey]);
  const transparency = useAsync(() => api.getModelTransparency(), [refreshKey]);

  const showToast = useCallback((msg) => {
    clearTimeout(toastTimer.current);
    setToast(msg);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  }, []);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const pendingRunId = useMemo(
    () => runtimeJobs.data?.find((job) => job.job_kind === "learning_goal" &&
      ["QUEUED", "RUNNING", "AWAITING_APPROVAL", "PAUSED"].includes(job.status))?.latest_run_id || null,
    [runtimeJobs.data],
  );
  const [trackedRunId, setTrackedRunId] = useState(null);
  const activeRunId = trackedRunId || pendingRunId;
  const activeRunState = useAgentRun({ runId: activeRunId, enabled: Boolean(activeRunId) });
  const handledTerminalRun = useRef(null);

  useEffect(() => {
    const run = activeRunState.run;
    if (!run || !activeRunState.isTerminal || handledTerminalRun.current === run.run_id) return;
    handledTerminalRun.current = run.run_id;
    if (run.status !== "SUCCEEDED") {
      showToast(run.status === "CANCELLED" ? "任务已取消，可重新发起" : "任务未完成，可稍后重试");
      return;
    }
    // 终态事件可见后再读取 Job，避免在异步写回 plan_id 前刷新出空计划。
    runtimeApi.getAgentJob(run.job_id).then((job) => {
      if (job?.input_ref?.plan_id) {
        showToast("计划草案已生成，请确认后创建待办");
        refresh();
      } else {
        showToast("任务已完成，但计划引用暂不可用，请重试");
      }
    }).catch(() => showToast("任务已完成，但计划加载失败，请重试"));
  }, [activeRunState.isTerminal, activeRunState.run, refresh, showToast]);

  const handleArchiveGoal = useCallback(async (goalId) => {
    setBusy(true);
    try {
      await api.archiveStudentGoal(goalId);
      showToast("已归档目标");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleCreateGoal = useCallback(async (body) => {
    setBusy(true);
    try { await api.createStudentGoal(body); showToast("目标已创建"); refresh(); return true; }
    catch (e) { showToast(e.message); return false; } finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleGoalProgress = useCallback(async (goalId, progress) => {
    setBusy(true);
    try { await api.recordGoalProgress(goalId, { progress_percent: progress, idempotency_key: `goal-progress-${goalId}-${progress}` }); showToast("进度已记录"); refresh(); }
    catch (e) { showToast(e.message); } finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleGoalUpdate = useCallback(async (goalId, body) => {
    setBusy(true);
    try { await api.updateStudentGoal(goalId, body); showToast("目标已更新"); refresh(); }
    catch (e) { showToast(e.message); } finally { setBusy(false); }
  }, [showToast, refresh]);

  const handlePlanAction = useCallback(async (action, planId) => {
    setBusy(true);
    try {
      if (action === "accept") await api.decideLearningPlan(planId, "ACCEPT");
      else if (action === "reject") await api.decideLearningPlan(planId, "REJECT");
      else if (action === "execute") await api.executeLearningPlan(planId);
      else if (action === "undo") await api.undoLearningPlan(planId);
      else if (action === "replan") await api.replanLearningPlan(planId, { idempotency_key: `replan-${Date.now()}` });
      showToast(`操作成功：${action}`);
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleGoalGenerate = useCallback(async (goalId, availableMinutes) => {
    setBusy(true);
    try {
      const job = await runtimeApi.createAgentJob(
        { job_kind: "learning_goal", input_ref: { goal_id: goalId, available_minutes: availableMinutes } },
        `learning-goal-${goalId}-${Date.now()}`,
      );
      setTrackedRunId(job?.latest_run_id || null);
      showToast("任务已加入队列，正在准备计划");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleGoalRunControl = useCallback(async (action, runId) => {
    setBusy(true);
    try {
      const key = `learning-goal-${action}-${runId}`;
      if (action === "pause") await runtimeApi.pauseAgentRun(runId, "学生在目标中心暂停", key);
      else if (action === "resume") await runtimeApi.resumeAgentRun(runId, key);
      else await runtimeApi.retryAgentRun(runId, key);
      showToast(action === "pause" ? "已暂停执行" : action === "resume" ? "已恢复执行" : "已创建重试运行");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleToggleSource = useCallback(async (sourceKey, status) => {
    setBusy(true);
    try {
      await api.updateDataControl(sourceKey, status, `toggle-${Date.now()}`);
      showToast(status === "PAUSED" ? "已暂停" : "已恢复");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleDelete = useCallback(async (scope) => {
    setBusy(true);
    try {
      await api.requestDeletion(scope, `delete-${Date.now()}`);
      showToast("删除完成");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleRevokeCorrection = useCallback(async (cid) => {
    setBusy(true);
    try {
      await api.revokeCorrection(cid, `revoke-${Date.now()}`);
      showToast("已撤销纠正");
      refresh();
    } catch (e) { showToast(e.message); }
    finally { setBusy(false); }
  }, [showToast, refresh]);

  const handleMarkInaccurate = useCallback((snap) => {
    setEvidenceSnapshot(snap);
  }, []);

  return {
    evidenceSnapshot,
    setEvidenceSnapshot,
    toast,
    busy,
    snapshots,
    worldSnapshots,
    changes,
    forecasts,
    goals,
    plans,
    currentIntervention,
    interventionOutcome,
    runtimeJobs,
    planSummary,
    controls,
    summary,
    corrections,
    transparency,
    activeRunState,
    handleArchiveGoal,
    handleCreateGoal,
    handleGoalProgress,
    handleGoalUpdate,
    handlePlanAction,
    handleGoalGenerate,
    handleGoalRunControl,
    handleToggleSource,
    handleDelete,
    handleRevokeCorrection,
    handleMarkInaccurate
  };
}
