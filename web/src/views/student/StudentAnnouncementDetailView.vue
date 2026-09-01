<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getAnnouncement, markAnnouncementRead, getStudentClasses } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const marking = ref(false);
const error = ref("");
const announcement = ref(null);
const className = ref("");

const isUnread = computed(() => announcement.value && announcement.value.has_read === false);
const isRequired = computed(() => Boolean(announcement.value?.require_read));
const sourceLabel = computed(() => className.value || route.query.source || "课程班级");

function formatDateTime(value) {
  if (!value) return "待发布";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return String(value);
  return date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return String(value);
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}
function relativeTime(value) {
  if (!value) return "";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "";
  const diff = Date.now() - time;
  if (diff < 0) return "即将发布";
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 172800000) return "昨天";
  return formatDate(value);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [data] = await Promise.all([getAnnouncement(route.params.announcementId), loadClassName()]);
    announcement.value = data;
    if (data?.class_group_id && !className.value) await resolveClassName(data.class_group_id);
    if (data && data.has_read === false) await autoMarkRead(data);
  } catch (e) {
    error.value = e.response?.data?.detail || "通知详情加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function loadClassName() {
  const name = route.query.source || route.query.className;
  if (name) className.value = String(name);
}

async function resolveClassName(classId) {
  try {
    const classes = (await getStudentClasses()).items || [];
    const matched = classes.find((item) => item.id === classId);
    if (matched) className.value = matched.name;
  } catch { /* 忽略，使用默认来源标签 */ }
}

async function autoMarkRead(data) {
  try {
    await markAnnouncementRead(data.id);
    data.has_read = true;
  } catch { /* 自动已读失败不阻塞展示 */ }
}

async function manualMarkRead() {
  if (!announcement.value || marking.value || announcement.value.has_read) return;
  marking.value = true;
  try {
    await markAnnouncementRead(announcement.value.id);
    announcement.value.has_read = true;
  } catch (e) {
    error.value = e.response?.data?.detail || "标记已读失败，请稍后重试。";
  } finally {
    marking.value = false;
  }
}

function gotoExtract() {
  if (!announcement.value) return;
  router.push({ path: "/notifications", query: { text: announcement.value.title + "\n" + (announcement.value.content || "") } });
}

onMounted(load);
</script>

<template>
  <main class="student-page announcement-detail-page">
    <button class="cd-back-link" @click="router.push('/notifications')"><UiIcon name="PhArrowLeft" />返回通知列表</button>

    <div v-if="loading" class="student-detail-loading"><div class="student-skeleton"></div></div>

    <div v-else-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div>

    <article v-else-if="announcement" class="announcement-detail-layout">
      <section class="student-panel surface">
        <div class="announcement-detail-kicker">
          <span class="status-pill" :class="isRequired ? 'red' : 'blue'">{{ isRequired ? "必读通知" : "课程通知" }}</span>
          <span class="status-pill" :class="isUnread ? 'warm' : 'green'">{{ isUnread ? "未读" : "已读" }}</span>
          <span class="announcement-source">{{ sourceLabel }}</span>
        </div>
        <h1>{{ announcement.title }}</h1>
        <p class="detail-description announcement-subtitle">来自 {{ announcement.author_name || "课程教师" }} · {{ relativeTime(announcement.published_at || announcement.created_at) }}</p>

        <div class="announcement-info-grid">
          <div><UiIcon name="PhMegaphone" /><span><small>通知来源</small><strong>{{ sourceLabel }}</strong></span></div>
          <div><UiIcon name="PhUserCircle" /><span><small>发布人</small><strong>{{ announcement.author_name || "课程教师" }}</strong></span></div>
          <div><UiIcon name="PhCalendarBlank" /><span><small>发布时间</small><strong>{{ formatDateTime(announcement.published_at || announcement.created_at) }}</strong></span></div>
          <div><UiIcon name="PhClock" /><span><small>更新时间</small><strong>{{ announcement.updated_at ? formatDateTime(announcement.updated_at) : "未更新" }}</strong></span></div>
        </div>

        <div class="detail-actions announcement-detail-actions">
          <button class="secondary-button" @click="router.push('/notifications')"><UiIcon name="PhList" />返回通知列表</button>
          <button class="secondary-button" @click="gotoExtract"><UiIcon name="PhSparkle" />生成待办</button>
          <button class="primary-button" :disabled="marking || !isUnread" @click="manualMarkRead">
            <UiIcon :name="isUnread ? 'PhCheck' : 'PhSealCheck'" />{{ marking ? "处理中…" : isUnread ? "标记已读" : "已读" }}
          </button>
        </div>
      </section>

      <section class="student-panel surface announcement-content-panel">
        <span class="eyebrow">NOTICE / 通知正文</span>
        <h2>通知内容</h2>
        <div class="rich-text announcement-content">{{ announcement.content || "该通知暂无正文内容。" }}</div>
      </section>

      <section class="student-panel surface announcement-meta-panel">
        <span class="eyebrow">META / 附加信息</span>
        <h2>通知属性</h2>
        <dl class="announcement-meta-list">
          <div><dt>通知编号</dt><dd>{{ announcement.id }}</dd></div>
          <div><dt>所属班级</dt><dd>{{ sourceLabel }}</dd></div>
          <div><dt>发布状态</dt><dd>{{ { draft: "草稿", published: "已发布", archived: "已归档" }[announcement.status] || announcement.status }}</dd></div>
          <div><dt>是否必读</dt><dd>{{ isRequired ? "是" : "否" }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ formatDateTime(announcement.created_at) }}</dd></div>
          <div><dt>阅读状态</dt><dd>{{ announcement.has_read === null ? "—" : announcement.has_read ? "已读" : "未读" }}</dd></div>
        </dl>
      </section>
    </article>
  </main>
</template>
