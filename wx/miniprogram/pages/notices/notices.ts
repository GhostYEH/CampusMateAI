import { repository } from '../../services/repository'
import { ExtractResult, Notice } from '../../services/types'

Page({
  data: {
    notices: [] as Notice[],
    filtered: [] as Notice[],
    query: '',
    sourceText: '各位同学：请于本周五 17:00 前登录教务系统完成 2026 年秋季学期选课确认，如有课程冲突请及时联系学院教务办公室。',
    extracting: false,
    results: [] as ExtractResult[],
    loading: true,
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
    error: '',
  },
  onLoad() {
    this.load()
  },
  async load() {
    const settings = repository.getSettings()
    this.setData({
      loading: true,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
      error: '',
    })
    try {
      if (!settings.reduceMotion) await new Promise((resolve) => setTimeout(resolve, 180))
      const notices = await repository.getNoticesAsync()
      this.setData({ notices, filtered: notices, loading: false })
    } catch (error) {
      this.setData({
        notices: [],
        filtered: [],
        loading: false,
        error: error instanceof Error ? error.message : '通知加载失败',
      })
    }
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
    this.setData({ sourceText: event.detail.value, results: [] })
  },
  async extract() {
    if (this.data.extracting) return
    this.setData({ extracting: true, results: [] })
    try {
      const results = await repository.extractNotice(this.data.sourceText)
      this.setData({ results })
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
  async saveTask(event: WechatMiniprogram.TouchEvent) {
    const id = event.currentTarget.dataset.id as string
    const result = this.data.results.find((item) => item.id === id)
    if (!result || result.saved) return
    try {
      wx.showLoading({ title: '正在保存' })
      await repository.addTask(
        result.title,
        result.rawDeadline || result.deadline,
        result.source,
        result.sourceText,
      )
      this.setData({
        results: this.data.results.map((item) => (
          item.id === id ? { ...item, saved: true } : item
        )),
      })
      wx.showToast({ title: '已保存到待办', icon: 'success' })
    } catch (error) {
      wx.showModal({
        title: '保存失败',
        content: error instanceof Error ? error.message : '请稍后重试',
        showCancel: false,
      })
    } finally {
      wx.hideLoading()
    }
  },
  openTasks() {
    wx.switchTab({ url: '/pages/tasks/tasks' })
  },
})
