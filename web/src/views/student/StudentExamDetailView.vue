<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../../components/UiIcon.vue";
import { deleteStudentExam, getStudentExams } from "../../services/studentApi";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const exam = ref(null);

const examId = computed(() => route.params.examId);

const countdown = computed(() => {
  if (!exam.value) return "";
  const start = new Date(`${exam.value.exam_date}T${exam.value.start_time || "00:00"}`);
  if (Number.isNaN(start.valueOf())) return "";
  const diff = start.valueOf() - Date.now();
  if (diff <= 0) return "已开始或已结束";
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return `${days} 天 ${hours} 小时`;
  if (hours > 0) return `${hours} 小时 ${minutes} 分钟`;
  return `${minutes} 分钟`;
});

function fmtDate(value) {
  if (!value) return "日期待定";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const list = await getStudentExams();
    const items = Array.isArray(list) ? list : list?.items || [];
    exam.value = items.find((item) => String(item.id) === String(examId.value));
    if (!exam.value) error.value = "未找到该考试记录。";
  } catch (e) {
    error.value = e.response?.data?.detail || "考试详情加载失败。";
  } finally {
    loading.value = false;
  }
}

async function remove() {
  if (!exam.value || !window.confirm("确认删除这条考试安排吗？")) return;
  try {
    await deleteStudentExam(exam.value.id);
    router.push("/exams");
  } catch (e) {
    error.value = e.response?.data?.detail || "删除失败，请重试。";
  }
}

onMounted(load);
</script>

<template>
  <main class="student-page exam-detail-page">
    <div class="student-heading">
      <div>
        <button class="back-link" @click="router.push('/exams')"><UiIcon name="PhArrowLeft" />返回考试列表</button>
        <span class="eyebrow">EXAM / 考试详情</span>
        <h1>{{ exam?.course_name || "考试详情" }}</h1>
        <p>查看考试时间、地点与备注信息。</p>
      </div>
      <div class="heading-actions">
        <button class="secondary-button" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button>
      </div>
    </div>

    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="router.push('/exams')">返回列表</button></div>

    <div v-if="loading" class="detail-loading">加载中…</div>
    <template v-else-if="exam">
      <section class="detail-countdown" v-if="countdown">
        <span class="countdown-label">距离开考</span>
        <strong class="countdown-value">{{ countdown }}</strong>
      </section>

      <section class="detail-card">
        <div class="detail-row"><span class="detail-icon blue"><UiIcon name="PhBookOpen" /></span><div><small>课程名称</small><strong>{{ exam.course_name || "—" }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon indigo"><UiIcon name="PhTag" /></span><div><small>考试类型</small><strong>{{ exam.exam_type || "未分类" }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon green"><UiIcon name="PhCalendarBlank" /></span><div><small>考试日期</small><strong>{{ fmtDate(exam.exam_date) }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon amber"><UiIcon name="PhClock" /></span><div><small>开始时间</small><strong>{{ exam.start_time || "时间待定" }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon amber"><UiIcon name="PhClock" /></span><div><small>结束时间</small><strong>{{ exam.end_time || "时间待定" }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon teal"><UiIcon name="PhMapPin" /></span><div><small>考试地点</small><strong>{{ exam.location || "地点待定" }}</strong></div></div>
        <div class="detail-row"><span class="detail-icon violet"><UiIcon name="PhClipboardText" /></span><div><small>座位号</small><strong>{{ exam.seat_number || "待定" }}</strong></div></div>
        <div class="detail-row" v-if="exam.notes"><span class="detail-icon rose"><UiIcon name="PhNotePencil" /></span><div><small>备注</small><strong>{{ exam.notes }}</strong></div></div>
      </section>

      <section class="detail-actions">
        <button class="primary-button" @click="router.push(`/exams/${exam.id}/edit`)"><UiIcon name="PhPencil" />编辑</button>
        <button class="danger-button" @click="remove"><UiIcon name="PhTrash" />删除</button>
        <button class="secondary-button" @click="router.push('/exams')"><UiIcon name="PhArrowLeft" />返回列表</button>
      </section>
    </template>
  </main>
</template>

<style scoped>
.exam-detail-page { display: flex; flex-direction: column; gap: 16px; }
.detail-loading { padding: 40px; text-align: center; color: #6b7280; }
.detail-countdown { display: flex; align-items: center; gap: 12px; padding: 18px 22px; background: linear-gradient(135deg, #2563eb, #4f46e5); color: #fff; border-radius: 14px; box-shadow: 0 6px 18px rgba(37,99,235,.18); }
.countdown-label { font-size: 13px; opacity: .9; }
.countdown-value { font-size: 22px; font-weight: 700; }
.detail-card { background: #fff; border-radius: 14px; padding: 8px 22px; box-shadow: 0 1px 3px rgba(15,23,42,.04); }
.detail-row { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid #f8fafc; }
.detail-row:last-child { border-bottom: none; }
.detail-icon { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.detail-icon.blue { background: #2563eb; }
.detail-icon.indigo { background: #4f46e5; }
.detail-icon.green { background: #059669; }
.detail-icon.amber { background: #d97706; }
.detail-icon.teal { background: #0d9488; }
.detail-icon.violet { background: #7c3aed; }
.detail-icon.rose { background: #e11d48; }
.detail-row small { display: block; font-size: 12px; color: #6b7280; }
.detail-row strong { display: block; font-size: 14px; color: #111827; margin-top: 2px; }
.detail-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.primary-button, .secondary-button, .danger-button { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.primary-button { background: #2563eb; color: #fff; }
.secondary-button { background: #f3f4f6; color: #374151; }
.danger-button { background: #fef2f2; color: #dc2626; }
.primary-button:hover { background: #1d4ed8; }
.secondary-button:hover { background: #e5e7eb; }
.danger-button:hover { background: #fee2e2; }
</style>