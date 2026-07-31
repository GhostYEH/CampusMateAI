<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UiIcon from "../components/UiIcon.vue";
import { useAppStore } from "../stores/app";
import {
  createTeacherAssignment,
  getAssignmentInsight,
  getTeacherAssignments,
  getTeacherCourses,
  getTeacherOverview,
  updateAssignmentStatus,
} from "../services/portalRepository";

const props = defineProps({ section: { type: String, default: "" } });
const store = useAppStore();
const route = useRoute();
const router = useRouter();
const current = computed(() => props.section || route.path.slice(1) || "home");
const loading = ref(true);
const error = ref("");
const saving = ref(false);
const overview = ref(null);
const courses = ref([]);
const classes = ref([]);
const assignments = ref([]);
const query = ref("");
const statusFilter = ref("");
const classFilter = ref("");
const showComposer = ref(false);
const selectedAssignment = ref(null);
const insight = ref(null);
const insightLoading = ref(false);
const toast = ref("");
const form = reactive({
  title: "",
  class_group_id: "",
  description: "",
  deadline: "",
  max_score: 100,
  allow_resubmit: true,
  submission_types: ["text", "file"],
  status: "published",
});

const classOptions = computed(() => classes.value.map((cls) => ({
  ...cls,
  course: courses.value.find((course) => course.id === cls.course_id),
})));
const filteredAssignments = computed(() => assignments.value.filter((item) => {
  const matchesQuery = !query.value || `${item.title}${item.class_name || ""}${item.course_name || ""}`.toLowerCase().includes(query.value.toLowerCase());
  const matchesStatus = !statusFilter.value || item.status === statusFilter.value;
  const matchesClass = !classFilter.value || item.class_group_id === classFilter.value;
  return matchesQuery && matchesStatus && matchesClass;
}));
const statusLabel = { draft: "草稿", published: "进行中", closed: "已结束", archived: "已归档" };

function flash(message) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ""; }, 2200);
}
function formatDate(value) {
  if (!value) return "未设置截止";
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
function completion(item) {
  const total = item.student_count || item.total_students || 0;
  const submitted = item.submitted_count || 0;
  return total ? Math.round((submitted / total) * 100) : 0;
}
function resetForm() {
  Object.assign(form, {
    title: "",
    class_group_id: classOptions.value[0]?.id || "",
    description: "",
    deadline: "",
    max_score: 100,
    allow_resubmit: true,
    submission_types: ["text", "file"],
    status: "published",
  });
}
async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [overviewData, courseData, assignmentData] = await Promise.all([
      getTeacherOverview(),
      getTeacherCourses(),
      getTeacherAssignments(),
    ]);
    overview.value = overviewData;
    courses.value = courseData.courses;
    classes.value = courseData.classes;
    assignments.value = assignmentData;
    if (!form.class_group_id) form.class_group_id = classes.value[0]?.id || "";
  } catch (err) {
    error.value = err.response?.data?.message || err.message || "教学数据加载失败";
  } finally {
    loading.value = false;
  }
}
async function submitAssignment() {
  if (!form.title.trim() || !form.class_group_id) return;
  saving.value = true;
  try {
    const payload = {
      ...form,
      title: form.title.trim(),
      description: form.description.trim() || null,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      max_score: Number(form.max_score),
    };
    await createTeacherAssignment(payload);
    showComposer.value = false;
    resetForm();
    await load();
    flash(payload.status === "published" ? "任务已发布，学生端会收到更新" : "任务已保存为草稿");
  } catch (err) {
    error.value = err.response?.data?.message || err.message || "任务保存失败";
  } finally {
    saving.value = false;
  }
}
async function changeStatus(item, status) {
  try {
    await updateAssignmentStatus(item.id, status);
    item.status = status;
    flash(status === "published" ? "任务已发布" : "任务已结束");
    overview.value = await getTeacherOverview();
  } catch (err) {
    flash(err.response?.data?.message || "状态更新失败");
  }
}
async function openInsight(item) {
  selectedAssignment.value = item;
  insight.value = null;
  insightLoading.value = true;
  try { insight.value = await getAssignmentInsight(item); }
  catch (err) { flash(err.response?.data?.message || "提交详情加载失败"); }
  finally { insightLoading.value = false; }
}
function openComposer() {
  resetForm();
  showComposer.value = true;
}

watch(current, () => {
  query.value = "";
  statusFilter.value = "";
});
onMounted(load);
</script>

