import { artifactTypeLabel } from "../../data/agentContracts.js";

/**
 * ArtifactViewer — 显示 agent 产物元信息与下载入口。
 *
 * 关键约束：
 * - 只展示元信息（类型、版本、大小、时间、内容哈希），不内联完整内容。
 * - 不展示 prompt、chain-of-thought、完整上下文或敏感 trace。
 * - 下载链接由后端 download_url 提供，复用 axios client 鉴权（同源 cookie + token）。
 * - 未知 artifact_type 显示"产物类型待确认"。
 */
export default function ArtifactViewer({ artifact, onDownload, loading = false }) {
  if (loading && !artifact) {
    return (
      <section className="agent-artifact-viewer state-card loading-state" aria-busy="true">
        <span className="loading-orb" aria-hidden="true" />
        <p>正在加载产物…</p>
      </section>
    );
  }
  if (!artifact) {
    return (
      <section className="agent-artifact-viewer state-card empty-state">
        <p>暂无产物</p>
      </section>
    );
  }

  const typeLabel = artifactTypeLabel(artifact.artifact_type);
  const sizeText = formatSize(artifact.size_bytes);

  return (
    <section className="agent-artifact-viewer" aria-labelledby="artifact-title">
      <h3 id="artifact-title">产物</h3>
      <dl className="artifact-meta">
        <dt>类型</dt>
        <dd>{typeLabel}</dd>
        {typeof artifact.version === "number" && (
          <>
            <dt>版本</dt>
            <dd>v{artifact.version}</dd>
          </>
        )}
        {sizeText && (
          <>
            <dt>大小</dt>
            <dd>{sizeText}</dd>
          </>
        )}
        {artifact.content_hash && (
          <>
            <dt>校验</dt>
            <dd className="artifact-hash" title={artifact.content_hash}>{shortHash(artifact.content_hash)}</dd>
          </>
        )}
        {artifact.created_at && (
          <>
            <dt>生成时间</dt>
            <dd>{formatTime(artifact.created_at)}</dd>
          </>
        )}
      </dl>
      {artifact.download_url && (
        <button
          className="button button-secondary artifact-download-btn"
          type="button"
          onClick={() => onDownload?.(artifact)}
          aria-label={`下载${typeLabel}`}
        >
          下载产物
        </button>
      )}
    </section>
  );
}

function formatSize(bytes) {
  if (typeof bytes !== "number" || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function shortHash(hash) {
  if (!hash || typeof hash !== "string") return "—";
  return hash.length > 16 ? `${hash.slice(0, 12)}…` : hash;
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