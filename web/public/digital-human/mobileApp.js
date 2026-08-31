import {
  applyAvatarSpeechMessage,
  CompatAvatarAnimator,
  createSpeechEndpoint,
  createUnitySpeechMessage,
  normalizeRuntimeConfig,
  PcmStreamPlayer,
  resolveDigitalHumanMode,
  resolveMobileLayout,
  resolveReducedMotion,
} from "./mobileRuntime.js";

const mobileLayout = resolveMobileLayout(window.location.search);
document.body.classList.toggle("harmony", mobileLayout === "harmony");
document.body.classList.toggle("embed", mobileLayout === "embed");
const runtimeMode = resolveDigitalHumanMode(window.location.search);
const reducedMotion = resolveReducedMotion(
  window.location.search,
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
);

const frame = document.querySelector("#avatar-frame");
const loading = document.querySelector("#loading");
const stateLabel = document.querySelector("#state-label");
const notice = document.querySelector("#notice");
const muteButton = document.querySelector("#mute");
const stopButton = document.querySelector("#stop");
const replayButton = document.querySelector("#replay");
const compatAvatar = document.querySelector("#compat-avatar");
let config = normalizeRuntimeConfig();
let lastText = "";
let muted = false;
let speaking = false;
let abortController = null;
const avatarAnimator = runtimeMode === "compat"
  ? new CompatAvatarAnimator(compatAvatar, { reducedMotion })
  : null;

avatarAnimator?.start();
if (runtimeMode === "compat") stateLabel.textContent = "随时为你解答";

function sendUnity(type, value) {
  if (runtimeMode === "compat") {
    applyAvatarSpeechMessage(avatarAnimator, type, value);
    return;
  }
  frame.contentWindow?.postMessage(createUnitySpeechMessage(type, value), window.location.origin);
}

function setSpeaking(value) {
  speaking = value;
  document.body.classList.toggle("speaking", value);
  stateLabel.textContent = value ? "正在讲解" : "随时为你解答";
  stopButton.disabled = !value;
  replayButton.disabled = !lastText || value || muted;
  sendUnity("speech-state", value);
}

function showNotice(message = "") {
  notice.textContent = message;
  notice.hidden = !message;
}

const player = new PcmStreamPlayer({
  onLevel: (level) => sendUnity("speech-level", level),
  onState: setSpeaking,
  onNeedsGesture: () => showNotice("轻触“重播”即可开启声音"),
});

function stop() {
  abortController?.abort();
  abortController = null;
  player.stop();
  sendUnity("speech-stop");
  paused = false;
  stopButton.textContent = "暂停";
}

function toggleMuted() {
  muted = !muted;
  muteButton.textContent = muted ? "开启语音" : "静音";
  muteButton.setAttribute("aria-pressed", String(muted));
  if (muted) stop();
  replayButton.disabled = !lastText || speaking || muted;
  return muted;
}

let paused = false;
async function togglePaused() {
  paused = await player.togglePaused();
  stopButton.textContent = paused ? "继续" : "暂停";
  return paused;
}

function replay() {
  return speak(lastText);
}

async function speak(text) {
  const cleanText = String(text || "").trim();
  if (!cleanText) return false;
  lastText = cleanText;
  replayButton.disabled = muted;
  if (muted) return false;
  stop();
  showNotice();
  const request = new AbortController();
  abortController = request;
  try {
    if (!config.apiBaseUrl || !config.accessToken) throw new Error("登录状态尚未同步");
    const response = await fetch(createSpeechEndpoint(config.apiBaseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${config.accessToken}` },
      body: JSON.stringify({ text: cleanText }),
      signal: request.signal,
    });
    if (!response.ok) throw new Error(`语音服务错误 (${response.status})`);
    const reader = response.body?.getReader();
    if (!reader) throw new Error("当前设备不支持流式语音");
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value?.byteLength) await player.append(value);
    }
    player.finish();
    return true;
  } catch (error) {
    if (error?.name !== "AbortError") showNotice(`${error?.message || "语音暂时不可用"}，文字回答不受影响`);
    if (abortController === request) player.stop();
    return false;
  } finally {
    if (abortController === request) abortController = null;
  }
}

window.CampusMateDigitalHuman = {
  configure(value) {
    config = normalizeRuntimeConfig(value);
    return Boolean(config.apiBaseUrl && config.accessToken);
  },
  speak,
  stop,
  toggleMuted,
  togglePaused,
  replay,
};

window.addEventListener("message", (event) => {
  if (event.source !== frame.contentWindow || event.origin !== window.location.origin || event.data?.source !== "campusmate-unity") return;
  if (event.data.type === "ready") {
    loading.hidden = true;
    stateLabel.textContent = "随时为你解答";
  } else if (event.data.type === "error") {
    loading.textContent = "数字人画面加载失败，语音仍可使用";
  }
});

muteButton.addEventListener("click", toggleMuted);
stopButton.addEventListener("click", togglePaused);
replayButton.addEventListener("click", replay);
window.addEventListener("pagehide", () => {
  stop();
  avatarAnimator?.stop();
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) avatarAnimator?.start();
});
