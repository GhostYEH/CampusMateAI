<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { getStudentExams, saveStudentExam } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const exam = ref(null);
const form = ref({ course_name: "", exam_date: "", start_time: "", end_time: "", location: "", seat_number: "", exam_type: "", reminder_enabled: true, notes: "" });

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const list = await getStudentExams();
    const items = Array.isArray(list) ? list : list?.items || [];
    exam.value = items.find((item) => String(item.id) === String(route.params.examId));
    if (!exam.value) {
      error.value = "未找到该考试记录。";
      return;
    }
    form.value = {
      course_name: exam.value.course_name || "",
      exam_date: exam.value.exam_date || "",
      start_time: exam.value.start_time || "",
      end_time: exam.value.end_time || "",
      location: exam.value.location || "",
      seat_number: exam.value.seat_number || "",
      exam_type: exam.value.exam_type || "",
      reminder_enabled: exam.value.reminder_enabled !== false,
      notes: exam.value.notes || "",
    };
  } catch (e) {
    error.value = e.response?.data?.detail || "考试数据加载失败。";
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!form.value.course_name.trim() || !form.value.exam_date || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await saveStudentExam(form.value, exam.value.id);
    router.push(`/exams/${exam.value.id}`);
  } catch (e) {
    error.value = e.response?.data?.detail || "保存失败，请重试。";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <main class="student-page page-enter exam-edit-page">
    <div class="student-heading">
      <div>
        <button class="back-link" @click="router.push(`/exams/${route.params.examId}`)"><UiIcon name="PhArrowLeft" />返回详情</button>
        <span class="eyebrow">EXAM / 编辑考试</span>
        <h1>编辑考试安排</h1>
        <p>修改考试信息后保存返回详情页。</p>
      </div>
    </div>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}</div>

    <div v-if="loading" class="edit-loading">加载中…</div>
    <form v-else-if="exam" class="edit-form" @submit.prevent="save">
      <div class="form-grid">
        <label class="form-field">课程名称<input v-model="form.course_name" required /></label>
        <label class="form-field">考试日期<input v-model="form.exam_date" type="date" required /></label>
        <label class="form-field">考试类型<input v-model="form.exam_type" placeholder="例如：期末考试" /></label>
        <label class="form-field">开始时间<input v-model="form.start_time" type="time" /></label>
        <label class="form-field">结束时间<input v-model="form.end_time" type="time" /></label>
        <label class="form-field">地点<input v-model="form.location" placeholder="例如：教学楼 A203" /></label>
        <label class="form-field">座位号<input v-model="form.seat_number" /></label>
      </div>
      <label class="form-field">备注<textarea v-model="form.notes" rows="3" placeholder="证件、材料或其他需要记住的事项"></textarea></label>
      <label class="form-check"><input v-model="form.reminder_enabled" type="checkbox" />保存提醒偏好</label>
      <div class="form-actions">
        <button type="button" class="secondary-button" @click="router.push(`/exams/${exam.id}`)">取消</button>
        <button type="submit" class="primary-button" :disabled="saving || !form.course_name.trim() || !form.exam_date">{{ saving ? "保存中…" : "保存修改" }}</button>
      </div>
    </form>
  </main>
</template>

<style scoped>
.exam-edit-page { display: flex; flex-direction: column; gap: 16px; }
.edit-loading { padding: 40px; text-align: center; color: #6b7280; }
.edit-form { background: #fff; border-radius: 14px; padding: 22px; box-shadow: 0 1px 3px rgba(15,23,42,.04); display: flex; flex-direction: column; gap: 14px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.form-field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #374151; }
.form-field input, .form-field textarea { padding: 9px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px; font-family: inherit; }
.form-check { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; }
.form-actions { display: flex; gap: 10px; justify-content: flex-end; }
.primary-button, .secondary-button { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.primary-button { background: #2563eb; color: #fff; }
.primary-button:disabled { opacity: .6; cursor: not-allowed; }
.secondary-button { background: #f3f4f6; color: #374151; }
</style>