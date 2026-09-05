function pcm16ToFloat32(bytes) {
  const count = Math.floor(bytes.byteLength / 2);
  const output = new Float32Array(count);
  const view = new DataView(bytes.buffer, bytes.byteOffset, count * 2);
  for (let index = 0; index < count; index += 1) output[index] = Math.max(-1, view.getInt16(index * 2, true) / 32768);
  return output;
}

function rmsLevel(samples) {
  if (!samples.length) return 0;
  let squares = 0;
  for (const sample of samples) squares += sample * sample;
  return Math.max(0, Math.min(1, Math.sqrt(squares / samples.length)));
}

class Pcm16Decoder {
  constructor() { this.pendingByte = null; }
  push(chunk) {
    const incoming = chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk || 0);
    const prefix = this.pendingByte == null ? 0 : 1;
    const combined = new Uint8Array(prefix + incoming.byteLength);
    if (prefix) combined[0] = this.pendingByte;
    combined.set(incoming, prefix);
    const evenLength = combined.byteLength - (combined.byteLength % 2);
    this.pendingByte = evenLength < combined.byteLength ? combined[combined.byteLength - 1] : null;
    return pcm16ToFloat32(combined.subarray(0, evenLength));
  }
  reset() { this.pendingByte = null; }
}

export class PcmStreamPlayer {
  constructor({ sampleRate = 24000, onLevel = () => {}, onState = () => {} } = {}) {
    this.sampleRate = sampleRate;
    this.onLevel = onLevel;
    this.onState = onState;
    this.context = null;
    this.analyser = null;
    this.levelSamples = null;
    this.levelFrame = null;
    this.decoder = new Pcm16Decoder();
    this.sources = new Set();
    this.nextStartTime = 0;
    this.smoothedLevel = 0;
    this.speaking = false;
    this.finishing = false;
  }
  async append(chunk) {
    const samples = this.decoder.push(chunk);
    if (!samples.length) return;
    if (!this.context) {
      const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!Context) throw new Error("当前浏览器不支持 Web Audio");
      this.context = new Context();
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.connect(this.context.destination);
      this.levelSamples = new Float32Array(this.analyser.fftSize);
    }
    if (this.context.state === "suspended") await this.context.resume();
    const buffer = this.context.createBuffer(1, samples.length, this.sampleRate);
    buffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser);
    this.nextStartTime = Math.max(this.context.currentTime + 0.025, this.nextStartTime);
    source.start(this.nextStartTime);
    this.nextStartTime += buffer.duration;
    this.sources.add(source);
    this.finishing = false;
    if (!this.speaking) {
      this.speaking = true;
      this.onState(true);
      this.samplePlaybackLevel();
    }
    source.onended = () => {
      this.sources.delete(source);
      if (this.finishing && this.sources.size === 0) this.markStopped();
    };
  }
  finish() {
    this.finishing = true;
    this.decoder.reset();
    if (this.sources.size === 0) this.markStopped();
  }
  stop() {
    for (const source of this.sources) { try { source.stop(); } catch { /* source already stopped */ } }
    this.sources.clear();
    this.decoder.reset();
    this.nextStartTime = 0;
    this.finishing = false;
    this.markStopped();
  }
  markStopped() {
    if (this.levelFrame != null) globalThis.cancelAnimationFrame?.(this.levelFrame);
    this.levelFrame = null;
    this.smoothedLevel = 0;
    this.onLevel(0);
    if (this.speaking) { this.speaking = false; this.onState(false); }
  }
  samplePlaybackLevel() {
    if (!this.speaking || !this.analyser || !this.levelSamples) return;
    this.analyser.getFloatTimeDomainData(this.levelSamples);
    const rawLevel = rmsLevel(this.levelSamples);
    const audibleLevel = rawLevel < 0.008 ? 0 : Math.min(1, rawLevel * 3.2);
    const smoothing = audibleLevel > this.smoothedLevel ? 0.48 : 0.24;
    this.smoothedLevel += (audibleLevel - this.smoothedLevel) * smoothing;
    this.onLevel(this.smoothedLevel);
    this.levelFrame = (globalThis.requestAnimationFrame || ((callback) => globalThis.setTimeout(callback, 16)))(() => this.samplePlaybackLevel());
  }
}
