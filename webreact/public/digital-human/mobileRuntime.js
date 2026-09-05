export function normalizeRuntimeConfig(value = {}) {
  return {
    apiBaseUrl: String(value.apiBaseUrl || "").trim().replace(/\/+$/, ""),
    accessToken: String(value.accessToken || "").trim(),
  };
}

export function resolveMobileLayout(search = "") {
  const params = new URLSearchParams(String(search));
  if (params.get("layout") === "harmony") return "harmony";
  if (params.get("embed") === "1") return "embed";
  return "default";
}

export function resolveDigitalHumanMode(search = "") {
  return new URLSearchParams(String(search)).get("fallback") === "1" ? "compat" : "live";
}

export function resolveReducedMotion(search = "", mediaMatches = false) {
  return new URLSearchParams(String(search)).get("reduceMotion") === "1" || Boolean(mediaMatches);
}

export function emphasizeSpeechLevel(value) {
  const level = Math.max(0, Math.min(1, Number(value) || 0));
  if (level === 0) return 0;
  return Math.min(1, Math.pow(level, 0.65) * 1.65);
}

export function nextBlinkDelay(randomValue = Math.random()) {
  const normalized = Math.max(0, Math.min(1, Number(randomValue) || 0));
  return Math.round(2800 + normalized * 2400);
}

export function avatarMotionFrame(
  elapsedMs,
  { speaking = false, speechLevel = 0, reducedMotion = false } = {},
) {
  const elapsed = Math.max(0, Number(elapsedMs) || 0);
  const mouthOpen = speaking ? emphasizeSpeechLevel(speechLevel) : 0;
  if (reducedMotion) {
    return { rotateDeg: 0, translateYPercent: 0, scale: 1, mouthOpen };
  }

  if (speaking) {
    return {
      rotateDeg: Math.sin((elapsed / 1800) * Math.PI * 2) * (1.7 + mouthOpen * 1.2),
      translateYPercent: Math.sin((elapsed / 980) * Math.PI * 2 + 0.45) * (0.7 + mouthOpen * 0.85),
      scale: 1.008 + Math.sin((elapsed / 760) * Math.PI * 2) * 0.006 + mouthOpen * 0.008,
      mouthOpen,
    };
  }

  return {
    rotateDeg: Math.sin((elapsed / 5600) * Math.PI * 2) * 0.8,
    translateYPercent: Math.sin((elapsed / 4300) * Math.PI * 2 + 0.55) * 0.65,
    scale: 1.004 + Math.sin((elapsed / 3600) * Math.PI * 2) * 0.004,
    mouthOpen,
  };
}

export class CompatAvatarAnimator {
  constructor(
    element,
    {
      requestFrame = globalThis.requestAnimationFrame?.bind(globalThis),
      cancelFrame = globalThis.cancelAnimationFrame?.bind(globalThis),
      now = () => globalThis.performance?.now?.() || Date.now(),
      random = Math.random,
      reducedMotion = false,
    } = {},
  ) {
    this.element = element;
    this.requestFrame = requestFrame || ((callback) => globalThis.setTimeout(() => callback(now()), 16));
    this.cancelFrame = cancelFrame || globalThis.clearTimeout?.bind(globalThis);
    this.now = now;
    this.random = random;
    this.reducedMotion = reducedMotion;
    this.frameId = null;
    this.startedAt = 0;
    this.nextBlinkAt = 0;
    this.blinkStartedAt = null;
    this.speaking = false;
    this.speechLevel = 0;
  }

  start() {
    if (this.frameId != null || !this.element) return;
    this.startedAt = this.now();
    this.nextBlinkAt = this.startedAt + nextBlinkDelay(this.random());
    this.frameId = this.requestFrame((timestamp) => this.tick(timestamp));
  }

  setSpeaking(value) {
    this.speaking = Boolean(value);
    this.element?.classList?.toggle("speaking", this.speaking);
    if (!this.speaking) this.setSpeechLevel(0);
  }

  setSpeechLevel(value) {
    this.speechLevel = Math.max(0, Math.min(1, Number(value) || 0));
  }

  tick(timestamp) {
    const current = Number(timestamp) || this.now();
    if (this.blinkStartedAt == null && current >= this.nextBlinkAt) {
      this.blinkStartedAt = current;
    }

    let blink = 0;
    if (this.blinkStartedAt != null) {
      const blinkElapsed = current - this.blinkStartedAt;
      if (blinkElapsed <= 160) {
        blink = Math.sin((Math.max(0, blinkElapsed) / 160) * Math.PI);
      } else {
        this.blinkStartedAt = null;
        this.nextBlinkAt = current + nextBlinkDelay(this.random());
      }
    }

    const motion = avatarMotionFrame(current - this.startedAt, {
      speaking: this.speaking,
      speechLevel: this.speechLevel,
      reducedMotion: this.reducedMotion,
    });
    this.element.style.setProperty("--avatar-rotate", `${motion.rotateDeg.toFixed(3)}deg`);
    this.element.style.setProperty("--avatar-shift-y", `${motion.translateYPercent.toFixed(3)}%`);
    this.element.style.setProperty("--avatar-scale", motion.scale.toFixed(4));
    this.element.style.setProperty("--mouth-open", motion.mouthOpen.toFixed(4));
    this.element.style.setProperty("--blink", blink.toFixed(4));
    this.frameId = this.requestFrame((nextTimestamp) => this.tick(nextTimestamp));
  }

