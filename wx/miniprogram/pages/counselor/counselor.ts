import {
  completeCpmAnswer,
  CpmCounselorState,
  CpmChatMessage,
  createCpmState,
  failCpmAnswer,
  shouldShowCpmSuggestions,
  shuffleCpmRecommendations,
  submitCpmQuestion,
} from '../../services/cpm-counselor-state'
import {
  digitalHumanAvatarUrl,
  DigitalHumanAudioController,
  DigitalHumanAudioSnapshot,
} from '../../services/digital-human-audio'
import { StableExpressionSignal } from '../../services/expression-signal'
import { LocalVisionSession, VisionState } from '../../services/local-vision-session'
import { repository } from '../../services/repository'
import { ExpressionSignalPayload } from '../../services/types'

let visionSession: LocalVisionSession | undefined
let digitalHumanAudio: DigitalHumanAudioController | undefined

const initialCpmState = createCpmState()

Page({
  data: {
    ...initialCpmState,
    showSuggestions: shouldShowCpmSuggestions(initialCpmState),
    scrollTarget: '',
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
    digitalHumanAvatar: '',
    digitalHumanAvatarFailed: false,
    digitalHumanAudioState: 'idle',
    digitalHumanAudioDetail: '随时为你解答',
    digitalHumanMuted: false,
    digitalHumanPaused: false,
    digitalHumanHasAudio: false,
    visionEnabled: false,
    cameraVisible: false,
    visionStatus: 'idle',
    visionDetail: '尚未启用',
    expressionLabel: '',
    expressionConfidence: 0,
  },

  onLoad() {
    visionSession = new LocalVisionSession()
    visionSession.subscribe((state) => this.onVisionState(state))
    digitalHumanAudio = new DigitalHumanAudioController()
    digitalHumanAudio.subscribe((snapshot) => this.onDigitalHumanAudioState(snapshot))
  },

  onShow() {
    const settings = repository.getSettings()
    this.setData({
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
      digitalHumanAvatar: digitalHumanAvatarUrl(settings.apiBaseUrl),
      digitalHumanAvatarFailed: false,
    })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },

  onHide() {
    visionSession?.stop()
    digitalHumanAudio?.stop()
    this.setData({ cameraVisible: false })
  },

  onUnload() {
    visionSession?.destroy()
    visionSession = undefined
    digitalHumanAudio?.destroy()
    digitalHumanAudio = undefined
  },

  onInput(event: WechatMiniprogram.Input) {
    this.setData({ input: event.detail.value })
  },

  useSuggestion(event: WechatMiniprogram.TouchEvent) {
    void this.sendPrompt(event.currentTarget.dataset.text as string)
  },

  shuffleSuggestions() {
    const next = shuffleCpmRecommendations(this.currentCpmState())
    this.setData({ recommendations: next.recommendations, recommendationOffset: next.recommendationOffset })
  },

  enableVision() {
    wx.showModal({
      title: '启用本机表情陪伴？',
      content: '前置摄像头画面只在本机用于识别可见表情或学习状态，不识别身份、不上传、不保存。退出本页即停止。',
      confirmText: '同意并启用',
      success: (result) => { if (result.confirm) this.requestCameraPermission() },
    })
  },

  requestCameraPermission() {
    wx.authorize({
      scope: 'scope.camera',
      success: () => { void this.prepareVision() },
      fail: () => {
        this.setData({ visionStatus: 'permission', visionDetail: '摄像头权限未授权，可在小程序设置中开启' })
        wx.showModal({
          title: '需要摄像头权限',
          content: '请在设置中允许使用摄像头；未授权时 CPM 问答仍可正常使用。',
          confirmText: '去设置',
          success: (result) => { if (result.confirm) wx.openSetting() },
        })
      },
    })
  },

  async prepareVision() {
    const modelUrl = repository.getSettings().expressionModelUrl
    const prepared = await visionSession?.prepare(modelUrl)
    if (!prepared) return
    this.setData({ visionEnabled: true, cameraVisible: true })
    wx.nextTick(() => visionSession?.start(wx.createCameraContext()))
  },

  disableVision() {
    visionSession?.stop()
    this.setData({ visionEnabled: false, cameraVisible: false, expressionLabel: '', expressionConfidence: 0 })
  },

  onCameraError(event: WechatMiniprogram.CustomEvent<{ errMsg: string }>) {
    visionSession?.stop()
    this.setData({
      cameraVisible: false,
      visionStatus: 'error',
      visionDetail: event.detail.errMsg || '前置摄像头不可用',
    })
  },

  onVisionState(state: VisionState) {
    const signal = state.signal
    this.setData({
      visionStatus: state.status,
      visionDetail: state.detail,
      expressionLabel: signal?.label || '',
      expressionConfidence: signal ? Math.round(signal.confidence * 100) : 0,
    })
  },

  send() {
    void this.sendPrompt(this.data.input)
  },

  async sendPrompt(rawQuestion: string) {
    const current = this.currentCpmState()
    const started = submitCpmQuestion(current, rawQuestion, Date.now())
    if (started === current || !started.sending) return
    const assistantMessage = started.messages[started.messages.length - 1]
    this.syncCpmState(started, assistantMessage.id)

    try {
      const reply = await repository.chat(started.lastPrompt, this.currentExpressionPayload())
      const completed = completeCpmAnswer(started, assistantMessage.id, reply.answer, reply.citation)
      this.syncCpmState(completed, assistantMessage.id)
      void this.playDigitalHuman(completed.speechText)
    } catch (error) {
      const detail = error instanceof Error ? error.message : '校园服务暂时不可用'
      this.syncCpmState(failCpmAnswer(started, assistantMessage.id, detail), assistantMessage.id)
    }
  },

  retryLastMessage() {
    if (!this.data.lastPrompt || this.data.sending) return
    const currentMessages = this.data.messages as CpmChatMessage[]
    const lastMessage = currentMessages[currentMessages.length - 1]
    const messages = lastMessage?.status === 'ERROR' ? currentMessages.slice(0, -2) : currentMessages
    this.setData({ messages, chatActive: messages.length > 0 })
    void this.sendPrompt(this.data.lastPrompt)
  },

  async playDigitalHuman(text: string) {
    try {
      const pcm = await repository.synthesizeCpmSpeech(text)
      if (!pcm) {
        this.setData({ digitalHumanAudioDetail: '演示模式仅展示文字回答' })
        return
      }
      await digitalHumanAudio?.playPcm(pcm)
      this.setData({ digitalHumanHasAudio: true })
    } catch (_) {
      this.setData({ digitalHumanAudioState: 'error', digitalHumanAudioDetail: '语音生成失败，文字回答不受影响' })
    }
  },

  toggleDigitalHumanMute() {
    const muted = digitalHumanAudio?.toggleMuted() || false
    this.setData({ digitalHumanMuted: muted, digitalHumanPaused: false })
    if (!muted && this.data.digitalHumanHasAudio) void digitalHumanAudio?.replay()
  },

  toggleDigitalHumanPause() {
    if (!this.data.digitalHumanHasAudio || this.data.digitalHumanMuted) {
      wx.showToast({ title: this.data.digitalHumanMuted ? '请先取消静音' : '暂无可播放语音', icon: 'none' })
      return
    }
    const paused = digitalHumanAudio?.togglePaused() || false
    this.setData({ digitalHumanPaused: paused })
  },

  async replayDigitalHuman() {
    if (!this.data.digitalHumanHasAudio) {
      wx.showToast({ title: '暂无可重播语音', icon: 'none' })
      return
    }
    const replayed = await digitalHumanAudio?.replay()
    if (!replayed) wx.showToast({ title: this.data.digitalHumanMuted ? '请先取消静音' : '暂无可重播语音', icon: 'none' })
  },

  onDigitalHumanAvatarError() {
    this.setData({ digitalHumanAvatarFailed: true })
  },

  onDigitalHumanAudioState(snapshot: DigitalHumanAudioSnapshot) {
    this.setData({
      digitalHumanAudioState: snapshot.state,
      digitalHumanAudioDetail: snapshot.detail,
      digitalHumanMuted: snapshot.muted,
      digitalHumanPaused: snapshot.state === 'paused',
    })
  },

  currentCpmState(): CpmCounselorState {
    return {
      messages: this.data.messages as CpmChatMessage[],
      input: this.data.input,
      sending: this.data.sending,
      chatActive: this.data.chatActive,
      recommendationOffset: this.data.recommendationOffset,
      recommendations: this.data.recommendations,
      speechText: this.data.speechText,
      speechRequestId: this.data.speechRequestId,
      lastPrompt: this.data.lastPrompt,
    }
  },

  syncCpmState(state: CpmCounselorState, scrollTarget = '') {
    this.setData({
      ...state,
      showSuggestions: shouldShowCpmSuggestions(state),
      scrollTarget: scrollTarget ? `message-${scrollTarget}` : this.data.scrollTarget,
    })
  },

  currentExpressionPayload(): ExpressionSignalPayload | undefined {
    const signal: StableExpressionSignal | undefined = visionSession?.latestSignal()
    return signal ? {
      label: signal.label,
      confidence: signal.confidence,
      is_stable: signal.isStable,
      timestamp: signal.timestamp,
      model_version: signal.modelVersion,
    } : undefined
  },
})
