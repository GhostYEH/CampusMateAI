<script setup>
import { onMounted, ref, computed } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import {
  adminListCommunityPosts, adminHideCommunityPost,
  adminListCommunityReports, adminResolveCommunityReport,
  adminMigrateLostFound,
} from "../../services/studentApi";

const tab = ref("posts");
const loading = ref(false);
const error = ref("");
const notice = ref("");

const posts = ref([]);
const postsTotal = ref(0);
const postsPage = ref(1);
const postsQuery = ref("");
const postsStatus = ref("");
const hiding = ref("");

const reports = ref([]);
const reportsTotal = ref(0);
const reportsPage = ref(1);
const reportsStatus = ref("pending");
const resolving = ref("");

const CATEGORY_LABELS = {
  question: "提问", recruit: "招募", errand: "带价帮忙", lostfound: "失物招领",
  campus: "校园动态", study: "学习交流", life: "生活随笔", secondhand: "二手交易",
  activity: "活动", experience: "经验分享", other: "其它",
};
const STATUS_LABELS = { published: "已发布", hidden: "已隐藏", deleted: "已删除" };
const REPORT_STATUS_LABELS = { pending: "待处理", resolved: "已处理", rejected: "已驳回" };
const REPORT_STATUS_COLORS = { pending: "#f59e0b", resolved: "#10b981", rejected: "#ef4444" };

async function loadPosts() {
  loading.value = true; error.value = "";
  try {
    const data = await adminListCommunityPosts({
      q: postsQuery.value || undefined,
      status: postsStatus.value || undefined,
      page: postsPage.value, page_size: 20,
    });
    posts.value = data.items || []; postsTotal.value = data.total || 0;
  } catch (e) { error.value = e.response?.data?.message || "加载失败"; }
  finally { loading.value = false; }
}
async function loadReports() {
  loading.value = true; error.value = "";
  try {
    const data = await adminListCommunityReports({
      status: reportsStatus.value || undefined,
      page: reportsPage.value, page_size: 20,
    });
    reports.value = data.items || []; reportsTotal.value = data.total || 0;
  } catch (e) { error.value = e.response?.data?.message || "加载失败"; }
  finally { loading.value = false; }
}
async function hidePost(id) {
  hiding.value = id;
  try { await adminHideCommunityPost(id); notice.value = "帖子已隐藏"; await loadPosts(); }
  catch (e) { error.value = e.response?.data?.message || "操作失败"; }
  finally { hiding.value = ""; }
}
async function resolveReport(id, action) {
  resolving.value = id;
  try { await adminResolveCommunityReport(id, action); notice.value = action === "resolve" ? "举报已处理" : "举报已驳回"; await loadReports(); }
  catch (e) { error.value = e.response?.data?.message || "操作失败"; }
  finally { resolving.value = ""; }
}
async function migrateLostFound() {
  loading.value = true;
  try { const r = await adminMigrateLostFound(); notice.value = `已迁移 ${r.migrated} 条失物招领`; await loadPosts(); }
  catch (e) { error.value = e.response?.data?.message || "迁移失败"; }
  finally { loading.value = false; }
}
function switchTab(t) { tab.value = t; error.value = ""; notice.value = ""; if (t === "posts") loadPosts(); else loadReports(); }
function searchPosts() { postsPage.value = 1; loadPosts(); }
function fmtTime(t) { try { return new Date(t).toLocaleString("zh-CN"); } catch { return t; } }
const hasMorePosts = computed(() => posts.value.length < postsTotal.value);
const hasMoreReports = computed(() => reports.value.length < reportsTotal.value);
onMounted(() => loadPosts());
</script>

