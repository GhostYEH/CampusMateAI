<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { createServiceRequest, getServiceRequests } from "../../services/studentApi";

const router = useRouter();
const loading = ref(true); const error = ref(""); const requests = ref([]); const show = ref(false); const saving = ref(false);
const query = ref(""); const filter = ref("all");
const form = ref({ kind: "repair", title: "", content: "" });
const heroImage = "/assets/campusmate-services-hero.png";
const services = [
  { kind: "repair", label: "宿舍报修", icon: "PhWrench", tone: "blue", desc: "提交设施、门锁、水电等宿舍问题", hint: "地点 · 故障描述" },
  { kind: "leave", label: "请假申请", icon: "PhCalendarBlank", tone: "warm", desc: "记录请假事由和时间范围", hint: "时间 · 事由" },
  { kind: "feedback", label: "意见反馈", icon: "PhChatCircleText", tone: "green", desc: "向学校提交建议或校园体验反馈", hint: "主题 · 具体内容" },
];
const serviceStats = computed(() => ({ total: requests.value.length, active: requests.value.filter((item) => !["completed", "closed"].includes(item.status)).length, done: requests.value.filter((item) => ["completed", "closed"].includes(item.status)).length }));
const filteredRequests = computed(() => requests.value.filter((item) => (filter.value === "all" || (filter.value === "active" ? !["completed", "closed"].includes(item.status) : ["completed", "closed"].includes(item.status))) && `${item.title} ${item.kind}`.toLowerCase().includes(query.value.trim().toLowerCase())));
const kindLabel = (kind) => services.find((item) => item.kind === kind)?.label || kind || "办事申请";
const kindIcon = (kind) => services.find((item) => item.kind === kind)?.icon || "PhClipboardText";
const statusLabel = (status) => ({ submitted: "已提交", processing: "处理中", completed: "已办结", closed: "已关闭" }[status] || status || "待更新");
const statusTone = (status) => ["completed", "closed"].includes(status) ? "green" : status === "processing" ? "warm" : "blue";
function openForm(kind = "repair") { form.value.kind = kind; show.value = true; }
async function load() { loading.value = true; error.value = ""; try { requests.value = await getServiceRequests(); } catch (e) { error.value = e.response?.data?.detail || "申请记录加载失败。"; } finally { loading.value = false; } }
async function submit() { if (!form.value.title.trim() || saving.value) return; saving.value = true; error.value = ""; try { await createServiceRequest(form.value); show.value = false; form.value = { kind: "repair", title: "", content: "" }; await load(); } catch (e) { error.value = e.response?.data?.detail || "提交申请失败。"; } finally { saving.value = false; } }
onMounted(load);
</script>

