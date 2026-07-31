<script setup>
defineProps({
  rows: { type: Number, default: 4 },
  cols: { type: Number, default: 4 },
  layout: { type: String, default: "grid" },
});
</script>
<template>
  <div v-if="layout === 'grid'" class="tch-skeleton-grid">
    <i v-for="n in rows" :key="n"></i>
  </div>
  <div v-else class="tch-skeleton-table">
    <div class="tch-skeleton-row tch-skeleton-head">
      <i v-for="c in cols" :key="c"></i>
    </div>
    <div v-for="r in rows" :key="r" class="tch-skeleton-row">
      <i v-for="c in cols" :key="c"></i>
    </div>
  </div>
</template>