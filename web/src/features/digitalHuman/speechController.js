export class DigitalHumanSpeechController {
  constructor({ player, streamSpeech, onError = () => {} }) {
    this.player = player;
    this.streamSpeech = streamSpeech;
    this.onError = onError;
    this.aborter = null;
    this.muted = false;
  }

  setMuted(value) {
    this.muted = Boolean(value);
    if (this.muted) this.stop();
  }

  async speak(text) {
    this.stop();
    if (this.muted || !String(text || "").trim()) return false;
    const aborter = new AbortController();
    this.aborter = aborter;
    try {
      await this.streamSpeech(text, {
        signal: aborter.signal,
        onChunk: (chunk) => this.player.append(chunk),
      });
      if (this.aborter !== aborter) return false;
      this.player.finish();
      this.aborter = null;
      return true;
    } catch (error) {
      if (this.aborter === aborter) this.aborter = null;
      this.player.stop();
      if (error?.name !== "AbortError") this.onError(error);
      return false;
    }
  }

  stop() {
    this.aborter?.abort();
    this.aborter = null;
    this.player.stop();
  }
}
