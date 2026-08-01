<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import {
  breakdownStudyTask,
  finishStudySession,
  getActiveStudySession,
  getPersonalTasks,
  getStudySessions,
  pauseStudySession,
  resumeStudySession,
  startStudySession,
} from "../../services/studentApi";

const loading = ref(true);
const error = ref("");
const active = ref(null);
const sessions = ref([]);
const tasks = ref([]);
const elapsed = ref(0);
const ticker = ref(null);
const goal = ref("");
const selfReport = ref("");
const selectedPreset = ref(25);
const customMinutes = ref(45);
const mode = ref("deep");
const soundOn = ref(true);
const blockNotifications = ref(true);
const breakdownResult = ref(null);
const breaking = ref(false);
const toast = ref("");

const presets = [25, 50, 75];
const modes = [
  { key: "deep", label: "深度专注", detail: "适合需要连续思考的任务" },
  { key: "steady", label: "稳步推进", detail: "保持轻量节奏，逐步完成" },
  { key: "quiet", label: "安静阅读", detail: "适合阅读、整理与复盘" },
];
const running = computed(() => active.value?.status === "active");
const timerText = computed(() => `${String(Math.floor(elapsed.value / 60)).padStart(2, "0")}:${String(elapsed.value % 60).padStart(2, "0")}`);
const completedSessions = computed(() => sessions.value.filter((item) => item.status === "completed"));
const localDateKey = (date = new Date()) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, "0"),
  String(date.getDate()).padStart(2, "0"),
].join("-");
const todayKey = localDateKey();
const todaySessions = computed(() => completedSessions.value.filter((item) => String(item.started_at || "").slice(0, 10) === todayKey));
const todayMinutes = computed(() => todaySessions.value.reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0));
const weekMinutes = computed(() => completedSessions.value.reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0));
const trend = computed(() => {
  const dates = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setDate(date.getDate() - (6 - index));
    return date;
  });
  return dates.map((date) => {
    const key = localDateKey(date);
    const minutes = completedSessions.value.filter((item) => String(item.started_at || "").slice(0, 10) === key).reduce((total, item) => total + Math.round((item.duration_seconds || 0) / 60), 0);
    return { label: `${date.getMonth() + 1}/${date.getDate()}`, minutes };
  });
});
const maxTrend = computed(() => Math.max(...trend.value.map((item) => item.minutes), 1));
const selectedMinutes = computed(() => selectedPreset.value === "custom" ? Number(customMinutes.value || 45) : selectedPreset.value);

function syncElapsed() {
  if (!active.value) return;
  const started = new Date(active.value.started_at).valueOf();
  if (Number.isNaN(started)) return;
  elapsed.value = Math.max(0, Math.round((Date.now() - started) / 1000) - (active.value.pause_seconds || 0));
}

function startTicker() {
  window.clearInterval(ticker.value);
  ticker.value = window.setInterval(syncElapsed, 1000);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [activeData, sessionData, taskData] = await Promise.all([
      getActiveStudySession(),
      getStudySessions(),
      getPersonalTasks({ status: "pending" }),
    ]);
    active.value = activeData;
    sessions.value = Array.isArray(sessionData) ? sessionData : sessionData?.items || [];
    tasks.value = Array.isArray(taskData) ? taskData : taskData?.items || [];
    syncElapsed();
    if (active.value) startTicker();
  } catch (err) {
    error.value = err.response?.data?.detail || "学习数据加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function start() {
  if (active.value) return;
  error.value = "";
  try {
    active.value = await startStudySession({ goal: goal.value.trim() || "完成一段专注学习" });
    elapsed.value = 0;
    startTicker();
    toast.value = `已开始 ${selectedMinutes.value} 分钟专注`;
    window.setTimeout(() => { toast.value = ""; }, 2200);
  } catch (err) {
    error.value = err.response?.data?.detail || "无法开始学习会话，请稍后重试。";
  }
}

async function togglePause() {
  if (!active.value) return;
  try {
    active.value = running.value ? await pauseStudySession(active.value.id, "主动休息") : await resumeStudySession(active.value.id);
    syncElapsed();
  } catch (err) {
    error.value = err.response?.data?.detail || "学习状态更新失败，请重试。";
  }
}

async function finish() {
  if (!active.value) return;
  try {
    await finishStudySession(active.value.id, { self_report: selfReport.value.trim() || null });
    active.value = null;
    selfReport.value = "";
    elapsed.value = 0;
    window.clearInterval(ticker.value);
    const refreshedSessions = await getStudySessions();
    sessions.value = Array.isArray(refreshedSessions) ? refreshedSessions : refreshedSessions?.items || sessions.value;
    toast.value = "本次专注已记录，做得很好";
    window.setTimeout(() => { toast.value = ""; }, 2600);
  } catch (err) {
    error.value = err.response?.data?.detail || "结束会话失败，请重试。";
  }
}

