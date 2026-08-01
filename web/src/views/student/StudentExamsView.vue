<script setup>
import { computed, onMounted, ref } from "vue";
import UiIcon from "../../components/UiIcon.vue";
import { deleteStudentExam, getStudentExams, saveStudentExam } from "../../services/studentApi";

const loading = ref(true);
const error = ref("");
const exams = ref([]);
const showForm = ref(false);
const saving = ref(false);
const form = ref({ course_name: "", exam_date: "", start_time: "", end_time: "", location: "", seat_number: "", exam_type: "", reminder_enabled: true, notes: "" });

const sortedExams = computed(() => [...exams.value].sort((a, b) => `${a.exam_date} ${a.start_time || ""}`.localeCompare(`${b.exam_date} ${b.start_time || ""}`)));
const upcomingExams = computed(() => sortedExams.value.filter((exam) => new Date(`${exam.exam_date}T${exam.end_time || exam.start_time || "23:59"}`).valueOf() >= Date.now()));
const locations = computed(() => new Set(exams.value.map((exam) => exam.location).filter(Boolean)).size);
const nextExam = computed(() => upcomingExams.value[0] || null);

function resetForm() { form.value = { course_name: "", exam_date: "", start_time: "", end_time: "", location: "", seat_number: "", exam_type: "", reminder_enabled: true, notes: "" }; }
function dateText(value) { if (!value) return "日期待定"; const date = new Date(`${value}T00:00:00`); return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "short" }); }
function monthText(value) { if (!value) return "--"; const date = new Date(`${value}T00:00:00`); return Number.isNaN(date.valueOf()) ? "--" : date.toLocaleDateString("zh-CN", { month: "short" }); }
function dayText(value) { if (!value) return "--"; const date = new Date(`${value}T00:00:00`); return Number.isNaN(date.valueOf()) ? "--" : date.getDate(); }
function isPast(exam) { return new Date(`${exam.exam_date}T${exam.end_time || exam.start_time || "23:59"}`).valueOf() < Date.now(); }
async function load() { loading.value = true; error.value = ""; try { exams.value = await getStudentExams(); } catch (e) { error.value = e.response?.data?.detail || "考试数据加载失败。"; } finally { loading.value = false; } }
async function save() { if (!form.value.course_name.trim() || !form.value.exam_date || saving.value) return; saving.value = true; error.value = ""; try { await saveStudentExam(form.value); showForm.value = false; resetForm(); await load(); } catch (e) { error.value = e.response?.data?.detail || "保存考试安排失败。"; } finally { saving.value = false; } }
async function remove(id) { if (!window.confirm("确认删除这条考试安排吗？")) return; try { await deleteStudentExam(id); exams.value = exams.value.filter((item) => item.id !== id); } catch (e) { error.value = e.response?.data?.detail || "删除失败，请重试。"; } }
onMounted(load);
</script>

