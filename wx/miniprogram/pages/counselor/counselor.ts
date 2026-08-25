import { greetingForExpression, StableExpressionSignal } from '../../services/expression-signal'
import { LocalVisionSession, VisionState } from '../../services/local-vision-session'
import { repository } from '../../services/repository'
import { ChatMessage, ExpressionSignalPayload } from '../../services/types'

let visionSession: LocalVisionSession | undefined

Page({
  data: {
    messages: [{
      id: 1, role: 'assistant',
      text: '你好，我是 AI 校园助手小灵。课程流程、奖助政策和校园服务，都可以来问我。\n\n我会结合校园知识库与后端配置，帮你整理清晰步骤。',
      citation: '校园知识库',
    }] as ChatMessage[],
    suggestions: [
      { label: '奖学金申请材料清单', prompt: '奖学金申请需要什么材料？', icon: '/assets/icons/service-academic.svg' },
      { label: '课程重修办理流程', prompt: '课程重修怎么办理？', icon: '/assets/icons/tab-courses-active-light.svg' },
      { label: '校园卡丢失补办地点', prompt: '校园卡丢失去哪里补办？', icon: '/assets/icons/service-account.svg' },
      { label: '请假流程怎么走', prompt: '请假流程怎么走？', icon: '/assets/icons/service-notices.svg' },
    ],
    input: '', sending: false, scrollTarget: 'message-1', lastFailedMessage: '', error: '',
    mockMode: true, reduceMotion: false, darkMode: false,
    visionEnabled: false, cameraVisible: false, visionStatus: 'idle', visionDetail: '尚未启用',
    expressionLabel: '', expressionConfidence: 0,
  },

  onLoad() {
    visionSession = new LocalVisionSession()
    visionSession.subscribe((state) => this.onVisionState(state))
  },
  onShow() {
    const settings = repository.getSettings()
    this.setData({ mockMode: settings.mockMode, reduceMotion: settings.reduceMotion, darkMode: settings.darkMode })
    wx.nextTick(() => { const tabBar = this.getTabBar(); if (tabBar) tabBar.sync() })
  },
  onHide() { visionSession?.stop(); this.setData({ cameraVisible: false }) },
  onUnload() { visionSession?.destroy(); visionSession = undefined },
  onInput(event: WechatMiniprogram.Input) { this.setData({ input: event.detail.value }) },
  useSuggestion(event: WechatMiniprogram.TouchEvent) {
    this.setData({ input: event.currentTarget.dataset.text as string })
    this.send()
  },

  enableVision() {
    wx.showModal({
      title: '启用本机表情陪伴？',
      content: '前置摄像头画面只在本机用于识别可见表情，不识别身份、不上传、不保存。退出本页即停止。',
      confirmText: '同意并启用',
      success: (result) => { if (result.confirm) this.requestCameraPermission() },
    })
  },
  requestCameraPermission() {
    wx.authorize({
      scope: 'scope.camera',
      success: () => this.prepareVision(),
      fail: () => {
        this.setData({ visionStatus: 'permission', visionDetail: '摄像头权限未授权，可在小程序设置中开启' })
        wx.showModal({ title: '需要摄像头权限', content: '请在设置中允许使用摄像头；未授权时 AI 问答仍可正常使用。', confirmText: '去设置', success: (result) => { if (result.confirm) wx.openSetting() } })
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
    this.setData({ cameraVisible: false, visionStatus: 'error', visionDetail: event.detail.errMsg || '前置摄像头不可用' })
  },
  onVisionState(state: VisionState) {
    const signal = state.signal
    this.setData({
      visionStatus: state.status,
      visionDetail: state.detail,
      expressionLabel: signal?.label || '',
      expressionConfidence: signal ? Math.round(signal.confidence * 100) : 0,
    })
    if (signal && this.data.messages.length === 1) {
      const greeting = greetingForExpression(signal)
      if (greeting) this.setData({ messages: [{ id: Date.now(), role: 'assistant', text: greeting, citation: '本机可见表情辅助' }] })
    }
  },

  async send() {
    const message = this.data.input.trim()
    if (!message || this.data.sending) return
    const userMessage: ChatMessage = { id: Date.now(), role: 'user', text: message }
    const messages = [...this.data.messages, userMessage]
    this.setData({ messages, input: '', sending: true, error: '', lastFailedMessage: '', scrollTarget: `message-${userMessage.id}` })
    try {
      const reply = await repository.chat(message, this.currentExpressionPayload())
      const assistantMessage: ChatMessage = { id: Date.now() + 1, role: 'assistant', text: reply.answer, citation: reply.citation }
      this.setData({ messages: [...messages, assistantMessage], scrollTarget: `message-${assistantMessage.id}` })
    } catch (error) {
      this.setData({ error: error instanceof Error ? error.message : '校园服务暂时不可用', lastFailedMessage: message })
    } finally { this.setData({ sending: false }) }
  },
  retryLastMessage() {
    if (!this.data.lastFailedMessage || this.data.sending) return
    this.setData({ input: this.data.lastFailedMessage, error: '', lastFailedMessage: '' })
    this.send()
  },
  dismissError() { this.setData({ error: '', lastFailedMessage: '' }) },
  currentExpressionPayload(): ExpressionSignalPayload | undefined {
    const signal: StableExpressionSignal | undefined = visionSession?.latestSignal()
    return signal ? {
      label: signal.label, confidence: signal.confidence, is_stable: signal.isStable,
      timestamp: signal.timestamp, model_version: signal.modelVersion,
    } : undefined
  },
})
