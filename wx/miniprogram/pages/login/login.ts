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
  },
  onLoad() {
    const settings = repository.getSettings()
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
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
  async submit() {
    if (this.data.loading) return
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
