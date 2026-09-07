import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import { deadlineLabel } from "./homeTime.js";

/**
 * Compact priority summary for the first viewport: up to three real
 * due items. Clicking an item opens its task route via onOpenDue; the
 * footer goes to the full task management page.
 */
export default function SylvaPriorityCard({ state, onNavigate, onOpenDue }) {
  const items = useMemo(() => state.filteredDueItems.slice(0, 3), [state.filteredDueItems]);

  return (
    <article className="sylva-priority-card" aria-labelledby="sylva-priority-title">
      <header className="sylva-card-head">
        <div><span>优先处理</span><h2 id="sylva-priority-title">优先事项</h2></div>
        <button className="sylva-card-link" onClick={() => onNavigate?.("/tasks")}>全部待办<Icon name="PhArrowRight" size={14} /></button>
      </header>

      {items.length ? (
        <div className="sylva-priority-list">
          {items.map((item, index) => (
            <button key={`${item.kind}-${item.id}`} onClick={() => onOpenDue?.(item)}>
              {index === 0 && <i className="sylva-priority-tag">优先</i>}
              <span className="sylva-priority-copy">
                <strong>{item.title}</strong>
                <time className={deadlineLabel(item.due, state.now).startsWith("今日") ? "today" : ""}>{deadlineLabel(item.due, state.now)}</time>
              </span>
              <Icon name="PhCaretRight" size={14} />
            </button>
          ))}
        </div>
      ) : (
        <div className="sylva-priority-empty">
          <Icon name="PhCheckCircle" size={24} />
          <span>没有临近截止事项</span>
          <button onClick={() => onNavigate?.("/tasks")}>进入待办</button>
        </div>
      )}

      <button className="sylva-priority-more" onClick={() => onNavigate?.("/tasks")}>
        <span>进入待办与作业</span>
        <i>{state.overviewMetrics.pendingCount} 项</i>
        <Icon name="PhArrowRight" size={14} />
      </button>
    </article>
  );
}
