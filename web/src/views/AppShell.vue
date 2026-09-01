<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";
import ToastHost from "../components/AppToastHost.vue";
import ConfirmHost from "../components/AppConfirmHost.vue";
import { getStudentAssignments, getStudentCourses } from "../services/studentApi";

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

const menus = [
  ["home", "首页", "PhHouse"],
  ["courses", "我的课程", "PhBookOpen"],
  ["community", "校园社区", "PhChatsCircle"],
  ["tasks", "待办与作业", "PhCheckSquare"],
  ["counselor", "AI 校园助手", "PhRobot"],
  ["notifications", "通知整理", "PhBell"],
  ["study", "学习陪伴", "PhChartLineUp"],
  ["profile", "个人中心", "PhUser"],
];

const todayLabel = computed(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date()).replace("星期", "周"));
const profileRoute = computed(() => route.path === "/profile" || route.path.startsWith("/profile/"));
const isGamifiedHome = computed(() => route.path === "/home" && store.dashboardStyle === "gamified");
const profileDetail = computed(() => store.session?.detail || [store.session?.college, store.session?.major].filter(Boolean).join(" · ") || "信息工程学院 · 计算机科学与技术");

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
  requestAnimationFrame(() => document.querySelector('[name="global-search"]')?.focus());
}
function closeSearch() { searchOpen.value = false; }

async function runSearch() {
  const query = search.value.trim().toLocaleLowerCase();
  if (query.length < 2) { searchResults.value = []; searchLoading.value = false; return; }
  searchLoading.value = true;
  try {
    const [courseData, assignmentData] = await Promise.all([getStudentCourses(), getStudentAssignments()]);
    const includes = (...values) => values.some((value) => String(value || "").toLocaleLowerCase().includes(query));
    searchResults.value = [
      ...(courseData.items || []).filter((item) => includes(item.name, item.code, item.semester)).map((item) => ({ type: "课程", id: item.id, title: item.name, subtitle: item.code || item.semester || "课程详情", path: `/courses/${item.id}` })),
      ...(assignmentData.items || []).filter((item) => includes(item.title, item.course_name, item.class_name)).map((item) => ({ type: "作业", id: item.id, title: item.title, subtitle: item.course_name || item.class_name || "课程作业", path: `/tasks/assignment/${item.id}` })),
    ].slice(0, 8);
  } catch { searchResults.value = []; }
  finally { searchLoading.value = false; }
}
function chooseSearchResult(item) {
  router.push(item.path); search.value = ""; closeSearch();
}
function keydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openSearch(); }
  if (event.key === "Escape") closeSearch();
}
watch(search, () => { searchOpen.value = true; clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 220); });
onMounted(() => window.addEventListener("keydown", keydown));
onUnmounted(() => { window.removeEventListener("keydown", keydown); clearTimeout(searchTimer); });
</script>

<template>
  <div class="app-layout student-layout" :class="{ collapsed, 'reduce-motion': store.reduceMotion, 'counselor-mode': route.path === '/counselor', 'study-mode': route.path === '/study', 'gamified-home-mode': isGamifiedHome }">
    <ToastHost /><ConfirmHost />
    <button v-if="!isGamifiedHome" class="mobile-menu" aria-label="打开导航" @click="mobileOpen = true"><UiIcon name="PhList" /></button>
    <div v-if="mobileOpen && !isGamifiedHome" class="mobile-backdrop" @click="mobileOpen = false"></div>
    <aside v-if="!isGamifiedHome" class="sidebar" :class="{ open: mobileOpen }">
      <button class="profile-mini" :class="{ active: profileRoute }" @click="go('profile')">
        <span class="avatar"><img :src="store.session?.avatar_url || '/assets/generated/home-reference-student-avatar.png'" alt="" /></span>
        <span class="profile-mini-copy"><span class="profile-mini-name"><strong>{{ profileRoute ? "个人中心" : (store.session?.name || "陈同学(演示)") }}</strong><b v-if="!profileRoute">学生</b></span><small v-if="!profileRoute">{{ profileDetail }}</small></span>
        <UiIcon name="PhCaretRight" :size="16" />
      </button>
      <nav aria-label="主导航">
        <button v-for="[key, label, icon] in menus" :key="key" :class="{ active: isActive(key) }" :title="collapsed ? label : undefined" :aria-label="label" @click="go(key)">
          <UiIcon :name="icon" :size="20" /><span>{{ label }}</span><b v-if="key === 'tasks'">16</b><i v-if="key === 'notifications' && store.unreadCount" class="nav-dot"></i>
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
          <UiIcon name="PhMagnifyingGlass" :size="20" /><input v-model="search" name="global-search" placeholder="搜索课程或作业、通知、社区内容…" autocomplete="off" @focus="searchOpen = true" /><kbd>⌘ K</kbd>
        </div>
        <div class="top-date"><UiIcon name="PhCalendarBlank" :size="18" />{{ todayLabel }}</div>
        <div class="sync-pill" :class="{ offline: !store.backendOnline && route.path !== '/counselor' }"><UiIcon :name="store.backendOnline || route.path === '/counselor' ? 'PhCheckCircle' : 'PhCloudSlash'" :size="18" />{{ store.backendOnline || route.path === '/counselor' ? "已同步 · 刚刚" : "后端未连接" }}</div>
        <button v-if="isGamifiedHome" class="icon-button rpg-top-action" aria-label="校园社区" @click="go('community')"><UiIcon name="PhChatsCircle" :size="20" /></button>
        <button class="icon-button notification-button" aria-label="通知" @click="go('notifications')"><UiIcon name="PhBell" :size="20" /><i></i></button>
        <button v-if="isGamifiedHome" class="rpg-top-avatar" aria-label="个人中心" @click="go('profile')"><img :src="store.session?.avatar_url || '/assets/generated/home-reference-student-avatar.png'" alt="" /></button>
      </header>
      <div v-if="searchOpen && search.length >= 2" class="global-search-panel">
        <div v-if="searchLoading" class="portal-empty">正在搜索真实数据…</div>
        <div v-else-if="!searchResults.length" class="portal-empty">没有匹配结果</div>
        <button v-for="item in searchResults" :key="`${item.type}-${item.id}`" @click="chooseSearchResult(item)"><span><strong>{{ item.title }}</strong><small>{{ item.type }} · {{ item.subtitle }}</small></span><UiIcon name="PhArrowRight" :size="15" /></button>
      </div>
      <RouterView :search-query="search" />
    </div>
  </div>
</template>
