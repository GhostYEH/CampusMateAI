import { useState } from 'react';

const DELETE_SCOPES = [
  { value: "STATE_ONLY", label: "仅状态投影", desc: "删除投影 run、snapshot 和 evidence" },
  { value: "EVENTS_AND_STATE", label: "事件与状态", desc: "删除 Learner Event 及其派生状态" },
  { value: "PLANS_ONLY", label: "仅行动计划", desc: "删除计划、计划项、反馈和评估" },
  { value: "MODEL_SHADOW_ONLY", label: "仅模型影子", desc: "删除在线影子记录" },
  { value: "ALL_LEARNER_MODEL_DATA", label: "全部学生模型数据", desc: "删除上述所有派生数据" },
];

function DataPrivacyControl({ controls, summary, onToggleSource, onDelete, corrections, onRevokeCorrection, busy }) {
  const [deleteScope, setDeleteScope] = useState(null);

  return (
    <section className="ls-section ls-privacy" aria-label="数据与隐私控制">
      <h3>数据源控制</h3>
      {controls?.items?.map((src) => (
        <div key={src.source_key} className="ls-source-row">
          <span className="ls-source-row__name">{SOURCE_LABEL[src.source_key] || src.source_key}</span>
          <span className={`ls-source-row__status ls-source-row__status--${(src.status || "").toLowerCase()}`}>{SOURCE_STATUS_LABEL[src.status] || src.status}</span>
          {src.can_pause && <button className="ls-btn ls-btn--sm" onClick={() => onToggleSource(src.source_key, "PAUSED")} disabled={busy}>暂停</button>}
          {src.can_resume && <button className="ls-btn ls-btn--sm" onClick={() => onToggleSource(src.source_key, "ENABLED")} disabled={busy}>恢复</button>}
        </div>
      ))}

      <h3>数据摘要</h3>
      {summary && (
        <div className="ls-summary-grid">
          <div className="ls-summary-item"><span>事件</span><strong>{summary.event_count || 0}</strong></div>
          <div className="ls-summary-item"><span>快照</span><strong>{summary.snapshot_count || 0}</strong></div>
          <div className="ls-summary-item"><span>计划</span><strong>{summary.learning_plan_count || 0}</strong></div>
          <div className="ls-summary-item"><span>影子</span><strong>{summary.shadow_run_count || 0}</strong></div>
        </div>
      )}

      <h3>删除学生模型数据</h3>
      <div className="ls-delete-zone">
        {DELETE_SCOPES.map((s) => (
          <label key={s.value} className="ls-delete-option">
            <input type="radio" name="delete-scope" value={s.value} onChange={() => setDeleteScope(s.value)} />
            <span className="ls-delete-option__label">{s.label}</span>
            <span className="ls-delete-option__desc">{s.desc}</span>
          </label>
        ))}
        {deleteScope && (
          <div className="ls-delete-confirm">
            <p>确认删除「{DELETE_SCOPES.find((s) => s.value === deleteScope)?.label}」？此操作不可撤销。</p>
            <button className="ls-btn ls-btn--danger" onClick={() => onDelete(deleteScope)} disabled={busy}>确认删除</button>
          </div>
        )}
      </div>

      {corrections?.items?.length > 0 && (
        <>
          <h3>状态纠正记录</h3>
          {corrections.items.map((c) => (
            <div key={c.correction_id} className="ls-correction-row">
              <span>{c.correction_type}</span>
              <span>{c.reason_code}</span>
              <span>{c.status === "ACTIVE" ? "活跃" : "已撤销"}</span>
              {c.status === "ACTIVE" && <button className="ls-btn ls-btn--sm" onClick={() => onRevokeCorrection(c.correction_id)} disabled={busy}>撤销</button>}
            </div>
          ))}
        </>
      )}
    </section>
  );
}

const SOURCE_LABEL = {
  CORE_STUDY: "核心学习记录", PERSONAL_TASK: "个人待办", CHAOXING: "学习通",
  EDU: "教务系统", MODEL_SHADOW: "模型影子评测", PROACTIVE_SUGGESTIONS: "主动建议",
};

const SOURCE_STATUS_LABEL = { ENABLED: "已启用", PAUSED: "已暂停", DISCONNECTED: "已断开", DELETE_REQUESTED: "删除请求中" };

export { DataPrivacyControl };