<template>
  <div class="admin-community">
    <header class="page-head">
      <div><h1>校园论坛管理</h1><p>审核帖子、处理举报、维护社区秩序</p></div>
      <nav class="tabs">
        <button :class="{ active: tab === 'posts' }" @click="switchTab('posts')"><UiIcon name="PhChatsCircle" :size="16" />帖子管理</button>
        <button :class="{ active: tab === 'reports' }" @click="switchTab('reports')"><UiIcon name="PhFlag" :size="16" />举报处理<span v-if="reportsStatus === 'pending'" class="tab-count">{{ reportsTotal }}</span></button>
      </nav>
    </header>
    <div v-if="error" class="alert error"><UiIcon name="PhWarningCircle" :size="18" />{{ error }}</div>
    <div v-if="notice" class="alert success"><UiIcon name="PhCheckCircle" :size="18" />{{ notice }}</div>

    <section v-if="tab === 'posts'" class="panel">
      <div class="toolbar">
        <form class="search" @submit.prevent="searchPosts"><UiIcon name="PhMagnifyingGlass" :size="16" /><input v-model="postsQuery" placeholder="搜索标题或内容" /></form>
        <select v-model="postsStatus" @change="searchPosts">
          <option value="">全部状态</option><option value="published">已发布</option><option value="hidden">已隐藏</option><option value="deleted">已删除</option>
        </select>
        <button class="btn secondary" @click="migrateLostFound"><UiIcon name="PhArrowPath" :size="15" />迁移失物招领</button>
      </div>
      <div v-if="loading" class="loading">加载中…</div>
      <table v-else-if="posts.length" class="data-table">
        <thead><tr><th>标题</th><th>作者</th><th>分类</th><th>状态</th><th>发布时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="p in posts" :key="p.id">
            <td class="title-cell">{{ p.title }}</td>
            <td>{{ p.author_name }}</td>
            <td>{{ CATEGORY_LABELS[p.category] || p.category }}</td>
            <td><span class="status-tag" :class="p.status">{{ STATUS_LABELS[p.status] || p.status }}</span></td>
            <td class="time-cell">{{ fmtTime(p.created_at) }}</td>
            <td><button v-if="p.status === 'published'" class="btn small danger" :disabled="hiding === p.id" @click="hidePost(p.id)"><UiIcon name="PhEyeSlash" :size="14" />隐藏</button><span v-else class="muted">—</span></td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty"><UiIcon name="PhChatsCircle" :size="32" /><p>暂无帖子</p></div>
      <div v-if="hasMorePosts" class="load-more"><button class="btn secondary" @click="postsPage++; loadPosts()">加载更多</button></div>
    </section>

    <section v-if="tab === 'reports'" class="panel">
      <div class="toolbar">
        <select v-model="reportsStatus" @change="reportsPage = 1; loadReports()">
          <option value="pending">待处理</option><option value="resolved">已处理</option><option value="rejected">已驳回</option><option value="">全部</option>
        </select>
      </div>
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="reports.length" class="report-list">
        <article v-for="r in reports" :key="r.id" class="report-card">
          <header>
            <span class="reason-tag">{{ r.reason }}</span>
            <span class="status-tag" :style="{ color: REPORT_STATUS_COLORS[r.status] }">{{ REPORT_STATUS_LABELS[r.status] || r.status }}</span>
          </header>
          <p class="report-target"><UiIcon name="PhArrowRight" :size="14" />目标 {{ r.target_type }}：{{ r.target_id }}</p>
          <p v-if="r.details" class="report-details">补充说明：{{ r.details }}</p>
          <footer>
            <span class="muted">举报人：{{ r.reporter_name }} · {{ fmtTime(r.created_at) }}</span>
            <div v-if="r.status === 'pending'" class="report-actions">
              <button class="btn small success" :disabled="resolving === r.id" @click="resolveReport(r.id, 'resolve')"><UiIcon name="PhCheck" :size="14" />处理</button>
              <button class="btn small danger" :disabled="resolving === r.id" @click="resolveReport(r.id, 'reject')"><UiIcon name="PhX" :size="14" />驳回</button>
            </div>
          </footer>
        </article>
      </div>
      <div v-else class="empty"><UiIcon name="PhFlag" :size="32" /><p>暂无举报记录</p></div>
      <div v-if="hasMoreReports" class="load-more"><button class="btn secondary" @click="reportsPage++; loadReports()">加载更多</button></div>
    </section>
  </div>
</template>

<style scoped>
.admin-community { padding: 24px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 16px; }
.page-head h1 { font-size: 22px; font-weight: 700; color: #111827; margin: 0; }
.page-head p { font-size: 13px; color: #6b7280; margin: 4px 0 0; }
.tabs { display: flex; gap: 6px; background: #fff; padding: 4px; border-radius: 10px; border: 1px solid #e5e7eb; }
.tabs button { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border: none; background: transparent; border-radius: 7px; font-size: 13px; font-weight: 600; color: #6b7280; cursor: pointer; }
.tabs button.active { background: #2563eb; color: #fff; }
.tab-count { background: #ef4444; color: #fff; font-size: 11px; padding: 1px 6px; border-radius: 999px; margin-left: 4px; }
.alert { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.alert.error { background: #fef2f2; color: #dc2626; }
.alert.success { background: #ecfdf5; color: #059669; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; }
.toolbar { display: flex; gap: 10px; padding: 14px 16px; border-bottom: 1px solid #f3f4f6; flex-wrap: wrap; align-items: center; }
.search { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 200px; padding: 0 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; }
.search input { flex: 1; border: none; background: transparent; padding: 8px 0; font-size: 13px; outline: none; }
.toolbar select { padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; background: #fff; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn.secondary { background: #f3f4f6; color: #374151; }
.btn.secondary:hover { background: #e5e7eb; }
.btn.small { padding: 5px 10px; font-size: 12px; }
.btn.danger { background: #fef2f2; color: #dc2626; }
.btn.danger:hover { background: #fee2e2; }
.btn.success { background: #ecfdf5; color: #059669; }
.btn.success:hover { background: #d1fae5; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.loading, .empty { padding: 48px; text-align: center; color: #9ca3af; font-size: 14px; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 10px 16px; font-size: 12px; font-weight: 600; color: #6b7280; background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
.data-table td { padding: 12px 16px; font-size: 13px; color: #374151; border-bottom: 1px solid #f3f4f6; }
.title-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.time-cell { color: #9ca3af; font-size: 12px; white-space: nowrap; }
.muted { color: #9ca3af; }
.status-tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.status-tag.published { background: #ecfdf5; color: #059669; }
.status-tag.hidden { background: #fef2f2; color: #dc2626; }
.status-tag.deleted { background: #f3f4f6; color: #6b7280; }
.load-more { padding: 14px; text-align: center; }
.report-list { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.report-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; }
.report-card header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.reason-tag { background: #fef3c7; color: #92400e; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.report-target, .report-details { font-size: 13px; color: #4b5563; margin: 4px 0; }
.report-card footer { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 12px; }
.report-actions { display: flex; gap: 8px; }
</style>