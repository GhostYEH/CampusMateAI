<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import Skeleton from "../../components/teacher/Skeleton.vue";
import ErrorState from "../../components/teacher/ErrorState.vue";
import EmptyState from "../../components/teacher/EmptyState.vue";
import StatusTag from "../../components/teacher/StatusTag.vue";
import Modal from "../../components/teacher/Modal.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { useConfirm } from "../../composables/useConfirm";
import { getCourse, updateCourse } from "../../services/teacher/courses";
import { createClass, updateClass, resetInviteCode, listMembers, removeMember } from "../../services/teacher/classes";
import { listClassAnnouncements, deleteAnnouncement } from "../../services/teacher/announcements";
import { listClassAssignments } from "../../services/teacher/assignments";
import { copyToClipboard, formatDate } from "../../composables/useFormat";

const route = useRoute();
const router = useRouter();
const teacherStore = useTeacherStore();
const toast = useToast();
const { confirm } = useConfirm();

const courseId = computed(() => route.params.courseId);
const activeTab = ref("overview");
const loading = ref(true);
const error = ref("");
const course = ref(null);
const membersByClass = ref({});
const announcementsByClass = ref({});
const assignmentsByClass = ref({});

const showClassForm = ref(false);
const editingClass = ref(null);
const savingClass = ref(false);
const classForm = reactive({ name: "", class_code: "", description: "", capacity: null });
const classErrors = reactive({});

const tabs = [
  { key: "overview", label: "课程概览", icon: "PhInfo" },
  { key: "classes", label: "教学班", icon: "PhUsers" },
  { key: "students", label: "学生名单", icon: "PhStudent" },
  { key: "announcements", label: "课程通知", icon: "PhMegaphone" },
  { key: "assignments", label: "课程作业", icon: "PhFileText" },
  { key: "data", label: "教学数据", icon: "PhChartBar" },
];

const classes = computed(() => teacherStore.classesOfCourse(courseId.value));