<template>
  <main class="student-page page-enter student-tool-page">
    <div class="student-heading"><div><button class="back-link" @click="$router.push('/home')"><UiIcon name="PhArrowLeft" />返回首页</button><span class="eyebrow">ACADEMIC / 学业安排</span><h1>考试安排</h1><p>把重要考试集中在一个可回看的时间轴里，提醒和座位信息只属于你自己的记录。</p></div><div class="heading-actions"><button class="secondary-button" :disabled="loading" @click="load"><UiIcon name="PhArrowClockwise" />刷新</button><button class="primary-button" @click="showForm=true"><UiIcon name="PhPlus" />添加考试</button></div></div>
    <div v-if="error" class="student-alert error"><UiIcon name="PhWarningCircle" />{{ error }}<button class="link-button" @click="load">重试</button></div>
    <section class="tool-summary-grid">
      <article class="tool-summary-card accent"><span class="tool-summary-icon"><UiIcon name="PhCalendarBlank" /></span><div><small>下一场考试</small><strong>{{ nextExam ? dateText(nextExam.exam_date) : "暂无安排" }}</strong><span>{{ nextExam?.course_name || "添加后会显示在这里" }}</span></div></article>
      <article class="tool-summary-card"><span class="tool-summary-icon blue"><UiIcon name="PhExam" /></span><div><small>全部记录</small><strong>{{ exams.length }}</strong><span>{{ upcomingExams.length }} 场尚未结束</span></div></article>
      <article class="tool-summary-card"><span class="tool-summary-icon green"><UiIcon name="PhMapPin" /></span><div><small>考试地点</small><strong>{{ locations }}</strong><span>已填写地点的记录</span></div></article>
    </section>
    <section class="tool-workspace">
      <section class="student-panel surface exam-agenda-panel"><div class="student-panel-head"><div><span class="eyebrow">PERSONAL AGENDA</span><h2>考试时间轴</h2></div><span class="toolbar-count">{{ sortedExams.length }} 条记录</span></div><div v-if="loading" class="tool-list-skeleton"><div v-for="i in 3" :key="i"></div></div><div v-else-if="sortedExams.length" class="exam-agenda"><article v-for="exam in sortedExams" :key="exam.id" class="exam-agenda-row" :class="{past:isPast(exam)}"><div class="exam-date-block"><strong>{{ dayText(exam.exam_date) }}</strong><small>{{ monthText(exam.exam_date) }}</small></div><div class="exam-agenda-body"><div class="exam-agenda-title"><div><span class="status-pill" :class="isPast(exam) ? 'muted' : 'blue'">{{ exam.exam_type || '考试' }}</span><h3>{{ exam.course_name }}</h3></div><span v-if="isPast(exam)" class="exam-past-label">已结束</span></div><div class="exam-agenda-meta"><span><UiIcon name="PhCalendarBlank" />{{ dateText(exam.exam_date) }}</span><span><UiIcon name="PhClock" />{{ exam.start_time || '时间待定' }}{{ exam.end_time ? ` - ${exam.end_time}` : '' }}</span><span><UiIcon name="PhMapPin" />{{ exam.location || '地点待定' }}</span><span><UiIcon name="PhClipboardText" />座位 {{ exam.seat_number || '待定' }}</span></div><p v-if="exam.notes" class="exam-note"><UiIcon name="PhNotePencil" />{{ exam.notes }}</p></div><button class="icon-button danger-icon" aria-label="删除考试安排" title="删除考试安排" @click="remove(exam.id)"><UiIcon name="PhTrash" /></button></article></div><div v-else class="tool-empty"><span class="tool-empty-icon"><UiIcon name="PhExam" :size="34" /></span><strong>还没有考试安排</strong><p>添加一条个人考试记录，之后可以在这里查看日期、地点、座位和备注。</p><button class="secondary-button" @click="showForm=true"><UiIcon name="PhPlus" />添加第一条记录</button></div></section>
      <aside class="tool-side-stack"><section class="student-panel surface tool-guide-card"><div class="tool-guide-mark"><UiIcon name="PhClipboardText" /></div><span class="eyebrow">考前准备</span><h2>让考试当天少一点慌乱</h2><p>把考场、座位和需要携带的材料写进记录，进入考前只需查看这一页。</p><div class="tool-guide-list"><div><b>01</b><span><strong>确认时间</strong><small>核对日期和起止时间</small></span></div><div><b>02</b><span><strong>记下地点</strong><small>提前熟悉楼栋与教室</small></span></div><div><b>03</b><span><strong>补充备注</strong><small>记录证件或材料提醒</small></span></div></div></section><section class="student-panel surface tool-source-card"><span class="eyebrow">DATA NOTE</span><h3>数据来源说明</h3><p>当前记录来自你的个人保存内容，学校教务系统同步能力开放后可接入统一来源。</p></section></aside>
    </section>
    <div v-if="showForm" class="student-modal-backdrop" @click.self="showForm=false"><form class="student-modal tool-modal" @submit.prevent="save"><div class="student-modal-head"><div><span class="eyebrow">PERSONAL EXAM</span><h2>添加考试安排</h2><p>只填写你确认过的信息，之后仍可以继续补充备注。</p></div><button type="button" class="icon-button" aria-label="关闭" @click="showForm=false"><UiIcon name="PhX" /></button></div><div class="student-form-grid"><label class="student-field">课程名称<input v-model="form.course_name" name="exam-course" required /></label><label class="student-field">考试日期<input v-model="form.exam_date" name="exam-date" type="date" required /></label><label class="student-field">考试类型<input v-model="form.exam_type" name="exam-type" placeholder="例如：期末考试" /></label><label class="student-field">开始时间<input v-model="form.start_time" name="exam-start" type="time" /></label><label class="student-field">结束时间<input v-model="form.end_time" name="exam-end" type="time" /></label><label class="student-field">地点<input v-model="form.location" name="exam-location" placeholder="例如：教学楼 A203" /></label><label class="student-field">座位号<input v-model="form.seat_number" name="exam-seat" /></label></div><label class="student-field">备注<textarea v-model="form.notes" name="exam-notes" rows="3" placeholder="证件、材料或其他需要记住的事项"></textarea></label><label class="tool-check-line"><input v-model="form.reminder_enabled" name="exam-reminder" type="checkbox" />保存提醒偏好</label><div class="student-modal-actions"><button type="button" class="secondary-button" @click="showForm=false">取消</button><button class="primary-button" :disabled="saving || !form.course_name.trim() || !form.exam_date">{{ saving?'保存中…':'保存考试安排' }}</button></div></form></div>
  </main>
</template>
