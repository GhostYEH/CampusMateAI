<script setup>
import { onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { getKnowledgeStatus, listKnowledgeDocuments, rebuildKnowledgeIndex } from "../../services/adminApi";

const status = ref(null);
const documents = ref([]);
const loading = ref(true);
const error = ref("");
const rebuildLoading = ref(false);
const rebuildMessage = ref("");
const rebuildError = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [s, docs] = await Promise.all([getKnowledgeStatus(), listKnowledgeDocuments()]);
    status.value = s;
    documents.value = docs || [];
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function rebuild() {
  if (!confirm("确认重建全部知识库索引?")) return;
  rebuildLoading.value = true;
  rebuildMessage.value = "";
  rebuildError.value = "";
  try {
    const res = await rebuildKnowledgeIndex();
    rebuildMessage.value = `索引已重建: ${res.chunk_count} 个分块, ${res.document_count} 份文档`;
    await load();
  } catch (e) {
    rebuildError.value = e?.response?.data?.detail || e.message || "重建失败";
  } finally {
    rebuildLoading.value = false;
  }
}

function fmt(dt) { if (!dt) return "—"; try { return new Date(dt).toLocaleString("zh-CN"); } catch { return dt; } }

onMounted(load);
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div><h2>RAG 索引</h2><p>查看检索增强生成索引状态与构建能力</p></div>
      <div class="header-actions">
        <button class="btn-secondary" :disabled="rebuildLoading" @click="rebuild"><UiIcon name="PhArrowsClockwise" :size="16" />{{ rebuildLoading ? "重建中…" : "重建索引" }}</button>
        <button class="btn-ghost" @click="load"><UiIcon name="PhArrowClockwise" :size="14" />刷新</button>
      </div>
    </header>

    <div v-if="rebuildMessage" class="banner success">{{ rebuildMessage }}</div>
    <div v-if="rebuildError" class="banner error">{{ rebuildError }}</div>
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error-box">{{ error }}</div>

    <section v-if="!loading && !error" class="stat-grid">
      <article class="stat-card">
        <div class="stat-icon blue"><UiIcon name="PhDatabase" :size="22" /></div>
        <div><div class="stat-value">{{ status?.document_count ?? 0 }}</div><div class="stat-label">文档数量</div></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon indigo"><UiIcon name="PhStack" :size="22" /></div>
        <div><div class="stat-value">{{ status?.chunk_count ?? 0 }}</div><div class="stat-label">索引分块</div></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon green"><UiIcon name="PhCheckCircle" :size="22" /></div>
        <div><div class="stat-value">{{ status?.index_status || "—" }}</div><div class="stat-label">索引状态</div></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon amber"><UiIcon name="PhClock" :size="22" /></div>
        <div><div class="stat-value">{{ fmt(status?.last_updated) }}</div><div class="stat-label">最近更新</div></div>
      </article>
    </section>

    <section v-if="!loading && !error" class="detail-grid">
      <article class="detail-card">
        <h3>检索配置</h3>
        <dl>
          <dt>检索方法</dt><dd>{{ status?.retrieval_method || "—" }}</dd>
          <dt>问答模式</dt><dd>{{ status?.qa_mode || "—" }}</dd>
          <dt>知识库类型</dt><dd>{{ status?.knowledge_base_type || "—" }}</dd>
          <dt>LLM 可用</dt><dd>{{ status?.llm_available ? "是" : "否" }}</dd>
          <dt>索引可用</dt><dd>{{ status?.is_available ? "是" : "否" }}</dd>
        </dl>
      </article>
      <article class="detail-card">
        <h3>文档分布</h3>
        <dl>
          <dt>演示文档</dt><dd>{{ status?.demo_document_count ?? 0 }}</dd>
          <dt>用户文档</dt><dd>{{ status?.user_document_count ?? 0 }}</dd>
          <dt>官方文档</dt><dd>{{ documents.filter((d) => d.is_official).length }}</dd>
          <dt>已过期</dt><dd>{{ documents.filter((d) => d.is_expired).length }}</dd>
          <dt>有效文档</dt><dd>{{ documents.filter((d) => !d.is_expired).length }}</dd>
        </dl>
      </article>
      <article class="detail-card">
        <h3>存储路径</h3>
        <p class="path">{{ status?.knowledge_base_path || "—" }}</p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.admin-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header p { margin: 0; color: #6b7280; font-size: 13px; }
.header-actions { display: flex; gap: 8px; }
.btn-primary, .btn-secondary, .btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-secondary:disabled { opacity: .6; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #6b7280; border: 1px solid #e5e7eb; }
.banner { padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.banner.success { background: #ecfdf5; color: #059669; }
.banner.error { background: #fef2f2; color: #dc2626; }
.loading, .error-box { padding: 32px; text-align: center; color: #6b7280; }
.error-box { color: #dc2626; background: #fef2f2; border-radius: 8px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; }
.stat-card { background: #fff; border-radius: 12px; padding: 18px; display: flex; align-items: center; gap: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; }
.stat-icon.blue { background: #2563eb; }
.stat-icon.indigo { background: #4f46e5; }
.stat-icon.green { background: #059669; }
.stat-icon.amber { background: #d97706; }
.stat-value { font-size: 22px; font-weight: 700; color: #111827; }
.stat-label { font-size: 12px; color: #6b7280; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
.detail-card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.detail-card h3 { margin: 0 0 12px; font-size: 15px; }
.detail-card dl { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; font-size: 13px; }
.detail-card dt { color: #6b7280; }
.detail-card dd { margin: 0; color: #111827; }
.detail-card .path { font-family: monospace; font-size: 12px; word-break: break-all; color: #374151; margin: 0; }
</style>