<script setup>
import { computed } from "vue";
import UiIcon from "../UiIcon.vue";
import { groupScheduleByWeekday } from "../../features/home/scheduleModel";

const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(["open-academic"]);

const weekdayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const todayWeekday = new Date().getDay() || 7;
const weeklySchedule = computed(() => groupScheduleByWeekday(props.items));
const hasSchedule = computed(() => weeklySchedule.value.some((items) => items.length));
const referenceScheduleWeek = computed(() => {
  const current = new Date();
  const mondayOffset = (current.getDay() + 6) % 7;
  const start = new Date(current);
  start.setDate(current.getDate() - mondayOffset);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const dateText = (value) => `${value.getMonth() + 1}月${value.getDate()}日`;
  return {
    label: `${dateText(start)} – ${dateText(end)}`,
    days: Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return { name: weekdayNames[index].replace("周", ""), date: date.getDate(), isToday: index + 1 === todayWeekday };
    }),
  };
});

function sectionText(item) {
  const start = item.start_section;
  const end = item.end_section ?? start;
  if (!start) return "时间待定";
  return start === end ? `第 ${start} 节` : `第 ${start}-${end} 节`;
}
</script>

<template>
  <article class="student-home-panel course-panel">
    <div class="home-panel-head">
      <h2><UiIcon name="PhCalendarBlank" :size="19" />课程表</h2>
      <button @click="emit('open-academic')">查看课表<UiIcon name="PhArrowRight" :size="15" /></button>
    </div>
    <div v-if="loading" class="home-schedule-loading" aria-label="正在加载课程表"><i></i><i></i><i></i></div>
    <div v-else-if="hasSchedule" class="home-schedule-grid" aria-label="课程表">
      <section v-for="(dayItems, index) in weeklySchedule" :key="weekdayNames[index]" :class="{ today: index + 1 === todayWeekday }">
        <header><strong>{{ weekdayNames[index] }}</strong><small v-if="index + 1 === todayWeekday">今日</small></header>
        <button v-for="item in dayItems" :key="item.id || `${item.course_name}-${item.start_section}-${item.location}`" @click="emit('open-academic')">
          <strong>{{ item.course_name || "未命名课程" }}</strong>
          <small>{{ sectionText(item) }}<template v-if="item.location"> · {{ item.location }}</template></small>
        </button>
        <span v-if="!dayItems.length" class="home-schedule-empty">—</span>
      </section>
    </div>
    <div v-else class="compact-empty home-reference-schedule-empty" role="status">
      <div class="reference-schedule-week">
        <strong>{{ referenceScheduleWeek.label }}</strong><small>本周</small>
        <span><i v-for="day in referenceScheduleWeek.days" :key="day.name" :class="{ today: day.isToday }"><b>{{ day.name }}</b>{{ day.date }}</i></span>
      </div>
      <div class="schedule-empty-art" aria-hidden="true">
        <svg viewBox="0 0 220 150" role="presentation">
          <defs>
            <linearGradient id="schedule-paper" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#ffffff" />
              <stop offset="1" stop-color="#dce7ff" />
            </linearGradient>
            <linearGradient id="schedule-cover" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#7e9eff" />
              <stop offset="1" stop-color="#4d6cf0" />
            </linearGradient>
            <filter id="schedule-soft-shadow" x="-20%" y="-20%" width="140%" height="150%">
              <feDropShadow dx="0" dy="8" stdDeviation="7" flood-color="#718ad5" flood-opacity=".18" />
            </filter>
          </defs>
          <ellipse cx="110" cy="133" rx="70" ry="10" fill="#e9efff" />
          <circle cx="42" cy="46" r="18" fill="#edf2ff" />
          <circle cx="181" cy="31" r="10" fill="#f0f4ff" />
          <g filter="url(#schedule-soft-shadow)" transform="rotate(-4 110 78)">
            <rect x="57" y="38" width="108" height="86" rx="12" fill="url(#schedule-paper)" stroke="#c9d7ff" stroke-width="2" />
            <rect x="57" y="38" width="108" height="25" rx="12" fill="url(#schedule-cover)" />
            <path d="M57 51h108" stroke="#6f8bf3" stroke-width="2" />
            <path d="M76 29v18M146 29v18" stroke="#4e6cf0" stroke-width="7" stroke-linecap="round" />
            <path d="M78 76h27M78 91h48M78 106h33" stroke="#bdd0ff" stroke-width="6" stroke-linecap="round" />
            <rect x="130" y="74" width="20" height="20" rx="6" fill="#e4ebff" />
            <path d="m136 84 5 5 9-11" fill="none" stroke="#5676ee" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
          </g>
        </svg>
      </div>
      <strong>暂无课程安排</strong><span>暂无课程安排，假期或未选课？</span>
      <button class="reference-empty-action" @click="emit('open-academic')">管理我的课表</button>
    </div>
    <button v-if="hasSchedule" class="panel-footer blue" @click="emit('open-academic')">管理教务课表<UiIcon name="PhArrowRight" :size="15" /></button>
  </article>
</template>