  stop() {
    if (this.frameId != null) this.cancelFrame?.(this.frameId);
    this.frameId = null;
    this.speaking = false;
    this.speechLevel = 0;
    this.element?.classList?.toggle("speaking", false);
    this.element?.style?.setProperty("--avatar-rotate", "0deg");
    this.element?.style?.setProperty("--avatar-shift-y", "0%");
    this.element?.style?.setProperty("--avatar-scale", "1");
    this.element?.style?.setProperty("--mouth-open", "0");
    this.element?.style?.setProperty("--blink", "0");
  }
}

export function applyAvatarSpeechMessage(animator, type, value) {
  if (!animator) return;
  if (type === "speech-state") animator.setSpeaking(Boolean(value));
  if (type === "speech-level") animator.setSpeechLevel(value);
  if (type === "speech-stop") {
    animator.setSpeechLevel(0);
    animator.setSpeaking(false);
  }
}

export function createSpeechEndpoint(apiBaseUrl) {
  return `${String(apiBaseUrl || "").replace(/\/+$/, "")}/assistant/tts`;
}

export function createUnitySpeechMessage(type, value) {
  if (type === "speech-level") {
    value = emphasizeSpeechLevel(value);
  }
  return { source: "campusmate", type, value };
}

export function pcm16ToFloat32(bytes) {
  const count = Math.floor(bytes.byteLength / 2);
  const samples = new Float32Array(count);
  const view = new DataView(bytes.buffer, bytes.byteOffset, count * 2);
  for (let index = 0; index < count; index += 1) {
    samples[index] = Math.max(-1, view.getInt16(index * 2, true) / 32768);
  }
  return samples;
}

export function rmsLevel(samples) {
  if (!samples.length) return 0;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / samples.length);
}

export class PcmStreamPlayer {
  constructor({ sampleRate = 24000, onLevel = () => {}, onState = () => {}, onNeedsGesture = () => {} } = {}) {
    this.sampleRate = sampleRate;
    this.onLevel = onLevel;
    this.onState = onState;
    this.onNeedsGesture = onNeedsGesture;
    this.context = null;
    this.analyser = null;
    this.levelBuffer = null;
    this.sources = new Set();
    this.nextStartTime = 0;
    this.frame = 0;
    this.smoothedLevel = 0;
    this.pendingByte = null;
    this.finishing = false;
  }

  async ensureContext() {
    if (!this.context) {
      const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!Context) throw new Error("当前设备不支持 Web Audio");
      this.context = new Context();
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.connect(this.context.destination);
      this.levelBuffer = new Float32Array(this.analyser.fftSize);
    }
    if (this.context.state === "suspended") await this.context.resume();
    if (this.context.state !== "running") this.onNeedsGesture();
  }

  decode(chunk) {
    const incoming = chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk || 0);
    const prefix = this.pendingByte == null ? 0 : 1;
    const combined = new Uint8Array(prefix + incoming.byteLength);
    if (prefix) combined[0] = this.pendingByte;
    combined.set(incoming, prefix);
    const evenLength = combined.byteLength - (combined.byteLength % 2);
    this.pendingByte = evenLength < combined.byteLength ? combined[combined.byteLength - 1] : null;
    return pcm16ToFloat32(combined.subarray(0, evenLength));
  }

  async append(chunk) {
    const samples = this.decode(chunk);
    if (!samples.length) return;
    await this.ensureContext();
    const buffer = this.context.createBuffer(1, samples.length, this.sampleRate);
    buffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser);
    this.nextStartTime = Math.max(this.context.currentTime + 0.035, this.nextStartTime);
    source.start(this.nextStartTime);
    this.nextStartTime += buffer.duration;
    this.sources.add(source);
    this.finishing = false;
    if (this.sources.size === 1) {
      this.onState(true);
      this.sampleLevel();
    }
    source.onended = () => {
      this.sources.delete(source);
      if (this.finishing && this.sources.size === 0) this.markStopped();
    };
  }

  sampleLevel() {
    if (!this.sources.size || !this.analyser) return;
    this.analyser.getFloatTimeDomainData(this.levelBuffer);
    const raw = rmsLevel(this.levelBuffer);
    const audible = raw < 0.008 ? 0 : Math.min(1, raw * 3.2);
    const smoothing = audible > this.smoothedLevel ? 0.48 : 0.24;
    this.smoothedLevel += (audible - this.smoothedLevel) * smoothing;
    this.onLevel(this.smoothedLevel);
    this.frame = requestAnimationFrame(() => this.sampleLevel());
  }

  finish() {
    this.finishing = true;
    this.pendingByte = null;
    if (!this.sources.size) this.markStopped();
  }

  async togglePaused() {
    if (!this.context || this.context.state === "closed") return false;
    if (this.context.state === "running") {
      await this.context.suspend();
      return true;
    }
    await this.context.resume();
    return false;
  }

  stop() {
    for (const source of this.sources) {
      try { source.stop(); } catch { /* already ended */ }
    }
    this.sources.clear();
    this.nextStartTime = 0;
    this.pendingByte = null;
    this.finishing = false;
    this.markStopped();
  }

  markStopped() {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.smoothedLevel = 0;
    this.onLevel(0);
    this.onState(false);
  }
}
