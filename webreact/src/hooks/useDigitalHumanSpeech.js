import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../data/api.js";
import { PcmStreamPlayer } from "../features/digitalHuman/pcmPlayer.js";
import { DigitalHumanSpeechController } from "../features/digitalHuman/speechController.js";
import { normalizeSpeechText } from "../features/digitalHuman/speechText.js";
import { createUnityBridge } from "../features/digitalHuman/unityBridge.js";

const MUTE_STORAGE_KEY = "campus_digital_human_muted";

export function useDigitalHumanSpeech({ onNotice = () => {} } = {}) {
  const [speaking, setSpeaking] = useState(false);
  const [muted, setMuted] = useState(() => localStorage.getItem(MUTE_STORAGE_KEY) === "true");
  const [unityStatus, setUnityStatus] = useState("loading");
  const [lastText, setLastText] = useState("");
  const bridgeRef = useRef(null);
  const playerRef = useRef(null);
  const controllerRef = useRef(null);
  const noticeRef = useRef(onNotice);
  noticeRef.current = onNotice;

  if (!playerRef.current) {
    playerRef.current = new PcmStreamPlayer({
      onLevel: (level) => bridgeRef.current?.setSpeechLevel(level),
      onState: (value) => { setSpeaking(value); bridgeRef.current?.setSpeaking(value); },
    });
    controllerRef.current = new DigitalHumanSpeechController({
      player: playerRef.current,
      streamSpeech: api.streamAssistantSpeech,
      onError: () => noticeRef.current("语音暂时不可用，文字回答不受影响"),
    });
    controllerRef.current.setMuted(muted);
  }

  useEffect(() => () => { controllerRef.current?.stop(); bridgeRef.current?.stop(); }, []);

  const setUnityReady = useCallback((iframe) => {
    bridgeRef.current = createUnityBridge(iframe);
    setUnityStatus("ready");
    bridgeRef.current.setSpeaking(speaking);
  }, [speaking]);

  const setUnityError = useCallback(() => { setUnityStatus("error"); bridgeRef.current = null; }, []);
  const speak = useCallback(async (markdown) => {
    const text = normalizeSpeechText(markdown);
    if (!text) return false;
    setLastText(text);
    return controllerRef.current?.speak(text);
  }, []);
  const replay = useCallback(() => speak(lastText), [lastText, speak]);
  const toggleMuted = useCallback(() => {
    const next = !muted;
    setMuted(next);
    localStorage.setItem(MUTE_STORAGE_KEY, String(next));
    controllerRef.current?.setMuted(next);
    noticeRef.current(next ? "数字人语音已静音" : "数字人语音已开启");
  }, [muted]);
  const stop = useCallback(() => { controllerRef.current?.stop(); bridgeRef.current?.stop(); }, []);

  return { speaking, muted, unityStatus, lastText, setUnityReady, setUnityError, speak, replay, toggleMuted, stop };
}
