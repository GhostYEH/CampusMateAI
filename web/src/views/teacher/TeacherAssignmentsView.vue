<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import FilterBar from "../../components/teacher/FilterBar.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import Modal from "../../components/teacher/Modal.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { useConfirm } from "../../composables/useConfirm";
import {
  listTeacherAssignments, createAssignment, updateAssignment,
  publishAssignment, closeAssignment, archiveAssignment,
  uploadAssignmentAttachment, listAssignmentAttachments, buildAttachmentDownloadUrl,
} from "../../services/teacher/assignments";
import {
  formatDate, formatDateTime, toLocalDatetimeInput, fromLocalDatetimeInput,
  formatFileSize, daysUntil, isOverdue,
} from "../../composables/useFormat";

const router = useRouter();
const teacherStore = useTeacherStore();
const toast = useToast();
const { confirm } = useConfirm();

const loading = ref(true);
const error = ref("");
const items = ref([]);
const total = ref(0);
const query = ref("");
const statusFilter = ref("");
const classFilter = ref("");
const courseFilter = ref("");

const showForm = ref(false);
const editing = ref(null);
const saving = ref(false);
const form = reactive({
  title: "", description: "", class_group_id: "",
  deadlineLocal: "", full_score: 100, allow_late: true,
});
const formErrors = reactive({});

const showAttachments = ref(false);
const attachmentItem = ref(null);
const attachments = ref([]);
const attachmentLoading = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const fileInput = ref(null);

const classOptions = computed(() => teacherStore.classOptionsWithCourse());

const filterConfig = computed(() => [
  {
    key: "status", label: "状态", value: statusFilter.value,
    options: [
      { value: "draft", label: "草稿" },
      { value: "published", label: "进行中" },
      { value: "closed", label: "已结束" },
      { value: "archived", label: "已归档" },
    ],
  },
  {
    key: "course", label: "课程", value: courseFilter.value,
    options: teacherStore.courses.map((c) => ({ value: c.id, label: c.name })),
  },
  {
    key: "class", label: "班级", value: classFilter.value,
    options: classOptions.value.map((c) => ({ value: c.id, label: `${c.course?.name || ""} / ${c.name}` })),
  },
]);

function onFiltersChange(next) {
  next.forEach((f) => {
    if (f.key === "status") statusFilter.value = f.value;
    if (f.key === "course") courseFilter.value = f.value;
    if (f.key === "class") classFilter.value = f.value;
  });
  load();
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    await teacherStore.loadAll().catch(() => null);
    const params = {};
    if (statusFilter.value) params.status = statusFilter.value;
    if (classFilter.value) params.class_id = classFilter.value;
    if (courseFilter.value) params.course_id = courseFilter.value;
    if (query.value) params.search = query.value;
    const page = await listTeacherAssignments(params);
    items.value = page.items || [];
    total.value = page.total || 0;
  } catch (err) {
    error.value = extractErrorMessage(err, "作业加载失败");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editing.value = null;
  Object.assign(form, {
    title: "", description: "", class_group_id: classOptions.value[0]?.id || "",
    deadlineLocal: "", full_score: 100, allow_late: true,
  });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}

async function openEdit(item) {
  editing.value = item;
  Object.assign(form, {
    title: item.title,
    description: item.description || "",
    class_group_id: item.class_group_id,
    deadlineLocal: toLocalDatetimeInput(item.deadline),
    full_score: item.full_score ?? 100,
    allow_late: item.allow_late ?? true,
  });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}

function validate() {
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  if (!form.title.trim()) formErrors.title = "标题不能为空";
  if (form.title.length > 200) formErrors.title = "标题不能超过 200 字";
  if (form.description.length > 5000) formErrors.description = "描述不能超过 5000 字";
  if (!form.class_group_id) formErrors.class_group_id = "请选择班级";
  if (form.full_score === "" || form.full_score === null) formErrors.full_score = "请输入满分";
  else {
    const fs = Number(form.full_score);
    if (!Number.isFinite(fs) || fs <= 0) formErrors.full_score = "满分须为正数";
    else if (fs > 1000) formErrors.full_score = "满分不能超过 1000";
  }
  return Object.keys(formErrors).length === 0;
}

async function submit(publishNow = false) {
  if (!validate()) return;
  saving.value = true;
  try {
    const payload = {
      title: form.title.trim(),
      description: form.description.trim(),
      deadline: fromLocalDatetimeInput(form.deadlineLocal),
      full_score: Number(form.full_score),
      allow_late: form.allow_late,
    };
    if (editing.value) {
      await updateAssignment(editing.value.id, payload);
      if (publishNow && editing.value.status === "draft") {
        await publishAssignment(editing.value.id);
      }
      toast.success(publishNow ? "作业已发布" : "作业已保存");
    } else {
      const created = await createAssignment(form.class_group_id, payload);
      if (publishNow) await publishAssignment(created.id);
      toast.success(publishNow ? "作业已发布" : "作业草稿已保存");
    }
    showForm.value = false;
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "作业保存失败"));
  } finally {
    saving.value = false;
  }
}

