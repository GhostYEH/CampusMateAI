import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import HomeLearningCommand from "./HomeLearningCommand.jsx";
import HomeLearningPulse from "./HomeLearningPulse.jsx";
import HomeSchedulePanel from "./HomeSchedulePanel.jsx";
import HomeFooter from "../../components/HomeFooter.jsx";
import { deadlineLabel } from "./homeTime.js";

const quickLinks = [
  { label: "通知整理", detail: "课程与校园通知", icon: "PhBell", path: "/notifications", tone: "amber" },
  { label: "校园社区", detail: "交流学习与生活", icon: "PhChatsCircle", path: "/community", tone: "violet" },
  { label: "学校与专业", detail: "查看校园背景信息", icon: "PhBuildings", path: "/university", tone: "rose" },
];

export default function ClassicHome({ state, searchQuery, onNavigate, onOpenDue, onReload }) {
  const totalPending = state.overviewMetrics.pendingCount;
  const dueItems = useMemo(() => state.filteredDueItems, [state.filteredDueItems]);

  return (
    <main className="student-page student-home simple-student-home">
      {state.error && (
        <div className="student-alert error" role="alert">
          <Icon name="PhWarningCircle" />{state.error}
          <button className="link-button" onClick={() => onReload?.()}>重试</button>
        </div>
      )}
      {state.loading ? (
        <section className="student-home-skeleton simple-home-skeleton" aria-label="正在加载首页" aria-busy="true">
          <div className="home-skeleton-focus" />
          <div className="home-skeleton-overview" />
          <div className="home-skeleton-panel" />
        </section>
      ) : (
        <>
        <HomeFooter fixedBrand>
          <section className="simple-home-command-stack">
            <HomeLearningCommand command={state.learningCommand} onNavigate={onNavigate} />
            <HomeLearningPulse items={state.learningCommand.pulse} onNavigate={onNavigate} />
          </section>
          {state.normalizedSearch && (
            <section className="home-search-note" aria-label="首页搜索结果">
              <div><Icon name="PhMagnifyingGlass" size={16} />正在筛选“{searchQuery}”，找到 {state.searchResults.length} 条相关内容</div>
              {state.searchResults.length ? <div className="home-search-results">{state.searchResults.map((item) => <button type="button" key={`${item.resultKind}-${item.id}`} onClick={() => onNavigate?.(item.resultRoute)}><Icon name={item.resultKind === "通知" ? "PhBell" : item.resultKind === "作业" ? "PhFileText" : "PhCheckSquare"} size={16} /><span><strong>{item.resultTitle}</strong><small>{item.resultKind} · {item.resultDetail}</small></span><Icon name="PhCaretRight" size={14} /></button>)}</div> : <span>没有找到匹配的课程、任务或通知。</span>}
            </section>
          )}
          <section className="simple-home-grid">
            <article className="student-home-panel task-panel simple-priority-panel">
              <div className="home-panel-head">
                <h2><Icon name="PhListChecks" size={19} />待办与作业</h2>
                <button onClick={() => onNavigate?.("/tasks")}>全部 {totalPending} 项</button>
              </div>
              {dueItems.length ? (
                <div className="priority-list">
                  {dueItems.map((item) => (
                    <button key={`${item.kind}-${item.id}`} onClick={() => onOpenDue?.(item)}>
                      <span className={`priority-kind ${item.kind === "作业" ? "assignment" : "personal"}`}>{item.kind}</span>
                      <strong>{item.title}</strong>
                      <time className={deadlineLabel(item.due, state.now).startsWith("今日") ? "today" : ""}>{deadlineLabel(item.due, state.now)}</time>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="compact-empty">
                  <Icon name="PhCheckCircle" size={26} />
                  <strong>全部完成</strong>
                  <span>新的课程作业和个人待办会自动汇合到这里。</span>
                </div>
              )}
              <button className="panel-footer simple" onClick={() => onNavigate?.("/tasks")}>进入待办管理<Icon name="PhArrowRight" size={15} /></button>
            </article>
            <HomeSchedulePanel items={state.scheduleItems} loading={state.scheduleLoading} onOpenAcademic={() => onNavigate?.("/profile/academic")} />
          </section>
          <section className="student-quick-section simple-quick-section">
            <div className="quick-section-head">
              <div><span>校园服务</span><h2>需要时再打开</h2></div>
              <small>学习主线之外的功能只保留一个入口</small>
            </div>
            <div className="student-quick-grid">
              {quickLinks.map((item) => (
                <button key={item.path} onClick={() => onNavigate?.(item.path)}>
                  <span className={`quick-icon ${item.tone}`}><Icon name={item.icon} size={20} /></span>
                  <span><strong>{item.label}</strong><small>{item.detail}</small></span>
                  <Icon name="PhCaretRight" size={15} />
                </button>
              ))}
            </div>
          </section>
        </HomeFooter>
        </>
      )}
    </main>
  );
}
