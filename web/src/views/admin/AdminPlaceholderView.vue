<script setup>
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
defineProps({ title: String, detail: String });
const router = useRouter();
</script>
<template><main class="portal-page admin-portal page-enter"><div class="portal-heading"><div><span class="portal-kicker">管理员模块</span><h1>{{ title }}</h1><p>{{ detail }}</p></div></div><section class="portal-panel admin-placeholder"><UiIcon name="PhInfo" :size="34" /><strong>该模块正在按阶段接入</strong><p>当前没有可用的假数据或无效操作入口。</p><button class="secondary-button" @click="router.push('/admin/dashboard')">返回管理概览</button></section></main></template>
