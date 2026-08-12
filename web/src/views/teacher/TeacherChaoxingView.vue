<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import PageHeader from "../../components/teacher/PageHeader.vue";
import UiIcon from "../../components/UiIcon.vue";
import { useToast } from "../../composables/useToast";
import { formatDateTime } from "../../composables/useFormat";
import {
  getChaoxingStatus,
  syncChaoxing,
  disconnectChaoxing,
} from "../../services/teacher/chaoxing";

const router = useRouter();
const toast = useToast();

const status = ref("offline");
const lastSyncedAt = ref(null);
const isChecking = ref(true);
const isSyncing = ref(false);
const isDisconnecting = ref(false);
const syncResult = ref(null);
const syncResultTone = ref("info");

const statusTextMap = {
  online: "已连接",
  offline: "未连接",
  expired: "登录已失效",
  unavailable: "暂不可用",
};
const statusToneMap = {
  online: "primary",
  expired: "danger",
  unavailable: "muted",
  offline: "muted",
};

function errorDetail(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return err?.message || "";
}

async function checkStatus() {
  isChecking.value = true;
  try {
    const data = await getChaoxingStatus();
    status.value = data.status || "offline";
    lastSyncedAt.value = data.last_synced_at || null;
    if (status.value === "unavailable") {
      syncResult.value = "学习通暂时不可用，请稍后重试";
      syncResultTone.value = "danger";
    }
  } catch (err) {
    syncResult.value = "状态检查失败，请检查网络后重试";
    syncResultTone.value = "danger";
  } finally {
    isChecking.value = false;
  }
}

async function syncNow() {
  if (isSyncing.value) return;
  isSyncing.value = true;
  syncResult.value = null;
  try {
    await syncChaoxing();
    syncResult.value = "同步成功";
    syncResultTone.value = "primary";
    await checkStatus();
    toast.success("学习通同步成功");
  } catch (err) {
    const detail = errorDetail(err);
    if (detail.includes("reauth_required") || detail.includes("verification_required")) {
      status.value = "expired";
      syncResult.value = "登录已失效或需要验证，请重新登录";
      syncResultTone.value = "danger";
    } else {
      syncResult.value = `同步失败：${detail || "未知错误"}`;
      syncResultTone.value = "danger";
    }
  } finally {
    isSyncing.value = false;
  }
}

async function disconnect() {
  if (isDisconnecting.value) return;
  isDisconnecting.value = true;
  try {
    await disconnectChaoxing();
    status.value = "offline";
    lastSyncedAt.value = null;
    syncResult.value = "已解除连接";
    syncResultTone.value = "primary";
    toast.success("已解除学习通连接");
  } catch (err) {
    syncResult.value = `解除失败：${errorDetail(err) || "未知错误"}`;
    syncResultTone.value = "danger";
  } finally {
    isDisconnecting.value = false;
  }
}

function goLogin() {
  router.push("/teacher/chaoxing/login");
}

onMounted(checkStatus);
</script>

