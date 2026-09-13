import { useState } from "react";
import { itemsOf } from "../../data/contracts.js";
import { createIdempotencyKey } from "../../data/agentContracts.js";

/**
 * FinalReviewPlanView — 展示不可变计划版本与今日日程。
 * 不把旧 LearningStatePage 的学习计划当成 Agent 版本计划（任务 §4）。
 * 计划版本只读，调整通过 AdjustmentProposal（后端裁决）。
 */
export default function FinalReviewPlanView({
  campaign,
  planVersions = [],
  todayAgenda = null,
  onGenerate,
  onActivate,
  onCheckin,
  onResolveProposal,
  generating = false,
  activating = false,
  checkingIn = false,
  checkinStatus = "",
  error = null,
}) {
  const [genKey, setGenKey] = useState(() => createIdempotencyKey("fr_generate"));
  const [actKey, setActKey] = useState(() => createIdempotencyKey("fr_activate"));
  const [checkinKey] = useState(() => createIdempotencyKey("fr_checkin"));
  const [completedItemIds, setCompletedItemIds] = useState([]);
  const [insufficientTime, setInsufficientTime] = useState(false);
  const [difficultyNotes, setDifficultyNotes] = useState("");
  const versions = itemsOf(planVersions);
  const agendaItems = itemsOf(todayAgenda?.items || todayAgenda);

  function toggleCompleted(itemId) {
    setCompletedItemIds((current) => current.includes(itemId)
      ? current.filter((id) => id !== itemId)
      : [...current, itemId]);
  }

  return (
    <section className="final-review-plan" aria-labelledby="fr-plan-title">
      <h3 id="fr-plan-title">复习计划</h3>
      {error && <p className="form-error" role="alert">{error.message || error}</p>}

      {!campaign && <p className="form-empty">请先创建活动。</p>}

      {campaign && versions.length === 0 && (
        <div className="plan-empty">
          <p>尚未生成计划。</p>
          <button
            className="button button-primary"
            type="button"
            disabled={generating}
            onClick={() => { onGenerate?.(campaign.campaign_id, { idempotency_key: genKey }); }}
          >
            {generating ? "正在生成…" : "生成计划提案"}
          </button>
        </div>
      )}

      {versions.length > 0 && (
        <div className="plan-versions">
          <h4>计划版本</h4>
          <ol className="version-list">
            {versions.map((v) => (
              <li key={v.version || v.plan_version_id} className={`version-item status-${v.status || "unknown"}`}>
                <span className="version-tag">v{v.version}</span>
                <span className="version-status">{v.status || "状态待确认"}</span>
                {v.created_at && <small>{v.created_at}</small>}
              </li>
            ))}
          </ol>
          <button
            className="button button-secondary"
            type="button"
            disabled={activating}
            onClick={() => onActivate?.(
              campaign.campaign_id,
              versions[versions.length - 1]?.version,
              actKey,
            )}
          >
            {activating ? "正在激活…" : "激活当前计划"}
          </button>
        </div>
      )}

      {agendaItems.length > 0 && (
        <div className="plan-agenda">
          <h4>今日日程</h4>
          <ul className="agenda-list">
            {agendaItems.map((item) => (
              <li key={item.item_id || item.id} className={`agenda-item priority-${item.priority || "normal"}`}>
                <span className="agenda-title">{item.title || item.task_title || "未命名"}</span>
                {item.scheduled_minutes && <small>约 {item.scheduled_minutes} 分钟</small>}
                {item.course_name && <span className="agenda-course">{item.course_name}</span>}
                <label>
                  <input
                    type="checkbox"
                    aria-label="标记已完成"
                    checked={completedItemIds.includes(item.item_id)}
                    onChange={() => toggleCompleted(item.item_id)}
                  />
                  已完成
                </label>
              </li>
            ))}
          </ul>
          <form
            className="daily-checkin-form"
            onSubmit={(event) => {
              event.preventDefault();
              onCheckin?.({
                report_date: todayAgenda.agenda_date,
                completed_item_ids: completedItemIds,
                insufficient_time: insufficientTime,
                ...(difficultyNotes.trim() ? { difficulty_notes: difficultyNotes.trim() } : {}),
              }, checkinKey);
            }}
          >
            <label>
              <input
                type="checkbox"
                checked={insufficientTime}
                onChange={(event) => setInsufficientTime(event.target.checked)}
              />
              今日时间不足
            </label>
            <label className="form-field">
              <span>复盘备注（可选）</span>
              <textarea
                value={difficultyNotes}
                maxLength={500}
                onChange={(event) => setDifficultyNotes(event.target.value)}
              />
            </label>
            <button className="button button-primary" type="submit" disabled={checkingIn}>
              {checkingIn ? "正在提交…" : "提交今日签到"}
            </button>
            {checkinStatus && <p role="status">{checkinStatus}</p>}
          </form>
        </div>
      )}
    </section>
  );
}
