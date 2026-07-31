<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/app";
import UiIcon from "../components/UiIcon.vue";
import TeacherPortalView from "./TeacherPortalView.vue";
import AdminPortalView from "./AdminPortalView.vue";
const store = useAppStore();
const router = useRouter();
const role = computed(() => store.session?.role || "student");
const courses = [
  { name:"数据结构", detail:"作业 3 已发布", time:"2小时前" },
  { name:"计算机组成原理", detail:"新增课堂资料", time:"昨天" },
  { name:"高等数学", detail:"课堂测验成绩已发布", time:"5月17日" },
  { name:"大学英语 IV", detail:"口语作业已批改", time:"5月16日" },
];
const days = [
  ["周一","7/27","数据结构","高等数学（下）"],
  ["周二","7/28","操作系统","大学英语 IV"],
  ["周三","7/29","计算机组成原理","体育"],
  ["周四","7/30","数据库系统","高等数学（下）"],
  ["周五","7/31","操作系统",""],
  ["周六","8/1","无课",""],
  ["周日","8/2","无课",""],
];
</script>

<template>
  <TeacherPortalView v-if="role === 'teacher'" section="home" />
  <AdminPortalView v-else-if="role === 'admin'" section="home" />
  <main v-else class="dashboard page-enter">
    <div class="page-title">
      <div><h1>{{ role === "student" ? "早上好，林知夏" : role === "teacher" ? "教学工作台" : "系统管理概览" }}</h1><p>{{ role === "student" ? "把今天的校园生活理清楚，专注重要的事。" : role === "teacher" ? "课程、班级和待批任务都在这里。" : "查看平台运行状态与关键管理任务。" }}</p></div>
      <button class="secondary-button"><UiIcon name="PhSlidersHorizontal" />自定义首页</button>
    </div>

    <template v-if="role === 'student'">
      <section class="next-action surface">
        <div><span>期末考试周进行中</span><strong>3</strong></div><article><h3>《数据结构》作业提交</h3><p class="danger-text">今天 23:59 截止</p></article><article><small>2</small><h3>图书馆预约</h3><p>今天 14:00</p></article><article><small>3</small><h3>计算机组成原理预习</h3><p>今天 16:30</p></article><button class="primary-button" @click="router.push('/tasks')">查看今日计划<UiIcon name="PhArrowRight" /></button>
      </section>
      <div class="dashboard-grid">
        <section class="data-panel"><div class="section-head"><h2>截止提醒 <b>{{ store.pendingCount }}</b></h2><button @click="router.push('/tasks')">全部待办<UiIcon name="PhCaretRight" /></button></div>
          <div v-if="store.tasks.length" class="rows"><label v-for="task in store.tasks.slice(0,5)" :key="task.id" class="task-row" :class="{done:task.done}"><input type="checkbox" :checked="task.done" @change="store.toggleTask(task.id)" /><span><strong>{{ task.title }}</strong><small :class="{'danger-text':!task.done}">{{ task.due }}</small></span><em>{{ task.course }}</em></label></div>
          <div v-else class="portal-empty"><UiIcon name="PhCheckCircle" :size="30" /><strong>今天的待办已经清空</strong><span>可以安心去做下一件重要的事。</span></div>
        </section>
        <section class="data-panel"><div class="section-head"><h2>校园通知</h2><button @click="router.push('/notifications')">全部通知<UiIcon name="PhCaretRight" /></button></div>
          <div class="filter-tabs"><button class="active">全部</button><button>未读</button><button>学生事务</button><button>教务教学</button></div>
          <div class="rows"><button v-for="notice in store.notices" :key="notice.id" class="notice-row" @click="notice.unread = false"><i v-if="notice.unread"></i><span><strong>{{ notice.title }}</strong><small>{{ notice.source }}</small></span><time>{{ notice.time }}</time></button></div>
        </section>
        <section class="data-panel"><div class="section-head"><h2>课程动态</h2><button @click="router.push('/courses')">全部课程<UiIcon name="PhCaretRight" /></button></div>
          <div class="rows"><button v-for="course in courses" :key="course.name" class="course-row"><span class="soft-icon"><UiIcon name="PhFileText" /></span><span><strong>{{ course.name }}</strong><small>{{ course.detail }}</small></span><time>{{ course.time }}</time></button></div>
        </section>
      </div>
      <section class="schedule data-panel"><div class="section-head"><h2>本周课表</h2><div><button aria-label="上一周">‹</button><button>今天</button><button aria-label="下一周">›</button></div></div><div class="week-grid"><article v-for="(day,i) in days" :key="day[0]" :class="{today:i===4}"><strong>{{ day[0] }}</strong><small>{{ day[1] }}</small><p>{{ day[2] }}</p><p>{{ day[3] }}</p></article></div></section>
      <aside class="companion-rail">
        <section class="companion"><div class="section-head"><h2>AI 导员 <em>Mock</em></h2><UiIcon name="PhRobot" :size="32" /></div><p>有问题，问小夏。</p><button v-for="q in ['期末考试周的自习教室推荐','如何申请课程重修？','奖学金申请条件有哪些？']" :key="q" @click="router.push('/counselor')">{{ q }}<UiIcon name="PhCaretRight" /></button></section>
        <section class="study-card"><h2>学习陪伴</h2><p>本周学习时长</p><strong>12.6<small> 小时</small></strong><div class="mini-bars"><i v-for="h in [42,58,36,76,64,88,50]" :key="h" :style="{height:h+'%'}"></i></div><div class="focus-score"><span>专注状态<small>识别结果仅供辅助参考</small></span><b>良好</b></div><button class="primary-button" @click="router.push('/study')">开始学习</button></section>
      </aside>
    </template>
  </main>
</template>
