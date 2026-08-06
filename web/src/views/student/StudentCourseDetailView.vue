<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getCourseDetail, getMySubmission, markAnnouncementRead } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const detail = ref(null);
const tab = ref("overview");
const selectedSubmission = ref(null);
const expandedNotice = ref(null);

const tabs = [
  { key: "overview", label: "课程概览" },
  { key: "materials", label: "资料" },
  { key: "assignments", label: "作业" },
  { key: "announcements", label: "通知" },
  { key: "grades", label: "成绩" },
  { key: "teacher", label: "教师信息" },
];

const classes = computed(() => detail.value?.classes || []);
const assignments = computed(() => classes.value.flatMap((item) => (item.assignments || []).map((assignment) => ({ ...assignment, className: item.name }))));
const announcements = computed(() => classes.value.flatMap((item) => (item.announcements || []).map((notice) => ({ ...notice, className: item.name }))));
const courseStats = computed(() => ({
  classes: classes.value.length,
  assignments: assignments.value.length,
  announcements: announcements.value.length,
  completed: assignments.value.filter((item) => ["submitted", "graded"].includes(item.submission_status)).length,
}));
const courseProgress = computed(() => courseStats.value.assignments ? Math.round((courseStats.value.completed / courseStats.value.assignments) * 100) : 0);
const ringCircumference = 314.16;
const ringDash = computed(() => `${Math.max(0, (ringCircumference * courseProgress.value) / 100)} ${ringCircumference}`);
const materials = computed(() => assignments.value.flatMap((assignment) => (assignment.attachments || []).map((file) => ({ ...file, assignmentId: assignment.id, assignmentTitle: assignment.title, className: assignment.className }))));

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}
function formatShortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return String(value);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return `${date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })}${sameYear ? "" : `/${date.getFullYear()}`}`;
}
function formatDeadline(value) {
  return value ? formatDate(value) : "无截止时间";
}
function submissionLabel(assignment) {
  return { draft: "草稿", submitted: "已提交", graded: "已评分" }[assignment.submission_status] || "未提交";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await getCourseDetail(route.params.courseId);
  } catch (e) {
    error.value = e.response?.data?.detail || "课程详情加载失败。";
  } finally {
    loading.value = false;
  }
}

async function openGrade(assignment) {
  selectedSubmission.value = null;
  try {
    selectedSubmission.value = await getMySubmission(assignment.id);
  } catch {
    selectedSubmission.value = { error: "成绩信息暂时无法加载" };
  }
}

async function readNotice(notice) {
  if (!notice.has_read) {
    try {
      await markAnnouncementRead(notice.id);
      notice.has_read = true;
    } catch {
      /* detail remains readable */
    }
  }
}

function toggleNotice(notice) {
  readNotice(notice);
  expandedNotice.value = expandedNotice.value === notice.id ? null : notice.id;
}

function openNoticeTab(notice) {
  if (notice) readNotice(notice);
  expandedNotice.value = notice?.id ?? null;
  tab.value = "announcements";
}

watch(tab, () => {
  selectedSubmission.value = null;
});

onMounted(load);
</script>

