<script setup>
import { onMounted, ref, computed } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import {
  getEduDiscoveryStats,
  listEduDiscoveryCandidates,
  reviewEduCandidate,
} from "../../services/adminApi";

const loading = ref(false);
const error = ref("");
const stats = ref(null);
const candidates = ref([]);
const filterStatus = ref("");
const filterProvider = ref("");
const filterHasUrl = ref("");
const page = ref(1);
const pageSize = ref(50);
const reviewBusy = ref("");

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "VERIFIED_OFFICIAL", label: "VERIFIED_OFFICIAL" },
  { value: "VERIFIED_LIVE", label: "VERIFIED_LIVE" },
  { value: "CANDIDATE", label: "CANDIDATE" },
  { value: "NOT_DISCOVERED", label: "NOT_DISCOVERED" },
  { value: "DEAD", label: "DEAD" },
  { value: "HISTORICAL", label: "HISTORICAL" },
  { value: "INTRANET_ONLY", label: "INTRANET_ONLY" },
];

const providerOptions = [
  { value: "", label: "全部厂商" },
  { value: "ZHENGFANG", label: "正方" },
  { value: "QIANGZHI", label: "强智" },
  { value: "QINGGUO", label: "青果" },
  { value: "URP", label: "URP" },
  { value: "NEW_URP", label: "NEW_URP" },
  { value: "SHUWEI", label: "树维" },
  { value: "CUSTOM", label: "CUSTOM" },
  { value: "UNKNOWN", label: "UNKNOWN" },
];

const statusColors = {
  VERIFIED_OFFICIAL: "green",
  VERIFIED_LIVE: "blue",
  CANDIDATE: "orange",
  NOT_DISCOVERED: "gray",
  DEAD: "red",
  HISTORICAL: "gray",
  INTRANET_ONLY: "purple",
};

function statusColor(s) {
  return statusColors[s] || "gray";
}

async function loadStats() {
  try {
    stats.value = await getEduDiscoveryStats();
  } catch (e) {
    error.value = e.response?.data?.message || "统计加载失败";
  }
}

async function loadCandidates() {
  loading.value = true;
  error.value = "";
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    };
    if (filterStatus.value) params.status = filterStatus.value;
    if (filterProvider.value) params.provider = filterProvider.value;
    if (filterHasUrl.value === "yes") params.has_url = true;
    if (filterHasUrl.value === "no") params.has_url = false;
    candidates.value = await listEduDiscoveryCandidates(params);
  } catch (e) {
    error.value = e.response?.data?.message || "候选列表加载失败";
  } finally {
    loading.value = false;
  }
}

async function doReview(schoolCode, action) {
  reviewBusy.value = `${schoolCode}:${action}`;
  try {
    await reviewEduCandidate(schoolCode, action);
    await loadCandidates();
    await loadStats();
  } catch (e) {
    error.value = e.response?.data?.message || "审核操作失败";
  } finally {
    reviewBusy.value = "";
  }
}

function applyFilter() {
  page.value = 1;
  loadCandidates();
}

onMounted(async () => {
  await Promise.all([loadStats(), loadCandidates()]);
});
</script>

