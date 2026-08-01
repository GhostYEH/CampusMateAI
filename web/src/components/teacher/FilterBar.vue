<script setup>
import UiIcon from "../UiIcon.vue";
const props = defineProps({
  modelValue: { type: [String, Number], default: "" },
  searchPlaceholder: { type: String, default: "搜索" },
  filters: { type: Array, default: () => [] },
  searchable: { type: Boolean, default: true },
});
const emit = defineEmits(["update:modelValue", "update:filters", "search"]);
function onSearch(e) {
  emit("update:modelValue", e.target.value);
  emit("search", e.target.value);
}
function onFilterChange(idx, value) {
  const next = props.filters.map((f, i) => (i === idx ? { ...f, value } : f));
  emit("update:filters", next);
}
</script>
<template>
  <div class="tch-filter-bar">
    <div v-if="searchable" class="tch-filter-search">
      <UiIcon name="PhMagnifyingGlass" :size="16" />
      <input
        :value="modelValue"
        type="search"
        :placeholder="searchPlaceholder"
        @input="onSearch"
      />
    </div>
    <div class="tch-filter-selects">
      <div v-for="(f, idx) in filters" :key="f.key" class="tch-filter-select">
        <select
          :value="f.value"
          @change="onFilterChange(idx, $event.target.value)"
        >
          <option value="">{{ f.placeholder || f.label }}</option>
          <option v-for="opt in f.options" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>
    <div class="tch-filter-extra"><slot /></div>
  </div>
</template>
