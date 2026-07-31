<script setup>
import { onMounted, onBeforeUnmount, watch } from "vue";
import UiIcon from "../UiIcon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  subtitle: { type: String, default: "" },
  width: { type: String, default: "regular" },
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
    <div v-if="open" class="tch-drawer-overlay" @click.self="closeOnBackdrop && close()">
      <aside class="tch-drawer" :class="`w-${width}`" role="dialog" aria-modal="true">
        <header class="tch-drawer-head">
          <div>
            <h2>{{ title }}</h2>
            <p v-if="subtitle">{{ subtitle }}</p>
          </div>
          <button class="icon-button" @click="close" aria-label="关闭">
            <UiIcon name="PhX" />
          </button>
        </header>
        <div class="tch-drawer-body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="tch-drawer-footer">
          <slot name="footer" />
        </footer>
      </aside>
    </div>
  </Teleport>
</template>