/**
 * useAgentRun — 管理一个 agent run 的完整状态：初始拉取 + SSE 订阅 + 取消。
 *
 * - 初始 GET /agent-runs/:id 获取 run 快照。
 * - 订阅 /agent-runs/:id/events/stream 实时事件。
 * - 事件中的 status/phase/progress 反映到 run 状态。
 * - 暴露 loading/error/streamStatus/events/cancel/refresh。
 * - 稳定 Idempotency-Key 由调用方在流程状态中保存（见各页面）。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "../data/agentRuntimeApi.js";
import { useAgentSse } from "./useAgentSse.js";
import { isTerminalRunStatus, runStatusLabel } from "../data/agentContracts.js";

export function useAgentRun({ runId, enabled = true }) {
  const [loading, setLoading] = useState(Boolean(runId));
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [events, setEvents] = useState([]);

  const handleEvent = useCallback((payload) => {
    if (!payload) return;
    setEvents((prev) => {
      if (prev.some((e) => e.sequence === payload.sequence)) return prev;
      return [...prev, payload].sort((a, b) => a.sequence - b.sequence);
    });
    if (payload.status || payload.phase || payload.progress) {
      setRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          ...(payload.status ? { status: payload.status } : {}),
          ...(payload.phase ? { phase: payload.phase } : {}),
          ...(payload.progress ? { progress: payload.progress } : {}),
          ...(payload.artifact_id ? { artifact_ids: Array.from(new Set([...(prev.artifact_ids || []), payload.artifact_id])) } : {}),
        };
      });
    }
  }, []);

  const sse = useAgentSse({ runId, onEvent: handleEvent, enabled: enabled && Boolean(runId) && !isTerminalRunStatus(run?.status) });

  const refresh = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAgentRun(runId);
      setRun(data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      setLoading(false);
      return;
    }
    refresh();
  }, [runId, refresh]);

  // run 到达终态后,若 artifact_ids 缺失,重新 GET 获取完整产物列表
  useEffect(() => {
    if (run && isTerminalRunStatus(run.status) && runId && (!run.artifact_ids || run.artifact_ids.length === 0)) {
      api.getAgentRun(runId).then((data) => { setRun(data); }).catch(() => {});
    }
  }, [run?.status, run?.artifact_ids, runId]);

  const cancel = useCallback(async (idempotencyKey) => {
    if (!runId) return;
    try {
      await api.cancelAgentRun(runId, idempotencyKey);
      sse.cancel();
      await refresh();
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [runId, sse, refresh]);

  const approval = useMemo(() => {
    const last = [...events].reverse().find((e) => e.approval_id);
    if (!last?.approval_id) return null;
    return { approval_id: last.approval_id, run_id: runId };
  }, [events, runId]);

  const isTerminal = useMemo(() => isTerminalRunStatus(run?.status), [run?.status]);

  return {
    loading,
    run,
    events,
    error: error || sse.error,
    streamStatus: sse.status,
    streamStatusLabel: sse.statusLabel,
    isLive: sse.isLive,
    isTerminal,
    approval,
    cancel,
    refresh,
    statusLabel: run ? runStatusLabel(run.status) : "状态待确认",
  };
}