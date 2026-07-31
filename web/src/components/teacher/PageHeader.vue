<script setup>
import UiIcon from "../UiIcon.vue";
defineProps({
  kicker: { type: String, default: "" },
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  breadcrumbs: { type: Array, default: () => [] },
});
defineEmits(["breadcrumb-click"]);
</script>
<template>
  <header class="tch-page-header">
    <nav v-if="breadcrumbs.length" class="tch-breadcrumb" aria-label="面包屑">
      <template v-for="(crumb, idx) in breadcrumbs" :key="idx">
        <button
          type="button"
          class="tch-breadcrumb-item"
          :class="{ active: idx === breadcrumbs.length - 1 }"
          :disabled="idx === breadcrumbs.length - 1"
          @click="$emit('breadcrumb-click', crumb)"
        >
          {{ crumb.label }}
        </button>
        <UiIcon v-if="idx < breadcrumbs.length - 1" name="PhCaretRight" :size="14" />
      </template>
    </nav>
    <div class="tch-page-header-main">
      <div class="tch-page-header-text">
        <span v-if="kicker" class="tch-kicker">{{ kicker }}</span>
        <h1>{{ title }}</h1>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
      <div class="tch-page-header-actions">
        <slot name="actions" />
      </div>
    </div>
  </header>
</template>