import { repository } from '../../services/repository'
import { AppSettings, User } from '../../services/types'
import { parseQrPayload } from '../../utils/qr-payload-parser'

Page({
  data: {
    user: null as User | null,
    settings: repository.getSettings() as AppSettings,
    editingUrl: false,
    apiBaseUrlInput: '',
    expressionModelUrlInput: '',
    showSettings: false,
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
      expressionModelUrlInput: settings.expressionModelUrl,
    })
    wx.nextTick(() => {
      const tabBar = this.getTabBar()
      if (tabBar) tabBar.sync()
    })
  },
  toggleMock(event: WechatMiniprogram.SwitchChange) {
    this.saveSetting({ mockMode: event.detail.value })
    repository.logout().finally(() => {
      wx.showToast({
        title: event.detail.value ? '已切换到 Mock，请重新登录' : '已切换到真实后端，请登录',
        icon: 'none',
      })
      setTimeout(() => wx.reLaunch({ url: '/pages/login/login' }), 400)
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
  openService(event: WechatMiniprogram.TouchEvent) {
    const kind = event.currentTarget.dataset.kind as string
    if (kind === 'files' || kind === 'favorites' || kind === 'help') {
      wx.navigateTo({ url: `/pages/hub/hub?kind=${kind}` })
      return
    }
    if (kind === 'academic') {
      wx.navigateTo({ url: '/package-academic/pages/edu/edu' })
      return
    }
    if (kind === 'university') {
      wx.navigateTo({ url: `/pages/hub/hub?kind=${kind}` })
      return
    }
    if (kind === 'community') {
      wx.navigateTo({ url: '/package-community/pages/community/community' })
      return
    }
    if (kind === 'study') {
      wx.navigateTo({ url: '/package-study/pages/study/study' })
      return
    }
    if (kind === 'notices') {
      wx.navigateTo({ url: '/package-campus/pages/notices/notices' })
      return
    }
    if (kind === 'settings' || kind === 'account') {
      this.setData({ showSettings: true })
      setTimeout(() => wx.pageScrollTo({ selector: '#settings-panel', duration: 260 }), 30)
      return
    }
    if (kind === 'about') {
      wx.showModal({ title: 'CampusMate', content: '大学生校园事务智能陪伴助手\n微信小程序端', showCancel: false })
      return
    }
    wx.showToast({ title: '该功能正在接入小程序', icon: 'none' })
  },
  closeSettings() {
    this.setData({ showSettings: false, editingUrl: false })
  },
  /**
   * 扫码登录 Web 端 — 调起微信原生扫码 (wx.scanCode)。
   * 扫到 CampusMate QR 协议字符串后跳转到确认页，由确认页调用后端 scan/confirm。
   * 非本协议二维码会提示用户并保留在当前页。
   */
  openScanner() {
    const user = this.data.user
    if (!user) {
      wx.showToast({ title: '请先登录后再扫码', icon: 'none' })
      return
    }
    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        const raw = res.result || ''
        const payload = parseQrPayload(raw)
        if (!payload) {
          wx.showModal({
            title: '无法识别',
            content: '这个二维码不是 CampusMate Web 登录二维码。请使用 Web 端登录页显示的二维码。',
            showCancel: false,
          })
          return
        }
        const params = `sid=${encodeURIComponent(payload.sessionId)}&token=${encodeURIComponent(payload.scanToken)}`
        wx.navigateTo({ url: `/pages/qr-confirm/qr-confirm?${params}` })
      },
      fail: (error) => {
        if (error && error.errMsg && error.errMsg.indexOf('cancel') >= 0) return
        wx.showToast({ title: '扫码失败，请重试', icon: 'none' })
      },
    })
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
  onExpressionModelUrlInput(event: WechatMiniprogram.Input) {
    this.setData({ expressionModelUrlInput: event.detail.value })
  },
  saveExpressionModelUrl() {
    const expressionModelUrl = this.data.expressionModelUrlInput.trim()
    if (expressionModelUrl && !/^https:\/\//.test(expressionModelUrl)) {
      wx.showToast({ title: '请输入 HTTPS 模型地址', icon: 'none' })
      return
    }
    this.saveSetting({ expressionModelUrl })
    wx.showToast({ title: expressionModelUrl ? '本机模型地址已保存' : '已清除模型地址', icon: 'success' })
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
      success: async (result) => {
        if (!result.confirm) return
        await repository.logout()
        wx.reLaunch({ url: '/pages/login/login' })
      },
    })
  },
})
