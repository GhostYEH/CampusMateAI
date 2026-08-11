<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import FilterBar from "../../components/teacher/FilterBar.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import Drawer from "../../components/teacher/Drawer.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { useConfirm } from "../../composables/useConfirm";
import { useCommonComments } from "../../composables/useCommonComments";
import {
  listTeacherSubmissions, getSubmission, gradeSubmission, buildSubmissionAttachmentDownloadUrl,
} from "../../services/teacher/submissions";
import { listTeacherAssignments } from "../../services/teacher/assignments";
import {
  formatDate, formatDateTime, formatFileSize, downloadCsv,
} from "../../composables/useFormat";

const route = useRoute();
const router = useRouter();
const teacherStore = useTeacherStore();
const toast = useToast();
const { confirm } = useConfirm();
const { comments: commonComments, add: addCommonComment, remove: removeCommonComment } = useCommonComments();

const loading = ref(true);
const error = ref("");
const items = ref([]);
const total = ref(0);
const query = ref("");
const assignmentFilter = ref("");
const classFilter = ref("");
const statusFilter = ref("");
const assignments = ref([]);

const showGrade = ref(false);
const current = ref(null);
const gradeLoading = ref(false);
const saving = ref(false);
const gradeForm = reactive({ score: "", teacher_comment: "" });
const gradeErrors = reactive({});
const showSaveComment = ref(false);
const newCommentText = ref("");

const classOptions = computed(() => teacherStore.classOptionsWithCourse());

const filterConfig = computed(() => [
  {
    key: "assignment", label: "作业", value: assignmentFilter.value,
    options: assignments.value.map((a) => ({ value: a.id, label: a.title })),
  },
  {
    key: "class", label: "班级", value: classFilter.value,
    options: classOptions.value.map((c) => ({ value: c.id, label: `${c.course?.name || ""} / ${c.name}` })),
  },
  {
    key: "status", label: "批改状态", value: statusFilter.value,
    options: [
      { value: "ungraded", label: "待批改" },
      { value: "graded", label: "已批改" },
    ],
  },
]);

function onFiltersChange(next) {
  next.forEach((f) => {
    if (f.key === "assignment") assignmentFilter.value = f.value;
    if (f.key === "class") classFilter.value = f.value;
    if (f.key === "status") statusFilter.value = f.value;
  });
  load();
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    await teacherStore.loadAll().catch(() => null);
    if (!assignments.value.length) {
      const page = await listTeacherAssignments({ page_size: 200 });
      assignments.value = page.items || [];
    }
    const params = {};
    if (assignmentFilter.value) params.assignment_id = assignmentFilter.value;
    if (classFilter.value) params.class_id = classFilter.value;
    if (query.value) params.search = query.value;
    const page = await listTeacherSubmissions(params);
    let list = page.items || [];
    if (statusFilter.value === "ungraded") list = list.filter((s) => s.score === null || s.score === undefined);
    if (statusFilter.value === "graded") list = list.filter((s) => s.score !== null && s.score !== undefined);
    items.value = list;
    total.value = page.total || list.length;

    const initialSubmissionId = route.query.submission_id;
    const initialAssignmentId = route.query.assignment_id;
    if (initialSubmissionId && !showGrade.value) {
      const target = list.find((s) => s.id === initialSubmissionId);
      if (target) openGrade(target);
      else {
        try {
          const sub = await getSubmission(initialSubmissionId);
          if (sub) openGrade(sub);
        } catch { /* ignore */ }
      }
    } else if (initialAssignmentId && !assignmentFilter.value) {
      assignmentFilter.value = initialAssignmentId;
    }
  } catch (err) {
    error.value = extractErrorMessage(err, "提交列表加载失败");
  } finally {
    loading.value = false;
  }
}

function openGrade(item) {
  current.value = item;
  gradeForm.score = item.score ?? "";
  gradeForm.teacher_comment = item.teacher_comment || "";
  Object.keys(gradeErrors).forEach((k) => delete gradeErrors[k]);
  showGrade.value = true;
  loadFullSubmission(item.id);
}

async function loadFullSubmission(submissionId) {
  gradeLoading.value = true;
  try {
    const full = await getSubmission(submissionId);
    if (current.value?.id === submissionId) {
      current.value = { ...current.value, ...full };
    }
  } catch (err) {
    toast.error(extractErrorMessage(err, "提交详情加载失败"));
  } finally {
    gradeLoading.value = false;
  }
}

