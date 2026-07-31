import { repository } from '../../services/repository'
import { ChatMessage } from '../../services/types'

Page({
  data: {
    messages: [
      {
        id: 1,
        role: 'assistant',
        text: '你好，我是 AI 导员。可以帮你整理校园办事流程、所需材料与下一步。当前为 Mock 知识库演示，请以学校最新通知为准。',
        citation: 'Mock 校园知识库',
      },
    ] as ChatMessage[],
    suggestions: ['奖学金申请需要哪些材料？', '缓考申请怎么提交？', '帮我整理竞赛报名步骤'],
    input: '',
    sending: false,
    scrollTarget: 'message-1',
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
  },
  onShow() {
    const settings = repository.getSettings()
    this.setData({
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
  },
  onInput(event: WechatMiniprogram.Input) {
    this.setData({ input: event.detail.value })
  },
  useSuggestion(event: WechatMiniprogram.TouchEvent) {
    this.setData({ input: event.currentTarget.dataset.text as string })
    this.send()
  },
  async send() {
    const message = this.data.input.trim()
    if (!message || this.data.sending) return
    const userMessage: ChatMessage = { id: Date.now(), role: 'user', text: message }
    const messages = [...this.data.messages, userMessage]
    this.setData({
      messages,
      input: '',
      sending: true,
      scrollTarget: `message-${userMessage.id}`,
    })
    try {
      const reply = await repository.chat(message)
      const assistantMessage: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        text: reply.answer,
        citation: reply.citation,
      }
      this.setData({
        messages: [...messages, assistantMessage],
        scrollTarget: `message-${assistantMessage.id}`,
      })
    } catch (error) {
      wx.showModal({
        title: '暂时无法回答',
        content: error instanceof Error ? error.message : '校园服务暂时不可用',
        showCancel: false,
      })
    } finally {
      this.setData({ sending: false })
    }
  },
})
