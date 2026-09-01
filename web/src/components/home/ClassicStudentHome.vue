<script setup>
import { computed } from "vue";
import UiIcon from "../UiIcon.vue";
import HomeLearningCommand from "./HomeLearningCommand.vue";
import HomeLearningPulse from "./HomeLearningPulse.vue";
import HomeSchedulePanel from "./HomeSchedulePanel.vue";
import HomeFooter from "./footer/HomeFooter.vue";

const props = defineProps({
  state: { type: Object, required: true },
  searchQuery: { type: String, default: "" },
});
const emit = defineEmits(["navigate", "open-due", "reload"]);

const totalPending = computed(() => props.state.overviewMetrics.pendingCount);
const urgentItems = computed(() => props.state.filteredDueItems.slice(0, 3));

const quickLinks = [
  { label: "办事大厅", detail: "申请与办理进度", icon: "PhClipboardText", path: "/services", tone: "blue" },
  { label: "空教室查询", detail: "找一间学习空间", icon: "PhSquaresFour", path: "/classrooms", tone: "green" },
  { label: "失物招领", detail: "查看待招领物品", icon: "PhMagnifyingGlass", path: "/lostfound", tone: "teal" },
  { label: "通知整理", detail: "课程与校园通知", icon: "PhBell", path: "/notifications", tone: "amber" },
  { label: "校园社区", detail: "交流学习与生活", icon: "PhChatsCircle", path: "/community", tone: "violet" },
  { label: "学校与专业", detail: "查看校园背景信息", icon: "PhBuildings", path: "/university", tone: "rose" },
];

function dateText(value) {
  if (!value) return "未设置截止时间";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "截止时间待确认" : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function deadlineLabel(value) {
  if (!value) return "未设置截止";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "截止时间待确认";
  const current = new Date(props.state.now);
  const sameDay = date.toDateString() === current.toDateString();
  return sameDay ? `今日截止 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}` : dateText(value);
}
</script>

<template>
  <main class="student-page student-home simple-student-home">
    <div v-if="state.error" class="student-alert error" role="alert">
      <UiIcon name="PhWarningCircle" />{{ state.error }}
      <button class="link-button" @click="emit('reload')">重试</button>
    </div>

    <section v-if="state.loading" class="student-home-skeleton simple-home-skeleton" aria-label="正在加载首页" aria-busy="true">
      <div class="home-skeleton-focus"></div>
      <div class="home-skeleton-overview"></div>
      <div class="home-skeleton-panel"></div>
    </section>

    <template v-else>
      <HomeFooter>
        <section class="simple-home-command-stack">
          <HomeLearningCommand :command="state.learningCommand" @navigate="emit('navigate', $event)" />
          <HomeLearningPulse :items="state.learningCommand.pulse" @navigate="emit('navigate', $event)" />
        </section>

        <div v-if="state.normalizedSearch" class="home-search-note">
          <UiIcon name="PhMagnifyingGlass" :size="16" />
          正在筛选“{{ searchQuery }}”，当前首页有 {{ state.filteredDueItems.length + state.filteredCourses.length }} 条相关内容
        </div>

        <section class="simple-home-grid">
          <article class="student-home-panel task-panel simple-priority-panel">
            <div class="home-panel-head">
              <h2><UiIcon name="PhFlag" :size="19" />优先处理</h2>
              <button @click="emit('navigate', '/tasks')">全部 {{ totalPending }} 项</button>
            </div>
            <div v-if="urgentItems.length" class="priority-list">
              <button v-for="(item, index) in urgentItems" :key="`${item.kind}-${item.id}`" @click="emit('open-due', item)">
                <span v-if="index === 0" class="urgent-tag">优先</span>
                <strong>{{ item.title }}</strong>
                <time :class="{ today: deadlineLabel(item.due).startsWith('今日') }">{{ deadlineLabel(item.due) }}</time>
              </button>
            </div>
            <div v-else class="compact-empty">
              <UiIcon name="PhCheckCircle" :size="26" />
              <strong>没有临近截止事项</strong>
              <span>新的课程作业和个人待办会自动汇合到这里。</span>
            </div>
            <button class="panel-footer simple" @click="emit('navigate', '/tasks')">进入待办与作业<UiIcon name="PhArrowRight" :size="15" /></button>
          </article>

          <HomeSchedulePanel :items="state.scheduleItems" :loading="state.scheduleLoading" @open-academic="emit('navigate', '/profile/academic')" />
        </section>

        <section class="student-quick-section simple-quick-section">
          <div class="quick-section-head">
            <div><span>校园服务</span><h2>需要时再打开</h2></div>
            <small>学习主线之外的功能只保留一个入口</small>
          </div>
          <div class="student-quick-grid">
            <button v-for="item in quickLinks" :key="item.path" @click="emit('navigate', item.path)">
              <span class="quick-icon" :class="item.tone"><UiIcon :name="item.icon" :size="20" /></span>
              <span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span>
              <UiIcon name="PhCaretRight" :size="15" />
            </button>
          </div>
        </section>
      </HomeFooter>
    </template>
  </main>
</template>

<style scoped>
.simple-home-command-stack{display:grid;gap:16px;margin-bottom:18px}
.simple-home-grid{display:grid;grid-template-columns:minmax(320px,.82fr) minmax(0,1.45fr);gap:18px;margin-bottom:18px}
.simple-home-grid :deep(.student-home-panel),.simple-priority-panel{min-height:350px}
.simple-priority-panel{border-color:#e1e7ed;background:#fff}
.panel-footer.simple{background:#edf5f3;color:#2f6f69}
.simple-quick-section{border-color:#e2e8ef;box-shadow:none}
.simple-quick-section .quick-section-head{display:flex;align-items:end;justify-content:space-between;gap:18px}
.simple-quick-section .quick-section-head>div{display:grid;gap:3px}
.simple-quick-section .quick-section-head span{color:#2f6f69;font-size:9px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.simple-quick-section .quick-section-head h2{margin:0}
.simple-quick-section .quick-section-head>small{color:#8794a2;font-size:10px}
.simple-home-skeleton{grid-template-columns:minmax(0,1.6fr) minmax(280px,.7fr)}
@media (max-width: 1100px){.simple-home-grid{grid-template-columns:1fr}}
@media (max-width: 700px){.simple-home-command-stack{gap:12px}.simple-home-grid{gap:12px}.simple-quick-section .quick-section-head{align-items:start}.simple-quick-section .quick-section-head>small{max-width:150px;text-align:right;line-height:1.5}.simple-home-skeleton{grid-template-columns:1fr}}
</style>
