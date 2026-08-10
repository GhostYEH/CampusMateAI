<script setup>
import { onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { createUser, listUsers, updateUser } from "../../services/adminApi";

const users = ref([]);
const loading = ref(true);
const error = ref("");
const filterRole = ref("");

const createOpen = ref(false);
const createForm = ref({ username: "", password: "", role: "student", display_name: "", student_number: "", college: "", major: "", grade: "" });
const createError = ref("");
const creating = ref(false);

onMounted(load);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await listUsers(filterRole.value ? { role: filterRole.value } : {});
    users.value = data.items || [];
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function toggleActive(u) {
  try {
    await updateUser(u.id, { is_active: !u.is_active });
    await load();
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || "操作失败";
  }
}

async function submitCreate() {
  creating.value = true;
  createError.value = "";
  try {
    await createUser(createForm.value);
    createOpen.value = false;
    createForm.value = { username: "", password: "", role: "student", display_name: "", student_number: "", college: "", major: "", grade: "" };
    await load();
  } catch (e) {
    createError.value = e?.response?.data?.detail || e.message || "创建失败";
  } finally {
    creating.value = false;
  }
}

function fmt(dt) { if (!dt) return "—"; try { return new Date(dt).toLocaleString("zh-CN"); } catch { return dt; } }
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div><h2>账号管理</h2><p>维护学生与管理员账号状态</p></div>
      <button class="btn-primary" @click="createOpen = true"><UiIcon name="PhUserPlus" :size="16" />新建账号</button>
    </header>
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="error" class="error-box">{{ error }}</div>
    <section v-else>
      <div class="filter-bar">
        <select v-model="filterRole" @change="load"><option value="">全部角色</option><option value="student">学生</option><option value="admin">管理员</option></select>
      </div>
      <div class="table-wrap">
        <table class="user-table">
          <thead><tr><th>用户名</th><th>显示名</th><th>角色</th><th>学号</th><th>学院</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.username }}</td>
              <td>{{ u.display_name || "—" }}</td>
              <td><span class="tag" :class="{ admin: u.role === 'admin' }">{{ u.role === 'admin' ? '管理员' : '学生' }}</span></td>
              <td>{{ u.student_number || "—" }}</td>
              <td>{{ u.college || "—" }}</td>
              <td><span class="tag" :class="{ inactive: !u.is_active }">{{ u.is_active ? '正常' : '已停用' }}</span></td>
              <td>{{ fmt(u.created_at) }}</td>
              <td><button class="btn-sm" @click="toggleActive(u)">{{ u.is_active ? '停用' : '启用' }}</button></td>
            </tr>
            <tr v-if="!users.length"><td colspan="8" class="empty">没有账号</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal">
        <header><h3>新建账号</h3><button @click="createOpen = false"><UiIcon name="PhX" :size="18" /></button></header>
        <div class="modal-body">
          <div class="field-row">
            <label class="field"><span>用户名</span><input v-model="createForm.username" /></label>
            <label class="field"><span>密码(≥8位)</span><input type="password" v-model="createForm.password" /></label>
          </div>
          <div class="field-row">
            <label class="field"><span>角色</span><select v-model="createForm.role"><option value="student">学生</option><option value="admin">管理员</option></select></label>
            <label class="field"><span>显示名</span><input v-model="createForm.display_name" /></label>
          </div>
          <label class="field" v-if="createForm.role === 'student'"><span>学号</span><input v-model="createForm.student_number" /></label>
          <div class="field-row">
            <label class="field"><span>学院</span><input v-model="createForm.college" /></label>
            <label class="field"><span>专业</span><input v-model="createForm.major" /></label>
          </div>
          <div v-if="createError" class="err">{{ createError }}</div>
        </div>
        <footer>
          <button class="btn-ghost" @click="createOpen = false">取消</button>
          <button class="btn-primary" :disabled="creating" @click="submitCreate">{{ creating ? "创建中…" : "确认创建" }}</button>
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
.btn-primary, .btn-ghost { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-primary:disabled { opacity: .6; }
.btn-ghost { background: transparent; color: #6b7280; border: 1px solid #e5e7eb; }
.loading, .error-box { padding: 32px; text-align: center; color: #6b7280; }
.error-box { color: #dc2626; background: #fef2f2; border-radius: 8px; }
.filter-bar { margin-bottom: 12px; }
.filter-bar select { padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; }
.table-wrap { background: #fff; border-radius: 10px; overflow: auto; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.user-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.user-table th { background: #f9fafb; text-align: left; padding: 10px 12px; color: #6b7280; font-weight: 600; border-bottom: 1px solid #e5e7eb; }
.user-table td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; background: #f3f4f6; color: #6b7280; }
.tag.admin { background: #dbeafe; color: #1d4ed8; }
.tag.inactive { background: #fee2e2; color: #dc2626; }
.btn-sm { background: #f3f4f6; border: none; padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.empty { text-align: center; color: #9ca3af; padding: 32px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; width: 480px; max-width: 92vw; }
.modal header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e7eb; }
.modal header h3 { margin: 0; font-size: 16px; }
.modal header button { background: none; border: none; cursor: pointer; color: #6b7280; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.field span { color: #6b7280; }
.field input, .field select { padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 7px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.err { color: #dc2626; font-size: 13px; }
.modal footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid #e5e7eb; }
</style>
