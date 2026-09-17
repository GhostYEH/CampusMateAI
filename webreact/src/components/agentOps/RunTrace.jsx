/**
 * RunTrace — 单个 Run 的安全时间线。
 *
 * 只展示状态、阶段、角色、模型名、Token、耗时、错误码与审批时长。
 * 后端已保证不含 prompt / 模型原文 / 凭据 / 原始工具参数；前端同样不做任何"展开原文"入口。
 * 未知事件类型只记录、不解释、不崩溃。
 */

const TERMINAL = new Set(["SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"]);

function formatMs(value) {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function isTerminalRunStatus(status) {
  return TERMINAL.has(status);
}

export default function RunTrace({ trace, loading, error, onClose }) {
  if (loading) {
    return <div className="state-card loading-state"><p>正在加载运行时间线…</p></div>;
  }
  if (error) {
    return (
      <div className="state-card error-state">
        <p>{error.message || "运行时间线加载失败"}</p>
        {onClose ? <button type="button" className="ls-btn" onClick={onClose}>关闭</button> : null}
      </div>
    );
  }
  if (!trace) return null;

  const { run, events = [], tool_calls: toolCalls = [], model_calls: modelCalls = [], approvals = [] } = trace;

  return (
    <section className="agent-ops__trace" aria-label="运行时间线">
      <header className="agent-ops__header">
        <h2>运行 {run.run_id}</h2>
        {onClose ? <button type="button" className="ls-btn" onClick={onClose}>关闭</button> : null}
      </header>

      <dl className="agent-ops__facts">
        <div><dt>状态</dt><dd>{run.status}</dd></div>
        <div><dt>阶段</dt><dd>{run.phase}</dd></div>
        <div><dt>处理器</dt><dd>{run.handler_code || "—"}{run.handler_version ? `@${run.handler_version}` : ""}</dd></div>
        <div><dt>尝试次数</dt><dd>{run.attempt_no}</dd></div>
        <div><dt>耗时</dt><dd>{formatMs(run.duration_ms)}</dd></div>
        <div><dt>错误码</dt><dd>{run.error_code || "—"}</dd></div>
      </dl>

      <div className="agent-ops__section">
        <h3>事件（{events.length}）</h3>
        {events.length === 0 ? <p>暂无事件。</p> : (
          <ol>
            {events.map((event) => (
              <li key={`${event.sequence}-${event.type}`}>
                <span className="agent-ops__seq">#{event.sequence}</span>
                <span className="agent-ops__type">{event.type}</span>
                <span>{event.status}</span>
                {event.summary ? <em>{event.summary}</em> : null}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="agent-ops__section">
        <h3>工具调用（{toolCalls.length}）</h3>
        {toolCalls.length === 0 ? <p>暂无工具调用。</p> : (
          <ul>
            {toolCalls.map((call) => (
              <li key={call.call_id}>
                <span>{call.tool_name}</span>
                <span>{call.status}</span>
                <span>{formatMs(call.duration_ms)}</span>
                {call.error_code ? <span>{call.error_code}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="agent-ops__section">
        <h3>模型调用（{modelCalls.length}）</h3>
        {modelCalls.length === 0 ? <p>暂无模型调用。</p> : (
          <ul>
            {modelCalls.map((call) => (
              <li key={call.call_id}>
                <span>{call.provider}</span>
                <span>{call.model}</span>
                <span>{call.route_policy}</span>
                <span>{call.total_tokens ?? 0} tokens</span>
                <span>{formatMs(call.latency_ms)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="agent-ops__section">
        <h3>审批（{approvals.length}）</h3>
        {approvals.length === 0 ? <p>暂无审批记录。</p> : (
          <ul>
            {approvals.map((approval) => (
              <li key={approval.approval_id}>
                <span>{approval.action_summary}</span>
                <span>{approval.status}</span>
                <span>{approval.risk_level}</span>
                <span>{formatMs(approval.wait_ms)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
