<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../components/UiIcon.vue";
import { useAppStore } from "../stores/app";
import { getActivities } from "../services/portalRepository";

const store = useAppStore();
const loading = ref(true);
const error = ref("");
const activities = ref([]);
const query = ref("");
const selected = ref(null);
const useMock = computed(() => store.mockMode || !store.backendOnline);
const filtered = computed(() => activities.value.filter((item) => `${item.title}${item.summary}${item.location}`.includes(query.value)));
const categoryLabel = { campus: "校园活动", academic: "学术交流", volunteer: "志愿服务", competition: "竞赛", lecture: "讲座", sports: "体育" };
function format(value) {
  return value ? new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "时间待定";
}
async function load() {
  loading.value = true;
  error.value = "";
  try { activities.value = (await getActivities(useMock.value, { status: "published" })).items; }
  catch (err) { error.value = err.response?.data?.message || "活动加载失败"; }
  finally { loading.value = false; }
}
onMounted(load);
</script>

<template>
  <main class="portal-page page-enter">
    <div class="portal-heading"><div><span class="portal-kicker">发现校园</span><h1>校园活动</h1><p>把报名截止、活动时间和地点放在一起，不再错过想参加的事。</p></div></div>
    <div class="portal-search student-activity-search"><UiIcon name="PhMagnifyingGlass" /><input v-model="query" name="campus-activity-search" placeholder="搜索讲座、竞赛或志愿服务" /></div>
    <div v-if="loading" class="portal-loading"><i v-for="n in 4" :key="n"></i></div>
    <div v-else-if="error" class="portal-error"><UiIcon name="PhCloudSlash" /><span>{{ error }}</span><button class="secondary-button" @click="load">重试</button></div>
    <section v-else class="student-activity-grid">
      <article v-for="activity in filtered" :key="activity.id">
        <header><span>{{ categoryLabel[activity.category] }}</span><time>{{ format(activity.starts_at) }}</time></header>
        <h2>{{ activity.title }}</h2><p>{{ activity.summary }}</p>
        <dl><div><dt><UiIcon name="PhMapPin" /></dt><dd>{{ activity.location || "地点待定" }}</dd></div><div><dt><UiIcon name="PhTimer" /></dt><dd>报名截止 {{ format(activity.registration_deadline) }}</dd></div></dl>
        <button class="secondary-button" @click="selected = activity">查看活动说明<UiIcon name="PhArrowRight" /></button>
      </article>
      <div v-if="!filtered.length" class="portal-empty"><UiIcon name="PhCalendarX" :size="36" />暂时没有符合条件的活动。</div>
    </section>
    <div v-if="selected" class="portal-overlay" @click.self="selected = null"><section class="portal-modal activity-detail-modal"><div class="drawer-head"><div><span>{{ categoryLabel[selected.category] }}</span><h2>{{ selected.title }}</h2></div><button class="icon-button" @click="selected = null"><UiIcon name="PhX" /></button></div><p>{{ selected.content }}</p><dl><div><dt>活动时间</dt><dd>{{ format(selected.starts_at) }}</dd></div><div><dt>活动地点</dt><dd>{{ selected.location || "待定" }}</dd></div><div><dt>报名截止</dt><dd>{{ format(selected.registration_deadline) }}</dd></div><div><dt>人数安排</dt><dd>{{ selected.capacity ? `限 ${selected.capacity} 人` : "不限人数" }}</dd></div></dl><div class="alert info"><UiIcon name="PhInfo" />演示版本展示活动发布链路，正式报名入口需对接学校报名系统。</div></section></div>
  </main>
</template>
