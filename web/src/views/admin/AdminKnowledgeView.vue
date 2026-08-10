<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { deleteKnowledgeDocument, getKnowledgeStatus, listKnowledgeDocuments, rebuildKnowledgeIndex, uploadKnowledgeDocument } from "../../services/adminApi";

const status = ref(null);
const documents = ref([]);
const loading = ref(true);
const error = ref("");
const search = ref("");
const filterOfficial = ref("");
const filterExpired = ref("");

const uploadOpen = ref(false);
const uploadFile = ref(null);
const uploadMeta = ref({ title: "", source_department: "", source_type: "", version: "", effective_from: "", effective_to: "", is_official: false });
const uploading = ref(false);
const uploadError = ref("");
const uploadSuccess = ref("");

const rebuildLoading = ref(false);
const rebuildMessage = ref("");
const confirmDeleteId = ref("");

onMounted(load);

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

const filtered = computed(() => {
  let list = documents.value;
  if (search.value) {
    const q = search.value.toLowerCase();
    list = list.filter((d) => (d.title || "").toLowerCase().includes(q) || (d.source_department || "").toLowerCase().includes(q) || (d.original_filename || "").toLowerCase().includes(q));
  }
  if (filterOfficial.value === "yes") list = list.filter((d) => d.is_official);
  if (filterOfficial.value === "no") list = list.filter((d) => !d.is_official);
  if (filterExpired.value === "yes") list = list.filter((d) => d.is_expired);
  if (filterExpired.value === "no") list = list.filter((d) => !d.is_expired);
  return list;
});

function fmt(dt) { if (!dt) return "—"; try { return new Date(dt).toLocaleString("zh-CN"); } catch { return dt; } }

function onFileChange(e) { uploadFile.value = e.target.files?.[0] || null; }

async function submitUpload() {
  if (!uploadFile.value) { uploadError.value = "请选择文件"; return; }
  uploading.value = true;
  uploadError.value = "";
  uploadSuccess.value = "";
  try {
    await uploadKnowledgeDocument(uploadFile.value, uploadMeta.value);
    uploadSuccess.value = "上传成功";
    uploadOpen.value = false;
    uploadFile.value = null;
    uploadMeta.value = { title: "", source_department: "", source_type: "", version: "", effective_from: "", effective_to: "", is_official: false };
    await load();
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || e.message || "上传失败";
  } finally {
    uploading.value = false;
  }
}

async function confirmDelete(doc) {
  if (!confirm(`确认删除文档「${doc.title || doc.document_id}」?删除后索引将自动重建。`)) return;
  try {
    await deleteKnowledgeDocument(doc.document_id);
    await load();
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "删除失败";
  }
}

