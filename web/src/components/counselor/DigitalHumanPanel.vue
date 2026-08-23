<script setup>
import { onBeforeUnmount, onMounted, useTemplateRef } from "vue";
import UiIcon from "../UiIcon.vue";

const props = defineProps({
  speaking: Boolean,
  muted: Boolean,
  status: { type: String, default: "loading" },
  canReplay: Boolean,
});
const emit = defineEmits(["ready", "error", "toggleMuted", "stop", "replay"]);
const frame = useTemplateRef("frame");

function handleUnityMessage(event) {
  if (event.origin !== window.location.origin || event.data?.source !== "campusmate-unity") return;
  if (event.data.type === "ready" && frame.value) emit("ready", frame.value);
  if (event.data.type === "error") emit("error");
}

function handleFrameError() {
  emit("error");
}

onMounted(() => window.addEventListener("message", handleUnityMessage));
onBeforeUnmount(() => window.removeEventListener("message", handleUnityMessage));
</script>

<template>
  <section class="digital-human-card" :class="{ speaking }" aria-labelledby="digital-human-title">
    <header class="digital-human-header">
      <div>
        <span class="digital-human-kicker">你的学习小帮手</span>
        <h2 id="digital-human-title">CampusMate 数字人</h2>
      </div>
      <span class="digital-human-state" role="status">
        <i aria-hidden="true"></i>{{ speaking ? "正在讲解" : status === "ready" ? "随时为你解答" : status === "error" ? "静态模式" : "正在载入" }}
      </span>
    </header>

    <div class="digital-human-stage" :aria-busy="status === 'loading'">
      <iframe
        v-show="status !== 'error'"
        ref="frame"
        class="digital-human-frame"
        src="/digital-human/index.html"
        title="CampusMate AI 数字人"
        allow="autoplay"
        @error="handleFrameError"
      ></iframe>
      <div v-if="status === 'loading'" class="digital-human-loading" role="status">
        <span aria-hidden="true"></span>正在唤醒数字人…
      </div>
      <div v-if="status === 'error'" class="digital-human-fallback">
        <img src="/assets/campusmate-counselor-hero.png" alt="CampusMate AI 助手" />
        <p>数字人画面暂未加载，文字与语音功能仍可使用。</p>
      </div>
    </div>

    <footer class="digital-human-controls">
      <button type="button" :aria-pressed="muted" @click="emit('toggleMuted')">
        <UiIcon :name="muted ? 'PhSpeakerSlash' : 'PhSpeakerHigh'" :size="16" />{{ muted ? "开启语音" : "静音" }}
      </button>
      <button type="button" :disabled="!speaking" @click="emit('stop')">
        <UiIcon name="PhStop" :size="16" />停止
      </button>
      <button type="button" :disabled="!canReplay || speaking || muted" @click="emit('replay')">
        <UiIcon name="PhArrowCounterClockwise" :size="16" />重播
      </button>
    </footer>
  </section>
</template>

<style scoped>
.digital-human-card { overflow: hidden; border: 1px solid #dfe5f5; border-radius: 16px; background: #f2f4ff; box-shadow: 0 10px 24px rgba(48, 65, 128, 0.08); }
.digital-human-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 16px 16px 10px; }
.digital-human-kicker { display: block; margin-bottom: 4px; color: #7b88ac; font-size: 12px; }
.digital-human-header h2 { margin: 0; color: #304bc8; font-size: 17px; line-height: 1.25; }
.digital-human-state { display: inline-flex; align-items: center; gap: 6px; color: #7180a7; font-size: 11px; white-space: nowrap; }
.digital-human-state i { width: 7px; height: 7px; border-radius: 50%; background: #98a5c7; }
.speaking .digital-human-state i { background: #5368ef; box-shadow: 0 0 0 4px rgba(83, 104, 239, 0.12); }
.digital-human-stage { position: relative; height: 430px; margin: 0 10px; overflow: hidden; border-radius: 12px; background: radial-gradient(circle at 50% 35%, #fafdff 0, #e4e9fb 72%); }
.digital-human-frame { width: 100%; height: 100%; border: 0; background: transparent; }
.digital-human-loading, .digital-human-fallback { position: absolute; inset: 0; display: grid; place-items: center; align-content: center; gap: 10px; padding: 18px; color: #7180a7; font-size: 12px; text-align: center; }
.digital-human-loading span { width: 24px; height: 24px; border: 2px solid #c9d1ed; border-top-color: #5368ef; border-radius: 50%; animation: digital-human-spin 0.9s linear infinite; }
.digital-human-fallback img { width: 72%; max-height: 178px; object-fit: contain; }
.digital-human-fallback p { margin: 0; line-height: 1.55; }
.digital-human-controls { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 12px; }
.digital-human-controls button { display: inline-flex; min-height: 36px; align-items: center; justify-content: center; gap: 5px; border: 1px solid #d9e0f4; border-radius: 9px; background: rgba(255, 255, 255, 0.86); color: #52618a; font: inherit; font-size: 12px; cursor: pointer; }
.digital-human-controls button:hover:not(:disabled), .digital-human-controls button:focus-visible { border-color: #8795ef; color: #4054d7; outline: none; }
.digital-human-controls button:focus-visible { box-shadow: 0 0 0 3px rgba(83, 104, 239, 0.16); }
.digital-human-controls button:disabled { cursor: not-allowed; opacity: 0.45; }
@keyframes digital-human-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .digital-human-loading span { animation: none; } }
@media (max-width: 1180px) { .digital-human-stage { height: 360px; } }
@media (max-width: 720px) { .digital-human-stage { height: 390px; } .digital-human-controls { grid-template-columns: 1fr; } }
</style>