async function publish(item) {
  const ok = await confirm({
    title: "发布作业",
    message: `发布后「${item.title}」将立即对学生可见。确定发布?`,
    confirmText: "发布",
  });
  if (!ok) return;
  try {
    await publishAssignment(item.id);
    toast.success("作业已发布");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "发布失败"));
  }
}

async function close(item) {
  const ok = await confirm({
    title: "结束作业",
    message: `结束后学生将不能再提交「${item.title}」。确定结束?`,
    confirmText: "结束",
  });
  if (!ok) return;
  try {
    await closeAssignment(item.id);
    toast.success("作业已结束");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "结束失败"));
  }
}

async function archive(item) {
  const ok = await confirm({
    title: "归档作业", message: `归档后作业将不再出现在学生列表。确定归档「${item.title}」?`, confirmText: "归档",
  });
  if (!ok) return;
  try {
    await archiveAssignment(item.id);
    toast.success("作业已归档");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "归档失败"));
  }
}

async function openAttachments(item) {
  attachmentItem.value = item;
  attachments.value = [];
  showAttachments.value = true;
  attachmentLoading.value = true;
  try {
    const data = await listAssignmentAttachments(item.id);
    attachments.value = Array.isArray(data) ? data : (data.items || []);
  } catch (err) {
    toast.error(extractErrorMessage(err, "附件列表加载失败"));
  } finally {
    attachmentLoading.value = false;
  }
}

function triggerUpload() {
  fileInput.value?.click();
}

async function onFileChange(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (!attachmentItem.value) return;
  if (file.size > 20 * 1024 * 1024) {
    toast.error("附件不能超过 20MB");
    event.target.value = "";
    return;
  }
  uploading.value = true;
  uploadProgress.value = 0;
  try {
    await uploadAssignmentAttachment(attachmentItem.value.id, file, (p) => { uploadProgress.value = p; });
    toast.success("附件已上传");
    const data = await listAssignmentAttachments(attachmentItem.value.id);
    attachments.value = Array.isArray(data) ? data : (data.items || []);
  } catch (err) {
    toast.error(extractErrorMessage(err, "上传失败"));
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
    event.target.value = "";
  }
}

const submitRate = (item) => {
  const totalStudents = item.total_students ?? item.student_count ?? 0;
  if (!totalStudents) return null;
  const submitted = item.submitted_count ?? 0;
  return Math.round((submitted / totalStudents) * 100);
};

const deadlineHint = (item) => {
  if (!item.deadline) return "无截止";
  if (isOverdue(item.deadline)) return "已截止";
  const d = daysUntil(item.deadline);
  if (d === 0) return "今日截止";
  if (d === 1) return "明日截止";
  return `${d} 天后截止`;
};

