<script setup>
import UiIcon from "../UiIcon.vue";

defineProps({
  command: { type: Object, required: true },
});
const emit = defineEmits(["navigate"]);

const stages = [
  { key: "observe", label: "观察", detail: "课程 · 任务 · 考试" },
  { key: "analyze", label: "分析", detail: "识别时间与优先级" },
  { key: "plan", label: "计划", detail: "选出当前行动" },
  { key: "execute", label: "执行", detail: "进入现有功能完成" },
];

function navigate(path) {
  if (path) emit("navigate", path);
}
</script>

<template>
  <section class="home-learning-command" aria-labelledby="home-command-title">
    <div class="command-copy">
      <span class="command-eyebrow"><i></i>{{ command.eyebrow }}</span>
      <h1 id="home-command-title">{{ command.headline }}</h1>
      <p>{{ command.detail }}</p>
      <div class="command-actions">
        <button class="command-primary" @click="navigate(command.primaryAction.path)">
          {{ command.primaryAction.label }}
          <UiIcon :name="command.primaryAction.icon" :size="17" weight="bold" />
        </button>
        <button class="command-secondary" @click="navigate(command.secondaryAction.path)">
          <UiIcon :name="command.secondaryAction.icon" :size="17" />
          {{ command.secondaryAction.label }}
        </button>
      </div>
      <small class="command-trust"><UiIcon name="PhShieldCheck" :size="15" />建议来自你已同步的校园数据，执行仍由你决定</small>
    </div>

    <aside class="home-agent-loop" aria-label="今日行动形成过程">
      <header><span>行动路径</span><b>Campus Agent</b></header>
      <ol>
        <li v-for="(stage, index) in stages" :key="stage.key" :class="{ active: index === stages.length - 1 }">
          <i>{{ index + 1 }}</i>
          <span><strong>{{ stage.label }}</strong><small>{{ stage.detail }}</small></span>
          <UiIcon v-if="index === stages.length - 1" name="PhArrowRight" :size="15" />
        </li>
      </ol>
    </aside>
  </section>
</template>

<style scoped>
.home-learning-command{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,.7fr);min-height:314px;overflow:hidden;border:1px solid #dce4ef;border-radius:20px;background:#f8fafc;color:#13263f;box-shadow:0 12px 34px rgba(30,54,86,.05)}
.command-copy{position:relative;display:grid;align-content:center;padding:36px 42px;background:linear-gradient(110deg,#f4f8fc 0%,#fff 76%)}
.command-copy::before{content:"";position:absolute;left:0;top:36px;bottom:36px;width:4px;border-radius:0 5px 5px 0;background:#2f6f69}
.command-eyebrow{display:flex;align-items:center;gap:8px;color:#54706e;font-size:12px;font-weight:750;letter-spacing:.04em}
.command-eyebrow i{width:7px;height:7px;border-radius:50%;background:#2f7d74;box-shadow:0 0 0 5px rgba(47,125,116,.1)}
.command-copy h1{max-width:760px;margin:17px 0 13px;color:#102944;font-size:clamp(30px,3vw,48px);font-weight:820;letter-spacing:-.045em;line-height:1.1}
.command-copy p{max-width:690px;margin:0;color:#5e6f83;font-size:14px;line-height:1.75}
.command-actions{display:flex;flex-wrap:wrap;gap:11px;margin-top:25px}
.command-actions button{height:46px;display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:0 18px;border-radius:12px;font-family:inherit;font-size:13px;font-weight:750;cursor:pointer;transition:transform .18s ease,border-color .18s ease,background .18s ease}
.command-actions button:hover{transform:translateY(-1px)}
.command-actions button:focus-visible{outline:3px solid rgba(47,111,105,.24);outline-offset:3px}
.command-primary{border:1px solid #245f59;background:#2f6f69;color:#fff}
.command-primary:hover{background:#285f5a}
.command-secondary{border:1px solid #ccd7e3;background:#fff;color:#26445f}
.command-secondary:hover{border-color:#9eb3c5;background:#f9fbfd}
.command-trust{display:flex;align-items:center;gap:6px;margin-top:17px;color:#7b8998;font-size:10px}
.command-trust svg{color:#3b7d76}
.home-agent-loop{display:grid;align-content:center;padding:28px 26px;border-left:1px solid #e1e7ee;background:#fff}
.home-agent-loop header{display:flex;align-items:center;justify-content:space-between;margin-bottom:17px;color:#798797;font-size:11px}
.home-agent-loop header span{font-weight:750;letter-spacing:.08em;text-transform:uppercase}
.home-agent-loop header b{color:#2f6f69;font-size:10px}
.home-agent-loop ol{display:grid;gap:0;margin:0;padding:0;list-style:none}
.home-agent-loop li{position:relative;display:grid;grid-template-columns:30px minmax(0,1fr) 15px;align-items:center;gap:10px;min-height:53px;color:#8190a0}
.home-agent-loop li:not(:last-child)::after{content:"";position:absolute;left:14px;top:39px;width:1px;height:28px;background:#d9e2e9}
.home-agent-loop li>i{width:30px;height:30px;display:grid;place-items:center;border:1px solid #d3dde6;border-radius:50%;background:#fff;color:#68798b;font-size:10px;font-style:normal;font-weight:750}
.home-agent-loop li>span{display:grid;gap:3px}
.home-agent-loop li strong{color:#334b63;font-size:12px}.home-agent-loop li small{font-size:10px}
.home-agent-loop li.active>i{border-color:#2f6f69;background:#2f6f69;color:#fff}.home-agent-loop li.active strong,.home-agent-loop li.active>svg{color:#2f6f69}
@media (max-width: 980px){.home-learning-command{grid-template-columns:1fr}.home-agent-loop{border-top:1px solid #e1e7ee;border-left:0}.home-agent-loop ol{grid-template-columns:repeat(4,1fr);gap:8px}.home-agent-loop li{grid-template-columns:30px minmax(0,1fr)}.home-agent-loop li>svg,.home-agent-loop li:not(:last-child)::after{display:none}}
@media (max-width: 700px){.home-learning-command{min-height:0;border-radius:16px}.command-copy{padding:29px 23px}.command-copy::before{top:28px;bottom:28px}.command-copy h1{font-size:31px}.command-actions{display:grid}.command-actions button{width:100%}.home-agent-loop{padding:22px}.home-agent-loop ol{grid-template-columns:1fr 1fr}.home-agent-loop li{min-height:48px}}
@media (prefers-reduced-motion: reduce){.command-actions button{transition:none}}
</style>
