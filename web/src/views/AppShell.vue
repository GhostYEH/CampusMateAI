<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";
import ToastHost from "../components/teacher/ToastHost.vue";
import ConfirmHost from "../components/teacher/ConfirmHost.vue";


const store = useAppStore();
const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const mobileOpen = ref(false);
const search = ref("");
const searchOpen = ref(false);
const searchResults = ref([]);
const searchLoading = ref(false);
let searchTimer;

const menus = computed(() => {
  return [
    ["home", "首页", "PhHouse"],
    ["courses", "我的课程", "PhBookOpen"],
    ["tasks", "待办与作业", "PhCheckSquare"],
    ["campus-activities", "校园活动", "PhCalendarStar"],
    ["counselor", "AI 导员", "PhRobot"],
    ["notifications", "通知整理", "PhBell"],
    ["study", "学习陪伴", "PhChartLineUp"],
    ["profile", "个人中心", "PhUser"],
  ];
});
const isStudent = true;
const todayLabel = computed(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date()));

function go(path) {
  router.push(`/${path}`);
  mobileOpen.value = false;
}

function isActive(key) {
  const path = `/${key}`;
  return route.path === path || route.path.startsWith(`${path}/`);
}

function logout() {
  store.logout();
  router.replace("/login");
}

function openSearch() {
  searchOpen.value = true;
  document.querySelector('[name="global-search"]')?.focus();
}

function closeSearch() {
  searchOpen.value = false;
}

async function runSearch() {
  searchResults.value = [];
}

function keydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openSearch();
  }
  if (event.key === "Escape") closeSearch();
}

watch(search, () => {
  searchOpen.value = true;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 220);
});
onMounted(() => window.addEventListener("keydown", keydown));
onUnmounted(() => { window.removeEventListener("keydown", keydown); clearTimeout(searchTimer); });
</script>

<template>
  <div class="app-layout student-layout" :class="{ collapsed, 'reduce-motion': store.reduceMotion }">
    <ToastHost /><ConfirmHost />
    <button class="mobile-menu" aria-label="打开导航" @click="mobileOpen = true"><UiIcon name="PhList" /></button>
    <div v-if="mobileOpen" class="mobile-backdrop" @click="mobileOpen = false"></div>
    <aside class="sidebar" :class="{ open: mobileOpen }">
      <div class="brand">
        <span class="brand-mark"><UiIcon name="PhGraduationCap" :size="23" weight="fill" /></span>
        <div><strong>CampusMate AI</strong><small>校园智能陪伴助手</small></div>
      </div>
      <div class="profile-mini">
        <div class="avatar">{{ store.session?.name?.slice(0, 1) || "同" }}</div>
        <div><strong>{{ store.session?.name || "陈同学（演示）" }}</strong><small>{{ store.session?.detail || "信息工程学院 · 计算机科学与技术" }}</small></div>
      </div>
      <nav aria-label="主导航">
        <button v-for="[key, label, icon] in menus" :key="key" :class="{ active: isActive(key) }" :title="collapsed ? label : undefined" :aria-label="label" @click="go(key)">
          <UiIcon :name="icon" :size="19" /><span>{{ label }}</span><b v-if="key === 'tasks' && store.pendingCount">{{ store.pendingCount }}</b><i v-if="key === 'notifications' && store.pendingCount" class="nav-dot"></i>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <button title="收藏" aria-label="收藏" @click="go('profile/favorites')"><UiIcon name="PhBookmarkSimple" /><span>收藏</span></button>
        <button title="设置" aria-label="设置" @click="go('profile/settings')"><UiIcon name="PhGear" /><span>设置</span></button>
        <button :title="collapsed ? '展开导航' : '收起导航'" :aria-label="collapsed ? '展开导航' : '收起导航'" @click="collapsed = !collapsed"><UiIcon :name="collapsed ? 'PhCaretRight' : 'PhCaretLeft'" /><span>{{ collapsed ? "展开" : "收起" }}</span></button>
        <button title="退出登录" aria-label="退出登录" @click="logout"><UiIcon name="PhSignOut" /><span>退出登录</span></button>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="command-search">
          <UiIcon name="PhMagnifyingGlass" :size="19" /><input v-model="search" name="global-search" placeholder="搜索课程、作业、通知或服务" /><kbd>⌘ K</kbd>
        </div>
        <div class="top-date"><span class="study-status">本周学习节奏 <b>· 良好</b></span><em></em><UiIcon name="PhCalendarBlank" />{{ todayLabel }}</div>
        <button class="icon-button notification-button" aria-label="通知" @click="go('notifications')"><UiIcon name="PhBell" :size="20" /><i v-if="store.pendingCount"></i></button>
      </header>
      <div v-if="searchOpen && search.length >= 2" class="global-search-panel"><div v-if="searchLoading" class="portal-empty">搜索中…</div><div v-else-if="!searchResults.length" class="portal-empty">没有匹配结果</div><button v-for="item in searchResults" :key="`${item.type}-${item.id}`" @click="router.push(item.path); closeSearch()"><strong>{{ item.title }}</strong><small>{{ item.type }} · {{ item.subtitle }}</small></button></div>
      <RouterView :search-query="search" />
    </div>
  </div>
</template>
