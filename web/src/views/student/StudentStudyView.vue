<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import StudyExperienceLayer from "../../components/study/StudyExperienceLayer.vue";
import {
  breakdownStudyTask,
  completePersonalTask,
  finishStudySession,
  getActiveStudySession,
  getPersonalTasks,
  getStudySessions,
  pauseStudySession,
  resumeStudySession,
  startStudySession,
  updatePersonalTask,
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
const trendCanvas = ref(null);
const experience = ref({ open: false, view: "", context: {} });

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

function drawTrend() {
  const canvas = trendCanvas.value;
  if (!canvas) return;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  const values = weekMinutes.value ? trend.value.map((item) => item.minutes) : [25, 46, 33, 61, 21, 60, 32];
  const points = values.map((value, index) => ({ x: 13 + (index * (width - 26)) / 6, y: height - 14 - (Math.min(value, 120) / 120) * (height - 28) }));
  const trace = () => {
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      context.bezierCurveTo((previous.x + current.x) / 2, previous.y, (previous.x + current.x) / 2, current.y, current.x, current.y);
    }
  };
  trace();
  context.lineTo(points.at(-1).x, height);
  context.lineTo(points[0].x, height);
  context.closePath();
  const fill = context.createLinearGradient(0, 0, 0, height);
  fill.addColorStop(0, "rgba(112, 116, 248, .2)");
  fill.addColorStop(1, "rgba(112, 116, 248, 0)");
  context.fillStyle = fill;
  context.fill();
  trace();
  context.strokeStyle = "#898df8";
  context.lineWidth = 2;
  context.stroke();
  points.forEach((point) => {
    context.beginPath();
    context.arc(point.x, point.y, 4, 0, Math.PI * 2);
    context.fillStyle = "#8d91f9";
    context.fill();
    context.lineWidth = 2;
    context.strokeStyle = "#fff";
    context.stroke();
  });
}

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

function openExperience(view, context = {}, event) {
  experience.value = { open: true, view, context };
  if (event?.currentTarget) {
    const rect = event.currentTarget.getBoundingClientRect();
    document.documentElement.style.setProperty("--study-origin-x", `${rect.left + rect.width / 2}px`);
    document.documentElement.style.setProperty("--study-origin-y", `${rect.top + rect.height / 2}px`);
  }
}

function closeExperience() {
  experience.value = { ...experience.value, open: false };
}

function reuseExperience(item) {
  if (!active.value) goal.value = item?.goal || item?.title || goal.value;
  closeExperience();
  toast.value = "目标已带入专注计划";
  window.setTimeout(() => { toast.value = ""; }, 2200);
}

async function saveTaskFromLayer(task) {
  if (!task?.id || !task.title) return;
  try {
    const updated = await updatePersonalTask(task.id, { title: task.title });
    tasks.value = tasks.value.map((item) => item.id === task.id ? { ...item, ...updated } : item);
    experience.value.context = { ...experience.value.context, ...updated };
    toast.value = "计划修改已保存";
    window.setTimeout(() => { toast.value = ""; }, 2200);
  } catch (err) {
    error.value = err.response?.data?.detail || "计划保存失败，请重试。";
  }
}

async function completeTaskFromLayer(task) {
  if (!task?.id) return;
  try {
    await completePersonalTask(task.id, true);
    tasks.value = tasks.value.filter((item) => item.id !== task.id);
    toast.value = "计划已完成";
    window.setTimeout(closeExperience, 780);
    window.setTimeout(() => { toast.value = ""; }, 2200);
  } catch (err) {
    error.value = err.response?.data?.detail || "计划状态更新失败，请重试。";
  }
}

watch(trend, () => nextTick(drawTrend), { deep: true });
onMounted(async () => { await load(); await nextTick(); drawTrend(); window.addEventListener("resize", drawTrend); });
onBeforeUnmount(() => { window.clearInterval(ticker.value); window.removeEventListener("resize", drawTrend); });
</script>

