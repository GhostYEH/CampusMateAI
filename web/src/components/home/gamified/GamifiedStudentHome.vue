<script setup>
import { computed } from "vue";
import CampusHotPostsPanel from "../../CampusHotPostsPanel.vue";
import UiIcon from "../../UiIcon.vue";
import HomeFooter from "../footer/HomeFooter.vue";
import { selectUpcomingExam } from "../../../features/dashboard/dashboardModel";
import AchievementHall from "./AchievementHall.vue";
import AdventureWorld from "./AdventureWorld.vue";
import AICompanion from "./AICompanion.vue";
import CampusMap from "./CampusMap.vue";
import CharacterPanel from "./CharacterPanel.vue";
import GrowthTree from "./GrowthTree.vue";
import QuestLog from "./QuestLog.vue";
import DailySignIn from "./DailySignIn.vue";

const props = defineProps({ state: { type: Object, required: true } });
const emit = defineEmits(["navigate", "reload"]);

const nextExam = computed(() => selectUpcomingExam(props.state.exams, new Date(props.state.now)));
function openPost(postId) {
  emit("navigate", `/community/${postId}`);
}
</script>

<template>
  <main class="student-page gamified-home">
    <div v-if="state.error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ state.error }}<button class="link-button" @click="emit('reload')">重试</button></div>
    <section v-if="state.loading" class="game-loading" aria-label="正在加载游戏化首页" aria-busy="true">
      <div class="game-loading-player"></div><div class="game-loading-hero"></div><div class="game-loading-panel"></div><div class="game-loading-panel"></div>
    </section>

    <HomeFooter v-else>
      <div class="rpg-world-shell">
        <CharacterPanel :user="state.user" :summary="state.gamification" />
        <AdventureWorld :summary="state.gamification" :next-exam="nextExam" :now="state.now" @navigate="emit('navigate', $event)" />

        <div v-if="state.normalizedSearch" class="rpg-search-note"><UiIcon name="PhMagnifyingGlass" :size="16" />正在扫描校园任务，发现 {{ state.filteredMainQuests.length }} 个匹配节点</div>

        <section class="rpg-command-deck">
          <QuestLog :quests="state.filteredMainQuests" @navigate="emit('navigate', $event)" />
          <div class="rpg-world-tools">
            <CampusMap @navigate="emit('navigate', $event)" />
            <AICompanion :summary="state.gamification" @navigate="emit('navigate', $event)" />
          </div>
        </section>

        <section class="rpg-growth-deck">
          <GrowthTree :summary="state.gamification" />
          <AchievementHall :summary="state.gamification" />
          <DailySignIn :summary="state.gamification" @navigate="emit('navigate', $event)" />
        </section>

        <section class="rpg-world-events rpg-hud-panel" aria-labelledby="world-events-title">
          <header class="rpg-panel-header"><div><span class="rpg-kicker">WORLD EVENTS · CAMPUS FEED</span><h2 id="world-events-title">校园世界</h2></div><button @click="emit('navigate', '/community')">进入社区<UiIcon name="PhArrowRight" :size="15" /></button></header>
          <CampusHotPostsPanel v-if="state.visibleHotPosts.length" :posts="state.visibleHotPosts" @open-post="openPost" />
          <div v-else class="rpg-empty-state compact" role="status"><UiIcon name="PhChatsCircle" :size="30" /><strong>校园世界暂时安静</strong><p>社区出现新的公开动态后，会继续使用原数据源显示在这里。</p><button @click="emit('navigate', '/community')">进入校园社区</button></div>
        </section>
      </div>
    </HomeFooter>
  </main>
</template>