async function planBreakdown() {
  if (!goal.value.trim() || breaking.value) return;
  breaking.value = true;
  error.value = "";
  try {
    breakdownResult.value = await breakdownStudyTask({ goal: goal.value.trim() });
  } catch (err) {
    error.value = err.response?.data?.detail || "任务拆解失败，请稍后再试。";
  } finally {
    breaking.value = false;
  }
}

function chooseTask(task) {
  if (!active.value) goal.value = task.title;
}

onMounted(load);
onBeforeUnmount(() => window.clearInterval(ticker.value));
</script>

<template>
  <main class="student-page campus-redesign study-redesign page-enter">
    <div class="redesign-heading">
      <div><span class="redesign-kicker">STUDY / 学习陪伴</span><h1>给专注留一段完整时间 <span class="heading-sparkle"><UiIcon name="PhSparkle" :size="24" weight="fill" /></span></h1><p>学习会话由服务端记录，结束时再由你主动填写本次学习感受。</p></div>
      <button class="redesign-button secondary" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" :class="{ spinning: loading }" />刷新</button>
    </div>
    <div v-if="error" class="redesign-alert error"><UiIcon name="PhWarningCircle" /><span>{{ error }}</span><button @click="load">重试</button></div>
    <div v-if="toast" class="redesign-toast"><UiIcon name="PhCheckCircle" />{{ toast }}</div>

    <div v-if="loading" class="study-loading-grid"><i></i><i></i><i></i><i></i></div>
    <template v-else>
      <section class="study-top-grid">
        <article class="focus-stage redesign-panel" :class="{ active: active }">
          <img class="focus-stage-art" src="/assets/campusmate-hero-illustration.png" alt="" aria-hidden="true" />
          <div class="focus-stage-copy"><span class="focus-stage-badge">专注会话</span><h2>专注当前，未来更从容 <UiIcon name="PhSparkle" :size="17" weight="fill" /></h2><p>{{ active ? active.goal : "选择时长，开始你的专注时光" }}</p><div class="focus-clock" :class="{ ticking: running }">{{ timerText }}</div></div>
          <div class="focus-presets"><button v-for="item in presets" :key="item" :class="{ active: selectedPreset === item }" :disabled="!!active" @click="selectedPreset = item">{{ item }} 分钟</button><button :class="{ active: selectedPreset === 'custom' }" :disabled="!!active" @click="selectedPreset = 'custom'">自定义</button><input v-if="selectedPreset === 'custom' && !active" v-model.number="customMinutes" class="custom-minutes" type="number" min="5" max="180" aria-label="自定义专注分钟数" /></div><div class="focus-stage-actions"><button v-if="!active" class="redesign-button primary" @click="start"><UiIcon name="PhPlay" weight="fill" />开始学习</button><template v-else><button class="redesign-button secondary" @click="togglePause"><UiIcon :name="running ? 'PhPause' : 'PhPlay'" />{{ running ? "暂停" : "继续" }}</button><button class="redesign-button primary" @click="finish"><UiIcon name="PhStop" />结束并记录</button></template></div>
          <div class="focus-controls"><label><span><UiIcon name="PhStudent" />专注模式</span><select v-model="mode" :disabled="!!active"><option v-for="item in modes" :key="item.key" :value="item.key">{{ item.label }}</option></select></label><label><span><UiIcon name="PhBell" />提醒设置</span><button class="focus-control-toggle" :class="{ on: blockNotifications }" :aria-pressed="blockNotifications" @click="blockNotifications = !blockNotifications"><i></i>{{ blockNotifications ? "阻止通知" : "允许通知" }}</button></label><label><span><UiIcon name="PhChatCircleText" />环境声音</span><button class="focus-control-toggle" :class="{ on: soundOn }" :aria-pressed="soundOn" @click="soundOn = !soundOn"><i></i>{{ soundOn ? "雨声 · 轻柔" : "静音" }}</button></label></div>
        </article>

        <article class="redesign-panel study-plan-panel"><div class="redesign-panel-head"><div><span class="redesign-label">STUDY PLAN</span><h2>先明确这一段要做什么</h2></div><span class="plan-mark"><UiIcon name="PhNotePencil" :size="22" /></span></div><label class="study-goal-field">学习目标<input v-model="goal" name="study-goal" :disabled="!!active" placeholder="例如：完成数据结构作业的查错与整理" /></label><div class="study-plan-actions"><button class="redesign-button secondary" :disabled="breaking || !!active || !goal.trim()" @click="planBreakdown"><UiIcon name="PhSparkle" />{{ breaking ? "拆解中…" : "让 AI 帮我拆解步骤" }}</button></div><div class="breakdown-list" v-if="breakdownResult?.steps?.length"><div v-for="(step, index) in breakdownResult.steps" :key="index"><b>{{ index + 1 }}</b><span><strong>{{ step.title || step }}</strong><small>{{ step.estimated_minutes ? `${step.estimated_minutes} 分钟` : "" }}</small></span></div></div><div v-else class="plan-examples"><span>试试这些示例：</span><button @click="goal = '复习线性代数矩阵与特征值'">复习线性代数知识点</button><button @click="goal = '准备数据结构实验报告'">准备数据结构实验报告</button></div></article>
      </section>

      <section class="study-metric-grid">
        <article class="redesign-panel study-metric"><span class="metric-icon indigo"><UiIcon name="PhClock" /></span><span><small>今日专注</small><strong>{{ todayMinutes }}<em>分钟</em></strong><i>较昨日 —</i></span></article><article class="redesign-panel study-metric"><span class="metric-icon green"><UiIcon name="PhCheckCircle" /></span><span><small>已完成会话</small><strong>{{ completedSessions.length }}<em>次</em></strong><i>真实记录</i></span></article><article class="redesign-panel study-metric"><span class="metric-icon amber"><UiIcon name="PhSparkle" /></span><span><small>连续专注</small><strong>{{ completedSessions.length ? "—" : "0" }}<em>天</em></strong><i>连续记录后显示</i></span></article><article class="redesign-panel study-metric"><span class="metric-icon violet"><UiIcon name="PhChartLineUp" /></span><span><small>专注评分</small><strong>—<em>/100</em></strong><i>暂不自动评估</i></span></article>
      </section>

      <section class="study-bottom-grid">
        <article class="redesign-panel study-record-panel"><div class="redesign-panel-head"><div><span class="redesign-label">RECENT RECORDS</span><h2>最近记录</h2></div><button class="link-action" @click="load">刷新 <UiIcon name="PhArrowClockwise" :size="14" /></button></div><div v-if="sessions.length" class="study-record-list"><div v-for="session in sessions.slice(0, 4)" :key="session.id"><span class="record-icon"><UiIcon name="PhCheckCircle" /></span><span><strong>{{ session.goal || "学习会话" }}</strong><small>{{ new Date(session.started_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) }}</small></span><b>{{ Math.round((session.duration_seconds || 0) / 60) }} 分钟</b></div></div><div v-else class="study-empty"><UiIcon name="PhClockCounterClockwise" :size="34" /><strong>还没有学习记录</strong><span>开始一次专注会话，你的记录会出现在这里。</span><button class="redesign-button secondary" @click="start"><UiIcon name="PhPlay" />去开始学习</button></div></article>

        <article class="redesign-panel trend-panel"><div class="redesign-panel-head"><div><span class="redesign-label">FOCUS TREND</span><h2>专注趋势（本周）</h2></div><span class="trend-unit">分钟</span></div><div class="trend-chart"><div class="trend-y-labels"><span>120</span><span>90</span><span>60</span><span>30</span><span>0</span></div><div class="trend-bars"><div v-for="item in trend" :key="item.label" class="trend-bar-wrap"><div class="trend-bar-track"><i :style="{ height: `${item.minutes ? Math.max(8, (item.minutes / maxTrend) * 100) : 3}%` }" :class="{ filled: item.minutes }"></i></div><small>{{ item.label }}</small></div></div></div><div class="trend-legend"><i></i>专注时长（分钟）<span v-if="!weekMinutes">完成会话后会显示趋势</span></div></article>

        <article class="redesign-panel todo-panel"><div class="redesign-panel-head"><div><span class="redesign-label">NEXT UP</span><h2>待完成计划</h2></div><button class="link-action" @click="$router.push('/tasks')">管理全部 <UiIcon name="PhArrowRight" :size="14" /></button></div><div v-if="tasks.length" class="study-todo-list"><button v-for="task in tasks.slice(0, 4)" :key="task.id" @click="chooseTask(task)"><span class="todo-circle"></span><span>{{ task.title }}</span><time>{{ task.deadline ? new Date(task.deadline).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '待安排' }}</time></button></div><div v-else class="study-todo-empty"><UiIcon name="PhCheckSquare" :size="23" /><span>当前没有待完成计划</span></div><button class="add-plan-button" @click="$router.push('/tasks')"><UiIcon name="PhPlus" />添加计划</button></article>
      </section>
      <div class="study-footer-note"><UiIcon name="PhSparkle" :size="18" /><span>每一次专注，都是在为未来的你积蓄力量。稳住节奏，你已经做得很好。</span></div>
    </template>
    <div v-if="active" class="study-report-dock"><label>本次学习感受（可选）<textarea v-model="selfReport" rows="2" placeholder="例如：完成了阅读，后半段注意力有些分散"></textarea></label></div>
  </main>
</template>