<template>
  <main class="student-page study-reference page-enter">
    <header class="study-reference-heading">
      <h1>给专注留一段完整时间 <UiIcon name="PhSparkle" :size="24" weight="fill" /></h1>
      <p>学习会让自我多维记录，结束时再由你主动填写本次学习感受。</p>
    </header>

    <div v-if="error" class="study-reference-alert"><UiIcon name="PhWarningCircle" /><span>{{ error }}</span><button @click="load">重试</button></div>
    <div v-if="toast" class="study-reference-toast"><UiIcon name="PhCheckCircle" />{{ toast }}</div>

    <div v-if="loading" class="study-reference-loading"><i></i><i></i><i></i><i></i></div>
    <template v-else>
      <section class="study-reference-top">
        <article class="study-reference-card focus-reference-card" :class="{ active }">
          <div class="focus-reference-main">
            <img class="focus-reference-art" src="/assets/focus-study-robot.png" alt="" aria-hidden="true" />
            <div class="focus-reference-copy">
              <span class="focus-reference-badge">专注会话</span>
              <h2>专注当前，未来更从容 <UiIcon name="PhSparkle" :size="17" weight="fill" /></h2>
              <p>{{ active ? active.goal : "选择时长，开始你的专注时光" }}</p>
              <strong class="focus-reference-clock" :class="{ ticking: running }">{{ timerText }}</strong>
              <div class="focus-reference-presets">
                <button v-for="item in presets" :key="item" :class="{ active: selectedPreset === item }" :disabled="!!active" @click="selectedPreset = item">{{ item }} 分钟</button>
                <button :class="{ active: selectedPreset === 'custom' }" :disabled="!!active" @click="selectedPreset = 'custom'">自定义</button>
                <input v-if="selectedPreset === 'custom' && !active" v-model.number="customMinutes" type="number" min="5" max="180" aria-label="自定义专注分钟数" />
              </div>
              <div class="focus-reference-actions">
                <button v-if="!active" class="study-primary-button" @click="start"><UiIcon name="PhPlay" weight="fill" />开始专注</button>
                <template v-else><button class="study-secondary-button" @click="togglePause"><UiIcon :name="running ? 'PhPause' : 'PhPlay'" />{{ running ? "暂停" : "继续" }}</button><button class="study-primary-button" @click="finish"><UiIcon name="PhStop" />结束并记录</button></template>
                <button class="study-immersive-entry" @click="openExperience('focus', active || { goal }, $event)"><UiIcon name="PhArrowsDownUp" />沉浸模式</button>
              </div>
            </div>
          </div>
          <div class="focus-reference-controls">
            <label><span><UiIcon name="PhStudent" />专注模式</span><select v-model="mode" :disabled="!!active"><option v-for="item in modes" :key="item.key" :value="item.key">{{ item.label }}</option></select></label>
            <label><span><UiIcon name="PhBell" />提醒设置</span><span class="study-switch-row"><button type="button" class="study-switch" :class="{ on: blockNotifications }" role="switch" :aria-checked="blockNotifications" @click="blockNotifications = !blockNotifications"><i></i></button>{{ blockNotifications ? "阻止通知" : "允许通知" }}</span></label>
            <label><span><UiIcon name="PhChatCircleText" />环境声音</span><span class="study-switch-row"><button type="button" class="study-switch" :class="{ on: soundOn }" role="switch" :aria-checked="soundOn" @click="soundOn = !soundOn"><i></i></button>{{ soundOn ? "雨声 · 轻柔" : "静音" }}</span></label>
          </div>
        </article>

        <div class="study-reference-side">
          <article class="study-reference-card study-reference-plan">
            <div class="study-reference-card-head"><div><span>STUDY PLAN</span><h2>先明确这一段要做什么</h2></div><button class="study-reference-open" aria-label="打开 AI 学习路线" @click="openExperience('plan', {}, $event)"><UiIcon name="PhNotePencil" :size="21" /></button></div>
            <label class="study-reference-goal">学习目标<input v-model="goal" name="study-goal" :disabled="!!active" placeholder="例如：完成数据结构作业的查错与整理" /></label>
            <div class="study-reference-plan-action"><button :disabled="breaking || !!active || !goal.trim()" @click="planBreakdown"><UiIcon name="PhSparkle" />{{ breaking ? "拆解中…" : "让 AI 帮我拆解步骤" }}</button></div>
            <div v-if="breakdownResult?.steps?.length" class="study-reference-breakdown"><div v-for="(step, index) in breakdownResult.steps" :key="index"><b>{{ index + 1 }}</b><span><strong>{{ step.title || step }}</strong><small>{{ step.estimated_minutes ? `${step.estimated_minutes} 分钟` : "" }}</small></span></div></div>
            <div v-else class="study-reference-examples"><span>试试这些示例：</span><button @click="goal = '复习线性代数矩阵与特征值'">复习线性代数知识点</button><button @click="goal = '准备数据结构实验报告'">准备数据结构实验报告</button><button @click="goal = '预习操作系统第3章'">预习操作系统第3章</button></div>
          </article>

          <section class="study-reference-metrics">
            <article class="study-reference-card study-reference-metric" role="button" tabindex="0" @click="openExperience('metric', { label: '今日专注', value: todayMinutes, unit: '分钟', eyebrow: 'TODAY RHYTHM', insight: '午后是你的高效区间' }, $event)" @keydown.enter="openExperience('metric', { label: '今日专注', value: todayMinutes, unit: '分钟' })"><i class="violet"><UiIcon name="PhClock" /></i><span><small>今日专注</small><strong>{{ todayMinutes }}<em>分钟</em></strong><b>点击查看节奏</b></span></article>
            <article class="study-reference-card study-reference-metric" role="button" tabindex="0" @click="openExperience('metric', { label: '已完成会话', value: completedSessions.length, unit: '次', eyebrow: 'FOCUS ARCHIVE', insight: '完成记录正在形成你的专注画像' }, $event)" @keydown.enter="openExperience('metric', { label: '已完成会话', value: completedSessions.length, unit: '次' })"><i class="green"><UiIcon name="PhCheckCircle" /></i><span><small>已完成会话</small><strong>{{ completedSessions.length }}<em>次</em></strong><b>查看累计记录</b></span></article>
            <article class="study-reference-card study-reference-metric" role="button" tabindex="0" @click="openExperience('metric', { label: '连续专注', value: completedSessions.length ? '—' : '0', unit: '天', eyebrow: 'FOCUS STREAK', insight: '保持出现，比偶尔超常更重要' }, $event)" @keydown.enter="openExperience('metric', { label: '连续专注', value: '0', unit: '天' })"><i class="amber"><UiIcon name="PhSparkle" /></i><span><small>连续专注</small><strong>{{ completedSessions.length ? "—" : "0" }}<em>天</em></strong><b>查看连续趋势</b></span></article>
            <article class="study-reference-card study-reference-metric" role="button" tabindex="0" @click="openExperience('metric', { label: '专注评分', value: '—', unit: '/100', eyebrow: 'FOCUS SCORE', insight: '完成更多会话后生成专注评分' }, $event)" @keydown.enter="openExperience('metric', { label: '专注评分', value: '—', unit: '/100' })"><i class="lilac"><UiIcon name="PhChartLineUp" /></i><span><small>专注评分</small><strong>—<em>/100</em></strong><b>查看评分说明</b></span></article>
          </section>
        </div>
      </section>

      <section class="study-reference-bottom">
        <article class="study-reference-card study-reference-records">
          <div class="study-reference-card-head"><h2>最近记录</h2><button @click="load">刷新 <UiIcon name="PhArrowClockwise" :size="14" /></button></div>
          <div v-if="sessions.length" class="study-reference-record-list"><div v-for="session in sessions.slice(0, 4)" :key="session.id" role="button" tabindex="0" @click="openExperience('record', session, $event)" @keydown.enter="openExperience('record', session)"><i><UiIcon name="PhCheckCircle" /></i><span><strong>{{ session.goal || "学习会话" }}</strong><small>{{ new Date(session.started_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) }}</small></span><b>{{ Math.round((session.duration_seconds || 0) / 60) }} 分钟</b></div></div>
          <div v-else class="study-reference-empty"><span><UiIcon name="PhListChecks" :size="36" /></span><strong>还没有学习记录</strong><p>开始一次专注会话，你的记录会出现在这里。</p><button @click="start"><UiIcon name="PhPlay" />去开始学习</button></div>
        </article>

        <article class="study-reference-card study-reference-trend">
          <div class="study-reference-card-head"><h2>专注趋势（本周）</h2><button class="study-reference-open-text" @click="openExperience('trend', {}, $event)">展开分析 <UiIcon name="PhArrowRight" :size="13" /></button></div>
          <div class="study-reference-chart"><div class="study-reference-y"><span>120</span><span>90</span><span>60</span><span>30</span><span>0</span></div><div class="study-reference-plot"><canvas ref="trendCanvas" aria-label="本周专注趋势图"></canvas><div><small v-for="item in trend" :key="item.label">{{ item.label }}</small></div></div></div>
          <div class="study-reference-legend"><i></i>专注时长（分钟）<span v-if="!weekMinutes">完成会话后会显示趋势</span></div>
        </article>

        <article class="study-reference-card study-reference-todos">
          <div class="study-reference-card-head"><h2>待完成计划</h2><button @click="$router.push('/tasks')">管理全部 <UiIcon name="PhArrowRight" :size="14" /></button></div>
          <div v-if="tasks.length" class="study-reference-todo-list"><button v-for="task in tasks.slice(0, 4)" :key="task.id" @click="openExperience('task', task, $event)"><i></i><span>{{ task.title }}</span><time>{{ task.deadline ? new Date(task.deadline).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '待安排' }}</time></button></div>
          <div v-else class="study-reference-todo-empty"><UiIcon name="PhCheckSquare" :size="23" /><span>当前没有待完成计划</span></div>
          <button class="study-reference-add" @click="$router.push('/tasks')"><UiIcon name="PhPlus" />添加计划</button>
        </article>
      </section>
    </template>

    <div v-if="active" class="study-reference-report"><label>本次学习感受（可选）<textarea v-model="selfReport" rows="2" placeholder="例如：完成了阅读，后半段注意力有些分散"></textarea></label></div>
    <StudyExperienceLayer
      :open="experience.open"
      :view="experience.view"
      :context="experience.context"
      :timer-text="timerText"
      :running="running"
      :active="!!active"
      :goal="goal"
      :mode="mode"
      :sound-on="soundOn"
      :block-notifications="blockNotifications"
      :breakdown="breakdownResult"
      :breaking="breaking"
      :trend="trend"
      @close="closeExperience"
      @start="start"
      @toggle-pause="togglePause"
      @finish="finish"
      @breakdown="planBreakdown"
      @update:goal="goal = $event"
      @update:mode="mode = $event"
      @toggle-sound="soundOn = !soundOn"
      @toggle-notifications="blockNotifications = !blockNotifications"
      @reuse-record="reuseExperience"
      @save-task="saveTaskFromLayer"
      @complete-task="completeTaskFromLayer"
    />
  </main>
</template>
