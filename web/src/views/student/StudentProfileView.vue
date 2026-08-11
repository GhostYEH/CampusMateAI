<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import {
  getStudentDashboard,
  getStudentProfile,
  getStudySessions,
  updateStudentProfile,
} from "../../services/studentApi";
import { useAppStore } from "../../stores/app";

const router = useRouter();
const store = useAppStore();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const saved = ref("");
const profile = ref({});
const dashboard = ref(null);
const sessions = ref([]);
const tab = ref("overview");
const editing = ref(false);
const settings = ref({
  reduceMotion: localStorage.getItem("campus_reduce_motion") === "true",
  noticeReminder: localStorage.getItem("campus_notice_reminder") !== "false",
});
const form = ref({ display_name: "", college: "", major: "", grade: "", email: "" });

const displayName = computed(() => profile.value.display_name || profile.value.username || "同学");
const initial = computed(() => displayName.value.slice(0, 1));
const identityLine = computed(() => [profile.value.college, profile.value.major, profile.value.grade].filter(Boolean).join(" · ") || "完善你的校园资料，让陪伴更贴合");
const completedSessions = computed(() => sessions.value.filter((item) => item.status === "completed"));
const weekMinutes = computed(() => completedSessions.value.reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0));
const stats = computed(() => [
  { label: "课程数量", value: dashboard.value?.enrolled_course_count ?? "—", hint: "本学期", icon: "PhBookOpen", tone: "blue" },
  { label: "待办事项", value: dashboard.value?.pending_assignment_count ?? store.pendingCount ?? "—", hint: "待完成", icon: "PhCheckSquare", tone: "green" },
  { label: "本周学习", value: weekMinutes.value ? `${(weekMinutes.value / 60).toFixed(1)}h` : "—", hint: "来自专注记录", icon: "PhChartLineUp", tone: "indigo" },
  { label: "成长积分", value: "—", hint: "暂未接入积分服务", icon: "PhSparkle", tone: "amber" },
]);
const details = computed(() => [
  { label: "姓名", value: displayName.value, icon: "PhUser" },
  { label: "专业", value: profile.value.major || "暂未填写", icon: "PhNotebook" },
  { label: "学号", value: profile.value.student_number || "暂未填写", icon: "PhIdentificationCard" },
  { label: "年级", value: profile.value.grade || "暂未填写", icon: "PhGraduationCap" },
  { label: "学院", value: profile.value.college || "暂未填写", icon: "PhBuildings" },
  { label: "邮箱", value: profile.value.email || "暂未填写", icon: "PhEnvelopeSimple" },
]);
const quickTools = [
  { label: "学习陪伴", detail: "开始一段专注时光", icon: "PhChartLineUp", path: "/study", tone: "violet" },
  { label: "课程表", detail: "查看本周课程安排", icon: "PhCalendarBlank", path: "/courses", tone: "blue" },
  { label: "待办事项", detail: "管理待完成任务", icon: "PhCheckSquare", path: "/tasks", tone: "green" },
  { label: "通知整理", detail: "查看重要校园信息", icon: "PhBell", path: "/notifications", tone: "indigo" },
  { label: "校园活动", detail: "发现感兴趣的活动", icon: "PhCalendarStar", path: "/campus-activities", tone: "amber" },
  { label: "AI 校园助手", detail: "获取校园问题建议", icon: "PhRobot", path: "/counselor", tone: "teal" },
];
const tabs = [
  { key: "overview", label: "资料编辑" },
  { key: "tools", label: "我的工具" },
  { key: "settings", label: "设置" },
];

async function copyStudentNumber() {
  const value = profile.value.student_number;
  if (!value || !navigator.clipboard) return;
  await navigator.clipboard.writeText(value);
  saved.value = "学号已复制";
  window.setTimeout(() => { saved.value = ""; }, 1800);
}

function formatSessionDate(value) {
  if (!value) return "时间待记录";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [profileData, dashboardData, sessionData] = await Promise.all([
      getStudentProfile(),
      getStudentDashboard().catch(() => null),
      getStudySessions().catch(() => []),
    ]);
    profile.value = profileData || {};
    dashboard.value = dashboardData;
    sessions.value = Array.isArray(sessionData) ? sessionData : sessionData?.items || [];
    form.value = {
      display_name: profile.value.display_name || "",
      college: profile.value.college || "",
      major: profile.value.major || "",
      grade: profile.value.grade || "",
      email: profile.value.email || "",
    };
  } catch (err) {
    error.value = err.response?.data?.detail || "个人资料加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    profile.value = await updateStudentProfile(form.value);
    editing.value = false;
    saved.value = "资料已保存";
    window.setTimeout(() => { saved.value = ""; }, 2200);
  } catch (err) {
    error.value = err.response?.data?.detail || "资料保存失败，请重试。";
  } finally {
    saving.value = false;
  }
}

