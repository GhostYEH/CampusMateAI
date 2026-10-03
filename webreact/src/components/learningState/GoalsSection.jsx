import { useState } from 'react';
import { EmptyState } from './shared.jsx';

const GOAL_CATEGORY_LABEL = {
  academic: "学业",
  research: "科研",
  competition: "竞赛",
  certificate: "证书",
  job_search: "求职",
  internship: "实习",
  campus_affair: "校园事务",
  health_habit: "健康习惯",
  personal_growth: "个人成长",
};

function GoalsSection({ goals, onArchive, onCreate, onProgress, onUpdate, busy }) {
  const items = goals?.items || [];
  const [draft, setDraft] = useState({ name: "", category: "academic", target_date: "", milestone_count: 0 });
  const [progress, setProgress] = useState({});
  const [milestones, setMilestones] = useState({});
  const [names, setNames] = useState({});
  return (
    <section className="ls-section ls-goals" aria-label="我的目标与里程碑">
      <form className="ls-goal-create" onSubmit={async (event) => { event.preventDefault(); const created = await onCreate({ ...draft, milestone_count: Number(draft.milestone_count), idempotency_key: `goal-${Date.now()}` }); if (created) setDraft({ name: "", category: "academic", target_date: "", milestone_count: 0 }); }}>
        <input aria-label="目标名称" required value={draft.name} placeholder="新建目标" onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        <select aria-label="目标分类" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>{Object.entries(GOAL_CATEGORY_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <button className="ls-btn ls-btn--sm" disabled={busy}>新建</button>
      </form>
      {items.length === 0 ? <EmptyState text="暂时没有目标数据" /> : (
      <div className="ls-goal-grid">
        {items.map((g) => (
          <article key={g.goal_id} className="ls-goal-card">
            <h3 className="ls-goal-card__name">{g.name || g.goal_id}</h3>
            <p className="ls-goal-card__category">{GOAL_CATEGORY_LABEL[g.category] || g.category}</p>
            <p className="ls-goal-card__progress">进度 {Math.round(g.progress_percent || 0)}%</p>
            <p className="ls-goal-card__milestones">里程碑 {g.milestone_count || 0}</p>
            {g.target_date && <p className="ls-goal-card__target">目标日期 {g.target_date}</p>}
            <p className="ls-goal-card__status">{g.status === "active" ? "进行中" : "已归档"}</p>
            {g.status === "active" && <div className="ls-goal-card__actions">
              <label>进度 <input type="number" min="0" max="100" value={progress[g.goal_id] ?? g.progress_percent} onChange={(e) => setProgress({ ...progress, [g.goal_id]: e.target.value })} /></label>
              <button className="ls-btn ls-btn--sm" onClick={() => onProgress(g.goal_id, Number(progress[g.goal_id] ?? g.progress_percent))} disabled={busy}>记录</button>
              <label>里程碑 <input type="number" min="0" max="100" value={milestones[g.goal_id] ?? g.milestone_count} onChange={(e) => setMilestones({ ...milestones, [g.goal_id]: e.target.value })} /></label>
              <button className="ls-btn ls-btn--sm" onClick={() => onUpdate(g.goal_id, { milestone_count: Number(milestones[g.goal_id] ?? g.milestone_count) })} disabled={busy}>保存</button>
              <label>名称 <input value={names[g.goal_id] ?? g.name} onChange={(e) => setNames({ ...names, [g.goal_id]: e.target.value })} /></label>
              <button className="ls-btn ls-btn--sm" onClick={() => onUpdate(g.goal_id, { name: names[g.goal_id] ?? g.name })} disabled={busy}>改名</button>
            </div>}
            {g.status === "active" && (
              <button className="ls-btn ls-btn--sm" onClick={() => onArchive(g.goal_id)} disabled={busy}>归档</button>
            )}
          </article>
        ))}
      </div>
      )}
    </section>
  );
}

export { GoalsSection };
