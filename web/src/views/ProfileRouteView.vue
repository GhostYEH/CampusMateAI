<script setup>
import { computed } from "vue";
import { useAppStore } from "../stores/app";
import AdminProfileView from "./admin/AdminProfileView.vue";
import StudentProfileView from "./student/StudentProfileView.vue";
const role = computed(() => useAppStore().session?.role);
</script>
<template><StudentProfileView v-if="role === 'student'" /><AdminProfileView v-else /></template>