function validateGrade() {
  Object.keys(gradeErrors).forEach((k) => delete gradeErrors[k]);
  if (gradeForm.score === "" || gradeForm.score === null) {
    gradeErrors.score = "请输入成绩";
  } else {
    const s = Number(gradeForm.score);
    if (!Number.isFinite(s)) gradeErrors.score = "成绩须为数字";
    else if (s < 0) gradeErrors.score = "成绩不能为负";
    else if (s > 1000) gradeErrors.score = "成绩不能超过 1000";
    else if (current.value?.assignment_max_score && s > current.value.assignment_max_score) {
      gradeErrors.score = `成绩不能超过满分 ${current.value.assignment_max_score}`;
    }
  }
  if (gradeForm.teacher_comment.length > 5000) gradeErrors.teacher_comment = "评语不能超过 5000 字";
  return Object.keys(gradeErrors).length === 0;
}

async function submitGrade() {
  if (!validateGrade() || !current.value) return;
  saving.value = true;
  try {
    const payload = {
      score: Number(gradeForm.score),
      teacher_comment: gradeForm.teacher_comment.trim(),
    };
    const updated = await gradeSubmission(current.value.id, payload);
    toast.success("成绩已保存");
    const idx = items.value.findIndex((s) => s.id === current.value.id);
    if (idx >= 0) items.value[idx] = { ...items.value[idx], ...updated };
    current.value = { ...current.value, ...updated };
    showGrade.value = false;
  } catch (err) {
    toast.error(extractErrorMessage(err, "保存成绩失败"));
  } finally {
    saving.value = false;
  }
}

function applyCommonComment(text) {
  const existing = gradeForm.teacher_comment || "";
  gradeForm.teacher_comment = existing ? `${existing}\n${text}` : text;
}

async function saveCurrentComment() {
  const text = newCommentText.value.trim();
  if (!text) return;
  addCommonComment(text);
  newCommentText.value = "";
  showSaveComment.value = false;
  toast.success("已加入常用评语");
}

async function removeCommon(id) {
  const ok = await confirm({
    title: "移除常用评语", message: "确定从常用评语中移除?", confirmText: "移除", danger: true,
  });
  if (!ok) return;
  removeCommonComment(id);
}

function navigate(delta) {
  if (!current.value) return;
  const idx = items.value.findIndex((s) => s.id === current.value.id);
  if (idx < 0) return;
  const next = idx + delta;
  if (next < 0 || next >= items.value.length) {
    toast.info(delta > 0 ? "已是最后一份" : "已是第一份");
    return;
  }
  openGrade(items.value[next]);
}

const currentIndex = computed(() => {
  if (!current.value) return -1;
  return items.value.findIndex((s) => s.id === current.value.id);
});

function exportCsv() {
  if (!items.value.length) {
    toast.info("当前列表无数据可导出");
    return;
  }
  const rows = items.value.map((s) => ({
    学号: s.student_number || "",
    姓名: s.student_name || "",
    班级: s.class_name || "",
    提交状态: s.status || "",
    提交时间: s.submitted_at ? formatDateTime(s.submitted_at) : "",
    是否迟交: s.is_late ? "是" : "否",
    成绩: s.score ?? "",
    教师评语: s.teacher_comment || "",
  }));
  const ts = new Date().toISOString().slice(0, 10);
  downloadCsv(`批改记录_${ts}.csv`, rows);
  toast.success("CSV 已导出");
}

