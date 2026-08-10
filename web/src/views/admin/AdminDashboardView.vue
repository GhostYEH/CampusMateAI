<script setup>
import { onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { getKnowledgeStatus, listKnowledgeDocuments } from "../../services/adminApi";

const status = ref(null);
const documents = ref([]);
const loading = ref(true);
const error = ref("");

onMounted(async () => {
  try {
    const [s, docs] = await Promise.all([getKnowledgeStatus(), listKnowledgeDocuments()]);
    status.value = s;
    documents.value = docs || [];
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "加载失败";
  } finally {
    loading.value = false;
  }
});

function fmt(dt) { if (!dt) return "—"; try { return new Date(dt).toLocaleString("zh-CN"); } catch { return dt; } }
</script>

<template>
  <div class="admin-page">
    <header class="page-header"><h2>控制台概览</h2><p>系统基础状态与知识库摘要</p></header>
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error-box">{{ error }}</div>
    <div v-else class="dashboard-grid">
      <section class="stat-card">
        <div class="stat-icon"><UiIcon name="PhBooks" :size="22" /></div>
        <div><div class="stat-value">{{ status?.document_count ?? 0 }}</div><div class="stat-label">知识库文档</div></div>
      </section>
      <section class="stat-card">
        <div class="stat-icon"><UiIcon name="PhCheckCircle" :size="22" /></div>
        <div><div class="stat-value">{{ status?.chunk_count ?? 0 }}</div><div class="stat-label">索引分块</div></div>
      </section>
      <section class="stat-card">
        <div class="stat-icon"><UiIcon name="PhRobot" :size="22" /></div>
        <div><div class="stat-value">{{ status?.qa_mode || "—" }}</div><div class="stat-label">问答模式</div></div>
      </section>
      <section class="stat-card">
        <div class="stat-icon"><UiIcon name="PhClock" :size="22" /></div>
        <div><div class="stat-value">{{ fmt(status?.last_updated) }}</div><div class="stat-label">最近更新</div></div>
      </section>
    </div>

    <section v-if="!loading && !error" class="knowledge-status">
      <h3>知识库状态</h3>
      <dl>
        <dt>索引状态</dt><dd>{{ status?.index_status || "—" }}</dd>
        <dt>检索方法</dt><dd>{{ status?.retrieval_method || "—" }}</dd>
        <dt>演示文档</dt><dd>{{ status?.demo_document_count ?? 0 }}</dd>
        <dt>用户文档</dt><dd>{{ status?.user_document_count ?? 0 }}</dd>
        <dt>LLM 可用</dt><dd>{{ status?.llm_available ? "是" : "否" }}</dd>
        <dt>知识库路径</dt><dd class="path">{{ status?.knowledge_base_path || "—" }}</dd>
      </dl>
    </section>
  </div>
</template>

<style scoped>
.admin-page { padding: 24px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header p { margin: 0 0 20px; color: #6b7280; font-size: 13px; }
.loading, .error-box { padding: 32px; text-align: center; color: #6b7280; }
.error-box { color: #dc2626; background: #fef2f2; border-radius: 8px; }
.dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card { background: #fff; border-radius: 12px; padding: 18px; display: flex; align-items: center; gap: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; background: #eff6ff; color: #2563eb; display: flex; align-items: center; justify-content: center; }
.stat-value { font-size: 22px; font-weight: 700; color: #111827; }
.stat-label { font-size: 12px; color: #6b7280; }
.knowledge-status { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.knowledge-status h3 { margin: 0 0 12px; font-size: 15px; }
.knowledge-status dl { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; font-size: 13px; }
.knowledge-status dt { color: #6b7280; }
.knowledge-status dd { margin: 0; color: #111827; }
.knowledge-status .path { font-family: monospace; font-size: 12px; word-break: break-all; }
</style>