<template>
  <main class="portal-page page-enter">
    <div v-if="toast" class="portal-toast" role="status"><UiIcon name="PhCheckCircle" weight="fill" />{{ toast }}</div>

    <div class="portal-heading">
      <div>
        <span class="portal-kicker">教师工作台</span>
        <h1>{{ current === "home" ? `上午好，${store.session?.name || "老师"}` : current === "courses" ? "课程与班级" : current === "stats" ? "任务完成情况" : "任务发布中心" }}</h1>
        <p>{{ current === "home" ? "先处理需要关注的提交，再安排下一次教学任务。" : current === "courses" ? "查看本学期负责的课程与教学班。" : current === "stats" ? "按班级和任务查看学生提交进度。" : "将要求、截止时间和提交方式一次说明清楚。" }}</p>
      </div>
      <button v-if="current !== 'courses'" class="primary-button" @click="openComposer"><UiIcon name="PhPlus" />发布任务</button>
    </div>

    <div v-if="loading" class="portal-loading" aria-label="正在加载">
      <i v-for="n in 6" :key="n"></i>
    </div>
    <div v-else-if="error" class="portal-error">
      <UiIcon name="PhCloudSlash" :size="34" />
      <div><strong>暂时没有加载出来</strong><p>{{ error }}</p></div>
      <button class="secondary-button" @click="load">重新加载</button>
    </div>

    <template v-else-if="current === 'home'">
      <section class="metric-strip">
        <article><span>进行中任务</span><strong>{{ overview.active_assignment_count }}</strong><small>{{ overview.pending_submission_count }} 份提交待处理</small></article>
        <article><span>教学班级</span><strong>{{ overview.class_count }}</strong><small>{{ overview.student_count }} 名学生</small></article>
        <article><span>逾期待跟进</span><strong class="warm-number">{{ overview.overdue_student_count }}</strong><small>建议优先发送提醒</small></article>
        <article><span>本学期课程</span><strong>{{ overview.course_count }}</strong><small>均处于正常教学状态</small></article>
      </section>

      <div class="portal-two-column">
        <section class="portal-panel">
          <div class="portal-section-title"><div><h2>最近发布</h2><p>按创建时间排列</p></div><button @click="router.push('/publish')">全部任务<UiIcon name="PhArrowRight" /></button></div>
          <div class="assignment-list">
            <button v-for="item in overview.recent_assignments" :key="item.assignment_id || item.id" class="assignment-line" @click="openInsight({ ...item, id: item.assignment_id || item.id })">
              <span class="line-date">{{ formatDate(item.deadline) }}</span>
              <span><strong>{{ item.title }}</strong><small>{{ item.course_name }} / {{ item.class_name }}</small></span>
              <em :class="`status-${item.status}`">{{ statusLabel[item.status] }}</em>
              <UiIcon name="PhCaretRight" />
            </button>
            <div v-if="!overview.recent_assignments.length" class="portal-empty"><UiIcon name="PhClipboardText" :size="32" />还没有教学任务，发布第一项任务后会显示在这里。</div>
          </div>
        </section>
        <aside class="teacher-priority">
          <span class="priority-icon"><UiIcon name="PhTray" :size="28" /></span>
          <h2>{{ overview.pending_submission_count }} 份提交等待处理</h2>
          <p>数据结构的两项任务最接近截止时间，建议先查看未提交名单。</p>
          <button class="secondary-button" @click="router.push('/stats')">查看完成情况</button>
        </aside>
      </div>
    </template>

    <template v-else-if="current === 'courses'">
      <section class="course-board">
        <article v-for="course in courses" :key="course.id" class="teacher-course">
          <div class="course-monogram">{{ course.code?.slice(0, 2) || "课" }}</div>
          <span>{{ course.semester || "当前学期" }}</span>
          <h2>{{ course.name }}</h2>
          <p>{{ classes.filter((item) => item.course_id === course.id).length }} 个教学班，{{ classes.filter((item) => item.course_id === course.id).reduce((sum, item) => sum + (item.capacity || 0), 0) }} 名学生</p>
          <div class="course-class-list">
            <span v-for="cls in classes.filter((item) => item.course_id === course.id)" :key="cls.id">{{ cls.name }}<b>{{ cls.capacity || 0 }} 人</b></span>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="portal-toolbar">
        <div class="portal-search"><UiIcon name="PhMagnifyingGlass" /><input v-model="query" name="assignment-search" placeholder="搜索任务或班级" /></div>
        <select v-model="classFilter" name="class-filter" aria-label="筛选班级"><option value="">全部班级</option><option v-for="cls in classOptions" :key="cls.id" :value="cls.id">{{ cls.course?.name }} / {{ cls.name }}</option></select>
        <select v-model="statusFilter" name="assignment-status-filter" aria-label="筛选状态"><option value="">全部状态</option><option value="published">进行中</option><option value="draft">草稿</option><option value="closed">已结束</option></select>
        <span>{{ filteredAssignments.length }} 项</span>
      </section>
      <section class="portal-panel assignment-board">
        <div class="assignment-head"><span>任务</span><span>截止时间</span><span>提交进度</span><span>状态</span><span>操作</span></div>
        <article v-for="item in filteredAssignments" :key="item.id" class="assignment-row-new">
          <div><strong>{{ item.title }}</strong><small>{{ item.course_name }} / {{ item.class_name }}</small></div>
          <time>{{ formatDate(item.deadline) }}</time>
          <button class="completion-cell" @click="openInsight(item)">
            <strong>{{ item.submitted_count || 0 }}/{{ item.student_count || 0 }}</strong>
            <span>{{ completion(item) }}% 已提交</span>
          </button>
          <em :class="`status-${item.status}`">{{ statusLabel[item.status] }}</em>
          <div class="row-actions">
            <button @click="openInsight(item)" title="查看详情"><UiIcon name="PhChartBar" /></button>
            <button v-if="item.status === 'draft'" @click="changeStatus(item, 'published')" title="发布"><UiIcon name="PhPaperPlaneTilt" /></button>
            <button v-if="item.status === 'published'" @click="changeStatus(item, 'closed')" title="结束"><UiIcon name="PhStopCircle" /></button>
          </div>
        </article>
        <div v-if="!filteredAssignments.length" class="portal-empty"><UiIcon name="PhMagnifyingGlass" :size="34" />没有符合当前条件的任务，换个关键词或筛选条件试试。</div>
      </section>
    </template>

    <Teleport to="body">
    <div v-if="showComposer" class="portal-overlay composer-overlay" role="presentation" @click.self="showComposer = false" @keydown.esc="showComposer = false">
      <form class="portal-drawer" role="dialog" aria-modal="true" aria-labelledby="assignment-composer-title" @submit.prevent="submitAssignment">
        <div class="drawer-head"><div><span>新教学任务</span><h2 id="assignment-composer-title">发布给学生</h2></div><button type="button" class="icon-button" @click="showComposer = false" aria-label="关闭"><UiIcon name="PhX" /></button></div>
        <label>任务名称<input v-model="form.title" name="assignment-title" maxlength="200" placeholder="例如：链表与栈综合练习" required /></label>
        <label>发布班级<select v-model="form.class_group_id" name="assignment-class" required><option disabled value="">请选择班级</option><option v-for="cls in classOptions" :key="cls.id" :value="cls.id">{{ cls.course?.name }} / {{ cls.name }}</option></select></label>
        <label>任务要求<textarea v-model="form.description" name="assignment-description" rows="5" placeholder="说明学习目标、提交内容和注意事项"></textarea></label>
        <div class="form-pair"><label>截止时间<input v-model="form.deadline" name="assignment-deadline" type="datetime-local" /></label><label>满分<input v-model.number="form.max_score" name="assignment-max-score" type="number" min="0" max="1000" /></label></div>
        <fieldset><legend>提交方式</legend><label class="check-line"><input v-model="form.submission_types" name="submission-type" type="checkbox" value="text" />在线文本</label><label class="check-line"><input v-model="form.submission_types" name="submission-type" type="checkbox" value="file" />文件附件</label></fieldset>
        <label class="switch-line"><span><strong>允许重新提交</strong><small>截止前学生可以更新提交内容</small></span><input v-model="form.allow_resubmit" name="allow-resubmit" type="checkbox" /></label>
        <div class="drawer-actions"><button type="button" class="secondary-button" :disabled="saving" @click="form.status = 'draft'; submitAssignment()">保存草稿</button><button class="primary-button" :disabled="saving || !form.title.trim() || !form.class_group_id" @click="form.status = 'published'">{{ saving ? "正在保存" : "确认发布" }}<UiIcon name="PhPaperPlaneTilt" /></button></div>
      </form>
    </div>
    </Teleport>

    <Teleport to="body">
    <div v-if="selectedAssignment" class="portal-overlay" role="presentation" @click.self="selectedAssignment = null" @keydown.esc="selectedAssignment = null">
      <section class="portal-modal insight-modal" role="dialog" aria-modal="true" aria-labelledby="assignment-insight-title">
        <div class="drawer-head"><div><span>任务完成情况</span><h2 id="assignment-insight-title">{{ selectedAssignment.title }}</h2></div><button class="icon-button" @click="selectedAssignment = null" aria-label="关闭"><UiIcon name="PhX" /></button></div>
        <div class="insight-modal-body">
        <div v-if="insightLoading" class="modal-loading"><i></i><i></i><i></i></div>
        <template v-else-if="insight">
          <div class="insight-metrics">
            <span><strong>{{ insight.stats.submitted_count || 0 }}</strong>已提交</span>
            <span><strong>{{ insight.stats.unsubmitted_count ?? Math.max(0, (insight.stats.total_students || 0) - (insight.stats.submitted_count || 0)) }}</strong>未提交</span>
            <span><strong>{{ insight.stats.late_count || 0 }}</strong>迟交</span>
            <span><strong>{{ insight.stats.graded_count || 0 }}</strong>已批改</span>
          </div>
          <div class="student-status-list">
            <div class="student-status-head"><span>学生</span><span>提交状态</span><span>成绩</span></div>
            <article v-for="student in insight.students" :key="student.student_id">
              <span><strong>{{ student.student_name }}</strong><small>{{ student.student_number }}</small></span>
              <em :class="`submission-${student.submission_status}`">{{ {submitted:"已提交",resubmitted:"已重交",late:"迟交",not_submitted:"未提交",draft:"草稿"}[student.submission_status] || student.submission_status }}</em>
              <b>{{ student.score ?? "待批" }}</b>
            </article>
          </div>
        </template>
        </div>
      </section>
    </div>
    </Teleport>
  </main>
</template>
