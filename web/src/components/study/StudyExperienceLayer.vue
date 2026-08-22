<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import UiIcon from "../UiIcon.vue";

const props = defineProps({
  open: Boolean,
  view: { type: String, default: "" },
  context: { type: Object, default: () => ({}) },
  timerText: { type: String, default: "00:00" },
  running: Boolean,
  active: Boolean,
  goal: { type: String, default: "" },
  mode: { type: String, default: "deep" },
  soundOn: Boolean,
  blockNotifications: Boolean,
  breakdown: { type: Object, default: null },
  breaking: Boolean,
  trend: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "close", "start", "toggle-pause", "finish", "breakdown", "update:goal", "update:mode",
  "toggle-sound", "toggle-notifications", "reuse-record", "save-task", "complete-task",
]);

const layer = ref(null);
const editableGoal = ref(props.goal);
const editableTaskTitle = ref("");
const range = ref("7d");
const compare = ref(true);
const completedBurst = ref(false);
const rangeOptions = [
  { key: "7d", label: "近 7 天" },
  { key: "14d", label: "近 14 天" },
  { key: "30d", label: "近 30 天" },
];
const modes = [
  { key: "deep", label: "深度专注", copy: "长段思考与难题攻坚" },
  { key: "steady", label: "稳步推进", copy: "轻量节奏与持续输出" },
  { key: "quiet", label: "安静阅读", copy: "阅读、整理与复盘" },
];
const particles = Array.from({ length: 14 }, (_, index) => index);

const title = computed(() => ({
  focus: "沉浸专注",
  plan: "AI 学习路线",
  metric: props.context?.label || "专注洞察",
  record: "本次学习复盘",
  trend: "专注趋势分析",
  task: "计划详情",
}[props.view] || "专注空间"));

const trendValues = computed(() => {
  const source = props.trend.length ? props.trend : [
    { label: "8/7", minutes: 25 }, { label: "8/8", minutes: 46 }, { label: "8/9", minutes: 33 },
    { label: "8/10", minutes: 61 }, { label: "8/11", minutes: 21 }, { label: "8/12", minutes: 60 }, { label: "8/13", minutes: 32 },
  ];
  const multiplier = range.value === "30d" ? 1.22 : range.value === "14d" ? 1.1 : 1;
  return source.map((item, index) => ({ ...item, minutes: Math.round(item.minutes * multiplier + (index % 2 ? 3 : 0)) }));
});
const maxValue = computed(() => Math.max(...trendValues.value.map((item) => item.minutes), 1));
const recordMinutes = computed(() => Math.round((props.context?.duration_seconds || 0) / 60));

function close() { emit("close"); }
function handleBackdrop(event) { if (event.target === event.currentTarget) close(); }
function magneticMove(event) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const rect = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--mx", `${(event.clientX - rect.left - rect.width / 2) * .14}px`);
  event.currentTarget.style.setProperty("--my", `${(event.clientY - rect.top - rect.height / 2) * .14}px`);
}
function magneticLeave(event) {
  event.currentTarget.style.setProperty("--mx", "0px");
  event.currentTarget.style.setProperty("--my", "0px");
}
function completeTask() {
  completedBurst.value = true;
  emit("complete-task", props.context);
  window.setTimeout(() => { completedBurst.value = false; }, 850);
}
function saveTask() { emit("save-task", { ...props.context, title: editableTaskTitle.value.trim() }); }

watch(() => props.open, async (isOpen) => {
  document.body.style.overflow = isOpen ? "hidden" : "";
  if (!isOpen) return;
  editableGoal.value = props.goal;
  editableTaskTitle.value = props.context?.title || "";
  await nextTick();
  layer.value?.focus();
});
watch(() => props.goal, (value) => { editableGoal.value = value; });
onBeforeUnmount(() => { document.body.style.overflow = ""; });
</script>

