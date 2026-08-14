import { repository } from '../../services/repository'

Page({
  data: {
    statusBarHeight: 24,
    username: 'student_demo',
    password: 'Demo123456',
    showPassword: false,
    loading: false,
    error: '',
    mockMode: true,
    reduceMotion: false,
    apiBaseUrlInput: '',
    checkingBackend: false,
  },
  onLoad() {
    const settings = repository.getSettings()
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      apiBaseUrlInput: settings.apiBaseUrl,
    })
    if (repository.getSession()) {
      wx.switchTab({ url: '/pages/index/index' })
    }
  },
  onUsername(event: WechatMiniprogram.Input) {
    this.setData({ username: event.detail.value, error: '' })
  },
  onPassword(event: WechatMiniprogram.Input) {
    this.setData({ password: event.detail.value, error: '' })
  },
  togglePassword() {
    this.setData({ showPassword: !this.data.showPassword })
  },
  chooseAccount(event: WechatMiniprogram.TouchEvent) {
    const username = event.currentTarget.dataset.username as string
    this.setData({ username, password: 'Demo123456', error: '' })
  },
  onBackendUrl(event: WechatMiniprogram.Input) {
    this.setData({ apiBaseUrlInput: event.detail.value, error: '' })
  },
  async saveBackendUrl() {
    if (this.data.checkingBackend) return
    const apiBaseUrl = this.data.apiBaseUrlInput.trim().replace(/\/$/, '')
    if (!/^https?:\/\//.test(apiBaseUrl)) {
      this.setData({ error: '请输入完整的 http(s) 后端地址' })
      return
    }
    repository.saveSettings({ apiBaseUrl })
    this.setData({ checkingBackend: true, error: '' })
    try {
      await repository.checkBackendHealth()
      wx.showToast({ title: '后端连接正常', icon: 'success' })
    } catch (error) {
      this.setData({
        error: error instanceof Error ? error.message : '后端连接失败',
      })
    } finally {
      this.setData({ checkingBackend: false })
    }
  },
  async useMockMode() {
    await repository.logout()
    repository.saveSettings({ mockMode: true })
    this.setData({
      mockMode: true,
      username: 'student_demo',
      password: 'Demo123456',
      error: '',
    })
    wx.showToast({ title: '已切回 Mock 模式', icon: 'none' })
  },
  async toggleLoginMode() {
    const mockMode = !this.data.mockMode
    await repository.logout()
    repository.saveSettings({ mockMode })
    this.setData({
      mockMode,
      username: mockMode ? 'student_demo' : '',
      password: mockMode ? 'Demo123456' : '',
      error: '',
    })
  },
  async submit() {
    if (this.data.loading) return
    if (!this.data.mockMode && !repository.getSettings().apiBaseUrl) {
      this.setData({ error: '请先配置并检查真实后端地址' })
      return
    }
    if (!this.data.username.trim() || !this.data.password) {
      this.setData({ error: '请输入账号和密码' })
      return
    }
    this.setData({ loading: true, error: '' })
    try {
      await repository.login(this.data.username.trim(), this.data.password)
      wx.showToast({ title: '欢迎回来', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 300)
    } catch (error) {
      this.setData({
        error: error instanceof Error ? error.message : '登录失败，请稍后再试',
      })
    } finally {
      this.setData({ loading: false })
    }
  },
})
