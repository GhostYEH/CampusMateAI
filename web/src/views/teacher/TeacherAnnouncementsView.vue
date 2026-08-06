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
import Drawer from "../../components/teacher/Drawer.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useTeacherStore } from "../../stores/teacher";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { useConfirm } from "../../composables/useConfirm";
import {
  listTeacherAnnouncements, createAnnouncement, updateAnnouncement,
  publishAnnouncement, deleteAnnouncement, getReadStatus,
} from "../../services/teacher/announcements";
import { formatDate, formatDateTime } from "../../composables/useFormat";

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
const form = reactive({ title: "", content: "", require_read: false, status: "draft", class_group_id: "" });
const formErrors = reactive({});

const showDetail = ref(false);
const detailItem = ref(null);
const detailReadStatus = ref(null);
const detailLoading = ref(false);

const classOptions = computed(() => teacherStore.classOptionsWithCourse());

const filterConfig = computed(() => [
  {
    key: "status", label: "状态", value: statusFilter.value,
    options: [
      { value: "draft", label: "草稿" },
      { value: "published", label: "已发布" },
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
    const page = await listTeacherAnnouncements(params);
    items.value = page.items || [];
    total.value = page.total || 0;
  } catch (err) {
    error.value = extractErrorMessage(err, "通知加载失败");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editing.value = null;
  Object.assign(form, { title: "", content: "", require_read: false, status: "draft", class_group_id: classOptions.value[0]?.id || "" });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}
function openEdit(item) {
  editing.value = item;
  Object.assign(form, {
    title: item.title, content: item.content, require_read: item.require_read,
    status: item.status, class_group_id: item.class_group_id,
  });
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  showForm.value = true;
}

function validate() {
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  if (!form.title.trim()) formErrors.title = "标题不能为空";
  if (form.title.length > 200) formErrors.title = "标题不能超过 200 字";
  if (!form.content.trim()) formErrors.content = "内容不能为空";
  if (form.content.length > 20000) formErrors.content = "内容不能超过 20000 字";
  if (!form.class_group_id) formErrors.class_group_id = "请选择班级";
  return Object.keys(formErrors).length === 0;
}

async function submit(publishNow = false) {
  if (!validate()) return;
  saving.value = true;
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      require_read: form.require_read,
      status: publishNow ? "published" : form.status,
    };
    let result;
    if (editing.value) {
      result = await updateAnnouncement(editing.value.id, payload);
      toast.success(publishNow ? "通知已发布" : "通知已保存");
    } else {
      result = await createAnnouncement(form.class_group_id, payload);
      toast.success(publishNow ? "通知已发布" : "通知草稿已保存");
    }
    showForm.value = false;
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "通知保存失败"));
  } finally {
    saving.value = false;
  }
}

async function publish(item) {
  const ok = await confirm({
    title: "发布通知",
    message: `发布后「${item.title}」将立即对学生可见。确定发布?`,
    confirmText: "发布",
  });
  if (!ok) return;
  try {
    await publishAnnouncement(item.id);
    toast.success("通知已发布");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "发布失败"));
  }
}

async function archive(item) {
  const ok = await confirm({
    title: "归档通知", message: `归档后学生将不再看到此通知。确定归档?`, confirmText: "归档",
  });
  if (!ok) return;
  try {
    await updateAnnouncement(item.id, { status: "archived" });
    toast.success("通知已归档");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "归档失败"));
  }
}

async function remove(item) {
  const ok = await confirm({
    title: "删除通知", message: `删除后不可恢复。确定删除「${item.title}」?`, confirmText: "删除", danger: true,
  });
  if (!ok) return;
  try {
    await deleteAnnouncement(item.id);
    toast.success("通知已删除");
    await load();
  } catch (err) {
    toast.error(extractErrorMessage(err, "删除失败"));
  }
}

async function openDetail(item) {
  detailItem.value = item;
  detailReadStatus.value = null;
  showDetail.value = true;
  if (item.status === "published") {
    detailLoading.value = true;
    try {
      detailReadStatus.value = await getReadStatus(item.id);
    } catch (err) {
      toast.error(extractErrorMessage(err, "已读统计加载失败"));
    } finally {
      detailLoading.value = false;
    }
  }
}

const readRate = (item) => {
  if (!item.total_recipients) return null;
  return Math.round((item.read_count / item.total_recipients) * 100);
};

