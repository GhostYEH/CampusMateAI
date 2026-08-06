<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getStudentCourses, getStudentAssignments } from "../../services/studentApi";

const router = useRouter();
const loading = ref(true);
const error = ref("");
const courses = ref([]);
const assignments = ref([]);
const query = ref("");
const sort = ref("name");
const showTip = ref(true);

const totalCourses = computed(() => courses.value.length);
const newSemesterCourses = computed(() => 0);
const pendingAssignments = computed(() => assignments.value.filter(a => !["submitted", "graded"].includes(a.submission_status)).length);
const currentSemester = computed(() => courses.value[0]?.semester || "2024-2025秋季");

const filtered = computed(() => {
  return courses.value
    .filter((course) => `${course.name} ${course.code || ""} ${course.teacher_name || ""}`.toLowerCase().includes(query.value.trim().toLowerCase()))
    .sort((a, b) => sort.value === "name" ? a.name.localeCompare(b.name, "zh-CN") : String(b.updated_at).localeCompare(String(a.updated_at)));
});

function courseTone(code) {
  const c = code || "";
  if (c.includes("CS") || c.includes("101")) return "violet";
  if (c.includes("ENG")) return "blue";
  if (c.includes("MATH")) return "green";
  return "violet";
}

function courseProgress(course) {
  const total = assignments.value.filter(a => a.course_id === course.id).length;
  if (total === 0) return 0;
  const done = assignments.value.filter(a => a.course_id === course.id && ["submitted", "graded"].includes(a.submission_status)).length;
  return Math.round((done / total) * 100);
}

function courseMaterialCount(course) {
  return 0;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [c, a] = await Promise.all([getStudentCourses(), getStudentAssignments()]);
    courses.value = c.items || [];
    assignments.value = a.items || [];
  } catch (e) {
    error.value = e.response?.data?.detail || "课程加载失败，请重试。";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <main class="student-page courses-redesign page-enter">
    <!-- Hero Section -->
    <section class="courses-hero courses-hero-bg">
      <div class="courses-hero-content">
        <span class="hero-eyebrow">COURSES / 我的学习空间</span>
        <div class="student-title-line hero-title">
          <h1>我的课程</h1>
          <UiIcon name="PhSparkle" class="heading-sparkle" :size="26" />
        </div>
        <p class="hero-desc">查看课程资料、作业、班级通知、成绩与任课教师信息。</p>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="stat-icon violet"><UiIcon name="PhBookOpen" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ totalCourses }}</strong>
              <small>课程总数</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon blue"><UiIcon name="PhBookBookmark" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ newSemesterCourses }}</strong>
              <small>本学期新课</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon green"><UiIcon name="PhCheckCircle" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ pendingAssignments }}</strong>
              <small>待完成作业</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon indigo"><UiIcon name="PhCalendarBlank" :size="18" /></span>
            <div class="stat-info">
              <strong class="semester-text">{{ currentSemester }}</strong>
              <small>当前学期</small>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div v-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <!-- Toolbar -->
    <section class="student-toolbar courses-toolbar surface">
      <div class="search-field">
        <UiIcon name="PhMagnifyingGlass" />
        <input v-model="query" placeholder="搜索课程名称、代码或教师" />
      </div>
      <select v-model="sort">
        <option value="name">按课程名称</option>
        <option value="updated">按最近更新</option>
      </select>
      <span class="toolbar-count"><UiIcon name="PhSquaresFour" :size="14" /> 共 {{ filtered.length }} 门课程</span>
    </section>

    <!-- Loading / Empty / Results -->
    <div v-if="loading" class="student-card-grid">
      <div v-for="i in 6" :key="i" class="student-skeleton"></div>
    </div>

    <div v-else-if="!filtered.length" class="student-empty large surface">
      <UiIcon name="PhBookOpen" :size="42" />
      <strong>还没有匹配的课程</strong>
      <span>课程数据来自你的班级加入记录，暂时没有可展示内容。</span>
    </div>

    <section v-else class="student-card-grid">
      <div
        v-for="course in filtered"
        :key="course.id"
        class="new-course-card surface"
        :class="`tone-${courseTone(course.code)}`"
      >
        <div class="course-card-header">
          <span class="course-code-badge" :class="`badge-${courseTone(course.code)}`">
            {{ course.code || "课程" }}
          </span>
          <button class="course-arrow-btn" @click="router.push(`/courses/${course.id}`)">
            <UiIcon name="PhArrowRight" :size="16" />
          </button>
        </div>

        <h2 class="course-name">{{ course.name }}</h2>
        <p class="course-desc">{{ course.description || "进入课程查看班级通知、作业和课程资料。" }}</p>

        <div class="course-meta-row">
          <span class="meta-item">
            <UiIcon name="PhChalkboardTeacher" :size="14" />
            {{ course.teacher_name || "任课教师" }}
          </span>
          <span class="meta-item">
            <UiIcon name="PhCalendarBlank" :size="14" />
            {{ course.semester || "2024-2025秋季" }}
          </span>
        </div>

        <div class="course-stats">
          <div class="course-stat">
            <div class="progress-ring" :class="`ring-${courseTone(course.code)}`">
              <svg viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15" fill="none" stroke-width="3" class="ring-bg"/>
                <circle cx="18" cy="18" r="15" fill="none" stroke-width="3" class="ring-fg"
                  :stroke-dasharray="`${courseProgress(course)} 100`"/>
              </svg>
              <span>{{ courseProgress(course) }}%</span>
            </div>
            <small>学习进度</small>
          </div>
          <div class="course-stat">
            <span class="material-icon" :class="`mat-${courseTone(course.code)}`">
              <UiIcon name="PhFolderOpen" :size="16" />
            </span>
            <div class="material-info">
              <strong>{{ courseMaterialCount(course) }} 个</strong>
              <small>课程资料</small>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Tip Banner -->
    <div v-if="showTip" class="tip-banner">
      <div class="tip-content">
        <span class="tip-icon"><UiIcon name="PhGraduationCap" :size="18" /></span>
        <div>
          <strong>小贴士</strong>
          <p>点击课程卡片右上角的箭头，可快速进入课程主页，查看课程详情与资源。</p>
        </div>
      </div>
      <button class="tip-close" @click="showTip = false">
        <UiIcon name="PhX" :size="16" />
      </button>
    </div>
  </main>
</template>
