import { useEffect, useRef, useState } from "react";
import { createNoiseBuffer } from "./whiteNoise.js";

// 场景音效：用 Web Audio 按场景塑形噪声（低通雨声 / 更柔和的雪声 / 暖云静默）。
// 资源体积很小，不需要引入外部音频文件。
const SCENE_TONE = Object.freeze({
  rain: { frequency: 1200, gain: 0.34 },
  snow: { frequency: 700, gain: 0.16 },
  cloud: null, // 暖云暂未配置音效，保持静默
  bamboo: { frequency: 900, gain: 0.24 },
  coast: { frequency: 480, gain: 0.14 },
});

export function useAmbientSound(scene) {
  const [enabled, setEnabled] = useState(false);
  const contextRef = useRef(null);
  const sourceRef = useRef(null);
  const gainRef = useRef(null);
  const filterRef = useRef(null);

  const stop = () => {
    sourceRef.current?.stop();
    sourceRef.current?.disconnect();
    sourceRef.current = null;
  };

  const build = (nextScene = scene) => {
    const tone = SCENE_TONE[nextScene];
    if (!tone) {
      stop();
      return;
    }
    const gain = gainRef.current;
    gain.gain.value = tone.gain;
    filterRef.current.type = "lowpass";
    filterRef.current.frequency.value = tone.frequency;
    const source = contextRef.current.createBufferSource();
    source.buffer = createNoiseBuffer(contextRef.current);
    source.loop = true;
    source.connect(filterRef.current).connect(gain).connect(contextRef.current.destination);
    source.start();
    sourceRef.current = source;
  };

  const start = async (nextScene = scene) => {
    if (!window.AudioContext && !window.webkitAudioContext) return false;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const context = contextRef.current || new AudioContext();
    contextRef.current = context;
    if (context.state === "suspended") await context.resume();
    stop();
    gainRef.current = gainRef.current || context.createGain();
    filterRef.current = filterRef.current || context.createBiquadFilter();
    build(nextScene);
    return true;
  };

  const toggle = async () => {
    if (enabled) {
      stop();
      setEnabled(false);
      return;
    }
    setEnabled(await start());
  };

  // 场景变化时保持播放连续，切换音色
  useEffect(() => {
    if (!enabled || !contextRef.current || !sourceRef.current) return;
    stop();
    build(scene);
  }, [scene, enabled]);

  useEffect(() => () => {
    stop();
    contextRef.current?.close();
  }, []);

  return { enabled, toggle };
}