onMounted(load);
watch(() => route.query, load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="批改中心" title="学生提交批改" subtitle="查看学生提交、评分、写评语，支持常用评语与 CSV 导出。">
      <template #actions>
        <button class="secondary-button" @click="exportCsv"><UiIcon name="PhDownloadSimple" :size="16" />导出 CSV</button>
      </template>
    </PageHeader>

    <FilterBar
      v-model="query"
      :filters="filterConfig"
      search-placeholder="搜索学生姓名或学号"
      @update:filters="onFiltersChange"
      @search="load"
    />

    <Skeleton v-if="loading" :rows="6" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!items.length" icon="PhPencilSimpleLine" title="暂无提交" description="学生提交作业后会出现在这里。" />
    <section v-else class="tch-panel">
      <div class="tch-table-wrap">
        <div class="tch-table-scroll" style="min-width: 920px">
          <table class="tch-table">
            <thead>
              <tr>
                <th>学号</th><th>姓名</th><th>作业</th><th>班级</th><th>提交状态</th><th>提交时间</th><th>成绩</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in items" :key="s.id">
                <td>{{ s.student_number || '—' }}</td>
                <td>{{ s.student_name || '—' }}</td>
                <td><small>{{ s.assignment_title || '—' }}</small></td>
                <td><small>{{ s.class_name || '—' }}</small></td>
                <td><StatusTag :status="s.status || 'submitted'" type="submission" /></td>
                <td><small>{{ s.submitted_at ? formatDateTime(s.submitted_at) : '—' }}</small></td>
                <td>
                  <strong v-if="s.score !== null && s.score !== undefined">{{ s.score }}</strong>
                  <span v-else class="muted">未批改</span>
                </td>
                <td><button class="tch-link" @click="openGrade(s)">批改</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <Drawer :open="showGrade" :title="current ? `批改：${current.assignment_title || ''}` : '批改'" width="wide" @update:open="showGrade = $event">
      <template v-if="current">
        <div class="tch-grade-meta">
          <span><UiIcon name="PhUser" :size="14" />{{ current.student_name || '—' }} <small>{{ current.student_number }}</small></span>
          <span><UiIcon name="PhUsers" :size="14" />{{ current.class_name || '—' }}</span>
          <StatusTag :status="current.status || 'submitted'" type="submission" />
          <span v-if="current.submitted_at"><UiIcon name="PhClock" :size="14" />{{ formatDateTime(current.submitted_at) }}</span>
          <span v-if="current.is_late" class="tch-tag-late">迟交</span>
        </div>

        <div class="tch-grade-nav">
          <button class="secondary-button" :disabled="currentIndex <= 0" @click="navigate(-1)"><UiIcon name="PhArrowLeft" :size="16" />上一份</button>
          <span class="muted">第 {{ currentIndex + 1 }} / {{ items.length }} 份</span>
          <button class="secondary-button" :disabled="currentIndex >= items.length - 1" @click="navigate(1)">下一份<UiIcon name="PhArrowRight" :size="16" /></button>
        </div>

        <section class="tch-grade-section">
          <h3>学生提交内容</h3>
          <div v-if="gradeLoading" class="tch-detail-loading"><UiIcon name="PhCircleNotch" :size="20" /> 加载中…</div>
          <template v-else>
            <article v-if="current.text_content" class="tch-detail-content">{{ current.text_content }}</article>
            <EmptyState v-else icon="PhFileText" title="无文字内容" compact />
            <div v-if="current.attachments?.length" class="tch-grade-attachments">
              <h4>提交附件</h4>
              <ul class="tch-attach-list">
                <li v-for="att in current.attachments" :key="att.id">
                  <UiIcon name="PhFile" :size="18" />
                  <div class="tch-attach-info">
                    <strong>{{ att.original_filename || att.filename || att.name }}</strong>
                    <small>{{ formatFileSize(att.size_bytes ?? att.size ?? att.file_size) }}</small>
                  </div>
                  <a class="tch-link" :href="buildSubmissionAttachmentDownloadUrl(current.id, att.id)" target="_blank" rel="noopener">
                    <UiIcon name="PhDownloadSimple" :size="14" />下载
                  </a>
                </li>
              </ul>
            </div>
          </template>
        </section>

        <section class="tch-grade-section">
          <h3>评分</h3>
          <form class="tch-form" @submit.prevent="submitGrade">
            <div class="tch-form-row">
              <label class="tch-field">
                <span>成绩 <em>*</em></span>
                <input v-model="gradeForm.score" type="number" min="0" :max="current.assignment_max_score || 1000" step="0.5" />
                <small v-if="gradeErrors.score" class="tch-field-error">{{ gradeErrors.score }}</small>
                <small v-else-if="current.assignment_max_score" class="muted">满分 {{ current.assignment_max_score }}</small>
              </label>
            </div>
            <label class="tch-field">
              <span>教师评语</span>
              <textarea v-model="gradeForm.teacher_comment" rows="5" maxlength="5000" placeholder="给学生反馈，可从常用评语选择"></textarea>
              <small v-if="gradeErrors.teacher_comment" class="tch-field-error">{{ gradeErrors.teacher_comment }}</small>
            </label>
          </form>

          <div class="tch-common-comments">
            <div class="tch-common-head">
              <h4>常用评语</h4>
              <button class="tch-link" @click="showSaveComment = !showSaveComment"><UiIcon name="PhPlus" :size="14" />新增</button>
            </div>
            <div v-if="showSaveComment" class="tch-common-add">
              <input v-model="newCommentText" type="text" maxlength="200" placeholder="输入评语后回车保存" @keyup.enter="saveCurrentComment" />
              <button class="primary-button" @click="saveCurrentComment">保存</button>
            </div>
            <EmptyState v-if="!commonComments.length" icon="PhChatCircleText" title="暂无常用评语" compact />
            <ul v-else class="tch-common-list">
              <li v-for="c in commonComments" :key="c.id">
                <button class="tch-common-pick" @click="applyCommonComment(c.text)">{{ c.text }}</button>
                <button class="icon-button" aria-label="移除" @click="removeCommon(c.id)"><UiIcon name="PhX" :size="14" /></button>
              </li>
            </ul>
          </div>
        </section>
      </template>
      <template #footer>
        <button class="secondary-button" @click="showGrade = false">取消</button>
        <button class="primary-button" :disabled="saving || gradeLoading" @click="submitGrade">
          <UiIcon v-if="saving" name="PhCircleNotch" :size="16" />保存成绩
        </button>
      </template>
    </Drawer>
  </main>
</template>