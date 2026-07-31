<script setup>
import UiIcon from "../UiIcon.vue";
defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  rowKey: { type: String, default: "id" },
  loading: { type: Boolean, default: false },
  empty: { type: String, default: "暂无数据" },
  minWidth: { type: String, default: "720px" },
});
defineEmits(["row-click"]);
</script>
<template>
  <div class="tch-table-wrap">
    <div class="tch-table-scroll" :style="{ minWidth }">
      <table class="tch-table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[`align-${col.align || 'left'}`, { numeric: col.numeric }]"
              :style="col.width ? { width: col.width } : null"
            >
              {{ col.title }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row[rowKey]"
            :class="{ clickable: $listeners['row-click'] }"
            @click="$emit('row-click', row)"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="[`align-${col.align || 'left'}`, { numeric: col.numeric }]"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!loading && !rows.length" class="tch-table-empty">
      <UiIcon name="PhClipboardText" :size="28" />
      <span>{{ empty }}</span>
    </div>
  </div>
</template>