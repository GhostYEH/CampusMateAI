<script setup>
import UiIcon from "../UiIcon.vue";
import { useToast } from "../../composables/useToast";
const { toast } = useToast();
const iconMap = {
  success: "PhCheckCircle",
  error: "PhWarningCircle",
  warning: "PhWarningCircle",
  info: "PhInfo",
};
</script>
<template>
  <Teleport to="body">
    <Transition name="tch-toast">
      <div v-if="toast.visible" class="tch-toast" :class="`type-${toast.type}`" role="status">
        <UiIcon :name="iconMap[toast.type]" :size="18" weight="fill" />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </Teleport>
</template>