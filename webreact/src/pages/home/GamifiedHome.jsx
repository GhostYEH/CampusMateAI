import { useMemo } from "react";
import { Icon } from "../../components/Icon.jsx";
import HomeFooter from "../../components/HomeFooter.jsx";
import { selectUpcomingExam } from "../../data/dashboardModel.js";
import CharacterPanel from "./gamified/CharacterPanel.jsx";
import AdventureWorld from "./gamified/AdventureWorld.jsx";
import QuestLog from "./gamified/QuestLog.jsx";
import CampusMap from "./gamified/CampusMap.jsx";
import AICompanion from "./gamified/AICompanion.jsx";
import GrowthTree from "./gamified/GrowthTree.jsx";
import AchievementHall from "./gamified/AchievementHall.jsx";
import DailySignIn from "./gamified/DailySignIn.jsx";
import CampusHotPostsPanel from "./gamified/CampusHotPostsPanel.jsx";

export default function GamifiedHome({ state, onNavigate, onReload }) {
  const nextExam = useMemo(() => selectUpcomingExam(state.exams, new Date(state.now)), [state.exams, state.now]);
  function openPost(postId) { onNavigate?.(`/community/${postId}`); }

  return (
    <main className="student-page gamified-home">
      {state.error && (
        <div className="student-alert error"><Icon name="PhWarningCircle" />{state.error}<button className="link-button" onClick={() => onReload?.()}>重试</button></div>
      )}
      {state.loading ? (
        <section className="game-loading" aria-label="正在加载游戏化首页" aria-busy="true">
          <div className="game-loading-player" /><div className="game-loading-hero" /><div className="game-loading-panel" /><div className="game-loading-panel" />
        </section>
      ) : (
        <>
        <HomeFooter>
          <div className="rpg-world-shell">
            <CharacterPanel user={state.user} summary={state.gamification} />
            <AdventureWorld summary={state.gamification} nextExam={nextExam} now={state.now} onNavigate={onNavigate} />
            {state.normalizedSearch && (
              <div className="rpg-search-note"><Icon name="PhMagnifyingGlass" size={16} />正在扫描校园任务，发现 {state.filteredMainQuests.length} 个匹配节点</div>
            )}
            <section className="rpg-command-deck">
              <QuestLog quests={state.filteredMainQuests} onNavigate={onNavigate} />
              <div className="rpg-world-tools">
                <CampusMap onNavigate={onNavigate} />
                <AICompanion summary={state.gamification} onNavigate={onNavigate} />
              </div>
            </section>
            <section className="rpg-growth-deck">
              <GrowthTree summary={state.gamification} />
              <AchievementHall summary={state.gamification} />
              <DailySignIn summary={state.gamification} onNavigate={onNavigate} />
            </section>
            <section className="rpg-world-events rpg-hud-panel" aria-labelledby="world-events-title">
              <header className="rpg-panel-header">
                <div><span className="rpg-kicker">WORLD EVENTS · CAMPUS FEED</span><h2 id="world-events-title">校园世界</h2></div>
                <button onClick={() => onNavigate?.("/community")}>进入社区<Icon name="PhArrowRight" size={15} /></button>
              </header>
              {state.visibleHotPosts?.length ? (
                <CampusHotPostsPanel posts={state.visibleHotPosts} onOpenPost={openPost} />
              ) : (
                <div className="rpg-empty-state compact" role="status">
                  <Icon name="PhChatsCircle" size={30} /><strong>校园世界暂时安静</strong>
                  <p>社区出现新的公开动态后，会继续使用原数据源显示在这里。</p>
                  <button onClick={() => onNavigate?.("/community")}>进入校园社区</button>
                </div>
              )}
            </section>
          </div>
        </HomeFooter>
        </>
      )}
    </main>
  );
}
