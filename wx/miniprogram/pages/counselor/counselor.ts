import { repository } from '../../services/repository'
import { ChatMessage } from '../../services/types'

Page({
  data: {
    messages: [
      {
        id: 1,
        role: 'assistant',
        text: '你好，我是 AI 校园助手小灵。课程流程、奖助政策和校园服务，都可以来问我。\n\n我会结合校园知识库与后端配置，帮你整理清晰步骤。',
        citation: '校园知识库',
      },
    ] as ChatMessage[],
    suggestions: [
      { label: '奖学金申请材料清单', icon: '/assets/icons/service-academic.svg' },
      { label: '课程重修办理流程', icon: '/assets/icons/tab-courses-active-light.svg' },
      { label: '校园卡丢失补办地点', icon: '/assets/icons/service-account.svg' },
      { label: '请假流程怎么走', icon: '/assets/icons/service-notices.svg' },
    ],
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
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
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
