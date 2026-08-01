<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getStudentCourses } from "../../services/studentApi";
const router = useRouter(); const loading = ref(true); const error = ref(""); const courses = ref([]); const query = ref(""); const sort = ref("name");
const filtered = computed(() => courses.value.filter((course) => `${course.name} ${course.code || ""} ${course.teacher_name || ""}`.toLowerCase().includes(query.value.trim().toLowerCase())).sort((a, b) => sort.value === "name" ? a.name.localeCompare(b.name, "zh-CN") : String(b.updated_at).localeCompare(String(a.updated_at))));
async function load() { loading.value = true; error.value = ""; try { courses.value = (await getStudentCourses()).items || []; } catch (e) { error.value = e.response?.data?.detail || "课程加载失败，请重试。"; } finally { loading.value = false; } }
onMounted(load);
</script>
<template>
  <main class="student-page page-enter"><div class="student-heading"><div><span class="eyebrow">COURSES / 我的学习空间</span><h1>我的课程</h1><p>查看课程资料、作业、班级通知、成绩与任课教师信息。</p></div><button class="secondary-button" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button></div>
    <section class="student-toolbar surface"><div class="search-field"><UiIcon name="PhMagnifyingGlass" /><input v-model="query" placeholder="搜索课程名称、代码或教师" /></div><select v-model="sort"><option value="name">按课程名称</option><option value="updated">按最近更新</option></select><span class="toolbar-count">{{ filtered.length }} 门课程</span></section>
    <div v-if="loading" class="student-card-grid"><div v-for="i in 6" :key="i" class="student-skeleton"></div></div><div v-else-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div><div v-else-if="!filtered.length" class="student-empty large surface"><UiIcon name="PhBookOpen" :size="42" /><strong>还没有匹配的课程</strong><span>课程数据来自你的班级加入记录，暂时没有可展示内容。</span></div>
    <section v-else class="student-card-grid"><button v-for="course in filtered" :key="course.id" class="student-course-card surface" @click="router.push(`/courses/${course.id}`)"><div class="course-card-top"><span class="course-badge">{{ course.code || "课程" }}</span><UiIcon name="PhArrowUpRight" /></div><h2>{{ course.name }}</h2><p>{{ course.description || "进入课程查看班级通知、作业和课程资料。" }}</p><div class="course-card-meta"><span><UiIcon name="PhChalkboardTeacher" />{{ course.teacher_name || "任课教师" }}</span><span><UiIcon name="PhCalendarBlank" />{{ course.semester || "当前学期" }}</span></div></button></section>
  </main>
</template>
