import { repository } from '../../services/repository'

Page({
  data: {
    statusBarHeight: 24,
    username: '',
    password: '',
    showPassword: false,
    loading: false,
    error: '',
    mockMode: true,
    reduceMotion: false,
    rememberMe: true,
    usernameFocused: false,
    passwordFocused: false,
    videoOk: true,
    videoSrc: '',
  },
  onVideoError() {
    this.setData({ videoOk: false })
  },
  prepareVideo() {
    if (this.data.reduceMotion) return
    const fs = wx.getFileSystemManager()
    const dest = `${wx.env.USER_DATA_PATH}/login_campus.mp4`
    fs.copyFile({
      srcPath: '/assets/login_campus.mp4',
      destPath: dest,
      success: () => this.setData({ videoSrc: dest }),
      fail: () => this.setData({ videoOk: false }),
    })
  },
  onLoad() {
    const settings = repository.getSettings()
    this.setData({
      statusBarHeight: wx.getWindowInfo().statusBarHeight || 24,
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
    })
    this.prepareVideo()
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
  onUserFocus() {
    this.setData({ usernameFocused: true })
  },
  onUserBlur() {
    this.setData({ usernameFocused: false })
  },
  onPwdFocus() {
    this.setData({ passwordFocused: true })
  },
  onPwdBlur() {
    this.setData({ passwordFocused: false })
  },
  togglePassword() {
    this.setData({ showPassword: !this.data.showPassword })
  },
  toggleRemember() {
    this.setData({ rememberMe: !this.data.rememberMe })
  },
  async submit() {
    if (this.data.loading) return
    let username = this.data.username.trim()
    let password = this.data.password
    if (this.data.mockMode && !username && !password) {
      username = 'student_demo'
      password = 'Demo123456'
    }
    if (!username || !password) {
      this.setData({ error: username ? '请输入密码后继续。' : '请输入学号、工号或用户名。' })
      return
    }
    if (!this.data.mockMode && !repository.getSettings().apiBaseUrl) {
      this.setData({ error: '请先在设置中配置真实后端地址' })
      return
    }
    this.setData({ loading: true, error: '' })
    try {
      await repository.login(username, password)
      wx.showToast({ title: '欢迎回来', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 300)
    } catch (error) {
      this.setData({
        error: error instanceof Error ? error.message : '暂时无法登录，请检查网络后重试。',
      })
    } finally {
      this.setData({ loading: false })
    }
  },
})
