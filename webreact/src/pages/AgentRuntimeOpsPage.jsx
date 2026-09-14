/**
 * AgentRuntimeOpsPage — 管理员只读的 Agent 运行观测页（/admin/agent-runtime）。
 *
 * 三条硬约束：
 * 1. **非管理员无入口**：页面自身再校验一次角色，非管理员直接回首页，不渲染任何运行数据。
 * 2. **严格只读**：没有重放、改状态、执行工具、查看原始模型内容的按钮。
 * 3. **不自动高频刷新**：默认手动刷新，可选 30 秒轮询，且离开页面即停止。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";

import { useApp } from "../app/AppContext.jsx";
import {
  canViewAgentOps,
  getAgentRunTrace,
  getAgentRuntimeOverview,
} from "../data/agentObservabilityApi.js";
import RuntimeOverview from "../components/agentOps/RuntimeOverview.jsx";
import RunTrace from "../components/agentOps/RunTrace.jsx";

const AUTO_REFRESH_MS = 30000;

export default function AgentRuntimeOpsPage() {
  const { session } = useApp();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [runId, setRunId] = useState("");
  const [trace, setTrace] = useState(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState(null);
  const mounted = useRef(true);

  const allowed = canViewAgentOps(session);

  const loadOverview = useCallback(async () => {
    if (!allowed) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getAgentRuntimeOverview(24);
      if (mounted.current) setOverview(data);
    } catch (err) {
      if (mounted.current) setError(err);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [allowed]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => { if (allowed) loadOverview(); }, [allowed, loadOverview]);

  useEffect(() => {
    if (!allowed || !autoRefresh) return undefined;
    const timer = setInterval(loadOverview, AUTO_REFRESH_MS);
    return () => clearInterval(timer);
  }, [allowed, autoRefresh, loadOverview]);

  const loadTrace = useCallback(async (targetRunId) => {
    const value = String(targetRunId || "").trim();
    if (!value) return;
    setTraceLoading(true);
    setTraceError(null);
    try {
      const data = await getAgentRunTrace(value);
      if (mounted.current) setTrace(data);
    } catch (err) {
      if (mounted.current) setTraceError(err);
    } finally {
      if (mounted.current) setTraceLoading(false);
    }
  }, []);

  if (!allowed) return <Navigate to="/home" replace />;

  return (
    <div className="agent-ops-page">
      <RuntimeOverview
        overview={overview}
        loading={loading}
        error={error}
        onRefresh={loadOverview}
      />

      <label className="agent-ops__auto">
        <input
          type="checkbox"
          checked={autoRefresh}
          onChange={(event) => setAutoRefresh(event.target.checked)}
        />
        每 30 秒自动刷新
      </label>

      <section className="agent-ops__lookup" aria-label="按运行 ID 查询时间线">
        <h2>运行时间线</h2>
        <form
          onSubmit={(event) => { event.preventDefault(); loadTrace(runId); }}
        >
          <input
            type="text"
            value={runId}
            placeholder="输入 run_id"
            onChange={(event) => setRunId(event.target.value)}
          />
          <button type="submit" className="ls-btn">查询</button>
        </form>
      </section>

      <RunTrace
        trace={trace}
        loading={traceLoading}
        error={traceError}
        onClose={() => { setTrace(null); setTraceError(null); }}
      />
    </div>
  );
}