<template>
  <main class="admin-page">
    <div class="admin-heading">
      <h1>教务系统发现</h1>
      <p>管理全国高校教务系统候选数据库：审核、标记、重新验证。</p>
    </div>

    <div v-if="error" class="admin-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>

    <section v-if="stats" class="admin-stats-grid">
      <div class="stat-card">
        <strong>{{ stats.universities_total }}</strong>
        <span>全国高校总数</span>
      </div>
      <div class="stat-card">
        <strong>{{ stats.candidates_total }}</strong>
        <span>候选总数</span>
      </div>
      <div class="stat-card green">
        <strong>{{ stats.verified_official }}</strong>
        <span>VERIFIED_OFFICIAL</span>
      </div>
      <div class="stat-card blue">
        <strong>{{ stats.verified_live }}</strong>
        <span>VERIFIED_LIVE</span>
      </div>
      <div class="stat-card orange">
        <strong>{{ stats.candidate }}</strong>
        <span>CANDIDATE</span>
      </div>
      <div class="stat-card gray">
        <strong>{{ stats.not_discovered }}</strong>
        <span>NOT_DISCOVERED</span>
      </div>
      <div class="stat-card red">
        <strong>{{ stats.dead }}</strong>
        <span>DEAD</span>
      </div>
      <div class="stat-card">
        <strong>{{ stats.wakeup_supported }}</strong>
        <span>WakeUp 已适配</span>
      </div>
    </section>

    <section class="admin-filters">
      <select v-model="filterStatus" @change="applyFilter">
        <option v-for="o in statusOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <select v-model="filterProvider" @change="applyFilter">
        <option v-for="o in providerOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <select v-model="filterHasUrl" @change="applyFilter">
        <option value="">全部</option>
        <option value="yes">有 URL</option>
        <option value="no">无 URL</option>
      </select>
      <button class="admin-btn" @click="loadCandidates"><UiIcon name="PhArrowClockwise" />刷新</button>
    </section>

    <section v-if="loading" class="admin-loading">加载中…</section>

    <section v-else class="admin-candidate-list">
      <table v-if="candidates.length" class="admin-table">
        <thead>
          <tr>
            <th>学校</th>
            <th>候选 URL</th>
            <th>厂商</th>
            <th>状态</th>
            <th>HTTP</th>
            <th>置信度</th>
            <th>来源</th>
            <th>WakeUp</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in candidates" :key="c.school_code + c.candidate_url">
            <td class="cell-school">
              <strong>{{ c.school_name }}</strong>
              <small>{{ c.school_code }}</small>
            </td>
            <td class="cell-url">
              <a v-if="c.candidate_url" :href="c.candidate_url" target="_blank" rel="noopener">{{ c.candidate_url }}</a>
              <span v-else class="muted">—</span>
            </td>
            <td>{{ c.provider }}</td>
            <td><span class="status-badge" :class="statusColor(c.verification_status)">{{ c.verification_status }}</span></td>
            <td>{{ c.http_status || "—" }}</td>
            <td>{{ (c.confidence * 100).toFixed(0) }}%</td>
            <td>{{ c.source_type }}</td>
            <td>{{ c.wakeup_supported ? "✓" : "—" }}</td>
            <td class="cell-actions">
              <button v-if="c.candidate_url" class="admin-btn small" :disabled="reviewBusy === `${c.school_code}:confirm`" @click="doReview(c.school_code, 'confirm')">确认</button>
              <button v-if="c.candidate_url" class="admin-btn small" :disabled="reviewBusy === `${c.school_code}:reject`" @click="doReview(c.school_code, 'reject')">拒绝</button>
              <button v-if="c.candidate_url" class="admin-btn small" :disabled="reviewBusy === `${c.school_code}:mark_historical`" @click="doReview(c.school_code, 'mark_historical')">历史</button>
              <button v-if="c.candidate_url" class="admin-btn small" :disabled="reviewBusy === `${c.school_code}:mark_intranet`" @click="doReview(c.school_code, 'mark_intranet')">校内网</button>
              <button v-if="c.candidate_url" class="admin-btn small" :disabled="reviewBusy === `${c.school_code}:reverify`" @click="doReview(c.school_code, 'reverify')">重验</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="admin-empty">无候选数据</p>
    </section>
  </main>
</template>

<style scoped>
.admin-page { padding: 24px; max-width: 1400px; margin: 0 auto; }
.admin-heading h1 { font-size: 24px; margin: 0 0 4px; }
.admin-heading p { color: var(--text-secondary, #666); margin: 0 0 20px; }
.admin-alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.admin-alert.error { background: #fee; color: #c33; }
.admin-stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: var(--surface, #f5f5f5); border-radius: 8px; padding: 16px; text-align: center; }
.stat-card strong { display: block; font-size: 28px; }
.stat-card span { color: var(--text-secondary, #666); font-size: 12px; }
.stat-card.green { background: #e6f9e6; }
.stat-card.blue { background: #e6f0ff; }
.stat-card.orange { background: #fff5e6; }
.stat-card.gray { background: #f0f0f0; }
.stat-card.red { background: #ffe6e6; }
.admin-filters { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.admin-filters select { padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border, #ddd); }
.admin-btn { padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border, #ddd); background: var(--surface, #fff); cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.admin-btn:hover { background: var(--surface-hover, #f0f0f0); }
.admin-btn.small { padding: 3px 8px; font-size: 12px; }
.admin-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th { text-align: left; padding: 8px; border-bottom: 2px solid var(--border, #ddd); background: var(--surface, #f5f5f5); }
.admin-table td { padding: 8px; border-bottom: 1px solid var(--border, #eee); vertical-align: top; }
.cell-school strong { display: block; }
.cell-school small { color: var(--text-secondary, #999); }
.cell-url a { color: var(--link, #0066cc); text-decoration: none; word-break: break-all; }
.cell-url a:hover { text-decoration: underline; }
.cell-actions { display: flex; gap: 4px; flex-wrap: wrap; }
.status-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-badge.green { background: #d4f4d4; color: #2a7a2a; }
.status-badge.blue { background: #d4e4f4; color: #2a5a8a; }
.status-badge.orange { background: #f4e4d4; color: #8a6a2a; }
.status-badge.gray { background: #e0e0e0; color: #666; }
.status-badge.red { background: #f4d4d4; color: #8a2a2a; }
.status-badge.purple { background: #e4d4f4; color: #6a2a8a; }
.muted { color: var(--text-secondary, #999); }
.admin-empty { text-align: center; padding: 40px; color: var(--text-secondary, #999); }
.admin-loading { text-align: center; padding: 40px; }
</style>