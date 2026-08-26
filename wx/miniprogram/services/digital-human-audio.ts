export type DigitalHumanAudioState = 'idle' | 'loading' | 'playing' | 'paused' | 'error'

export interface DigitalHumanAudioSnapshot {
  state: DigitalHumanAudioState
  muted: boolean
  detail: string
}

function writeAscii(view: DataView, offset: number, value: string): void {
  for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index))
}

export function pcm16ToWav(pcm: ArrayBuffer, sampleRate = 24000, channels = 1): ArrayBuffer {
  const source = new Uint8Array(pcm)
  const result = new ArrayBuffer(44 + source.byteLength)
  const view = new DataView(result)
  const bytesPerSample = 2
  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + source.byteLength, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, channels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * channels * bytesPerSample, true)
  view.setUint16(32, channels * bytesPerSample, true)
  view.setUint16(34, bytesPerSample * 8, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, source.byteLength, true)
  new Uint8Array(result, 44).set(source)
  return result
}

export function digitalHumanAvatarUrl(apiBaseUrl: string): string {
  const origin = apiBaseUrl.trim().replace(/\/+$/, '').replace(/\/api\/v1$/, '')
  return origin ? `${origin}/digital-human/fallback-avatar.png` : ''
}

export class DigitalHumanAudioController {
  private readonly audio = wx.createInnerAudioContext()
  private muted = false
  private lastWav?: ArrayBuffer
  private callback: (snapshot: DigitalHumanAudioSnapshot) => void = () => undefined

  constructor() {
    this.audio.onPlay(() => this.publish('playing', 'CPM 正在讲解'))
    this.audio.onPause(() => this.publish('paused', '语音已暂停'))
    this.audio.onStop(() => this.publish('idle', '随时为你解答'))
    this.audio.onEnded(() => this.publish('idle', '随时为你解答'))
    this.audio.onError(() => this.publish('error', '语音播放失败，文字回答不受影响'))
  }

  subscribe(callback: (snapshot: DigitalHumanAudioSnapshot) => void): void {
    this.callback = callback
    this.publish('idle', '随时为你解答')
  }

  async playPcm(pcm: ArrayBuffer): Promise<void> {
    const wav = pcm16ToWav(pcm)
    this.lastWav = wav
    if (this.muted) return
    this.publish('loading', '正在生成 CPM 语音')
    const filePath = `${wx.env.USER_DATA_PATH}/cpm-answer.wav`
    await new Promise<void>((resolve, reject) => wx.getFileSystemManager().writeFile({
      filePath,
      data: wav,
      success: () => resolve(),
      fail: () => reject(new Error('语音文件写入失败')),
    }))
    this.audio.stop()
    this.audio.src = filePath
    this.audio.play()
  }

  toggleMuted(): boolean {
    this.muted = !this.muted
    if (this.muted) this.audio.stop()
    this.publish('idle', this.muted ? '语音已静音' : '语音已开启')
    return this.muted
  }

  togglePaused(): boolean {
    if (this.audio.paused) {
      this.audio.play()
      return false
    }
    this.audio.pause()
    return true
  }

  async replay(): Promise<boolean> {
    if (!this.lastWav || this.muted) return false
    await this.playPcm(this.lastWav.slice(44))
    return true
  }

  stop(): void { this.audio.stop() }

  destroy(): void {
    this.audio.stop()
    this.audio.destroy()
    this.callback = () => undefined
    this.lastWav = undefined
  }

  private publish(state: DigitalHumanAudioState, detail: string): void {
    this.callback({ state, muted: this.muted, detail })
  }
}
