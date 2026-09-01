<script setup>
import UiIcon from "../UiIcon.vue";

defineProps({
  items: { type: Array, required: true },
});
const emit = defineEmits(["navigate"]);

function navigate(path) {
  if (path) emit("navigate", path);
}
</script>

<template>
  <section class="home-learning-pulse" aria-labelledby="learning-pulse-title">
    <header class="pulse-heading">
      <div><span>今日数据</span><h2 id="learning-pulse-title">校园学习脉搏</h2></div>
      <small>课程、任务、考试与学习记录实时汇合</small>
    </header>
    <div class="pulse-grid">
      <button v-for="item in items" :key="item.key" @click="navigate(item.path)">
        <span class="pulse-icon"><UiIcon :name="item.icon" :size="20" /></span>
        <span class="pulse-copy"><small>{{ item.label }}</small><strong>{{ item.value }}</strong><em>{{ item.detail }}</em></span>
        <UiIcon name="PhArrowUpRight" class="pulse-arrow" :size="15" />
      </button>
    </div>
  </section>
</template>

<style scoped>
.home-learning-pulse{display:grid;gap:15px;padding:19px 20px;border:1px solid #e2e8ef;border-radius:18px;background:#fff;color:#152a42}
.pulse-heading{display:flex;align-items:end;justify-content:space-between;gap:18px}
.pulse-heading>div{display:grid;gap:3px}.pulse-heading span{color:#2f6f69;font-size:9px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.pulse-heading h2{margin:0;font-size:17px;letter-spacing:-.015em}.pulse-heading>small{color:#8794a2;font-size:10px}
.pulse-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid #edf1f4}
.pulse-grid button{min-width:0;display:grid;grid-template-columns:39px minmax(0,1fr) 15px;align-items:center;gap:10px;padding:17px 13px;border:0;border-right:1px solid #edf1f4;background:#fff;color:inherit;font-family:inherit;text-align:left;cursor:pointer;transition:background .18s ease}
.pulse-grid button:first-child{padding-left:0}.pulse-grid button:last-child{padding-right:0;border-right:0}.pulse-grid button:hover{background:#f8fafb}.pulse-grid button:focus-visible{position:relative;z-index:1;outline:3px solid rgba(47,111,105,.22);outline-offset:2px}
.pulse-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:11px;background:#edf5f3;color:#2f6f69}
.pulse-copy{display:grid;min-width:0;gap:2px}.pulse-copy small,.pulse-copy strong,.pulse-copy em{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pulse-copy small{color:#758393;font-size:9px}.pulse-copy strong{color:#172e47;font-size:18px}.pulse-copy em{color:#8b98a5;font-size:9px;font-style:normal}.pulse-arrow{color:#9aa6b1}
@media (max-width: 1000px){.pulse-grid{grid-template-columns:1fr 1fr}.pulse-grid button:nth-child(2){border-right:0}.pulse-grid button:nth-child(-n+2){border-bottom:1px solid #edf1f4}.pulse-grid button:first-child,.pulse-grid button:nth-child(3){padding-left:0}.pulse-grid button:nth-child(2),.pulse-grid button:last-child{padding-right:0}}
@media (max-width: 700px){.home-learning-pulse{padding:17px}.pulse-heading{align-items:start}.pulse-heading>small{max-width:150px;text-align:right;line-height:1.5}.pulse-grid{grid-template-columns:1fr}.pulse-grid button{padding:13px 0;border-right:0;border-bottom:1px solid #edf1f4}.pulse-grid button:nth-child(3){border-bottom:1px solid #edf1f4}.pulse-grid button:last-child{border-bottom:0}}
@media (prefers-reduced-motion: reduce){.pulse-grid button{transition:none}}
</style>
