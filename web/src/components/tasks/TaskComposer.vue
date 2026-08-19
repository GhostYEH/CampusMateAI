<script setup>
import { reactive, watch } from "vue";
import UiIcon from "../UiIcon.vue";

const props = defineProps({ open: Boolean, task: { type: Object, default: null }, saving: Boolean });
const emit = defineEmits(["close", "save"]);
const blank = () => ({ title: "", deadline: "", priority: "medium", description: "", reminder_minutes: 30 });
const form = reactive(blank());

function localDeadline(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "";
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
function sync() {
  Object.assign(form, blank(), props.task ? {
    title: props.task.title || "",
    deadline: localDeadline(props.task.deadline),
    priority: props.task.priority || "medium",
    description: props.task.description || "",
    reminder_minutes: props.task.reminder_minutes ?? 30,
  } : {});
}
watch(() => [props.open, props.task], sync, { immediate: true });
function submit() {
  if (!form.title.trim() || props.saving) return;
  emit("save", { ...form, title: form.title.trim(), deadline: form.deadline ? new Date(form.deadline).toISOString() : null });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="task-modal-backdrop" @click.self="emit('close')">
      <form class="task-composer-card" @submit.prevent="submit">
        <header class="task-composer-head"><div><span class="task-section-eyebrow">PERSONAL TASK</span><h2>{{ task ? '编辑待办' : '新建待办' }}</h2><p>{{ task ? '把任务信息更新得更清楚' : '把想做的事放下来，下一步会更清晰' }}</p></div><button type="button" aria-label="关闭" @click="emit('close')"><UiIcon name="PhX" :size="18" /></button></header>
        <label>事项名称<input v-model="form.title" maxlength="256" required placeholder="例如：准备奖学金申请材料" /></label>
        <div class="task-form-grid"><label>截止时间<input v-model="form.deadline" type="datetime-local" /></label><label>优先级<select v-model="form.priority"><option value="high">高优先级</option><option value="medium">中优先级</option><option value="low">低优先级</option></select></label></div>
        <label>提醒<select v-model.number="form.reminder_minutes"><option :value="0">截止时提醒</option><option :value="30">提前 30 分钟</option><option :value="1440">提前 1 天</option></select></label>
        <label>备注 <span class="task-optional">选填</span><textarea v-model="form.description" rows="4" maxlength="4000" placeholder="补充材料、地点或下一步"></textarea></label>
        <footer><button type="button" class="task-secondary-button" @click="emit('close')">取消</button><button class="task-primary-button" :disabled="saving || !form.title.trim()"><UiIcon name="PhCheck" :size="15" />{{ saving ? '保存中…' : '保存待办' }}</button></footer>
      </form>
    </div>
  </Teleport>
</template>
