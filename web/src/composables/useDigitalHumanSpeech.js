import { onBeforeUnmount, shallowRef } from "vue";
import { streamAssistantSpeech } from "../services/api";
import { PcmStreamPlayer } from "../features/digitalHuman/pcmPlayer";
import { DigitalHumanSpeechController } from "../features/digitalHuman/speechController";
import { normalizeSpeechText } from "../features/digitalHuman/speechText";
import { createUnityBridge } from "../features/digitalHuman/unityBridge";

const MUTE_STORAGE_KEY = "campus_digital_human_muted";

export function useDigitalHumanSpeech({ onNotice = () => {} } = {}) {
  const speaking = shallowRef(false);
  const muted = shallowRef(localStorage.getItem(MUTE_STORAGE_KEY) === "true");
  const unityStatus = shallowRef("loading");
  const lastText = shallowRef("");
  const bridge = shallowRef(null);

  const player = new PcmStreamPlayer({
    onLevel: (level) => bridge.value?.setSpeechLevel(level),
    onState: (value) => {
      speaking.value = value;
      bridge.value?.setSpeaking(value);
    },
  });
  const controller = new DigitalHumanSpeechController({
    player,
    streamSpeech: streamAssistantSpeech,
    onError: () => onNotice("语音暂时不可用，文字回答不受影响"),
  });
  controller.setMuted(muted.value);

  function setUnityReady(iframe) {
    bridge.value = createUnityBridge(iframe);
    unityStatus.value = "ready";
    bridge.value.setSpeaking(speaking.value);
  }

  function setUnityError() {
    unityStatus.value = "error";
    bridge.value = null;
  }

  async function speak(markdown) {
    const text = normalizeSpeechText(markdown);
    if (!text) return false;
    lastText.value = text;
    return controller.speak(text);
  }

  function replay() {
    return speak(lastText.value);
  }

  function toggleMuted() {
    muted.value = !muted.value;
    localStorage.setItem(MUTE_STORAGE_KEY, String(muted.value));
    controller.setMuted(muted.value);
    onNotice(muted.value ? "数字人语音已静音" : "数字人语音已开启");
  }

  function stop() {
    controller.stop();
    bridge.value?.stop();
  }

  onBeforeUnmount(stop);

  return {
    speaking,
    muted,
    unityStatus,
    lastText,
    setUnityReady,
    setUnityError,
    speak,
    replay,
    toggleMuted,
    stop,
  };
}