onMounted(load);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="通知中心" title="通知管理" subtitle="向教学班发布通知，查看已读统计与未读名单。">
      <template #actions>
        <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />发布通知</button>
      </template>
    </PageHeader>

    <FilterBar
      v-model="query"
      :filters="filterConfig"
      search-placeholder="搜索通知标题或内容"
      @update:filters="onFiltersChange"
      @search="load"
    />

    <Skeleton v-if="loading" :rows="6" layout="grid" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!items.length" icon="PhMegaphone" title="暂无通知" description="发布第一条通知开始与学生同步信息。">
      <button class="primary-button" @click="openCreate"><UiIcon name="PhPlus" :size="18" />发布通知</button>
    </EmptyState>
    <section v-else class="tch-panel">
      <div class="tch-table-wrap">
        <div class="tch-table-scroll">
          <table class="tch-table" style="min-width: 880px">
            <thead>
              <tr>
                <th>标题</th><th>课程 / 班级</th><th>状态</th><th>已读</th><th>发布时间</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id">
                <td><strong>{{ item.title }}</strong></td>
                <td><small>{{ item.course_name }} / {{ item.class_name }}</small></td>
                <td><StatusTag :status="item.status" type="announcement" /></td>
                <td>
                  <template v-if="item.status === 'published'">
                    {{ item.read_count }}/{{ item.total_recipients }}
                    <small v-if="readRate(item) !== null">（{{ readRate(item) }}%）</small>
                  </template>
                  <span v-else>—</span>
                </td>
                <td><small>{{ formatDate(item.published_at || item.created_at) }}</small></td>
                <td>
                  <div class="tch-row-actions">
                    <button class="tch-link" @click="openDetail(item)">详情</button>
                    <button v-if="item.status === 'draft'" class="tch-link" @click="publish(item)">发布</button>
                    <button class="tch-link" @click="openEdit(item)">编辑</button>
                    <button v-if="item.status === 'published'" class="tch-link" @click="archive(item)">归档</button>
                    <button v-if="item.status !== 'published'" class="tch-link danger" @click="remove(item)">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <Modal :open="showForm" :title="editing ? '编辑通知' : '发布通知'" size="wide" @update:open="showForm = $event">
      <form class="tch-form" @submit.prevent="submit(false)">
        <label class="tch-field">
          <span>发布班级 <em>*</em></span>
          <select v-model="form.class_group_id" :disabled="!!editing">
            <option value="">请选择班级</option>
            <option v-for="cls in classOptions" :key="cls.id" :value="cls.id">{{ cls.course?.name }} / {{ cls.name }}</option>
          </select>
          <small v-if="formErrors.class_group_id" class="tch-field-error">{{ formErrors.class_group_id }}</small>
        </label>
        <label class="tch-field">
          <span>标题 <em>*</em></span>
          <input v-model="form.title" type="text" maxlength="200" />
          <small v-if="formErrors.title" class="tch-field-error">{{ formErrors.title }}</small>
        </label>
        <label class="tch-field">
          <span>内容 <em>*</em></span>
          <textarea v-model="form.content" rows="6" maxlength="20000"></textarea>
          <small v-if="formErrors.content" class="tch-field-error">{{ formErrors.content }}</small>
        </label>
        <label class="tch-field-inline">
          <input type="checkbox" v-model="form.require_read" />
          <span>要求学生确认已读</span>
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

    <Drawer :open="showDetail" :title="detailItem?.title || '通知详情'" width="wide" @update:open="showDetail = $event">
      <template v-if="detailItem">
        <div class="tch-detail-meta">
          <span><UiIcon name="PhBookOpen" :size="14" />{{ detailItem.course_name }} / {{ detailItem.class_name }}</span>
          <StatusTag :status="detailItem.status" type="announcement" />
          <span>{{ formatDateTime(detailItem.published_at || detailItem.created_at) }}</span>
        </div>
        <article class="tch-detail-content">{{ detailItem.content }}</article>

        <div v-if="detailItem.status === 'published'" class="tch-read-stats">
          <h3>已读统计</h3>
          <div v-if="detailLoading" class="tch-detail-loading"><UiIcon name="PhCircleNotch" :size="20" /> 加载中…</div>
          <template v-else-if="detailReadStatus">
            <div class="tch-read-summary">
              <span><strong>{{ detailReadStatus.read_count }}</strong> 已读</span>
              <span><strong>{{ detailReadStatus.unread_count }}</strong> 未读</span>
              <span><strong>{{ detailReadStatus.total_recipients ? Math.round(detailReadStatus.read_count / detailReadStatus.total_recipients * 100) : 0 }}%</strong> 已读率</span>
            </div>
            <div class="tch-read-lists">
              <div class="tch-read-list">
                <h4>已读名单</h4>
                <ul>
                  <li v-for="r in detailReadStatus.receipts" :key="r.user_id">{{ r.display_name || r.username }} <small>{{ r.student_number }}</small></li>
                  <li v-if="!detailReadStatus.receipts.length" class="muted">暂无</li>
                </ul>
              </div>
              <div class="tch-read-list">
                <h4>未读名单</h4>
                <ul>
                  <li v-for="name in (detailReadStatus.unread_names || [])" :key="name">{{ name }}</li>
                  <li v-if="!(detailReadStatus.unread_names || []).length" class="muted">暂无或未提供名单</li>
                </ul>
              </div>
            </div>
          </template>
        </div>
      </template>
    </Drawer>
  </main>
</template>