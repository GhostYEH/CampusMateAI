<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useAppStore } from "../../stores/app";
import { useToast, extractErrorMessage } from "../../composables/useToast";
import { updateAdminProfile } from "../../services/adminRepository";

const router = useRouter();
const store = useAppStore();
const toast = useToast();

const saving = ref(false);
const loading = ref(true);
const account = ref(null);
const form = reactive({
  display_name: "",
  college: "",
  major: "",
  grade: "",
});
const formErrors = reactive({});

const session = computed(() => store.session);
const initial = computed(() => (session.value?.name || "师").slice(0, 1));

async function loadAccount() {
  loading.value = true;
  try {
    // 复用与 AdminProfileView 一致的资料保存逻辑：先回填本地 session 信息
    const s = session.value || {};
    form.display_name = s.name || "";
    form.college = s.college || "";
    form.major = s.major || "";
    form.grade = s.grade || "";
    account.value = s;
  } finally {
    loading.value = false;
  }
}

function validate() {
  Object.keys(formErrors).forEach((k) => delete formErrors[k]);
  if (!form.display_name.trim()) formErrors.display_name = "姓名不能为空";
  if (form.display_name.length > 64) formErrors.display_name = "姓名不能超过 64 字";
  if (form.college.length > 128) formErrors.college = "学院不能超过 128 字";
  if (form.major.length > 128) formErrors.major = "专业不能超过 128 字";
  if (form.grade.length > 32) formErrors.grade = "年级不能超过 32 字";
  return Object.keys(formErrors).length === 0;
}

async function save() {
  if (!validate()) return;
  saving.value = true;
  try {
    const updated = await updateAdminProfile({
      display_name: form.display_name.trim(),
      college: form.college.trim() || null,
      major: form.major.trim() || null,
      grade: form.grade.trim() || null,
    });
    // 同步本地 session，保持与 AdminProfileView 一致的行为
    const next = {
      ...(session.value || {}),
      name: updated.display_name || updated.username || session.value?.name,
      display_name: updated.display_name,
      college: updated.college ?? form.college,
      major: updated.major ?? form.major,
      grade: updated.grade ?? form.grade,
      detail: [updated.college, updated.major, updated.grade].filter(Boolean).join(" · ") || session.value?.detail,
    };
    store.session = next;
    localStorage.setItem("campus_session", JSON.stringify(next));
    account.value = next;
    toast.success("资料已保存");
  } catch (err) {
    toast.error(extractErrorMessage(err, "保存失败"));
  } finally {
    saving.value = false;
  }
}

onMounted(loadAccount);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader kicker="个人中心" title="账户资料" subtitle="仅编辑后端真实支持的个人资料字段，保存后立即生效。">
      <template #actions>
        <button class="secondary-button" @click="router.push('/teacher/dashboard')">
          <UiIcon name="PhArrowLeft" :size="16" />返回工作台
        </button>
      </template>
    </PageHeader>

    <div class="tch-profile-grid">
      <aside class="tch-profile-card">
        <div class="tch-profile-identity">
          <div class="tch-profile-avatar">{{ initial }}</div>
          <h2>{{ session?.name || '老师' }}</h2>
          <span class="tch-profile-role"><UiIcon name="PhChalkboardTeacher" :size="13" />教师</span>
        </div>
        <ul class="tch-profile-meta">
          <li><span>账号</span><b>{{ session?.username || '—' }}</b></li>
          <li><span>学院</span><b>{{ account?.college || '—' }}</b></li>
          <li><span>专业</span><b>{{ account?.major || '—' }}</b></li>
          <li><span>年级</span><b>{{ account?.grade || '—' }}</b></li>
        </ul>
      </aside>

      <section class="tch-profile-card">
        <div class="tch-profile-form-head">
          <div>
            <h2>基本资料</h2>
            <p>修改后将同步到学生看到的通知署名与作业发布信息。</p>
          </div>
        </div>
        <form class="tch-form" @submit.prevent="save">
          <label class="tch-field">
            <span>姓名 <em>*</em></span>
            <input v-model="form.display_name" type="text" maxlength="64" placeholder="如：陈老师" />
            <small v-if="formErrors.display_name" class="tch-field-error">{{ formErrors.display_name }}</small>
          </label>
          <div class="tch-form-row">
            <label class="tch-field">
              <span>学院</span>
              <input v-model="form.college" type="text" maxlength="128" placeholder="如：信息工程学院" />
              <small v-if="formErrors.college" class="tch-field-error">{{ formErrors.college }}</small>
            </label>
            <label class="tch-field">
              <span>专业</span>
              <input v-model="form.major" type="text" maxlength="128" placeholder="如：计算机科学与技术" />
              <small v-if="formErrors.major" class="tch-field-error">{{ formErrors.major }}</small>
            </label>
          </div>
          <label class="tch-field">
            <span>年级</span>
            <input v-model="form.grade" type="text" maxlength="32" placeholder="如：2025-2026 秋季" />
            <small v-if="formErrors.grade" class="tch-field-error">{{ formErrors.grade }}</small>
          </label>
        </form>
        <div class="tch-profile-actions">
          <button class="secondary-button" :disabled="saving" @click="router.push('/teacher/dashboard')">取消</button>
          <button class="primary-button" :disabled="saving || loading" @click="save">
            <UiIcon v-if="saving" name="PhCircleNotch" :size="16" />
            {{ saving ? '保存中…' : '保存资料' }}
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
