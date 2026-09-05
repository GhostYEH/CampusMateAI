import { useCallback, useEffect, useRef, useState } from "react";

export function clampVolume(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(100, Math.max(0, Math.round(numeric)));
}

export function volumeToGain(value) {
  return (clampVolume(value) / 100) ** 1.35 * 0.24;
}

export function createNoiseBuffer(audioContext, durationSeconds = 2) {
  const frameCount = Math.ceil(audioContext.sampleRate * durationSeconds);
  const buffer = audioContext.createBuffer(1, frameCount, audioContext.sampleRate);
  const channel = buffer.getChannelData(0);
  for (let index = 0; index < channel.length; index += 1) {
    channel[index] = Math.random() * 2 - 1;
  }
  return buffer;
}

export function useWhiteNoise(defaultVolume = 32) {
  const [enabled, setEnabled] = useState(false);
  const [volume, setVolumeState] = useState(() => clampVolume(defaultVolume));
  const contextRef = useRef(null);
  const sourceRef = useRef(null);
  const gainRef = useRef(null);

  const stop = useCallback(() => {
    sourceRef.current?.stop();
    sourceRef.current?.disconnect();
    sourceRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (!window.AudioContext && !window.webkitAudioContext) return false;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const context = contextRef.current || new AudioContext();
    contextRef.current = context;
    if (context.state === "suspended") await context.resume();

    stop();
    const gain = gainRef.current || context.createGain();
    gain.gain.value = volumeToGain(volume);
    gainRef.current = gain;
    const source = context.createBufferSource();
    source.buffer = createNoiseBuffer(context);
    source.loop = true;
    source.connect(gain).connect(context.destination);
    source.start();
    sourceRef.current = source;
    return true;
  }, [stop, volume]);

  const toggle = useCallback(async () => {
    if (enabled) {
      stop();
      setEnabled(false);
      return;
    }
    setEnabled(await start());
  }, [enabled, start, stop]);

  const setVolume = useCallback((value) => {
    const nextVolume = clampVolume(value);
    setVolumeState(nextVolume);
    if (gainRef.current) gainRef.current.gain.value = volumeToGain(nextVolume);
  }, []);

  useEffect(() => () => {
    stop();
    contextRef.current?.close();
  }, [stop]);

  return { enabled, volume, setVolume, toggle };
}
