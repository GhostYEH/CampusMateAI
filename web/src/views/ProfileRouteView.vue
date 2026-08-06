<script setup>
import { computed } from "vue";
import { useAppStore } from "../stores/app";
import AdminProfileView from "./admin/AdminProfileView.vue";
import StudentProfileView from "./student/StudentProfileView.vue";
import TeacherProfileView from "./teacher/TeacherProfileView.vue";
const role = computed(() => useAppStore().session?.role);
</script>
<template>
  <StudentProfileView v-if="role === 'student'" />
  <TeacherProfileView v-else-if="role === 'teacher'" />
  <AdminProfileView v-else />
</template>