async function rebuild() {
  if (!confirm("确认重建全部知识库索引?")) return;
  rebuildLoading.value = true;
  rebuildMessage.value = "";
  try {
    const res = await rebuildKnowledgeIndex();
    rebuildMessage.value = `索引已重建: ${res.chunk_count} 个分块, ${res.document_count} 份文档`;
    await load();
  } catch (e) {
    rebuildMessage.value = e?.response?.data?.detail || e.message || "重建失败";
  } finally {
    rebuildLoading.value = false;
  }
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div><h2>知识库管理</h2><p>上传、维护校园知识文档,支持 MD / TXT / PDF / DOCX</p></div>
      <div class="header-actions">
        <button class="btn-secondary" :disabled="rebuildLoading" @click="rebuild"><UiIcon name="PhArrowsClockwise" :size="16" />{{ rebuildLoading ? "重建中…" : "重建索引" }}</button>
        <button class="btn-primary" @click="uploadOpen = true"><UiIcon name="PhUpload" :size="16" />上传文档</button>
      </div>
    </header>

    <div v-if="rebuildMessage" class="banner">{{ rebuildMessage }}</div>
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error-box">{{ error }}</div>

    <section v-if="!loading && !error" class="summary-bar">
      <span>文档总数 <b>{{ status?.document_count ?? 0 }}</b></span>
      <span>有效 <b>{{ filtered.filter((d) => !d.is_expired).length }}</b></span>
      <span>过期 <b>{{ documents.filter((d) => d.is_expired).length }}</b></span>
      <span>官方 <b>{{ documents.filter((d) => d.is_official).length }}</b></span>
      <span>演示 <b>{{ documents.filter((d) => d.is_demo).length }}</b></span>
    </section>

    <section v-if="!loading && !error" class="filter-bar">
      <input v-model="search" placeholder="搜索标题 / 来源 / 文件名" />
      <select v-model="filterOfficial"><option value="">全部来源</option><option value="yes">官方</option><option value="no">非官方</option></select>
      <select v-model="filterExpired"><option value="">全部有效期</option><option value="no">有效</option><option value="yes">已过期</option></select>
      <button class="btn-ghost" @click="load"><UiIcon name="PhArrowClockwise" :size="14" />刷新</button>
    </section>

    <section v-if="!loading && !error" class="doc-table-wrap">
      <table class="doc-table">
        <thead><tr><th>标题</th><th>来源</th><th>版本</th><th>有效期</th><th>状态</th><th>更新时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="d in filtered" :key="d.document_id">
            <td class="title-cell">
              <div class="title-main">{{ d.title || "(未命名)" }}</div>
              <div class="title-sub">{{ d.original_filename }} · {{ d.file_ext || "?" }} · {{ Math.round((d.file_size || 0) / 1024) }}KB</div>
            </td>
            <td>{{ d.source_department || "—" }}<span v-if="d.source_type" class="sub"> / {{ d.source_type }}</span></td>
            <td>{{ d.version || "—" }}</td>
            <td>
              <div>{{ fmt(d.effective_from) }}</div>
              <div class="sub">至 {{ fmt(d.effective_to) }}</div>
            </td>
            <td>
              <span class="tag" :class="{ official: d.is_official }">{{ d.is_official ? "官方" : "普通" }}</span>
              <span class="tag" :class="{ expired: d.is_expired }">{{ d.is_expired ? "已过期" : "有效" }}</span>
              <span v-if="d.is_demo" class="tag demo">演示</span>
            </td>
            <td>{{ fmt(d.updated_at || d.imported_at) }}</td>
            <td>
              <button class="btn-danger-sm" @click="confirmDelete(d)">删除</button>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="empty">没有匹配的文档</td></tr>
        </tbody>
      </table>
    </section>

    <div v-if="uploadOpen" class="modal-mask" @click.self="uploadOpen = false">
      <div class="modal">
        <header><h3>上传知识文档</h3><button @click="uploadOpen = false"><UiIcon name="PhX" :size="18" /></button></header>
        <div class="modal-body">
          <label class="field"><span>文件 (MD/TXT/PDF/DOCX)</span><input type="file" @change="onFileChange" accept=".md,.txt,.pdf,.docx" /></label>
          <label class="field"><span>标题</span><input v-model="uploadMeta.title" placeholder="留空则使用文件名" /></label>
          <div class="field-row">
            <label class="field"><span>来源部门</span><input v-model="uploadMeta.source_department" /></label>
            <label class="field"><span>来源类型</span><input v-model="uploadMeta.source_type" /></label>
          </div>
          <div class="field-row">
            <label class="field"><span>版本</span><input v-model="uploadMeta.version" placeholder="如 2024-v1" /></label>
            <label class="field"><span>是否官方</span><select v-model="uploadMeta.is_official"><option :value="false">否</option><option :value="true">是</option></select></label>
          </div>
          <div class="field-row">
            <label class="field"><span>生效起</span><input type="datetime-local" v-model="uploadMeta.effective_from" /></label>
            <label class="field"><span>生效止</span><input type="datetime-local" v-model="uploadMeta.effective_to" /></label>
          </div>
          <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
          <div v-if="uploadSuccess" class="upload-success">{{ uploadSuccess }}</div>
        </div>
        <footer>
          <button class="btn-ghost" @click="uploadOpen = false">取消</button>
          <button class="btn-primary" :disabled="uploading" @click="submitUpload">{{ uploading ? "上传中…" : "确认上传" }}</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 20px; }
.page-header p { margin: 0; color: #6b7280; font-size: 13px; }
.header-actions { display: flex; gap: 8px; }
.btn-primary, .btn-secondary, .btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.btn-ghost { background: transparent; color: #6b7280; border: 1px solid #e5e7eb; }
.banner { background: #ecfdf5; color: #059669; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
.loading, .error-box { padding: 32px; text-align: center; color: #6b7280; }
.error-box { color: #dc2626; background: #fef2f2; border-radius: 8px; }
.summary-bar { background: #fff; border-radius: 10px; padding: 12px 16px; display: flex; gap: 24px; font-size: 13px; color: #6b7280; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.summary-bar b { color: #111827; font-size: 15px; margin-left: 4px; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.filter-bar input, .filter-bar select { padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; background: #fff; }
.filter-bar input { flex: 1; }
.doc-table-wrap { background: #fff; border-radius: 10px; overflow: auto; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.doc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.doc-table th { background: #f9fafb; text-align: left; padding: 10px 12px; color: #6b7280; font-weight: 600; border-bottom: 1px solid #e5e7eb; }
.doc-table td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.title-cell .title-main { font-weight: 600; color: #111827; }
.title-cell .title-sub { font-size: 11px; color: #9ca3af; }
.sub { color: #9ca3af; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; background: #f3f4f6; color: #6b7280; margin-right: 4px; }
.tag.official { background: #dbeafe; color: #1d4ed8; }
.tag.expired { background: #fee2e2; color: #dc2626; }
.tag.demo { background: #fef3c7; color: #d97706; }
.btn-danger-sm { background: #fef2f2; color: #dc2626; border: none; padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.btn-danger-sm:hover { background: #fee2e2; }
.empty { text-align: center; color: #9ca3af; padding: 32px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; width: 520px; max-width: 92vw; max-height: 88vh; overflow: auto; }
.modal header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e7eb; }
.modal header h3 { margin: 0; font-size: 16px; }
.modal header button { background: none; border: none; cursor: pointer; color: #6b7280; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.field span { color: #6b7280; }
.field input, .field select { padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 6px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.upload-error { color: #dc2626; font-size: 13px; }
.upload-success { color: #059669; font-size: 13px; }
.modal footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid #e5e7eb; }
</style>