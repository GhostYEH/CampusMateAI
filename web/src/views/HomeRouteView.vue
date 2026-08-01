<script setup>
import { computed } from "vue";
import { useAppStore } from "../stores/app";
import DashboardView from "./DashboardView.vue";
import StudentHomeView from "./student/StudentHomeView.vue";
const role = computed(() => useAppStore().session?.role);
</script>
<template><StudentHomeView v-if="role === 'student'" /><DashboardView v-else /></template>