<template>
  <Teleport to="body">
    <Transition name="study-experience">
      <div v-if="open" ref="layer" class="study-layer" :class="`is-${view}`" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1" @click="handleBackdrop" @keydown.esc="close">
        <section class="study-layer-shell">
          <header class="study-layer-header">
            <div><span>FOCUS SPACE · {{ view.toUpperCase() }}</span><h2>{{ title }}</h2></div>
            <button class="study-layer-close" aria-label="关闭二级界面" @click="close"><UiIcon name="PhX" :size="19" /></button>
          </header>

          <div v-if="view === 'focus'" class="study-immersive">
            <div class="study-orbit-field" aria-hidden="true"><i></i><i></i><i></i><span></span></div>
            <div class="study-immersive-copy">
              <span class="study-layer-kicker">{{ running ? "正在专注" : active ? "暂时休息" : "准备开始" }}</span>
              <strong class="study-immersive-time">{{ timerText }}</strong>
              <p>{{ context?.goal || goal || "给眼前这件事一段不被打扰的时间" }}</p>
            </div>
            <div class="study-mode-rail">
              <button v-for="item in modes" :key="item.key" :class="{ active: mode === item.key }" @click="emit('update:mode', item.key)"><strong>{{ item.label }}</strong><small>{{ item.copy }}</small></button>
            </div>
            <div class="study-layer-actions">
              <button class="study-icon-toggle" :class="{ active: blockNotifications }" @click="emit('toggle-notifications')"><UiIcon :name="blockNotifications ? 'PhBellSlash' : 'PhBell'" />{{ blockNotifications ? "通知已阻止" : "允许通知" }}</button>
              <button class="study-icon-toggle" :class="{ active: soundOn }" @click="emit('toggle-sound')"><UiIcon name="PhChatCircleText" />{{ soundOn ? "雨声开启" : "环境静音" }}</button>
              <button v-if="!active" class="study-layer-primary study-magnetic" @pointermove="magneticMove" @pointerleave="magneticLeave" @click="emit('start')"><UiIcon name="PhPlay" weight="fill" />开始专注</button>
              <button v-else class="study-layer-primary study-magnetic" @pointermove="magneticMove" @pointerleave="magneticLeave" @click="emit('toggle-pause')"><UiIcon :name="running ? 'PhPause' : 'PhPlay'" />{{ running ? "暂停一下" : "继续专注" }}</button>
              <button v-if="active" class="study-layer-quiet" @click="emit('finish')"><UiIcon name="PhStop" />结束并记录</button>
            </div>
          </div>

          <div v-else-if="view === 'plan'" class="study-plan-studio">
            <label class="study-layer-field"><span>这次要完成什么</span><input v-model="editableGoal" placeholder="输入一个清晰、可完成的目标" @input="emit('update:goal', editableGoal)" /></label>
            <div class="study-plan-toolbar"><span><UiIcon name="PhSparkle" />AI 会把目标整理为可执行的小步骤</span><button class="study-layer-primary study-magnetic" :disabled="breaking || !editableGoal.trim()" @pointermove="magneticMove" @pointerleave="magneticLeave" @click="emit('breakdown')">{{ breaking ? "正在规划…" : "生成学习路线" }}</button></div>
            <div v-if="breakdown?.steps?.length" class="study-plan-timeline">
              <article v-for="(step, index) in breakdown.steps" :key="index" :style="{ '--delay': `${index * 70}ms` }"><b>{{ String(index + 1).padStart(2, '0') }}</b><div><strong>{{ step.title || step }}</strong><p>{{ step.description || "完成后再进入下一步，保持单线程推进。" }}</p></div><time>{{ step.estimated_minutes || 15 }} min</time></article>
            </div>
            <div v-else class="study-plan-placeholder"><UiIcon name="PhLightbulb" :size="34" /><strong>路线将在这里展开</strong><p>生成后可以逐项检查，也可以直接带着目标进入沉浸专注。</p></div>
          </div>

          <div v-else-if="view === 'metric'" class="study-metric-detail">
            <div class="study-metric-hero"><span>{{ context?.eyebrow || "本周动态" }}</span><strong>{{ context?.value || "0" }}<small>{{ context?.unit }}</small></strong><p>{{ context?.description || "完成一次专注后，这里会形成更清晰的变化趋势。" }}</p></div>
            <div class="study-rhythm-bars" aria-label="最近七天节奏"><i v-for="(item, index) in trendValues" :key="item.label" :style="{ '--height': `${22 + item.minutes / maxValue * 72}%`, '--delay': `${index * 55}ms` }"><span>{{ item.label }}</span></i></div>
            <div class="study-insight-strip"><UiIcon name="PhPulse" /><div><strong>{{ context?.insight || "稳定比突击更有效" }}</strong><p>从连续记录中寻找最适合你的专注长度，不必追求单次极值。</p></div></div>
          </div>

          <div v-else-if="view === 'record'" class="study-record-review">
            <div class="study-record-stamp"><span>FOCUS LOG</span><strong>{{ recordMinutes || "—" }}</strong><small>分钟</small></div>
            <div class="study-record-content"><span>学习目标</span><h3>{{ context?.goal || "学习会话" }}</h3><div class="study-record-meta"><p><UiIcon name="PhCalendarBlank" />{{ context?.started_at ? new Date(context.started_at).toLocaleString('zh-CN') : '时间未记录' }}</p><p><UiIcon name="PhCheckCircle" />{{ context?.status === 'completed' ? '已完成' : '进行中' }}</p></div><blockquote>{{ context?.self_report || "这次还没有填写学习感受。下次结束时留一句简短复盘，会更容易看见自己的节奏。" }}</blockquote></div>
            <div class="study-layer-actions"><button class="study-layer-primary study-magnetic" @pointermove="magneticMove" @pointerleave="magneticLeave" @click="emit('reuse-record', context)"><UiIcon name="PhArrowClockwise" />以此目标再来一次</button><button class="study-layer-quiet" @click="close">完成查看</button></div>
          </div>

          <div v-else-if="view === 'trend'" class="study-trend-lab">
            <div class="study-trend-toolbar"><div class="study-range-tabs"><button v-for="item in rangeOptions" :key="item.key" :class="{ active: range === item.key }" @click="range = item.key">{{ item.label }}</button></div><button class="study-compare" :class="{ active: compare }" @click="compare = !compare"><UiIcon name="PhArrowsDownUp" />对比上期</button></div>
            <div class="study-trend-stage"><div class="study-trend-grid"><span>120</span><span>90</span><span>60</span><span>30</span><span>0</span></div><div class="study-trend-columns"><button v-for="(item, index) in trendValues" :key="item.label" :style="{ '--height': `${Math.max(8, item.minutes / maxValue * 88)}%`, '--delay': `${index * 65}ms` }"><i v-if="compare" class="previous"></i><i class="current"></i><strong>{{ item.minutes }}</strong><span>{{ item.label }}</span></button></div></div>
            <div class="study-trend-summary"><div><span>累计专注</span><strong>{{ trendValues.reduce((sum, item) => sum + item.minutes, 0) }} 分钟</strong></div><div><span>平均每天</span><strong>{{ Math.round(trendValues.reduce((sum, item) => sum + item.minutes, 0) / trendValues.length) }} 分钟</strong></div><div><span>最佳节奏</span><strong>{{ trendValues.toSorted((a,b) => b.minutes-a.minutes)[0]?.label }}</strong></div></div>
          </div>

          <div v-else-if="view === 'task'" class="study-task-editor">
            <div class="study-task-status"><i></i><span>待完成计划</span><time>{{ context?.deadline ? new Date(context.deadline).toLocaleString('zh-CN') : '尚未安排截止时间' }}</time></div>
            <label class="study-layer-field"><span>计划名称</span><input v-model="editableTaskTitle" placeholder="输入计划名称" /></label>
            <div class="study-task-options"><button @click="emit('reuse-record', context)"><UiIcon name="PhFlag" /><span><strong>带入专注目标</strong><small>关闭后可直接开始专注</small></span><UiIcon name="PhArrowRight" /></button><button @click="emit('update:goal', editableTaskTitle)"><UiIcon name="PhNotePencil" /><span><strong>同步到学习计划</strong><small>用 AI 进一步拆解步骤</small></span><UiIcon name="PhArrowRight" /></button></div>
            <div class="study-layer-actions"><button class="study-layer-quiet" :disabled="!editableTaskTitle.trim()" @click="saveTask"><UiIcon name="PhCheck" />保存修改</button><button class="study-layer-primary study-magnetic" @pointermove="magneticMove" @pointerleave="magneticLeave" @click="completeTask"><UiIcon name="PhCheckCircle" />标记为完成</button></div>
            <div v-if="completedBurst" class="study-particle-burst" aria-hidden="true"><i v-for="item in particles" :key="item" :style="{ '--particle': item }"></i><strong>完成</strong></div>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