onMounted(load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="作业管理" title="作业列表" subtitle="布置、发布、跟进作业，管理附件与学生提交。">
      <template #actions>
        <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />布置作业</button>
      </template>
    </PageHeader>

    <FilterBar
      v-model="query"
      :filters="filterConfig"
      search-placeholder="搜索作业标题或描述"
      @update:filters="onFiltersChange"
      @search="load"
    />

    <Skeleton v-if="loading" :rows="6" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!items.length" icon="PhFileText" title="暂无作业" description="布置第一项作业开始跟进学生提交。">
      <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />布置作业</button>
    </EmptyState>
    <section v-else class="tch-panel">
      <div class="tch-table-wrap">
        <div class="tch-table-scroll" style="min-width: 980px">
          <table class="tch-table">
            <thead>
              <tr>
                <th>标题</th><th>课程 / 班级</th><th>状态</th><th>截止</th><th>提交情况</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id">
                <td>
                  <button class="tch-link strong" @click="router.push(`/teacher/assignments/${item.id}`)">{{ item.title }}</button>
                </td>
                <td><small>{{ item.course_name }} / {{ item.class_name }}</small></td>
                <td><StatusTag :status="item.status" type="assignment" /></td>
                <td>
                  <small>{{ formatDate(item.deadline) }}</small>
                  <em v-if="item.deadline" class="tch-deadline-hint">{{ deadlineHint(item) }}</em>
                </td>
                <td>
                  <template v-if="item.status !== 'draft'">
                    {{ item.submitted_count ?? 0 }}/{{ item.total_students ?? item.student_count ?? 0 }}
                    <small v-if="submitRate(item) !== null">（{{ submitRate(item) }}%）</small>
                  </template>
                  <span v-else>—</span>
                </td>
                <td>
                  <div class="tch-row-actions">
                    <button class="tch-link" @click="router.push(`/teacher/assignments/${item.id}`)">详情</button>
                    <button class="tch-link" @click="openAttachments(item)"><UiIcon name="PhPaperclip" :size="14" />附件</button>
                    <button v-if="item.status === 'draft'" class="tch-link" @click="publish(item)">发布</button>
                    <button class="tch-link" @click="openEdit(item)">编辑</button>
                    <button v-if="item.status === 'published'" class="tch-link" @click="close(item)">结束</button>
                    <button v-if="item.status === 'closed' || item.status === 'published'" class="tch-link" @click="archive(item)">归档</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <Modal :open="showForm" :title="editing ? '编辑作业' : '布置作业'" size="wide" @update:open="showForm = $event">
      <form class="tch-form" @submit.prevent="submit(false)">
        <label class="tch-field">
          <span>布置班级 <em>*</em></span>
          <select v-model="form.class_group_id" :disabled="!!editing">
            <option value="">请选择班级</option>
            <option v-for="cls in classOptions" :key="cls.id" :value="cls.id">{{ cls.course?.name }} / {{ cls.name }}</option>
          </select>
          <small v-if="formErrors.class_group_id" class="tch-field-error">{{ formErrors.class_group_id }}</small>
        </label>
        <label class="tch-field">
          <span>作业标题 <em>*</em></span>
          <input v-model="form.title" type="text" maxlength="200" placeholder="如：第三章习题集" />
          <small v-if="formErrors.title" class="tch-field-error">{{ formErrors.title }}</small>
        </label>
        <label class="tch-field">
          <span>作业描述</span>
          <textarea v-model="form.description" rows="6" maxlength="5000" placeholder="作业要求、提交格式、注意事项等"></textarea>
          <small v-if="formErrors.description" class="tch-field-error">{{ formErrors.description }}</small>
        </label>
        <div class="tch-form-row">
          <label class="tch-field">
            <span>截止时间</span>
            <input v-model="form.deadlineLocal" type="datetime-local" />
          </label>
          <label class="tch-field">
            <span>满分分值 <em>*</em></span>
            <input v-model="form.full_score" type="number" min="1" max="1000" step="1" />
            <small v-if="formErrors.full_score" class="tch-field-error">{{ formErrors.full_score }}</small>
          </label>
        </div>
        <label class="tch-field-inline">
          <input type="checkbox" v-model="form.allow_late" />
          <span>允许迟交（迟交会标记但不拒绝）</span>
        </label>
      </form>
      <template #footer>
        <button class="secondary-button" @click="showForm = false">取消</button>
        <button class="secondary-button" :disabled="saving" @click="submit(false)">
          <UiIcon v-if="saving" name="PhCircleNotch" :size="16" />保存草稿
        </button>
        <button class="primary-button" :disabled="saving" @click="submit(true)">
          <UiIcon name="PhPaperPlaneTilt" :size="16" />{{ editing ? "保存并发布" : "发布" }}
        </button>
      </template>
    </Modal>

    <Drawer :open="showAttachments" :title="attachmentItem?.title || '作业附件'" width="regular" @update:open="showAttachments = $event">
      <template v-if="attachmentItem">
        <div class="tch-attach-head">
          <p class="tch-hint">单个附件不超过 20MB。附件对学生可见。</p>
          <button class="primary-button" :disabled="uploading" @click="triggerUpload">
            <UiIcon name="PhUpload" :size="16" />上传附件
          </button>
          <input ref="fileInput" type="file" class="visually-hidden" @change="onFileChange" />
        </div>
        <div v-if="uploading" class="tch-upload-progress">
          <UiIcon name="PhCircleNotch" :size="16" />
          <span>上传中 {{ uploadProgress }}%</span>
        </div>
        <div v-if="attachmentLoading" class="tch-detail-loading"><UiIcon name="PhCircleNotch" :size="20" /> 加载中…</div>
        <EmptyState v-else-if="!attachments.length" icon="PhPaperclip" title="暂无附件" compact />
        <ul v-else class="tch-attach-list">
          <li v-for="att in attachments" :key="att.id">
            <UiIcon name="PhFile" :size="18" />
            <div class="tch-attach-info">
              <strong>{{ att.filename || att.name }}</strong>
              <small>{{ formatFileSize(att.size || att.file_size) }} · {{ formatDateTime(att.created_at) }}</small>
            </div>
            <a class="tch-link" :href="buildAttachmentDownloadUrl(attachmentItem.id, att.id)" target="_blank" rel="noopener">
              <UiIcon name="PhDownloadSimple" :size="14" />下载
            </a>
          </li>
        </ul>
      </template>
    </Drawer>
  </main>
</template>