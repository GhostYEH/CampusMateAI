const DATA_QUALITY_LABEL = {
  FRESH: "数据较新",
  PARTIAL: "部分数据可用",
  STALE: "数据可能已过期",
  UNAVAILABLE: "暂时没有足够数据",
};

const CONFIDENCE_LABEL = (c) => {
  if (c >= 0.7) return "证据较充分";
  if (c >= 0.35) return "证据一般";
  return "证据有限";
};

function Spinner({ label = "加载中" }) {
  return <div className="ls-loading" aria-busy="true" aria-live="polite">{label}…</div>;
}

function ErrorBar({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="ls-error" role="alert">
      <span>{error.message || "操作失败，请稍后重试"}</span>
      {onRetry && <button onClick={onRetry} className="ls-retry-btn">重试</button>}
    </div>
  );
}

function EmptyState({ text = "暂时没有数据" }) {
  return <div className="ls-empty">{text}</div>;
}

function QualityBadge({ quality }) {
  return <span className={`ls-quality ls-quality--${(quality || "UNAVAILABLE").toLowerCase()}`}>{DATA_QUALITY_LABEL[quality] || "未知"}</span>;
}

function ConfidenceBadge({ confidence }) {
  return <span className="ls-confidence">{CONFIDENCE_LABEL(confidence)}</span>;
}

function formatTime(iso) {
  if (!iso) return "未知";
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60000) return "刚刚";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return d.toLocaleDateString("zh-CN");
  } catch { return "未知"; }
}

export { DATA_QUALITY_LABEL, Spinner, ErrorBar, EmptyState, QualityBadge, ConfidenceBadge, formatTime };
