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
import { listCourses, createCourse, updateCourse } from "../../services/teacher/courses";

const router = useRouter();
const teacherStore = useTeacherStore();
const toast = useToast();
const { confirm } = useConfirm();

const loading = ref(true);
const error = ref("");
const query = ref("");
const semesterFilter = ref("");
const statusFilter = ref("");
const showForm = ref(false);
const editing = ref(null);
const saving = ref(false);
const form = reactive({
  name: "",
  code: "",
  semester: "",
  description: "",
  status: "active",
});
const formErrors = reactive({});

const courses = computed(() => teacherStore.courses);
const semesters = computed(() => {
  const set = new Set();
  courses.value.forEach((c) => { if (c.semester) set.add(c.semester); });
  return Array.from(set);
});
const filtered = computed(() => courses.value.filter((c) => {
  if (query.value) {
    const q = query.value.toLowerCase();
    if (!(`${c.name}${c.code || ""}${c.description || ""}`.toLowerCase().includes(q))) return false;
  }
  if (semesterFilter.value && c.semester !== semesterFilter.value) return false;
  if (statusFilter.value && c.status !== statusFilter.value) return false;
  return true;
}));

const filterConfig = computed(() => [
  {
    key: "semester", label: "学期", value: semesterFilter.value,
    options: semesters.value.map((s) => ({ value: s, label: s })),
  },
  {
    key: "status", label: "状态", value: statusFilter.value,
    options: [
      { value: "active", label: "进行中" },
      { value: "draft", label: "未发布" },
      { value: "archived", label: "已归档" },
    ],
  },
]);

function onFiltersChange(next) {
  next.forEach((f) => {
    if (f.key === "semester") semesterFilter.value = f.value;
    if (f.key === "status") statusFilter.value = f.value;
  });
}

function openCreate() {
  editing.value = null;
  Object.assign(form, { name: "", code: "", semester: "", description: "", status: "active" });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}
function openEdit(course) {
  editing.value = course;
  Object.assign(form, {
    name: course.name,
    code: course.code || "",
    semester: course.semester || "",
    description: course.description || "",
    status: course.status,
  });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}

function validate() {
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  if (!form.name.trim()) formErrors.name = "课程名称不能为空";
  if (form.name.length > 128) formErrors.name = "课程名称不能超过 128 字";
  return Object.keys(formErrors).length === 0;
}

async function submit() {
  if (!validate()) return;
  saving.value = true;
  try {
    const payload = {
      name: form.name.trim(),
      code: form.code.trim() || null,
      semester: form.semester.trim() || null,
      description: form.description.trim() || null,
      status: form.status,
    };
    if (editing.value) {
      await updateCourse(editing.value.id, payload);
      toast.success("课程已更新");
    } else {
      await createCourse(payload);
      toast.success("课程已创建");
    }
    showForm.value = false;
    await teacherStore.loadCourses(true);
  } catch (err) {
    toast.error(extractErrorMessage(err, "课程保存失败"));
  } finally {
    saving.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    await teacherStore.loadCourses(true);
    await teacherStore.loadClasses(true);
  } catch (err) {
    error.value = extractErrorMessage(err, "课程加载失败");
  } finally {
    loading.value = false;
  }
}

function classCount(courseId) {
  return teacherStore.classesOfCourse(courseId).length;
}
function studentCount(courseId) {
  return teacherStore.classesOfCourse(courseId).reduce((sum, c) => sum + (c.capacity || 0), 0);
}

onMounted(load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="课程与班级" title="我的课程" subtitle="查看本学期负责的课程与教学班，点击进入详情管理。">
      <template #actions>
        <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />创建课程</button>
      </template>
    </PageHeader>

    <FilterBar
      v-model="query"
      :filters="filterConfig"
      search-placeholder="搜索课程名称、代码或描述"
      @update:filters="onFiltersChange"
    />

    <Skeleton v-if="loading" :rows="6" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!filtered.length" icon="PhBookOpen" title="暂无课程" description="创建第一门课程开始管理教学班。">
      <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />创建课程</button>
    </EmptyState>
    <section v-else class="tch-course-grid">
      <article v-for="course in filtered" :key="course.id" class="tch-course-card" @click="router.push(`/teacher/courses/${course.id}`)">
        <div class="tch-course-monogram">{{ course.code?.slice(0, 2) || "课" }}</div>
        <div class="tch-course-meta">
          <span class="tch-course-semester">{{ course.semester || "当前学期" }}</span>
          <StatusTag :status="course.status" type="course" />
        </div>
        <h2>{{ course.name }}</h2>
        <p>{{ course.description || "暂无课程介绍" }}</p>
        <div class="tch-course-stats">
          <span><UiIcon name="PhUsers" :size="14" />{{ classCount(course.id) }} 个教学班</span>
          <span><UiIcon name="PhStudent" :size="14" />约 {{ studentCount(course.id) }} 人</span>
        </div>
        <div class="tch-course-actions" @click.stop>
          <button class="tch-link" @click="router.push(`/teacher/courses/${course.id}`)">查看详情<UiIcon name="PhCaretRight" :size="14" /></button>
          <button class="icon-button" @click="openEdit(course)" aria-label="编辑"><UiIcon name="PhPencil" :size="16" /></button>
        </div>
      </article>
    </section>

    <Modal :open="showForm" :title="editing ? '编辑课程' : '创建课程'" size="regular" @update:open="showForm = $event">
      <form class="tch-form" @submit.prevent="submit">
        <label class="tch-field">
          <span>课程名称 <em>*</em></span>
          <input v-model="form.name" type="text" maxlength="128" placeholder="如：数据结构" />
          <small v-if="formErrors.name" class="tch-field-error">{{ formErrors.name }}</small>
        </label>
        <div class="tch-form-row">
          <label class="tch-field">
            <span>课程代码</span>
            <input v-model="form.code" type="text" maxlength="64" placeholder="如：CS201" />
          </label>
          <label class="tch-field">
            <span>学期</span>
            <input v-model="form.semester" type="text" maxlength="32" placeholder="如：2025-2026秋季" />
          </label>
        </div>
        <label class="tch-field">
          <span>课程介绍</span>
          <textarea v-model="form.description" rows="3" maxlength="2000" placeholder="简要描述课程内容"></textarea>
        </label>
        <label class="tch-field">
          <span>状态</span>
          <select v-model="form.status">
            <option value="active">进行中</option>
            <option value="draft">未发布</option>
            <option value="archived">已归档</option>
          </select>
        </label>
      </form>
      <template #footer>
        <button class="secondary-button" @click="showForm = false">取消</button>
        <button class="primary-button" :disabled="saving" @click="submit">
          <UiIcon v-if="saving" name="PhCircleNotch" :size="16" />
          {{ saving ? "保存中…" : (editing ? "保存修改" : "创建课程") }}
        </button>
      </template>
    </Modal>
  </main>
</template>