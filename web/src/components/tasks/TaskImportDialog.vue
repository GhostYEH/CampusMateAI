<script setup>
import { computed, nextTick, reactive, useTemplateRef, watch } from "vue";
import UiIcon from "../UiIcon.vue";
import { selectedTaskCount, updateTaskImportDraftTitle } from "../../features/tasks/taskImportModel.js";

const props = defineProps({
  open: Boolean,
  result: { type: Object, default: null },
  analyzing: Boolean,
  saving: Boolean,
  error: { type: String, default: "" },
});
const emit = defineEmits(["close", "analyze", "commit", "reset"]);
const dialog = useTemplateRef("dialog");
const form = reactive({ sourceName: "学习材料", content: "", drafts: [] });
const count = computed(() => selectedTaskCount(form.drafts));

watch(() => props.result, (result) => {
  form.drafts = (result?.tasks || []).map((task) => ({ ...task }));
}, { immediate: true });
watch(() => props.open, async (open) => {
  if (!open) return;
  await nextTick();
  if (!props.open) return;
  (focusableElements()[0] || dialog.value)?.focus();
});

function focusableElements() {
  return Array.from(dialog.value?.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  ) || []).filter((element) => element.getClientRects().length > 0);
}
function handleDialogKeydown(event) {
  if (event.key === "Escape") { event.preventDefault(); close(); return; }
  if (event.key !== "Tab") return;
  const elements = focusableElements();
  if (!elements.length) { event.preventDefault(); dialog.value?.focus(); return; }
  const first = elements[0];
  const last = elements[elements.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
function analyze() {
  if (!form.content.trim() || props.analyzing) return;
  emit("analyze", { content: form.content.trim(), source_name: form.sourceName.trim() || null });
}
function close() { if (!props.analyzing && !props.saving) emit("close"); }
function reset() { form.drafts = []; emit("reset"); }
function updateDraftTitle(draft, title) { Object.assign(draft, updateTaskImportDraftTitle(draft, title)); }
</script>

<template>
  <Teleport to="body">
    <div v-if="open" ref="dialog" class="task-import-backdrop" role="dialog" aria-modal="true" aria-labelledby="task-import-title" tabindex="-1" @click.self="close" @keydown="handleDialogKeydown">
      <section class="task-import-shell">
        <aside class="task-import-scene" aria-hidden="true">
          <img src="/assets/generated/tasks-hero-illustration.png" alt="" />
          <div><span>SMART INTAKE</span><strong>把一页计划<br />变成下一步</strong><p>原文留存，进度不被覆盖。</p></div>
        </aside>
        <div class="task-import-glass">
          <header class="task-import-head">
            <div><span class="task-section-eyebrow">AI TASK IMPORT</span><h2 id="task-import-title">{{ result ? '确认识别结果' : '导入学习材料' }}</h2><p>{{ result ? '勾选并修改后再保存，不会覆盖已有任务进度。' : '粘贴课程计划、作业要求或 Markdown 清单。' }}</p></div>
            <button type="button" aria-label="关闭导入" @click="close"><UiIcon name="PhX" :size="18" /></button>
          </header>

          <form v-if="!result" class="task-import-input" @submit.prevent="analyze">
            <label>材料名称<input v-model="form.sourceName" maxlength="256" placeholder="例如：数据结构第 3 周计划" /></label>
            <label>计划内容<textarea v-model="form.content" maxlength="20000" required placeholder="粘贴课程通知、复习计划或清单…"></textarea></label>
            <div class="task-import-hint"><UiIcon name="PhShieldCheck" :size="15" /><span>只保存你确认的任务；原始材料用于本次复核。</span></div>
            <p v-if="error" class="task-import-error" role="alert">{{ error }}</p>
            <footer><button type="button" class="task-secondary-button" @click="close">取消</button><button class="task-primary-button" :disabled="analyzing || !form.content.trim()"><UiIcon name="PhSparkle" :size="16" />{{ analyzing ? '正在分析…' : '分析并拆分' }}</button></footer>
          </form>

          <div v-else class="task-import-review">
            <div class="task-import-summary"><span><UiIcon name="PhListChecks" :size="16" />识别到 {{ form.drafts.length }} 项</span><small>{{ result.split_reason ? `${result.split_reason} · 最多保留 50 项` : '最多保留 50 项' }}</small></div>
            <div v-if="form.drafts.length" class="task-import-list">
              <article v-for="(draft, index) in form.drafts" :key="`${draft.title}-${index}`" class="task-import-item" :class="{ duplicate: draft.existing_task_id }">
                <label class="task-import-select"><input v-model="draft.selected" type="checkbox" :disabled="Boolean(draft.existing_task_id)" /><span></span></label>
                <div>
                  <input :value="draft.title" class="task-import-title" maxlength="256" aria-label="任务标题" @input="updateDraftTitle(draft, $event.target.value)" />
                  <textarea v-model="draft.description" rows="2" maxlength="4000" aria-label="任务备注" placeholder="补充下一步或完成标准（选填）"></textarea>
                  <p v-if="draft.existing_task_id"><UiIcon name="PhCheckCircle" :size="13" />已有{{ draft.existing_status === 'completed' ? '已完成' : '待办' }}任务，已保留原进度</p>
                </div>
                <select v-model="draft.priority" aria-label="优先级"><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select>
              </article>
            </div>
            <div v-else class="task-import-empty"><UiIcon name="PhFileText" :size="28" /><strong>没有识别到明确任务</strong><span>尝试使用项目符号或编号列出每一项。</span></div>
            <p v-if="error" class="task-import-error" role="alert">{{ error }}</p>
            <footer><button type="button" class="task-secondary-button" @click="reset">返回修改原文</button><button class="task-primary-button" :disabled="saving || count === 0" @click="emit('commit', form.drafts)"><UiIcon name="PhCheck" :size="16" />{{ saving ? '正在保存…' : `保存 ${count} 项任务` }}</button></footer>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>