<template>
  <main class="student-page campus-redesign course-detail-redesign page-enter">
    <button class="cd-back-link" type="button" @click="router.push('/courses')">
      <UiIcon name="PhArrowLeft" />返回课程列表
    </button>

    <div v-if="loading" class="cd-loading" aria-label="课程详情加载中">
      <div class="cd-loading-hero"></div>
      <div class="cd-loading-grid">
        <span></span><span></span><span></span>
      </div>
    </div>

    <div v-else-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" type="button" @click="load">重试</button>
    </div>

    <template v-else-if="detail">
      <header class="cd-hero">
        <div class="cd-hero-main">
          <div class="cd-hero-info">
            <span class="cd-hero-code">{{ detail.course.code || "COURSE" }} · {{ detail.course.semester || "当前学期" }}</span>
            <h1 class="cd-hero-title">
              {{ detail.course.name }}
              <UiIcon name="PhSparkle" class="cd-sparkle" :size="22" />
            </h1>
            <p class="cd-hero-sub">{{ detail.course.teacher_name ? `任课教师 · ${detail.course.teacher_name}` : "课程信息已同步" }}</p>
            <p class="cd-hero-desc">{{ detail.course.description || "这门课程的班级通知、作业与资料会集中展示在这里。" }}</p>
          </div>
          <div class="cd-hero-stats">
            <div class="cd-stat-card">
              <span class="cd-stat-icon"><UiIcon name="PhChalkboardTeacher" /></span>
              <div><strong>{{ courseStats.classes }}</strong><small>教学班</small></div>
            </div>
            <div class="cd-stat-card">
              <span class="cd-stat-icon"><UiIcon name="PhFileText" /></span>
              <div><strong>{{ courseStats.assignments }}</strong><small>课程作业</small></div>
            </div>
            <div class="cd-stat-card">
              <span class="cd-stat-icon pie"><UiIcon name="PhChartPie" /></span>
              <div><strong>{{ courseProgress }}%</strong><small>提交进度</small></div>
            </div>
            <div class="cd-stat-card">
              <span class="cd-stat-icon"><UiIcon name="PhMegaphone" /></span>
              <div><strong>{{ courseStats.announcements }}</strong><small>课程通知</small></div>
            </div>
          </div>
        </div>
        <aside class="cd-hero-side">
          <div class="cd-teacher-card">
            <span class="cd-teacher-avatar">{{ detail.course.teacher_name?.slice(0, 1) || "师" }}</span>
            <span class="cd-teacher-meta">
              <small>任课教师</small>
              <strong>{{ detail.course.teacher_name || "未设置" }}</strong>
            </span>
          </div>
        </aside>
      </header>

      <nav class="cd-tabs" aria-label="课程内容">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          :class="{ active: tab === item.key }"
          @click="tab = item.key"
        >{{ item.label }}</button>
      </nav>

      <section v-if="tab === 'overview'" class="cd-overview">
        <div class="cd-overview-left">
          <article class="cd-panel">
            <div class="cd-panel-head">
              <div>
                <span class="cd-eyebrow">学习结构</span>
                <h2>班级与作业</h2>
              </div>
              <span class="cd-count">{{ courseStats.completed }}/{{ courseStats.assignments }} 已提交</span>
            </div>
            <div class="cd-structure-body">
              <div class="cd-progress-ring">
                <svg class="cd-ring-svg" viewBox="0 0 120 120" aria-hidden="true">
                  <circle class="cd-ring-bg" cx="60" cy="60" r="50"></circle>
                  <circle class="cd-ring-fg" cx="60" cy="60" r="50" :stroke-dasharray="ringDash"></circle>
                </svg>
                <span class="cd-ring-text">
                  <strong>{{ courseProgress }}%</strong>
                  <small>提交进度</small>
                </span>
              </div>
              <div v-if="classes.length" class="cd-class-list">
                <div v-for="item in classes" :key="item.id" class="cd-class-card">
                  <span class="cd-class-icon"><UiIcon name="PhChalkboardTeacher" /></span>
                  <span class="cd-class-info">
                    <strong>{{ item.name }}</strong>
                    <small>{{ item.class_code || "课程班级" }} · {{ item.description || "已加入课程班级" }}</small>
                  </span>
                  <span class="cd-class-assign">{{ item.assignments?.length || 0 }} 项作业</span>
                  <UiIcon name="PhCaretRight" />
                </div>
              </div>
              <div v-else class="cd-mini-empty">暂无班级信息，课程数据同步后这里会展示班级结构。</div>
            </div>
          </article>

          <article class="cd-panel">
            <div class="cd-panel-head">
              <div>
                <span class="cd-eyebrow">最近更新</span>
                <h2>课程通知</h2>
              </div>
              <button class="cd-text-link" type="button" @click="tab = 'announcements'">查看全部<UiIcon name="PhArrowRight" /></button>
            </div>
            <div v-if="announcements.length" class="cd-notice-list">
              <button
                v-for="notice in announcements.slice(0, 4)"
                :key="notice.id"
                type="button"
                class="cd-notice-item"
                @click="openNoticeTab(notice)"
              >
                <span class="cd-notice-icon"><UiIcon name="PhMegaphone" /></span>
                <span class="cd-notice-main">
                  <strong>{{ notice.title }}</strong>
                  <small>{{ notice.className }} · {{ notice.author_name || "课程教师" }}</small>
                </span>
                <time>{{ formatShortDate(notice.published_at || notice.created_at) }}</time>
                <UiIcon name="PhCaretRight" />
              </button>
            </div>
            <div v-else class="cd-mini-empty">暂无课程通知，任课教师发布后会显示在这里。</div>
          </article>
        </div>

        <div class="cd-overview-right">
          <aside class="cd-panel cd-pulse-panel">
            <div class="cd-panel-head">
              <div>
                <span class="cd-eyebrow">Course pulse</span>
                <h2>这门课的内容</h2>
              </div>
            </div>
            <div class="cd-pulse-stats">
              <div class="cd-pulse-stat">
                <span class="cd-pulse-icon"><UiIcon name="PhChalkboardTeacher" /></span>
                <div><strong>{{ courseStats.classes }}</strong><small>教学班</small></div>
              </div>
              <div class="cd-pulse-stat">
                <span class="cd-pulse-icon"><UiIcon name="PhFileText" /></span>
                <div><strong>{{ courseStats.assignments }}</strong><small>项作业</small></div>
              </div>
              <div class="cd-pulse-stat">
                <span class="cd-pulse-icon"><UiIcon name="PhMegaphone" /></span>
                <div><strong>{{ courseStats.announcements }}</strong><small>条通知</small></div>
              </div>
            </div>
            <button class="cd-primary-btn" type="button" @click="tab = 'assignments'">查看作业<UiIcon name="PhArrowRight" /></button>
          </aside>

          <aside class="cd-panel cd-side-panel">
            <div class="cd-panel-head">
              <div>
                <span class="cd-eyebrow">近期作业</span>
                <h2>任务预览</h2>
              </div>
              <span class="cd-count">{{ assignments.length }} 项</span>
            </div>
            <div v-if="assignments.length" class="cd-assign-list">
              <button
                v-for="assignment in assignments.slice(0, 4)"
                :key="assignment.id"
                type="button"
                class="cd-assign-card"
                @click="router.push(`/tasks/assignment/${assignment.id}`)"
              >
                <span class="cd-assign-icon"><UiIcon name="PhFileText" /></span>
                <span class="cd-assign-main">
                  <strong>{{ assignment.title }}</strong>
                  <small>{{ assignment.className }}</small>
                </span>
                <span class="cd-assign-meta">
                  <time>{{ formatDeadline(assignment.deadline) }}</time>
                  <span class="cd-status" :class="['submitted', 'graded'].includes(assignment.submission_status) ? 'done' : 'pending'">{{ submissionLabel(assignment) }}</span>
                </span>
              </button>
            </div>
            <div v-else class="cd-mini-empty">课程作业发布后会出现在这里。</div>
          </aside>

          <aside class="cd-panel cd-tips-panel">
            <div>
              <span class="cd-eyebrow">学习建议</span>
              <h2>本周先从这里开始</h2>
            </div>
            <div class="cd-tip-card">
              <span class="cd-tip-bulb"><UiIcon name="PhLightbulb" /></span>
              <p>优先完成尚未提交的作业，提交进度会同步到课程概览。</p>
            </div>
            <button class="cd-plan-link" type="button" @click="router.push('/study')">前往学习陪伴<UiIcon name="PhArrowRight" /></button>
          </aside>
        </div>
      </section>

      <section v-else-if="tab === 'materials'" class="cd-panel cd-tab-panel">
        <div class="cd-panel-head">
          <div>
            <span class="cd-eyebrow">课程资料</span>
            <h2>资料与附件</h2>
            <p class="cd-panel-sub">从作业和课程内容中汇总可下载的附件。</p>
          </div>
          <span class="cd-count">{{ materials.length }} 个文件</span>
        </div>
        <div v-if="materials.length" class="cd-material-list">
          <a
            v-for="material in materials"
            :key="`${material.assignmentId}-${material.id}`"
            class="cd-material-card"
            :href="`/api/v1/assignments/${material.assignmentId}/attachments/${material.id}`"
            target="_blank"
            rel="noopener"
          >
            <span class="cd-material-icon"><UiIcon name="PhFileText" /></span>
            <span class="cd-material-info">
              <strong>{{ material.original_filename }}</strong>
              <small>{{ material.assignmentTitle }} · {{ material.className }}</small>
            </span>
            <span class="cd-enter-btn">下载<UiIcon name="PhDownloadSimple" /></span>
          </a>
        </div>
        <div v-else class="cd-mini-empty">暂无课程资料，教师上传附件后会显示在这里。</div>
      </section>

      <section v-else-if="tab === 'assignments'" class="cd-panel cd-tab-panel">
        <div class="cd-panel-head">
          <div>
            <span class="cd-eyebrow">Coursework</span>
            <h2>课程作业</h2>
            <p class="cd-panel-sub">点击作业进入详情页查看要求并提交。</p>
          </div>
          <span class="cd-count">{{ assignments.length }} 项</span>
        </div>
        <div v-if="assignments.length" class="cd-assign-table">
          <button
            v-for="assignment in assignments"
            :key="assignment.id"
            type="button"
            class="cd-assign-row"
            @click="router.push(`/tasks/assignment/${assignment.id}`)"
          >
            <span class="cd-row-icon blue"><UiIcon name="PhFileText" /></span>
            <span class="cd-row-main">
              <strong>{{ assignment.title }}</strong>
              <small>{{ assignment.className }} · {{ assignment.status === 'closed' ? '已结束' : '可提交' }}</small>
            </span>
            <time>{{ formatDeadline(assignment.deadline) }}</time>
            <UiIcon name="PhCaretRight" />
          </button>
        </div>
        <div v-else class="cd-mini-empty">暂无作业，教师发布后会显示在这里。</div>
      </section>

      <section v-else-if="tab === 'announcements'" class="cd-panel cd-tab-panel">
        <div class="cd-panel-head">
          <div>
            <span class="cd-eyebrow">Class updates</span>
            <h2>课程通知</h2>
            <p class="cd-panel-sub">课程班级发布的通知会集中显示在这里。</p>
          </div>
          <span class="cd-count">{{ announcements.length }} 条</span>
        </div>
        <div v-if="announcements.length" class="cd-announce-list">
          <article
            v-for="notice in announcements"
            :key="notice.id"
            class="cd-announce-card"
            :class="{ unread: !notice.has_read, open: expandedNotice === notice.id }"
          >
            <button class="cd-announce-head" type="button" @click="toggleNotice(notice)">
              <span class="cd-notice-icon"><UiIcon name="PhMegaphone" /></span>
              <span class="cd-announce-main">
                <strong>{{ notice.title }}</strong>
                <small>{{ notice.className }} · {{ notice.author_name || "课程教师" }} · {{ formatDate(notice.published_at || notice.created_at) }}</small>
              </span>
              <span v-if="!notice.has_read" class="cd-unread-dot" aria-label="未读"></span>
              <UiIcon name="PhCaretDown" />
            </button>
            <p>{{ notice.content }}</p>
          </article>
        </div>
        <div v-else class="cd-mini-empty">暂无课程通知，任课教师发布后会显示在这里。</div>
      </section>

      <section v-else-if="tab === 'grades'" class="cd-panel cd-tab-panel">
        <div class="cd-panel-head">
          <div>
            <span class="cd-eyebrow">成绩记录</span>
            <h2>作业成绩</h2>
            <p class="cd-panel-sub">查看各作业的评分与教师评语。</p>
          </div>
          <span class="cd-count">以教师发布结果为准</span>
        </div>
        <div v-if="assignments.length" class="cd-assign-table">
          <button
            v-for="assignment in assignments"
            :key="assignment.id"
            type="button"
            class="cd-assign-row"
            @click="openGrade(assignment)"
          >
            <span class="cd-row-icon green"><UiIcon name="PhChartBar" /></span>
            <span class="cd-row-main">
              <strong>{{ assignment.title }}</strong>
              <small>{{ assignment.className }} · {{ submissionLabel(assignment) }}</small>
            </span>
            <time>{{ formatDeadline(assignment.deadline) }}</time>
            <UiIcon name="PhCaretRight" />
          </button>
        </div>
        <div v-if="selectedSubmission" class="cd-grade-result" :class="{ error: selectedSubmission.error }">
          <div class="cd-grade-score" :class="{ empty: selectedSubmission.score == null }">
            <strong>{{ selectedSubmission.error ? "—" : selectedSubmission.score == null ? "待" : selectedSubmission.score }}</strong>
            <small>{{ selectedSubmission.error ? "加载失败" : selectedSubmission.score == null ? "未评分" : "分" }}</small>
          </div>
          <div class="cd-grade-main">
            <span class="cd-eyebrow">提交结果</span>
            <h3>{{ selectedSubmission.error ? "成绩信息暂时无法加载" : selectedSubmission.score == null ? "尚未评分" : "教师已评分" }}</h3>
            <p>{{ selectedSubmission.error || selectedSubmission.teacher_comment || "教师暂未留下评语。" }}</p>
          </div>
        </div>
        <div v-else-if="!assignments.length" class="cd-mini-empty">暂无成绩记录，完成作业后教师发布的成绩会显示在这里。</div>
      </section>

      <section v-else class="cd-panel cd-tab-panel">
        <div class="cd-panel-head">
          <div>
            <span class="cd-eyebrow">任课教师</span>
            <h2>教师信息</h2>
          </div>
        </div>
        <div class="cd-teacher-profile">
          <span class="cd-teacher-avatar large">{{ detail.course.teacher_name?.slice(0, 1) || "师" }}</span>
          <div class="cd-teacher-profile-main">
            <span class="cd-eyebrow">Teacher</span>
            <h3>{{ detail.course.teacher_name || "未设置教师信息" }}</h3>
            <p>{{ detail.course.description || "教师联系方式与课程说明由学校教务数据提供。" }}</p>
          </div>
        </div>
        <dl class="cd-teacher-grid">
          <div><dt>课程代码</dt><dd>{{ detail.course.code || "—" }}</dd></div>
          <div><dt>开课学期</dt><dd>{{ detail.course.semester || "—" }}</dd></div>
          <div><dt>课程状态</dt><dd>{{ detail.course.status }}</dd></div>
          <div><dt>教学班数量</dt><dd>{{ courseStats.classes }}</dd></div>
        </dl>
      </section>
    </template>
  </main>
</template>
