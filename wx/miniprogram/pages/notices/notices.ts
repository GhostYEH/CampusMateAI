import { repository } from '../../services/repository'
import { ExtractResult, Notice } from '../../services/types'

Page({
  data: {
    notices: [] as Notice[],
    filtered: [] as Notice[],
    query: '',
    sourceText: '各位同学：请于本周五 17:00 前登录教务系统完成 2026 年秋季学期选课确认，如有课程冲突请及时联系学院教务办公室。',
    extracting: false,
    result: null as ExtractResult | null,
    loading: true,
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
  },
  onLoad() {
    this.load()
  },
  load() {
    const settings = repository.getSettings()
    this.setData({
      loading: true,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    setTimeout(() => {
      const notices = repository.getNotices()
      this.setData({ notices, filtered: notices, loading: false })
    }, settings.reduceMotion ? 0 : 180)
  },
  onQuery(event: WechatMiniprogram.Input) {
    const query = event.detail.value
    const normalized = query.trim().toLowerCase()
    const filtered = normalized
      ? this.data.notices.filter((notice) => (
        notice.title.toLowerCase().includes(normalized)
        || notice.source.toLowerCase().includes(normalized)
      ))
      : this.data.notices
    this.setData({ query, filtered })
  },
  onSourceText(event: WechatMiniprogram.Input) {
    this.setData({ sourceText: event.detail.value, result: null })
  },
  async extract() {
    if (this.data.extracting) return
    this.setData({ extracting: true, result: null })
    try {
      const result = await repository.extractNotice(this.data.sourceText)
      this.setData({ result })
    } catch (error) {
      wx.showModal({
        title: '提取失败',
        content: error instanceof Error ? error.message : '请稍后再试',
        showCancel: false,
      })
    } finally {
      this.setData({ extracting: false })
    }
  },
  saveTask() {
    const result = this.data.result
    if (!result || result.saved) return
    repository.addTask(result.title, result.deadline, result.source)
    this.setData({ result: { ...result, saved: true } })
    wx.showToast({ title: '已保存到待办', icon: 'success' })
  },
  openTasks() {
    wx.switchTab({ url: '/pages/tasks/tasks' })
  },
})
