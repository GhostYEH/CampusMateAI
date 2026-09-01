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
const statusTone = computed(() => statusIndex.value === 2 ? "green" : statusIndex.value === 1 ? "amber" : "blue");
function dateText(value) { if (!value) return "时间待补充"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN"); }
async function load() { loading.value = true; error.value = ""; try { item.value = await getServiceRequest(route.params.requestId); } catch (e) { error.value = e.response?.data?.detail || "申请详情加载失败。"; } finally { loading.value = false; } }
onMounted(load);
</script>

<template>
  <main class="student-page services-detail-redesign">
    <button class="cd-back-link" @click="router.push('/services')"><UiIcon name="PhArrowLeft" />返回办事大厅</button>

    <div v-if="loading" class="cd-loading">
      <div class="cd-loading-hero"></div>
      <div class="cd-loading-grid"><span></span><span></span></div>
    </div>

    <div v-else-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <template v-else-if="item">
      <!-- Hero -->
      <section class="td-hero tone-blue">
        <div class="td-hero-main">
          <div class="td-hero-head">
            <span class="td-kind blue">{{ kindLabel }}</span>
            <span class="td-state" :class="statusTone">{{ statusLabel }}</span>
          </div>
          <h1 class="td-title">{{ item.title }}<UiIcon name="PhSparkle" class="td-sparkle" :size="26" /></h1>
          <p class="td-context">申请编号 {{ item.id }}</p>
          <p class="td-desc">{{ item.content || '未补充说明。' }}</p>
        </div>

        <div class="td-focus" :class="statusTone">
          <div class="td-focus-head"><span class="td-focus-icon" :class="statusTone"><UiIcon :name="statusSteps[statusIndex].icon" :size="17" /></span>当前状态</div>
          <div class="td-focus-date">{{ statusLabel }}</div>
          <div class="td-focus-state" :class="statusTone">{{ statusSteps[statusIndex].desc }}</div>
          <div class="td-focus-divider"></div>
          <div class="td-focus-meta">
            <span><small>提交时间</small><strong>{{ dateText(item.created_at) }}</strong></span>
            <span><small>更新时间</small><strong>{{ dateText(item.updated_at) }}</strong></span>
          </div>
        </div>
      </section>

      <!-- Stats -->
      <section class="td-stats">
        <div class="td-stat"><span class="td-stat-icon indigo"><UiIcon name="PhClipboardText" :size="17" /></span><span><small>事项类型</small><strong>{{ kindLabel }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon" :class="statusTone"><UiIcon :name="statusSteps[statusIndex].icon" :size="17" /></span><span><small>当前状态</small><strong>{{ statusLabel }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon blue"><UiIcon name="PhClock" :size="17" /></span><span><small>提交时间</small><strong>{{ dateText(item.created_at) }}</strong></span></div>
        <div class="td-stat"><span class="td-stat-icon green"><UiIcon name="PhClockCounterClockwise" :size="17" /></span><span><small>更新时间</small><strong>{{ dateText(item.updated_at) }}</strong></span></div>
      </section>

      <!-- Two column -->
      <section class="td-layout">
        <div class="td-main">
          <section class="cd-panel">
            <div class="cd-panel-head">
              <div><span class="cd-eyebrow">REQUEST STATUS</span><h2>处理进度</h2></div>
              <button class="cd-enter-btn" @click="load"><UiIcon name="PhArrowClockwise" :size="14" />刷新状态</button>
            </div>
            <div class="sd-timeline">
              <div v-for="(step, index) in statusSteps" :key="step.key" class="sd-timeline-step" :class="{active: index <= statusIndex, current: index === statusIndex}">
                <span class="sd-timeline-node"><UiIcon :name="step.icon" :size="16" /></span>
                <span class="sd-timeline-main">
                  <strong>{{ step.label }}</strong>
                  <small>{{ index === 0 ? dateText(item.created_at) : index === statusIndex ? '当前状态由服务端返回' : step.desc }}</small>
                </span>
                <span v-if="index <= statusIndex" class="sd-timeline-check"><UiIcon name="PhCheck" :size="12" /></span>
              </div>
            </div>
            <div class="td-block">
              <div class="td-block-head"><UiIcon name="PhNotePencil" :size="15" />事项说明</div>
              <p class="td-description">{{ item.content || '未补充说明。' }}</p>
            </div>
          </section>
        </div>

        <aside class="td-side">
          <section class="cd-panel">
            <div class="cd-panel-head"><div><span class="cd-eyebrow">REQUEST INFO</span><h2>申请信息</h2></div></div>
            <dl class="sd-facts">
              <div><dt>事项类型</dt><dd>{{ kindLabel }}</dd></div>
              <div><dt>当前状态</dt><dd>{{ statusLabel }}</dd></div>
              <div><dt>创建时间</dt><dd>{{ dateText(item.created_at) }}</dd></div>
              <div><dt>更新时间</dt><dd>{{ dateText(item.updated_at) }}</dd></div>
            </dl>
          </section>

          <section class="cd-panel cd-tips-panel">
            <h2>下一步</h2>
            <div class="cd-tip-card"><span class="cd-tip-bulb"><UiIcon name="PhLightbulb" :size="15" /></span><p>{{ statusIndex === 2 ? '事项已经办结，你可以返回申请列表继续查看其他记录。' : '如果事项紧急，请按学校正式渠道联系对应部门。' }}</p></div>
            <button class="cd-plan-link" @click="router.push('/services')">返回申请列表<UiIcon name="PhArrowRight" :size="14" /></button>
          </section>
        </aside>
      </section>
    </template>
  </main>
</template>
