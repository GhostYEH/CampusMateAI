import { repository } from '../../services/repository'
import { AppSettings, User } from '../../services/types'

Page({
  data: {
    user: null as User | null,
    settings: repository.getSettings() as AppSettings,
    editingUrl: false,
    apiBaseUrlInput: '',
  },
  onShow() {
    const user = repository.getSession()
    if (!user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    const settings = repository.getSettings()
    this.setData({
      user,
      settings,
      apiBaseUrlInput: settings.apiBaseUrl,
    })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  toggleMock(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ mockMode: event.detail.value })
    wx.showToast({
      title: event.detail.value ? '已切换到 Mock 模式' : '已切换到真实后端',
      icon: 'none',
    })
  },
  toggleMotion(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ reduceMotion: event.detail.value })
  },
  toggleDark(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ darkMode: event.detail.value })
  },
  toggleReminders(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ remindersEnabled: event.detail.value })
  },
  toggleDemo(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ demoMode: event.detail.value })
  },
  saveSetting(next: Partial<AppSettings>) {
    this.setData({ settings: repository.saveSettings(next) })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  editUrl() {
    this.setData({ editingUrl: true })
  },
  onUrlInput(event: WechatMiniprogram.Input) {
    this.setData({ apiBaseUrlInput: event.detail.value })
  },
  saveUrl() {
    const apiBaseUrl = this.data.apiBaseUrlInput.trim().replace(/\/$/, '')
    if (apiBaseUrl && !/^https?:\/\//.test(apiBaseUrl)) {
      wx.showToast({ title: '请输入 http(s) 地址', icon: 'none' })
      return
    }
    this.saveSetting({ apiBaseUrl })
    this.setData({ editingUrl: false })
    wx.showToast({ title: '后端地址已保存', icon: 'success' })
  },
  logout() {
    wx.showModal({
      title: '退出当前账号？',
      content: '本机待办与学习记录会保留。',
      confirmText: '退出',
      success: (result) => {
        if (!result.confirm) return
        repository.logout()
        wx.reLaunch({ url: '/pages/login/login' })
      },
    })
  },
})
