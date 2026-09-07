import { Icon } from "../../components/Icon.jsx";
import HomeFooter from "../../components/HomeFooter.jsx";

export default function ClassicHome({ state, searchQuery, onNavigate, onReload }) {
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
          {state.normalizedSearch && (
            <section className="home-search-note" aria-label="首页搜索结果">
              <div><Icon name="PhMagnifyingGlass" size={16} />正在筛选“{searchQuery}”，找到 {state.searchResults.length} 条相关内容</div>
              {state.searchResults.length ? <div className="home-search-results">{state.searchResults.map((item) => <button type="button" key={`${item.resultKind}-${item.id}`} onClick={() => onNavigate?.(item.resultRoute)}><Icon name={item.resultKind === "通知" ? "PhBell" : item.resultKind === "作业" ? "PhFileText" : "PhCheckSquare"} size={16} /><span><strong>{item.resultTitle}</strong><small>{item.resultKind} · {item.resultDetail}</small></span><Icon name="PhCaretRight" size={14} /></button>)}</div> : <span>没有找到匹配的课程、任务或通知。</span>}
            </section>
          )}
        </HomeFooter>
        </>
      )}
    </main>
  );
}
