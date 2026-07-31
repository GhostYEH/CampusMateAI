import { defineStore } from "pinia";
import { ref } from "vue";
import * as coursesApi from "../services/teacher/courses";
import * as classesApi from "../services/teacher/classes";

export const useTeacherStore = defineStore("teacher", () => {
  const courses = ref([]);
  const classes = ref([]);
  const coursesLoadedAt = ref(0);
  const classesLoadedAt = ref(0);
  const loading = ref(false);
  const error = ref("");

  const CACHE_TTL = 60_000;

  async function loadCourses(force = false) {
    if (!force && Date.now() - coursesLoadedAt.value < CACHE_TTL && courses.value.length) {
      return courses.value;
    }
    loading.value = true;
    error.value = "";
    try {
      const page = await coursesApi.listCourses();
      courses.value = page.items || [];
      coursesLoadedAt.value = Date.now();
      return courses.value;
    } catch (err) {
      error.value = err.response?.data?.message || err.message || "课程加载失败";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function loadClasses(force = false) {
    if (!force && Date.now() - classesLoadedAt.value < CACHE_TTL && classes.value.length) {
      return classes.value;
    }
    loading.value = true;
    error.value = "";
    try {
      const page = await classesApi.listClasses();
      classes.value = page.items || [];
      classesLoadedAt.value = Date.now();
      return classes.value;
    } catch (err) {
      error.value = err.response?.data?.message || err.message || "班级加载失败";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function loadAll(force = false) {
    await Promise.all([loadCourses(force), loadClasses(force)]);
  }

  function classOptionsWithCourse() {
    return classes.value.map((cls) => ({
      ...cls,
      course: courses.value.find((c) => c.id === cls.course_id),
    }));
  }

  function classesOfCourse(courseId) {
    return classes.value.filter((cls) => cls.course_id === courseId);
  }

  function invalidate() {
    coursesLoadedAt.value = 0;
    classesLoadedAt.value = 0;
  }

  return {
    courses,
    classes,
    loading,
    error,
    loadCourses,
    loadClasses,
    loadAll,
    classOptionsWithCourse,
    classesOfCourse,
    invalidate,
  };
});