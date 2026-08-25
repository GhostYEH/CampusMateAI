import { ExpressionSignalProcessor, StableExpressionSignal } from './expression-signal'
import { EXPRESSION_INPUT_SHAPE, preprocessExpressionFrame } from './vision-preprocess'

export type VisionStatus = 'idle' | 'checking' | 'permission' | 'model-missing' | 'loading' | 'running' | 'unsupported' | 'error'

export interface VisionState {
  status: VisionStatus
  detail: string
  signal?: StableExpressionSignal
}

interface InferenceTensor { type: 'float32'; shape: number[]; data: ArrayBuffer }
interface InferenceOutput { data: ArrayBuffer | Float32Array }
interface InferenceSession {
  onLoad(callback: () => void): void
  onError(callback: (error: { errMsg?: string }) => void): void
  run(inputs: Record<string, InferenceTensor>): Promise<Record<string, InferenceOutput>>
  destroy(): void
}
interface InferenceApi {
  createInferenceSession?: (options: { model: string; precisionLevel: number; allowNPU: boolean; allowQuantize: boolean }) => InferenceSession
  getInferenceEnvInfo?: (options: { success: () => void; fail: (error: { errMsg?: string }) => void }) => void
}

const LABELS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
const FRAME_INTERVAL_MS = 750

export class LocalVisionSession {
  private state: VisionState = { status: 'idle', detail: '尚未启用' }
  private readonly processor = new ExpressionSignalProcessor()
  private session?: InferenceSession
  private preparedModelUrl = ''
  private listener?: WechatMiniprogram.CameraFrameListener
  private lastFrameAt = 0
  private processing = false
  private active = false
  private onState: (state: VisionState) => void = () => undefined

  subscribe(callback: (state: VisionState) => void): void {
    this.onState = callback
    callback(this.state)
  }

  latestSignal(): StableExpressionSignal | undefined { return this.processor.latest() }

  async prepare(modelUrl: string): Promise<boolean> {
    this.publish('checking', '正在检查本机推理能力')
    const api = wx as unknown as InferenceApi
    if (!wx.canIUse('createInferenceSession') || !api.createInferenceSession || !api.getInferenceEnvInfo) {
      this.publish('unsupported', '当前微信版本不支持本机 ONNX 推理')
      return false
    }
    const normalizedModelUrl = modelUrl.trim()
    if (!normalizedModelUrl) {
      this.publish('model-missing', '未配置兼容的表情 ONNX 模型地址')
      return false
    }
    if (!/^https:\/\//.test(normalizedModelUrl)) {
      this.publish('error', '表情模型必须使用 HTTPS 下载地址')
      return false
    }
    if (this.session && this.preparedModelUrl === normalizedModelUrl) {
      this.publish('permission', '模型已就绪，等待前置摄像头授权')
      return true
    }
    try {
      await this.checkEnvironment(api)
      this.session?.destroy()
      this.session = undefined
      this.preparedModelUrl = ''
      const modelPath = await this.obtainModel(normalizedModelUrl)
      await this.createSession(api, modelPath)
      this.preparedModelUrl = normalizedModelUrl
      this.publish('permission', '模型已就绪，等待前置摄像头授权')
      return true
    } catch (error) {
      this.publish('error', error instanceof Error ? error.message : '本机模型加载失败')
      return false
    }
  }

  start(cameraContext: WechatMiniprogram.CameraContext): void {
    if (!this.session || this.active) return
    this.active = true
    this.listener = cameraContext.onCameraFrame((frame) => this.consumeFrame(frame))
    this.listener.start({
      success: () => this.publish('running', '正在本机识别可见表情，画面不上传、不保存'),
      fail: () => { this.active = false; this.publish('error', '无法读取前置摄像头画面') },
    })
  }

  stop(): void {
    this.active = false
    this.listener?.stop()
    this.listener = undefined
    this.processor.reset()
    if (this.session) this.publish('permission', '本机识别已停止')
    else this.publish('idle', '尚未启用')
  }

  destroy(): void {
    this.stop()
    this.session?.destroy()
    this.session = undefined
    this.preparedModelUrl = ''
    this.onState = () => undefined
  }

  private async consumeFrame(frame: WechatMiniprogram.OnCameraFrameCallbackResult): Promise<void> {
    const now = Date.now()
    if (!this.active || !this.session || this.processing || now - this.lastFrameAt < FRAME_INTERVAL_MS) return
    this.lastFrameAt = now
    this.processing = true
    try {
      const tensor = preprocessExpressionFrame(frame.data, frame.width, frame.height)
      const activeSession = this.session
      const outputs = await activeSession.run({ input: { type: 'float32', shape: EXPRESSION_INPUT_SHAPE, data: tensor.buffer } })
      if (!this.active || this.session !== activeSession) return
      const first = outputs[Object.keys(outputs)[0]]
      if (!first) throw new Error('模型没有返回输出张量')
      const scores = first.data instanceof Float32Array ? first.data : new Float32Array(first.data)
      let best = 0
      for (let index = 1; index < Math.min(scores.length, LABELS.length); index += 1) if (scores[index] > scores[best]) best = index
      const signal = this.processor.push({ label: LABELS[best], confidence: scores[best], timestamp: now })
      if (signal) this.publish('running', `稳定表情：${this.displayLabel(signal.label)} · 仅本机处理`, signal)
    } catch (error) {
      if (!this.active) return
      this.publish('error', error instanceof Error ? error.message : '本机推理失败')
      this.active = false
      this.listener?.stop()
    } finally { this.processing = false }
  }

  private checkEnvironment(api: InferenceApi): Promise<void> {
    return new Promise((resolve, reject) => api.getInferenceEnvInfo?.({
      success: resolve,
      fail: (error) => reject(new Error(error.errMsg || '当前设备不支持微信本机推理')),
    }))
  }

  private obtainModel(modelUrl: string): Promise<string> {
    return new Promise((resolve, reject) => wx.downloadFile({
      url: modelUrl,
      success: (download) => {
        if (download.statusCode < 200 || download.statusCode >= 300) { reject(new Error('模型下载失败')); return }
        wx.getFileSystemManager().saveFile({
          tempFilePath: download.tempFilePath,
          success: (saved) => resolve(saved.savedFilePath),
          fail: () => reject(new Error('模型无法保存到本机缓存')),
        })
      },
      fail: () => reject(new Error('模型下载失败，请检查下载域名配置')),
    }))
  }

  private createSession(api: InferenceApi, modelPath: string): Promise<void> {
    this.publish('loading', '正在加载本机表情模型')
    return new Promise((resolve, reject) => {
      const session = api.createInferenceSession?.({ model: modelPath, precisionLevel: 3, allowNPU: true, allowQuantize: false })
      if (!session) { reject(new Error('无法创建本机推理会话')); return }
      session.onLoad(() => { this.session = session; resolve() })
      session.onError((error) => reject(new Error(error.errMsg || '表情模型与当前设备不兼容')))
    })
  }

  private publish(status: VisionStatus, detail: string, signal?: StableExpressionSignal): void {
    this.state = { status, detail, ...(signal ? { signal } : {}) }
    this.onState(this.state)
  }

  private displayLabel(label: string): string {
    return ({ angry: '生气', disgust: '不适', fear: '紧张', happy: '愉快', neutral: '平静', sad: '难过', surprise: '惊讶' } as Record<string, string>)[label] || label
  }
}
