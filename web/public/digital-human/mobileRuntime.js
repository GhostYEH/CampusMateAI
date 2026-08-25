export function normalizeRuntimeConfig(value = {}) {
  return {
    apiBaseUrl: String(value.apiBaseUrl || "").trim().replace(/\/+$/, ""),
    accessToken: String(value.accessToken || "").trim(),
  };
}

export function resolveMobileLayout(search = "") {
  return new URLSearchParams(String(search)).get("layout") === "harmony" ? "harmony" : "default";
}

export function resolveDigitalHumanMode(search = "") {
  return new URLSearchParams(String(search)).get("fallback") === "1" ? "compat" : "live";
}

export function createSpeechEndpoint(apiBaseUrl) {
  return `${String(apiBaseUrl || "").replace(/\/+$/, "")}/assistant/tts`;
}

export function createUnitySpeechMessage(type, value) {
  if (type === "speech-level") {
    value = Math.max(0, Math.min(1, Number(value) || 0));
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
