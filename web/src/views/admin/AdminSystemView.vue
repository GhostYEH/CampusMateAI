<script setup>
import { onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import client from "../../services/api";
import { getKnowledgeStatus } from "../../services/adminApi";

const health = ref(null);
const knowledge = ref(null);
const loading = ref(true);
const error = ref("");


async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [h, k] = await Promise.all([
      client.get("/health").then((r) => r.data).catch((e) => ({ error: e?.message || "健康检查失败" })),
      getKnowledgeStatus().catch((e) => ({ error: e?.response?.data?.detail || e.message || "知识库状态失败" })),
    ]);
    health.value = h;
    knowledge.value = k;
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}


function fmt(dt) { if (!dt) return "—"; try { return new Date(dt).toLocaleString("zh-CN"); } catch { return dt; } }

onMounted(load);
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div><h2>系统状态</h2><p>查看后端、AI、RAG 与数据库实时状态</p></div>
      <div class="header-actions">

        <button class="btn-ghost" @click="load"><UiIcon name="PhArrowClockwise" :size="14" />刷新</button>
      </div>
    </header>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error-box">{{ error }}</div>

    <section v-if="!loading && !error" class="status-grid">
      <article class="status-card" :class="{ ok: !health?.error, err: !!health?.error }">
        <header><span class="status-icon"><UiIcon name="PhServer" :size="20" /></span><h3>Backend 服务</h3></header>
        <dl>
          <dt>状态</dt><dd>{{ health?.error ? "异常" : (health?.status || "—") }}</dd>
          <dt>环境</dt><dd>{{ health?.env || "—" }}</dd>
          <dt>版本</dt><dd>{{ health?.version || "—" }}</dd>
          <dt>模式</dt><dd>{{ health?.mode || "—" }}</dd>
          <template v-if="health?.error"><dt>错误</dt><dd class="err-text">{{ health.error }}</dd></template>
        </dl>
      </article>

      <article class="status-card" :class="{ ok: health?.llm_available, err: health && !health?.llm_available }">
        <header><span class="status-icon"><UiIcon name="PhRobot" :size="20" /></span><h3>AI Provider</h3></header>
        <dl>
          <dt>Provider</dt><dd>{{ health?.llm_provider || "—" }}</dd>
          <dt>可用</dt><dd>{{ health?.llm_available ? "是" : "否" }}</dd>
          <dt>降级模式</dt><dd>{{ health?.fallback_enabled ? "启用" : "禁用" }}</dd>

        </dl>
      </article>

      <article class="status-card" :class="{ ok: knowledge?.is_available, err: knowledge && !knowledge?.is_available }">
        <header><span class="status-icon"><UiIcon name="PhDatabase" :size="20" /></span><h3>RAG / 知识库</h3></header>
        <dl>
          <dt>索引状态</dt><dd>{{ knowledge?.index_status || "—" }}</dd>
          <dt>检索方法</dt><dd>{{ knowledge?.retrieval_method || "—" }}</dd>
          <dt>文档数</dt><dd>{{ knowledge?.document_count ?? 0 }}</dd>
          <dt>分块数</dt><dd>{{ knowledge?.chunk_count ?? 0 }}</dd>
          <dt>最近更新</dt><dd>{{ fmt(knowledge?.last_updated) }}</dd>
        </dl>
      </article>

      <article class="status-card ok">
        <header><span class="status-icon"><UiIcon name="PhHardDrives" :size="20" /></span><h3>Database</h3></header>
        <dl>
          <dt>知识库初始化</dt><dd>{{ health?.knowledge_base_initialized ? "是" : "否" }}</dd>
          <dt>文档记录</dt><dd>{{ health?.document_count ?? 0 }}</dd>
          <dt>分块记录</dt><dd>{{ health?.chunk_count ?? 0 }}</dd>
          <dt>存储路径</dt><dd class="path">{{ knowledge?.knowledge_base_path || "—" }}</dd>
        </dl>
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
.btn-secondary, .btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-secondary:disabled { opacity: .6; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #6b7280; border: 1px solid #e5e7eb; }
.loading, .error-box { padding: 32px; text-align: center; color: #6b7280; }
.error-box { color: #dc2626; background: #fef2f2; border-radius: 8px; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.status-card { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.06); border-left: 4px solid #9ca3af; }
.status-card.ok { border-left-color: #059669; }
.status-card.err { border-left-color: #dc2626; }
.status-card header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.status-icon { width: 36px; height: 36px; border-radius: 8px; background: #f3f4f6; color: #374151; display: flex; align-items: center; justify-content: center; }
.status-card h3 { margin: 0; font-size: 15px; }
.status-card dl { display: grid; grid-template-columns: auto 1fr; gap: 8px 14px; font-size: 13px; }
.status-card dt { color: #6b7280; }
.status-card dd { margin: 0; color: #111827; }
.status-card dd.ok { color: #059669; }
.status-card dd.err { color: #dc2626; }
.status-card dd.warn { color: #d97706; }
.status-card dd.err-text { color: #dc2626; word-break: break-all; }
.status-card dd.path { font-family: monospace; font-size: 11px; word-break: break-all; }
</style>