<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../components/UiIcon.vue";
import { getStudentActivities } from "../services/studentApi";

const router = useRouter();
const loading = ref(true);
const error = ref("");
const activities = ref([]);
const query = ref("");
const category = ref("all");
const status = ref("all");

const categoryNames = { lecture: "学术讲座", volunteer: "志愿服务", culture: "文体活动", innovation: "创新创业", society: "社团活动", career: "就业指导" };
const categories = computed(() => [...new Set(activities.value.map((item) => item.category).filter(Boolean))]);
const filtered = computed(() => activities.value.filter((item) => {
  const haystack = `${item.title} ${item.summary || ""} ${item.location || ""}`.toLowerCase();
  return haystack.includes(query.value.trim().toLowerCase()) && (category.value === "all" || item.category === category.value) && (status.value === "all" || (status.value === "open" ? !item.is_closed : item.is_closed));
}));
const featured = computed(() => filtered.value[0] || activities.value[0]);
const listItems = computed(() => filtered.value);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    activities.value = (await getStudentActivities()).items || [];
  } catch (e) {
    error.value = e.response?.data?.detail || "活动加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

function dateText(value) {
  if (!value) return "时间待发布";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit" });
}

function categoryLabel(value) {
  return categoryNames[value] || value || "校园活动";
}

function openActivity(item) {
  if (item?.id) router.push(`/campus-activities/${item.id}`);
}

onMounted(load);
</script>

<template>
  <main class="student-page activities-page page-enter">
    <div class="student-heading page-heading-wide">
      <div>
        <span class="eyebrow">CAMPUS / 校园生活</span>
        <h1>校园活动</h1>
        <p>发现学校发布的精彩活动，参与丰富多彩的校园生活，拓展视野，结识更多伙伴。</p>
      </div>
      <div class="hero-side"><div class="hero-decoration"><UiIcon name="PhSparkle" /></div><button class="secondary-button" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button></div>
    </div>

    <section class="activity-filter surface">
      <div class="filter-main">
        <div class="search-field"><UiIcon name="PhMagnifyingGlass" /><input v-model="query" placeholder="搜索活动、地点或主办方" /></div>
        <select v-model="category"><option value="all">全部类别</option><option v-for="item in categories" :key="item" :value="item">{{ categoryLabel(item) }}</option></select>
        <select v-model="status"><option value="all">全部状态</option><option value="open">可报名</option><option value="closed">已结束</option></select>
      </div>
      <div class="filter-bottom">
        <div class="filter-tabs"><button :class="{ active: category === 'all' }" @click="category = 'all'">全部</button><button v-for="item in categories" :key="item" :class="{ active: category === item }" @click="category = item">{{ categoryLabel(item) }}</button></div>
        <div class="status-tabs"><button :class="{ active: status === 'all' }" @click="status = 'all'">全部</button><button :class="{ active: status === 'open' }" @click="status = 'open'">可报名</button><button :class="{ active: status === 'closed' }" @click="status = 'closed'">已结束</button><button class="clear-filter" @click="category = 'all'; status = 'all'; query = ''"><UiIcon name="PhSlidersHorizontal" />清除筛选</button></div>
      </div>
    </section>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div>
    <template v-if="loading">
      <section class="student-card-grid"><div v-for="i in 3" :key="i" class="student-skeleton"></div></section>
    </template>
    <template v-else-if="featured">
      <button class="activity-feature surface" @click="openActivity(featured)">
        <div class="feature-copy"><span class="status-pill blue">精选推荐</span><h2>{{ featured.title }}</h2><p>{{ featured.summary || featured.content || "从真实校园问题出发，发现更多值得参与的活动。" }}</p><div class="activity-feature-meta"><span><UiIcon name="PhCalendarBlank" />{{ dateText(featured.starts_at) }}</span><span><UiIcon name="PhMapPin" />{{ featured.location || "地点待发布" }}</span><span><UiIcon name="PhUsersThree" />校园同学可参与</span></div></div>
        <div class="feature-visual"><img src="/assets/campusmate-activity-hero.png" alt="校园活动插画" /><span class="feature-cta">立即报名 <UiIcon name="PhArrowRight" /></span></div>
      </button>

      <div class="section-bar"><div><h2>活动列表</h2><span>共 {{ filtered.length }} 项活动</span></div><div class="view-tools"><button class="sort-button">推荐排序 <UiIcon name="PhCaretDown" /></button><button class="icon-button active"><UiIcon name="PhSquaresFour" /></button><button class="icon-button"><UiIcon name="PhList" /></button></div></div>
      <section class="student-card-grid activity-grid">
        <button v-for="(activity, index) in (listItems.length ? listItems : [featured])" :key="`${activity.id}-${index}`" class="activity-card surface" @click="openActivity(activity)">
          <div class="activity-art" :class="`art-${index % 2}`"><img :src="index % 2 ? '/assets/campusmate-activity-volunteer.png' : '/assets/campusmate-activity-lecture.png'" :alt="`${categoryLabel(activity.category)}插画`" /><span>{{ categoryLabel(activity.category) }}</span></div>
          <div class="activity-card-body"><div class="activity-card-top"><span class="status-pill" :class="index % 2 ? 'green' : 'blue'">{{ categoryLabel(activity.category) }}</span><span class="status-pill orange">{{ activity.is_closed ? "已结束" : "可报名" }}</span></div><h2>{{ activity.title }}</h2><p>{{ activity.summary || activity.content || "欢迎来参加这场校园活动，和同学们一起探索新的可能。" }}</p><div class="activity-card-meta"><span><UiIcon name="PhCalendarBlank" />{{ dateText(activity.starts_at) }}</span><span><UiIcon name="PhMapPin" />{{ activity.location || "地点待发布" }}</span></div><div class="card-actions"><span>查看详情</span><span>{{ activity.is_closed ? "已结束" : "立即报名" }} <UiIcon name="PhArrowRight" /></span></div></div>
        </button>
      </section>
      <div class="list-end">已经到底啦</div>
    </template>
    <div v-else class="student-empty large surface"><UiIcon name="PhCalendarStar" :size="42" /><strong>暂时没有已发布活动</strong><span>活动由学校部门发布后会在这里出现。</span></div>
  </main>
</template>
