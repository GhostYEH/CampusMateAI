<script setup>
import { onMounted, onBeforeUnmount, watch } from "vue";
import UiIcon from "../UiIcon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  size: { type: String, default: "regular" },
  closeOnBackdrop: { type: Boolean, default: true },
});
const emit = defineEmits(["close", "update:open"]);

function close() {
  emit("update:open", false);
  emit("close");
}
function onKey(e) {
  if (e.key === "Escape" && props.open) close();
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
watch(() => props.open, (v) => {
  if (v) document.body.style.overflow = "hidden";
  else document.body.style.overflow = "";
});
</script>
<template>
  <Teleport to="body">
    <div v-if="open" class="tch-modal-overlay" @click.self="closeOnBackdrop && close()">
      <section class="tch-modal" :class="`s-${size}`" role="dialog" aria-modal="true">
        <header class="tch-modal-head">
          <h2>{{ title }}</h2>
          <button class="icon-button" @click="close" aria-label="关闭">
            <UiIcon name="PhX" />
          </button>
        </header>
        <div class="tch-modal-body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="tch-modal-footer">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>