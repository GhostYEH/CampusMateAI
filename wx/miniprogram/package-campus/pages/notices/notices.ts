import {
  createInboxRecord, filterInboxRecords, NotificationFilter,
  NotificationInboxRecord, NotificationInboxStore,
} from '../../../services/notification-inbox'
import { repository } from '../../../services/repository'
import { ExtractResult, Notice } from '../../../services/types'

const inboxStore = new NotificationInboxStore()

Page({
  data: {
    notices: [] as Notice[], filteredNotices: [] as Notice[],
    localNotices: [] as NotificationInboxRecord[], filteredLocalNotices: [] as NotificationInboxRecord[],
    selectedLocalNotice: null as NotificationInboxRecord | null,
    sourceFilters: [
      { value: 'all', label: '全部' }, { value: 'wechat', label: '微信' },
      { value: 'wecom', label: '企业微信' }, { value: 'qq', label: 'QQ' },
      { value: 'xuexitong', label: '学习通' }, { value: 'campus', label: '校园' },
    ],
    activeSource: 'all' as NotificationFilter, query: '',
    sourceText: '各位同学：请于本周五 17:00 前登录教务系统完成 2026 年秋季学期选课确认，如有课程冲突请及时联系学院教务办公室。',
    extracting: false, results: [] as ExtractResult[], loading: true,
    mockMode: true, reduceMotion: false, darkMode: false, error: '',
  },

  onLoad() { this.load() },
  onShow() { this.refreshLocalInbox() },
  async load() {
    const settings = repository.getSettings()
    this.setData({ loading: true, mockMode: settings.mockMode, reduceMotion: settings.reduceMotion, darkMode: settings.darkMode, error: '' })
    this.refreshLocalInbox()
    try {
      const notices = await repository.getNoticesAsync()
      this.setData({ notices, filteredNotices: this.filterRemoteNotices(notices, this.data.query), loading: false })
    } catch (error) {
      this.setData({ notices: [], filteredNotices: [], loading: false, error: error instanceof Error ? error.message : '通知加载失败' })
    }
  },
  refreshLocalInbox() {
    const localNotices = inboxStore.load()
    this.setData({ localNotices, filteredLocalNotices: filterInboxRecords(localNotices, this.data.activeSource, this.data.query) })
  },
  onQuery(event: WechatMiniprogram.Input) {
    const query = event.detail.value
    this.setData({ query, filteredNotices: this.filterRemoteNotices(this.data.notices, query), filteredLocalNotices: filterInboxRecords(this.data.localNotices, this.data.activeSource, query) })
  },
  selectSource(event: WechatMiniprogram.TouchEvent) {
    const activeSource = event.currentTarget.dataset.source as NotificationFilter
    this.setData({ activeSource, filteredLocalNotices: filterInboxRecords(this.data.localNotices, activeSource, this.data.query) })
  },
  onSourceText(event: WechatMiniprogram.Input) { this.setData({ sourceText: event.detail.value, results: [] }) },
  importClipboard() {
    wx.getClipboardData({
      success: (response) => {
        const content = response.data.trim()
        if (!content) { wx.showToast({ title: '剪贴板没有文字', icon: 'none' }); return }
        this.importText(content, '剪贴板')
      },
      fail: () => wx.showToast({ title: '未能读取剪贴板，请手动粘贴', icon: 'none' }),
    })
  },
  importText(content: string, sourceName: string) {
    const title = content.split(/\r?\n/).map((line) => line.trim()).find(Boolean) || '校园通知'
    const localNotices = inboxStore.add(createInboxRecord(sourceName, title.slice(0, 60), content))
    this.setData({ sourceText: content, results: [], localNotices, filteredLocalNotices: filterInboxRecords(localNotices, this.data.activeSource, this.data.query) })
    wx.showToast({ title: '已导入，可开始整理', icon: 'success' })
  },
  async extract() {
    if (this.data.extracting) return
    const content = this.data.sourceText.trim()
    if (!content) return
    this.importText(content, '手动导入')
    this.setData({ extracting: true, results: [] })
    try { this.setData({ results: await repository.extractNotice(content) }) }
    catch (error) { wx.showModal({ title: '提取失败', content: error instanceof Error ? error.message : '请稍后再试', showCancel: false }) }
    finally { this.setData({ extracting: false }) }
  },
  updateResultField(event: WechatMiniprogram.Input) {
    const id = event.currentTarget.dataset.id as string
    const field = event.currentTarget.dataset.field as 'title' | 'source' | 'deadline'
    const value = event.detail.value
    this.setData({ results: this.data.results.map((item) => item.id === id ? { ...item, [field]: value } : item) })
  },
  async saveTask(event: WechatMiniprogram.TouchEvent) {
    const id = event.currentTarget.dataset.id as string
    const result = this.data.results.find((item) => item.id === id)
    if (!result || result.saved || !result.title.trim()) return
    try {
      wx.showLoading({ title: '正在保存' })
      await repository.addTask(result.title.trim(), result.rawDeadline || result.deadline, result.source.trim(), result.sourceText)
      this.setData({ results: this.data.results.map((item) => item.id === id ? { ...item, saved: true } : item) })
      wx.showToast({ title: '已保存到待办', icon: 'success' })
    } catch (error) {
      wx.showModal({ title: '保存失败', content: error instanceof Error ? error.message : '请稍后重试', showCancel: false })
    } finally { wx.hideLoading() }
  },
  openLocalNotice(event: WechatMiniprogram.TouchEvent) {
    const id = event.currentTarget.dataset.id as string
    this.setData({ selectedLocalNotice: this.data.localNotices.find((item) => item.id === id) || null })
  },
  closeLocalNotice() { this.setData({ selectedLocalNotice: null }) },
  noop() {},
  useSelectedNotice() {
    const notice = this.data.selectedLocalNotice
    if (!notice) return
    this.setData({ sourceText: notice.content, results: [], selectedLocalNotice: null })
    wx.pageScrollTo({ selector: '#manual-extract', duration: this.data.reduceMotion ? 0 : 260 })
  },
  deleteLocalNotice(event: WechatMiniprogram.TouchEvent) {
    const id = (event.currentTarget.dataset.id as string) || this.data.selectedLocalNotice?.id
    if (!id) return
    const localNotices = inboxStore.remove(id)
    this.setData({ localNotices, filteredLocalNotices: filterInboxRecords(localNotices, this.data.activeSource, this.data.query), selectedLocalNotice: null })
  },
  clearLocalNotices() {
    if (!this.data.localNotices.length) return
    wx.showModal({ title: '清空最近导入？', content: '只会删除本机导入记录，不影响校园后端通知。', confirmText: '清空', success: (result) => {
      if (result.confirm) { inboxStore.clear(); this.setData({ localNotices: [], filteredLocalNotices: [], selectedLocalNotice: null }) }
    } })
  },
  openTasks() { wx.switchTab({ url: '/pages/tasks/tasks' }) },
  filterRemoteNotices(notices: Notice[], query: string): Notice[] {
    const normalized = query.trim().toLowerCase()
    return normalized ? notices.filter((notice) => `${notice.title} ${notice.source}`.toLowerCase().includes(normalized)) : notices
  },
})