<template>
  <main class="tch-page page-enter">
    <PageHeader
      kicker="学习通同步"
      title="连接学习通"
      subtitle="同步课程、作业与课程通知到本地，会话仅保留登录凭证，不会保存你的密码。"
    >
      <template #actions>
        <button class="secondary-button" :disabled="isChecking" @click="checkStatus">
          <UiIcon name="PhArrowClockwise" :size="16" />刷新状态
        </button>
      </template>
    </PageHeader>

    <section class="cx-status-card tch-panel">
      <div class="cx-status-head">
        <span class="cx-icon"><UiIcon name="PhGraduationCap" :size="20" weight="fill" /></span>
        <div class="cx-status-title">
          <strong>学习通</strong>
          <span class="cx-status-tag" :class="`tone-${statusToneMap[status]}`">
            {{ statusTextMap[status] || "未知状态" }}
          </span>
        </div>
        <UiIcon v-if="status === 'expired'" name="PhCloudSlash" :size="18" class="cx-warn-icon" />
      </div>

      <div v-if="isChecking" class="cx-checking"><UiIcon name="PhCircleNotch" :size="16" />正在检查连接状态…</div>

      <template v-else>
        <hr v-if="status === 'online' || status === 'expired'" class="cx-divider" />
        <div v-if="status === 'online'" class="cx-info">
          <div class="cx-info-line">
            <span>上次同步</span><b>{{ lastSyncedAt ? formatDateTime(lastSyncedAt) : "—" }}</b>
          </div>
          <div class="cx-info-line"><span>自动同步</span><b>每 1 小时</b></div>
          <div class="cx-info-line"><span>同步范围</span><b>课程 / 作业 / 课程通知</b></div>
        </div>
        <p v-else-if="status === 'expired'" class="cx-warn-text">
          学习通会话已过期，请重新登录后继续同步。
        </p>
        <p v-else-if="status === 'offline'" class="cx-muted-text">
          连接后可同步课程、作业与课程通知。
        </p>
        <p v-else-if="status === 'unavailable'" class="cx-warn-text">
          学习通服务暂时不可用，请稍后重试。
        </p>
      </template>
    </section>

    <section class="cx-actions" v-if="!isChecking">
      <template v-if="status === 'online'">
        <button class="primary-button" :disabled="isSyncing" @click="syncNow">
          <UiIcon :name="isSyncing ? 'PhCircleNotch' : 'PhArrowClockwise'" :size="16" />
          {{ isSyncing ? "同步中…" : "立即同步" }}
        </button>
        <button class="secondary-button" :disabled="isDisconnecting" @click="disconnect">
          <UiIcon name="PhLinkSimpleHorizontalBreak" :size="16" />解除连接
        </button>
      </template>
      <template v-else-if="status === 'expired'">
        <button class="primary-button" @click="goLogin">
          <UiIcon name="PhGraduationCap" :size="16" />重新登录
        </button>
        <button class="secondary-button" :disabled="isDisconnecting" @click="disconnect">
          <UiIcon name="PhLinkSimpleHorizontalBreak" :size="16" />解除连接
        </button>
      </template>
      <template v-else>
        <button class="primary-button" @click="goLogin">
          <UiIcon name="PhGraduationCap" :size="16" />连接学习通
        </button>
      </template>
    </section>

    <div v-if="syncResult" class="cx-result" :class="`tone-${syncResultTone}`">
      <UiIcon
        :name="syncResultTone === 'primary' ? 'PhCheckCircle' : 'PhWarningCircle'"
        :size="15"
      />
      <span>{{ syncResult }}</span>
    </div>
  </main>
</template>

<style scoped>
.cx-status-card {
  max-width: 560px;
}
.cx-status-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cx-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
}
.cx-status-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.cx-status-title strong {
  font-size: 15px;
  color: var(--text);
}
.cx-status-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
  width: fit-content;
}
.cx-status-tag.tone-primary {
  background: var(--primary-soft);
  color: var(--primary);
}
.cx-status-tag.tone-danger {
  background: #fdece8;
  color: #c0432a;
}
.cx-status-tag.tone-muted {
  background: #eef1f4;
  color: var(--muted);
}
.cx-warn-icon {
  color: #c0432a;
  margin-left: auto;
}
.cx-checking {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}
.cx-divider {
  border: 0;
  border-top: 1px solid var(--line);
  margin: 14px 0 12px;
}
.cx-info {
  display: grid;
  gap: 8px;
}
.cx-info-line {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.cx-info-line span {
  color: var(--muted);
}
.cx-info-line b {
  color: var(--text);
  font-weight: 600;
}
.cx-warn-text {
  margin: 12px 0 0;
  font-size: 12px;
  color: #c0432a;
}
.cx-muted-text {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.cx-actions {
  max-width: 560px;
  margin-top: 16px;
  display: grid;
  gap: 10px;
}
.cx-actions .primary-button,
.cx-actions .secondary-button {
  width: 100%;
  justify-content: center;
  height: 44px;
}
.cx-result {
  max-width: 560px;
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
}
.cx-result.tone-primary {
  background: var(--primary-soft);
  color: var(--primary);
}
.cx-result.tone-danger {
  background: #fdece8;
  color: #c0432a;
}
.cx-result.tone-info {
  background: #eef1f4;
  color: var(--muted);
}
</style>