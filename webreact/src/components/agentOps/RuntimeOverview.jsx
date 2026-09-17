/**
 * RuntimeOverview — 队列、成功率、耗时、Token、工具、重试与审批等待的聚合卡片。
 *
 * 只读：不提供任何写操作按钮。数据缺失或后端尚未产生样本时按"暂无样本"渲染，
 * 不使用 0 伪装成"健康"。
 */

const KNOWN_STATUS_ORDER = [
  "QUEUED",
  "RUNNING",
  "AWAITING_APPROVAL",
  "PAUSED",
  "SUCCEEDED",
  "PARTIAL",
  "FAILED",
  "CANCELLED",
];

const STATUS_LABEL = {
  QUEUED: "排队中",
  RUNNING: "运行中",
  AWAITING_APPROVAL: "等待审批",
  PAUSED: "已暂停",
  SUCCEEDED: "已完成",
  PARTIAL: "部分完成",
  FAILED: "失败",
  CANCELLED: "已取消",
};

function formatMs(value) {
  if (value === null || value === undefined) return "暂无样本";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatPercent(value) {
  if (value === null || value === undefined) return "暂无样本";
  return `${(value * 100).toFixed(1)}%`;
}

export function describeStatus(status) {
  return STATUS_LABEL[status] || "未知状态";
}

export default function RuntimeOverview({ overview, loading, error, onRefresh }) {
  if (loading) {
    return <div className="state-card loading-state"><p>正在加载运行概览…</p></div>;
  }
  if (error) {
    return (
      <div className="state-card error-state">
        <p>{error.message || "运行概览加载失败"}</p>
        <button type="button" className="ls-btn" onClick={onRefresh}>重试</button>
      </div>
    );
  }
  if (!overview) {
    return <div className="state-card"><p>暂无运行概览数据。</p></div>;
  }

  const distribution = overview.status_distribution || {};
  const known = KNOWN_STATUS_ORDER.filter((status) => distribution[status]);
  const unknown = Object.keys(distribution).filter((status) => !KNOWN_STATUS_ORDER.includes(status));

  return (
    <section className="agent-ops" aria-label="Agent 运行概览">
      <header className="agent-ops__header">
        <h2>运行概览</h2>
        <span className="agent-ops__window">最近 {overview.window_hours} 小时</span>
        <button type="button" className="ls-btn" onClick={onRefresh}>刷新</button>
      </header>

      <div className="agent-ops__cards">
        <article><h3>队列深度</h3><p>{overview.queue_depth}</p></article>
        <article><h3>陈旧租约</h3><p>{overview.stale_lease_count}</p></article>
        <article><h3>运行总数</h3><p>{overview.run_count}</p></article>
        <article><h3>成功率</h3><p>{formatPercent(overview.success_rate)}</p></article>
        <article><h3>总耗时 P50</h3><p>{formatMs(overview.duration_ms?.p50)}</p></article>
        <article><h3>总耗时 P95</h3><p>{formatMs(overview.duration_ms?.p95)}</p></article>
        <article><h3>模型耗时 P95</h3><p>{formatMs(overview.model_latency_ms?.p95)}</p></article>
        <article><h3>Token 总量</h3><p>{overview.token_usage?.total_tokens ?? 0}</p></article>
        <article><h3>工具调用</h3><p>{overview.tool_call_count}</p></article>
        <article><h3>工具失败</h3><p>{overview.tool_failure_count}</p></article>
        <article><h3>重试次数</h3><p>{overview.retry_count}</p></article>
        <article><h3>审批等待 P95</h3><p>{formatMs(overview.approval?.wait_p95_ms)}</p></article>
      </div>

      <div className="agent-ops__distribution">
        <h3>状态分布</h3>
        {known.length === 0 && unknown.length === 0 ? (
          <p>该时间窗内没有运行记录。</p>
        ) : (
          <ul>
            {known.map((status) => (
              <li key={status}><span>{describeStatus(status)}</span><strong>{distribution[status]}</strong></li>
            ))}
            {unknown.map((status) => (
              // 未知状态安全降级为只读计数，不解释、不提升权限、不崩溃。
              <li key={status}><span>其他（{status}）</span><strong>{distribution[status]}</strong></li>
            ))}
          </ul>
        )}
      </div>

      <div className="agent-ops__approval">
        <h3>审批</h3>
        <ul>
          <li><span>待处理</span><strong>{overview.approval?.pending ?? 0}</strong></li>
          <li><span>已处理</span><strong>{overview.approval?.resolved ?? 0}</strong></li>
          <li><span>已过期</span><strong>{overview.approval?.expired ?? 0}</strong></li>
          <li><span>等待 P50</span><strong>{formatMs(overview.approval?.wait_p50_ms)}</strong></li>
        </ul>
      </div>
    </section>
  );
}