<template>
  <main class="student-page services-redesign page-enter">
    <!-- Hero Section -->
    <section class="sv-hero">
      <div class="sv-hero-content">
        <span class="hero-eyebrow">CAMPUS SERVICE / 校园事务</span>
        <div class="student-title-line hero-title">
          <h1>办事大厅</h1>
          <UiIcon name="PhSparkle" class="heading-sparkle" :size="26" />
        </div>
        <p class="hero-desc">把需要学校处理的事情写清楚、交出去，再从申请记录里跟进处理状态。</p>

        <div class="hero-stats cols-3">
          <div class="hero-stat">
            <span class="stat-icon indigo"><UiIcon name="PhClipboardText" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ serviceStats.total }}</strong>
              <small>我的申请</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon amber"><UiIcon name="PhHourglass" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ serviceStats.active }}</strong>
              <small>处理中</small>
            </div>
          </div>
          <div class="hero-stat">
            <span class="stat-icon green"><UiIcon name="PhSealCheck" :size="18" /></span>
            <div class="stat-info">
              <strong>{{ serviceStats.done }}</strong>
              <small>已办结</small>
            </div>
          </div>
        </div>
      </div>

      <div class="sv-hero-art">
        <div class="hero-illustration">
          <img :src="heroImage" alt="办事大厅插图" class="hero-illust-img" />
        </div>
      </div>
    </section>

    <div v-if="error" class="student-alert error">
      <UiIcon name="PhWarningCircle" />{{ error }}
      <button class="link-button" @click="load">重试</button>
    </div>

    <!-- Toolbar -->
    <section class="student-toolbar sv-toolbar surface">
      <div class="search-field">
        <UiIcon name="PhMagnifyingGlass" />
        <input v-model="query" name="request-query" placeholder="搜索申请标题或类型" />
      </div>
      <div class="segmented">
        <button v-for="item in [{key:'all',label:'全部'},{key:'active',label:'处理中'},{key:'done',label:'已办结'}]" :key="item.key" :class="{active:filter===item.key}" @click="filter=item.key">{{ item.label }}</button>
      </div>
      <span class="toolbar-count"><UiIcon name="PhListChecks" :size="14" /> {{ filteredRequests.length }} 条记录</span>
      <div class="toolbar-actions">
        <button class="refresh-btn" :disabled="loading" @click="load">
          <UiIcon name="PhArrowClockwise" :size="16" />刷新
        </button>
        <button class="new-task-btn" @click="openForm()">
          <UiIcon name="PhPlus" :size="16" />新建申请
        </button>
      </div>
    </section>

    <!-- Service Entry Cards -->
    <section class="sv-entry-grid">
      <button v-for="service in services" :key="service.kind" class="sv-entry-card surface" :class="`sv-tone-${service.tone}`" @click="openForm(service.kind)">
        <span class="sv-entry-icon" :class="service.tone"><UiIcon :name="service.icon" :size="24" /></span>
        <span class="sv-entry-main">
          <strong>{{ service.label }}</strong>
          <small>{{ service.desc }}</small>
          <em>{{ service.hint }}</em>
        </span>
        <UiIcon name="PhArrowUpRight" :size="16" class="sv-entry-arrow" />
      </button>
    </section>

    <!-- Workspace: Request Board + Side Guide -->
    <section class="sv-workspace">
      <section class="student-panel surface sv-board">
        <div class="student-panel-head">
          <div>
            <span class="eyebrow">MY REQUESTS</span>
            <h2>申请进度</h2>
          </div>
          <span class="toolbar-count">{{ requests.length }} 条记录</span>
        </div>
        <div v-if="loading" class="list-skeleton-stack">
          <div v-for="i in 4" :key="i" class="list-skeleton"></div>
        </div>
        <div v-else-if="filteredRequests.length" class="sv-board-list">
          <button v-for="request in filteredRequests" :key="request.id" class="sv-request-row" @click="router.push(`/services/${request.id}`)">
            <span class="sv-request-icon" :class="statusTone(request.status)"><UiIcon :name="kindIcon(request.kind)" :size="17" /></span>
            <span class="sv-request-main">
              <span><strong>{{ request.title }}</strong><small>{{ kindLabel(request.kind) }} · {{ request.created_at }}</small></span>
            </span>
            <span class="status-pill" :class="statusTone(request.status)">{{ statusLabel(request.status) }}</span>
            <UiIcon name="PhCaretRight" :size="15" class="sv-request-arrow" />
          </button>
        </div>
        <div v-else class="student-empty">
          <UiIcon name="PhClipboardText" :size="40" />
          <strong>{{ query ? '没有匹配的申请' : '还没有申请记录' }}</strong>
          <span>{{ query ? '换个关键词或筛选条件再试试。' : '从上面的服务入口开始，提交第一条需要学校处理的事项。' }}</span>
          <button v-if="!query" class="secondary-button" @click="openForm()"><UiIcon name="PhPlus" />新建申请</button>
        </div>
      </section>

      <aside class="sv-side-stack">
        <section class="student-panel surface sv-guide-card">
          <div class="sv-guide-mark"><UiIcon name="PhListChecks" :size="20" /></div>
          <span class="eyebrow">HOW IT WORKS</span>
          <h2>一条申请的处理路径</h2>
          <div class="sv-step-list">
            <div><b>1</b><span><strong>提交信息</strong><small>写明事项、地点和具体诉求</small></span></div>
            <div><b>2</b><span><strong>等待受理</strong><small>处理状态由服务端返回</small></span></div>
            <div><b>3</b><span><strong>查看进度</strong><small>打开详情页回看申请内容</small></span></div>
          </div>
        </section>
        <section class="student-panel surface sv-tip-card">
          <span class="eyebrow">KEEP IT CLEAR</span>
          <h3>提交前检查</h3>
          <p>标题尽量具体，正文补充时间、地点和联系方式，方便对应部门定位问题。</p>
        </section>
      </aside>
    </section>

    <!-- New Request Modal -->
    <div v-if="show" class="student-modal-backdrop" @click.self="show=false">
      <form class="student-modal tool-modal" @submit.prevent="submit">
        <div class="student-modal-head">
          <div>
            <span class="eyebrow">CAMPUS REQUEST</span>
            <h2>新建办事申请</h2>
            <p>提交后可以在申请进度里查看服务端返回的状态。</p>
          </div>
          <button type="button" class="icon-button" aria-label="关闭" @click="show=false"><UiIcon name="PhX" /></button>
        </div>
        <label class="student-field">事项类型<select v-model="form.kind" name="request-kind"><option value="repair">宿舍报修</option><option value="leave">请假申请</option><option value="feedback">意见反馈</option></select></label>
        <label class="student-field">标题<input v-model="form.title" name="request-title" required placeholder="请用一句话说明事项" /></label>
        <label class="student-field">详细说明<textarea v-model="form.content" name="request-content" rows="6" placeholder="补充地点、时间和需要说明的情况"></textarea></label>
        <div class="student-modal-actions">
          <button type="button" class="secondary-button" @click="show=false">取消</button>
          <button class="primary-button" :disabled="saving || !form.title.trim()">{{ saving?'提交中…':'提交申请' }}</button>
        </div>
      </form>
    </div>
  </main>
</template>