async function load() {
  loading.value = true;
  error.value = "";
  try {
    await teacherStore.loadAll(true);
    course.value = await getCourse(courseId.value);
  } catch (err) {
    error.value = extractErrorMessage(err, "课程详情加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadClassContent(classId) {
  try {
    if (!membersByClass.value[classId]) {
      const m = await listMembers(classId);
      membersByClass.value[classId] = m.items || [];
    }
    if (!announcementsByClass.value[classId]) {
      const a = await listClassAnnouncements(classId);
      announcementsByClass.value[classId] = a.items || [];
    }
    if (!assignmentsByClass.value[classId]) {
      const asg = await listClassAssignments(classId);
      assignmentsByClass.value[classId] = asg.items || [];
    }
  } catch (err) {
    toast.error(extractErrorMessage(err, "班级内容加载失败"));
  }
}

watch(activeTab, async (tab) => {
  if ((tab === "students" || tab === "announcements" || tab === "assignments") && classes.value.length) {
    await Promise.all(classes.value.map((c) => loadClassContent(c.id)));
  }
});

function openCreateClass() {
  editingClass.value = null;
  Object.assign(classForm, { name: "", class_code: "", description: "", capacity: null });
  Object.keys(classErrors).forEach((k) => delete classErrors[k]);
  showClassForm.value = true;
}
function openEditClass(cls) {
  editingClass.value = cls;
  Object.assign(classForm, {
    name: cls.name,
    class_code: cls.class_code || "",
    description: cls.description || "",
    capacity: cls.capacity,
  });
  Object.keys(classErrors).forEach((k) => delete classErrors[k]);
  showClassForm.value = true;
}

function validateClass() {
  Object.keys(classErrors).forEach((k) => delete classErrors[k]);
  if (!classForm.name.trim()) classErrors.name = "班级名称不能为空";
  if (classForm.capacity !== null && classForm.capacity < 1) classErrors.capacity = "容量须为正数";
  return Object.keys(classErrors).length === 0;
}

async function submitClass() {
  if (!validateClass()) return;
  savingClass.value = true;
  try {
    const payload = {
      name: classForm.name.trim(),
      class_code: classForm.class_code.trim() || null,
      description: classForm.description.trim() || null,
      capacity: classForm.capacity ? Number(classForm.capacity) : null,
    };
    if (editingClass.value) {
      await updateClass(editingClass.value.id, payload);
      toast.success("班级已更新");
    } else {
      await createClass(courseId.value, payload);
      toast.success("班级已创建");
    }
    showClassForm.value = false;
    await teacherStore.loadClasses(true);
  } catch (err) {
    toast.error(extractErrorMessage(err, "班级保存失败"));
  } finally {
    savingClass.value = false;
  }
}

async function copyInvite(cls) {
  try {
    await copyToClipboard(cls.invite_code);
    toast.success(`邀请码已复制：${cls.invite_code}`);
  } catch {
    toast.error("复制失败，请手动复制");
  }
}

async function resetInvite(cls) {
  const ok = await confirm({
    title: "重置邀请码",
    message: `将生成新的邀请码，旧邀请码 ${cls.invite_code} 将立即失效。确定继续?`,
    confirmText: "重置",
    danger: true,
  });
  if (!ok) return;
  try {
    await resetInviteCode(cls.id);
    toast.success("邀请码已重置");
    await teacherStore.loadClasses(true);
  } catch (err) {
    toast.error(extractErrorMessage(err, "重置失败"));
  }
}

async function removeStudent(cls, member) {
  const ok = await confirm({
    title: "移除学生",
    message: `确定将 ${member.display_name || member.username} 从「${cls.name}」移除? 该学生将无法再访问此班级内容。`,
    confirmText: "移除",
    danger: true,
  });
  if (!ok) return;
  try {
    await removeMember(cls.id, member.user_id);
    toast.success("学生已移除");
    membersByClass.value[cls.id] = (membersByClass.value[cls.id] || []).filter((m) => m.user_id !== member.user_id);
  } catch (err) {
    toast.error(extractErrorMessage(err, "移除失败"));
  }
}

async function archiveAnnouncement(ann) {
  const ok = await confirm({
    title: "归档通知",
    message: `归档后学生将不再看到此通知。确定归档「${ann.title}」?`,
    confirmText: "归档",
  });
  if (!ok) return;
  try {
    const { updateAnnouncement } = await import("../../services/teacher/announcements");
    await updateAnnouncement(ann.id, { status: "archived" });
    toast.success("通知已归档");
    ann.status = "archived";
  } catch (err) {
    toast.error(extractErrorMessage(err, "归档失败"));
  }
}

const breadcrumbs = computed(() => [
  { label: "课程与班级", to: "/teacher/courses" },
  { label: course.value?.name || "课程详情" },
]);

onMounted(load);
watch(courseId, load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader
      kicker="课程详情"
      :title="course?.name || '加载中…'"
      :subtitle="course?.description || ''"
      :breadcrumbs="breadcrumbs"
      @breadcrumb-click="(c) => c.to && router.push(c.to)"
    >
      <template #actions>
        <button class="secondary-button" @click="router.push('/teacher/courses')"><UiIcon name="PhArrowLeft" :size="16" />返回列表</button>
      </template>
    </PageHeader>

    <Skeleton v-if="loading" :rows="4" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <template v-else-if="course">
      <nav class="tch-tabs">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
          <UiIcon :name="tab.icon" :size="16" /><span>{{ tab.label }}</span>
        </button>
      </nav>

      <section v-show="activeTab === 'overview'" class="tch-tab-panel">
        <div class="tch-overview-grid">
          <div class="tch-panel">
            <h2>课程信息</h2>
            <dl class="tch-info-list">
              <div><dt>课程代码</dt><dd>{{ course.code || "未设置" }}</dd></div>
              <div><dt>学期</dt><dd>{{ course.semester || "未设置" }}</dd></div>
              <div><dt>状态</dt><dd><StatusTag :status="course.status" type="course" /></dd></div>
              <div><dt>课程介绍</dt><dd>{{ course.description || "暂无" }}</dd></div>
            </dl>
          </div>
          <div class="tch-panel">
            <h2>教学班概览</h2>
            <EmptyState v-if="!classes.length" icon="PhUsers" title="暂无教学班" compact>
              <button class="primary-button" @click="openCreateClass">创建班级</button>
            </EmptyState>
            <ul v-else class="tch-class-summary">
              <li v-for="cls in classes" :key="cls.id">
                <strong>{{ cls.name }}</strong>
                <small>邀请码 {{ cls.invite_code }} · 容量 {{ cls.capacity || "不限" }}</small>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'classes'" class="tch-tab-panel">
        <div class="tch-panel-head-row">
          <h2>教学班</h2>
          <button class="primary-button" @click="openCreateClass"><UiIcon name="PhPlus" :size="16" />创建班级</button>
        </div>
        <EmptyState v-if="!classes.length" icon="PhUsers" title="暂无教学班" description="创建班级后可生成邀请码供学生加入。" />
        <div v-else class="tch-class-grid">
          <article v-for="cls in classes" :key="cls.id" class="tch-class-card">
            <div class="tch-class-card-head">
              <h3>{{ cls.name }}</h3>
              <span v-if="cls.class_code" class="tch-class-code-tag">{{ cls.class_code }}</span>
            </div>
            <p>{{ cls.description || "暂无说明" }}</p>
            <div class="tch-invite-box">
              <span class="tch-invite-label">邀请码</span>
              <code>{{ cls.invite_code }}</code>
              <button class="tch-link" @click="copyInvite(cls)"><UiIcon name="PhCopy" :size="14" />复制</button>
              <button class="tch-link" @click="resetInvite(cls)"><UiIcon name="PhArrowClockwise" :size="14" />重置</button>
            </div>
            <div class="tch-class-card-stats">
              <span>容量 {{ cls.capacity || "不限" }}</span>
              <span>已加入 {{ membersByClass[cls.id]?.length || 0 }} 人</span>
            </div>
            <div class="tch-class-card-actions">
              <button class="secondary-button" @click="activeTab = 'students'">查看名单</button>
              <button class="icon-button" @click="openEditClass(cls)" aria-label="编辑"><UiIcon name="PhPencil" :size="16" /></button>
            </div>
          </article>
        </div>
      </section>

      <section v-show="activeTab === 'students'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>学生名单</h2></div>
        <EmptyState v-if="!classes.length" icon="PhStudent" title="暂无班级" />
        <div v-else class="tch-class-students">
          <div v-for="cls in classes" :key="cls.id" class="tch-panel">
            <h3>{{ cls.name }} <small>{{ (membersByClass[cls.id] || []).filter(m => m.member_role === 'student').length }} 名学生</small></h3>
            <EmptyState v-if="!(membersByClass[cls.id]?.length)" icon="PhStudent" title="暂无学生" description="将邀请码分享给学生加入。" compact />
            <div v-else class="tch-table-wrap">
              <div class="tch-table-scroll" style="min-width: 560px">
                <table class="tch-table">
                  <thead><tr><th>学号</th><th>姓名</th><th>学院</th><th>专业</th><th>操作</th></tr></thead>
                  <tbody>
                    <tr v-for="m in membersByClass[cls.id].filter(x => x.member_role === 'student')" :key="m.user_id">
                      <td>{{ m.student_number || m.username }}</td>
                      <td>{{ m.display_name || m.username }}</td>
                      <td>{{ m.college || "—" }}</td>
                      <td>{{ m.major || "—" }}</td>
                      <td><button class="tch-link danger" @click="removeStudent(cls, m)"><UiIcon name="PhTrash" :size="14" />移除</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'announcements'" class="tch-tab-panel">
        <div class="tch-panel-head-row">
          <h2>课程通知</h2>
          <button class="primary-button" @click="router.push('/teacher/announcements')"><UiIcon name="PhPlus" :size="16" />发布通知</button>
        </div>
        <EmptyState v-if="!classes.length" icon="PhMegaphone" title="暂无班级" />
        <div v-else class="tch-class-students">
          <div v-for="cls in classes" :key="cls.id" class="tch-panel">
            <h3>{{ cls.name }}</h3>
            <EmptyState v-if="!(announcementsByClass[cls.id]?.length)" icon="PhMegaphone" title="暂无通知" compact />
            <ul v-else class="tch-ann-list">
              <li v-for="ann in announcementsByClass[cls.id]" :key="ann.id">
                <div class="tch-ann-line-main">
                  <strong>{{ ann.title }}</strong>
                  <small>{{ formatDate(ann.published_at || ann.created_at) }}</small>
                </div>
                <StatusTag :status="ann.status" type="announcement" />
                <button v-if="ann.status === 'published'" class="tch-link" @click="archiveAnnouncement(ann)">归档</button>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'assignments'" class="tch-tab-panel">
        <div class="tch-panel-head-row">
          <h2>课程作业</h2>
          <button class="primary-button" @click="router.push('/teacher/assignments')"><UiIcon name="PhPlus" :size="16" />布置作业</button>
        </div>
        <EmptyState v-if="!classes.length" icon="PhFileText" title="暂无班级" />
        <div v-else class="tch-class-students">
          <div v-for="cls in classes" :key="cls.id" class="tch-panel">
            <h3>{{ cls.name }}</h3>
            <EmptyState v-if="!(assignmentsByClass[cls.id]?.length)" icon="PhFileText" title="暂无作业" compact />
            <ul v-else class="tch-ann-list">
              <li v-for="asg in assignmentsByClass[cls.id]" :key="asg.id">
                <button class="tch-ann-line-main clickable" @click="router.push(`/teacher/assignments/${asg.id}`)">
                  <strong>{{ asg.title }}</strong>
                  <small>截止 {{ formatDate(asg.deadline) }}</small>
                </button>
                <StatusTag :status="asg.status" type="assignment" />
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'data'" class="tch-tab-panel">
        <div class="tch-panel-head-row"><h2>教学数据</h2></div>
        <div class="tch-panel">
          <p class="tch-hint">该课程的综合学情分析请在学情分析页查看。</p>
          <button class="primary-button" @click="router.push('/teacher/analytics')"><UiIcon name="PhChartBar" :size="16" />前往学情分析</button>
        </div>
      </section>
    </template>

    <Modal :open="showClassForm" :title="editingClass ? '编辑班级' : '创建班级'" size="regular" @update:open="showClassForm = $event">
      <form class="tch-form" @submit.prevent="submitClass">
        <label class="tch-field">
          <span>班级名称 <em>*</em></span>
          <input v-model="classForm.name" type="text" maxlength="128" placeholder="如：计科1班" />
          <small v-if="classErrors.name" class="tch-field-error">{{ classErrors.name }}</small>
        </label>
        <div class="tch-form-row">
          <label class="tch-field">
            <span>班级代码</span>
            <input v-model="classForm.class_code" type="text" maxlength="64" placeholder="如：CS201-CLS1" />
          </label>
          <label class="tch-field">
            <span>容量</span>
            <input v-model.number="classForm.capacity" type="number" min="1" max="1000" placeholder="不限请留空" />
            <small v-if="classErrors.capacity" class="tch-field-error">{{ classErrors.capacity }}</small>
          </label>
        </div>
        <label class="tch-field">
          <span>班级说明</span>
          <textarea v-model="classForm.description" rows="2" maxlength="2000"></textarea>
        </label>
      </form>
      <template #footer>
        <button class="secondary-button" @click="showClassForm = false">取消</button>
        <button class="primary-button" :disabled="savingClass" @click="submitClass">
          <UiIcon v-if="savingClass" name="PhCircleNotch" :size="16" />
          {{ savingClass ? "保存中…" : (editingClass ? "保存修改" : "创建班级") }}
        </button>
      </template>
    </Modal>
  </main>
</template>