function setSetting(key, value) {
  settings.value[key] = value;
  if (key === "reduceMotion") {
    store.setReduceMotion(value);
    localStorage.setItem("campus_reduce_motion", String(value));
  } else {
    localStorage.setItem("campus_notice_reminder", String(value));
  }
}

onMounted(load);
</script>

<template>
  <main class="student-page campus-redesign profile-redesign page-enter">
    <div class="redesign-heading">
      <div>
        <span class="redesign-kicker">PROFILE / 个人中心</span>
        <h1>个人中心</h1>
        <p>管理你的资料、学习工具入口和陪伴偏好设置。</p>
      </div>
      <button class="redesign-button secondary" :disabled="loading" @click="load">
        <UiIcon name="PhArrowClockwise" :class="{ spinning: loading }" />刷新
      </button>
    </div>

    <div v-if="error" class="redesign-alert error">
      <UiIcon name="PhWarningCircle" />
      <span>{{ error }}</span>
      <button @click="load">重试</button>
    </div>

    <div v-if="loading" class="profile-loading" aria-label="正在加载个人中心">
      <div class="profile-loading-banner"></div>
      <div class="profile-loading-grid"><i></i><i></i><i></i></div>
    </div>

    <template v-else>
      <header class="profile-banner redesign-panel">
        <div class="profile-banner-main">
          <div class="profile-avatar-wrap">
            <div class="profile-avatar">{{ initial }}</div>
            <span class="profile-avatar-check"><UiIcon name="PhCheck" :size="13" weight="bold" /></span>
          </div>
          <div class="profile-intro">
            <div class="profile-name-row">
              <h2>{{ displayName }}</h2>
              <span class="profile-tag">本科生</span>
            </div>
            <div class="profile-meta-row profile-primary-meta">
              <span><UiIcon name="PhUser" />{{ profile.student_number || "学号待完善" }}<button aria-label="复制学号" @click="copyStudentNumber"><UiIcon name="PhCopy" :size="13" /></button></span>
              <span><UiIcon name="PhBuildings" />{{ profile.college || "学院待完善" }}</span>
              <span><UiIcon name="PhBookOpen" />{{ profile.major || "专业待完善" }}</span>
            </div>
            <div class="profile-secondary-meta">
              <span><UiIcon name="PhGraduationCap" />{{ profile.grade || "年级待完善" }}</span>
              <span class="profile-status">账号状态：正常</span>
            </div>
          </div>
        </div>
        <div class="profile-stat-grid">
          <article v-for="item in stats" :key="item.label" class="profile-stat">
            <span class="profile-stat-icon" :class="item.tone"><UiIcon :name="item.icon" :size="20" /></span>
            <span><small>{{ item.label }}</small><strong>{{ item.value }}</strong><em>{{ item.hint }}</em></span>
          </article>
        </div>
        <img class="profile-banner-art" src="/assets/campusmate-profile-banner-v2.png" alt="" aria-hidden="true" />
      </header>

      <nav class="redesign-tabs" aria-label="个人中心分区">
        <button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" @click="tab = item.key">{{ item.label }}</button>
      </nav>

      <section v-if="tab === 'overview'" class="profile-overview-grid">
        <div class="profile-main-column">
          <article class="redesign-panel profile-info-panel">
            <div class="redesign-panel-head">
              <h2>基本资料</h2>
              <div class="panel-head-actions">
                <span v-if="saved" class="redesign-status success"><UiIcon name="PhCheckCircle" />{{ saved }}</span>
                <button v-if="!editing" class="text-action" @click="editing = true"><UiIcon name="PhPencil" />编辑资料</button>
              </div>
            </div>
            <dl v-if="!editing" class="profile-detail-list">
              <div v-for="item in details" :key="item.label">
                <UiIcon :name="item.icon" :size="18" />
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </div>
            </dl>
            <form v-else class="profile-edit-form" @submit.prevent="save">
              <label>姓名<input v-model="form.display_name" autocomplete="name" /></label>
              <label>学号<input :value="profile.student_number || '暂未填写'" disabled /></label>
              <label>学院<input v-model="form.college" autocomplete="organization" /></label>
              <label>专业<input v-model="form.major" /></label>
              <label>年级<input v-model="form.grade" /></label>
              <label>邮箱<input v-model="form.email" type="email" autocomplete="email" /></label>
              <div class="profile-edit-actions"><button type="button" class="redesign-button secondary" @click="editing = false">取消</button><button class="redesign-button primary" :disabled="saving">{{ saving ? "保存中…" : "保存资料" }}</button></div>
            </form>
          </article>

          <article class="redesign-panel profile-tools-panel">
            <div class="redesign-panel-head"><h2>快捷入口</h2></div>
            <div class="profile-quick-grid">
              <button v-for="item in quickTools" :key="item.path" class="profile-quick-card" @click="router.push(item.path)">
                <span class="profile-quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="27" /></span>
                <span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span>
              </button>
            </div>
          </article>
        </div>

        <aside class="profile-side-column">
          <article class="redesign-panel campus-card">
            <div class="redesign-panel-head"><h2>校园身份卡</h2></div>
            <div class="campus-card-body">
              <div class="campus-card-seal">{{ initial }}</div>
              <div><strong>{{ displayName }} <em>本科生</em></strong><span>{{ profile.student_number || "学号待完善" }}</span><span>{{ identityLine }}</span></div>
              <UiIcon name="PhQrCode" class="campus-card-check" :size="24" weight="bold" />
              <UiIcon name="PhSealCheck" class="campus-card-watermark" :size="120" weight="duotone" />
            </div>
          </article>

          <article class="redesign-panel activity-panel">
            <div class="redesign-panel-head"><h2>最近活动</h2><button class="link-action" @click="router.push('/study')">查看学习记录 <UiIcon name="PhArrowRight" :size="14" /></button></div>
            <div v-if="sessions.length" class="profile-activity-list">
              <div v-for="session in sessions.slice(0, 4)" :key="session.id"><span class="activity-dot"></span><span><strong>{{ session.goal || "完成了一次学习陪伴" }}</strong><small>{{ formatSessionDate(session.started_at) }} · {{ session.status === "completed" ? `${Math.round((session.duration_seconds || 0) / 60)} 分钟` : "进行中" }}</small></span></div>
            </div>
            <div v-else class="profile-mini-empty"><UiIcon name="PhClockCounterClockwise" :size="19" /><span>还没有学习活动记录，开始一次专注后会显示在这里。</span></div>
          </article>
        </aside>
      </section>

      <section v-else-if="tab === 'tools'" class="profile-tools-view">
        <article class="redesign-panel tools-intro"><div><span class="redesign-label">YOUR TOOLBOX</span><h2>把校园服务整理成自己的工作台</h2><p>从课程、通知到专注记录，常用入口都可以在这里快速打开。</p></div><button class="redesign-button primary" @click="router.push('/home')"><UiIcon name="PhHouse" />回到首页</button></article>
        <div class="profile-tools-large-grid"><button v-for="item in quickTools" :key="item.path" class="redesign-panel profile-tool-large" @click="router.push(item.path)"><span class="profile-quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="24" /></span><span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span><UiIcon name="PhArrowUpRight" :size="17" /></button></div>
      </section>

      <section v-else class="redesign-panel profile-settings-panel">
        <div class="redesign-panel-head"><div><span class="redesign-label">PREFERENCES</span><h2>陪伴偏好</h2></div><span class="panel-hint">设置会保存在当前设备</span></div>
        <div class="preference-list">
          <div class="preference-row"><span class="preference-icon blue"><UiIcon name="PhSparkle" /></span><span><strong>减少动态效果</strong><small>关闭页面进入动画和不必要的过渡，适合需要更稳定界面的场景。</small></span><button class="preference-toggle" :class="{ on: settings.reduceMotion }" :aria-pressed="settings.reduceMotion" @click="setSetting('reduceMotion', !settings.reduceMotion)"><i></i></button></div>
          <div class="preference-row"><span class="preference-icon green"><UiIcon name="PhBell" /></span><span><strong>截止提醒</strong><small>控制待办与作业的提醒展示，具体通知能力以学校数据源为准。</small></span><button class="preference-toggle" :class="{ on: settings.noticeReminder }" :aria-pressed="settings.noticeReminder" @click="setSetting('noticeReminder', !settings.noticeReminder)"><i></i></button></div>
        </div>
        <div class="settings-links"><button @click="router.push('/study')"><UiIcon name="PhChartLineUp" />查看学习统计</button><button @click="router.push('/counselor')"><UiIcon name="PhRobot" />打开 AI 校园助手</button></div>
      </section>
    </template>
  </main>
</template>
