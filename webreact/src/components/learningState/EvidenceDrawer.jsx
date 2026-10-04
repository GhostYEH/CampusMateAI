import { formatRelativeTime } from "../../utils/date.js";
import { useState, useEffect, useCallback } from 'react';
import { useAsyncResource as useAsync } from '../../hooks/useAsyncResource.js';
import * as api from '../../data/learnerStateApi.js';
import { Spinner, ErrorBar, EmptyState } from './shared.jsx';

function EvidenceDrawer({ snapshot, onClose, onCorrection }) {
  const [page, setPage] = useState(1);
  const [correctionType, setCorrectionType] = useState(null);
  const [correctionBusy, setCorrectionBusy] = useState(false);
  const [correctionMsg, setCorrectionMsg] = useState(null);
  const { loading, data, error } = useAsync(
    () => api.getSnapshotEvidence(snapshot.snapshot_id, page),
    [snapshot.snapshot_id, page]
  );

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSubmitCorrection = useCallback(async () => {
    if (!correctionType) return;
    setCorrectionBusy(true);
    try {
      await api.createCorrection({
        projection_kind: snapshot.projection_kind || "CORE",
        projection_scope: snapshot.projection_scope || "__user__",
        target_snapshot_id: snapshot.snapshot_id,
        scope_type: snapshot.scope_type,
        scope_id: snapshot.scope_id,
        state_type: snapshot.state_type,
        correction_type: correctionType,
        reason_code: "OTHER_CONTROLLED_REASON",
        idempotency_key: `corr-${snapshot.snapshot_id}-${Date.now()}`,
      });
      setCorrectionMsg("已提交纠正，投影将在下次读取时更新");
      if (onCorrection) onCorrection(snapshot);
    } catch (e) {
      setCorrectionMsg(e.message);
    } finally {
      setCorrectionBusy(false);
    }
  }, [correctionType, snapshot, onCorrection]);

  return (
    <div className="ls-drawer-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="证据详情">
      <div className="ls-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="ls-drawer__header">
          <h2>证据详情</h2>
          <button className="ls-drawer__close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="ls-drawer__body">
          {loading && <Spinner />}
          <ErrorBar error={error} />
          {!loading && !error && data?.items?.length === 0 && <EmptyState text="暂时没有证据" />}
          {!loading && !error && data?.items?.map((ev) => (
            <div key={`${ev.evidence_kind}-${ev.event_id || ev.source_category}`} className="ls-evidence-item">
              <p className="ls-evidence-item__kind">{EVIDENCE_KIND_LABEL[ev.evidence_kind] || ev.evidence_kind}</p>
              <p className="ls-evidence-item__source">{ev.source_category}</p>
              {ev.event_type && <p className="ls-evidence-item__type">{ev.event_type}</p>}
              <p className="ls-evidence-item__time">{formatRelativeTime(ev.occurred_at)}</p>
              <p className="ls-evidence-item__role">{ev.role === "SUPPORTS" ? "支持" : ev.role === "INVALIDATES" ? "否定" : "限制"}</p>
            </div>
          ))}
          {data?.has_more && (
            <button className="ls-more-btn" onClick={() => setPage((p) => p + 1)}>加载更多</button>
          )}
        </div>
        <div className="ls-drawer__correction">
          <h3>标记此状态</h3>
          {correctionMsg && <p className="ls-correction-msg">{correctionMsg}</p>}
          <div className="ls-correction-options">
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("MARK_INACCURATE")} disabled={correctionBusy}>标记不准确</button>
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("SOURCE_OUTDATED")} disabled={correctionBusy}>数据源已过时</button>
            <button className="ls-btn ls-btn--sm" onClick={() => setCorrectionType("NOT_APPLICABLE")} disabled={correctionBusy}>不适用</button>
          </div>
          {correctionType && (
            <button className="ls-btn ls-btn--primary" onClick={handleSubmitCorrection} disabled={correctionBusy}>
              {correctionBusy ? "提交中…" : `确认提交（${correctionType}）`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const EVIDENCE_KIND_LABEL = {
  EVENT: "学习事件",
  SOURCE_ROW: "业务记录",
  SYNC_STATUS: "同步状态",
};

export { EvidenceDrawer };
