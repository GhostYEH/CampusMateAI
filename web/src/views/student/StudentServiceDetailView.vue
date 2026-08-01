<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getServiceRequest } from "../../services/studentApi";

const route = useRoute(); const router = useRouter(); const loading = ref(true); const error = ref(""); const item = ref(null);
const statusSteps = [
  { key: "submitted", label: "已提交", icon: "PhPaperPlaneTilt", desc: "申请已进入服务记录" },
  { key: "processing", label: "处理中", icon: "PhHourglass", desc: "等待对应部门更新进度" },
  { key: "completed", label: "已办结", icon: "PhCheckCircle", desc: "事项处理完成" },
];
const kindLabel = computed(() => ({ repair: "宿舍报修", leave: "请假申请", feedback: "意见反馈" }[item.value?.kind] || item.value?.kind || "办事申请"));
const statusIndex = computed(() => { const status = item.value?.status; if (status === "closed" || status === "completed") return 2; if (status === "processing") return 1; return 0; });
const statusLabel = computed(() => statusSteps[statusIndex.value]?.label || item.value?.status || "待更新");
function dateText(value) { if (!value) return "时间待补充"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN"); }
async function load() { loading.value = true; error.value = ""; try { item.value = await getServiceRequest(route.params.requestId); } catch (e) { error.value = e.response?.data?.detail || "申请详情加载失败。"; } finally { loading.value = false; } }
onMounted(load);
</script>

<template>
  <main class="student-page page-enter student-detail-page"><button class="back-link" @click="router.push('/services')"><UiIcon name="PhArrowLeft" />返回办事大厅</button><div v-if="loading" class="student-detail-loading"><div class="student-skeleton"></div><div class="student-skeleton"></div></div><div v-else-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div><template v-else-if="item"><section class="detail-hero-board surface"><div class="detail-hero-icon blue"><UiIcon name="PhClipboardText" :size="30" /></div><div><span class="eyebrow">REQUEST / {{ kindLabel }}</span><h1>{{ item.title }}</h1><p>申请编号 {{ item.id }} · 提交于 {{ dateText(item.created_at) }}</p></div><span class="status-pill" :class="statusIndex === 2 ? 'green' : statusIndex === 1 ? 'warm' : 'blue'">{{ statusLabel }}</span></section><section class="detail-two-column"><article class="student-panel surface request-detail-card"><div class="student-panel-head"><div><span class="eyebrow">REQUEST STATUS</span><h2>处理进度</h2></div><button class="secondary-button" @click="load"><UiIcon name="PhArrowClockwise" />刷新状态</button></div><div class="request-timeline"><div v-for="(step, index) in statusSteps" :key="step.key" class="request-timeline-step" :class="{active:index <= statusIndex,current:index === statusIndex}"><span class="timeline-node"><UiIcon :name="step.icon" /></span><span><strong>{{ step.label }}</strong><small>{{ index === 0 ? dateText(item.created_at) : index === statusIndex ? '当前状态由服务端返回' : step.desc }}</small></span></div></div><div class="request-content-block"><span class="eyebrow">DESCRIPTION</span><h3>事项说明</h3><p class="rich-text">{{ item.content || '未补充说明。' }}</p></div></article><aside class="tool-side-stack"><section class="student-panel surface request-fact-card"><span class="eyebrow">REQUEST INFO</span><dl class="detail-facts"><div><dt>事项类型</dt><dd>{{ kindLabel }}</dd></div><div><dt>当前状态</dt><dd>{{ statusLabel }}</dd></div><div><dt>创建时间</dt><dd>{{ dateText(item.created_at) }}</dd></div><div><dt>更新时间</dt><dd>{{ dateText(item.updated_at) }}</dd></div></dl></section><section class="student-panel surface tool-source-card"><span class="eyebrow">NEXT STEP</span><h3>{{ statusIndex === 2 ? '事项已经办结' : '等待服务端更新' }}</h3><p>{{ statusIndex === 2 ? '你可以返回申请列表继续查看其他记录。' : '如果事项紧急，请按学校正式渠道联系对应部门。' }}</p><button class="text-button" @click="router.push('/services')">返回申请列表<UiIcon name="PhArrowRight" /></button></section></aside></section></template></main>
</template>
