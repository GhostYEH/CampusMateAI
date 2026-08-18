import { repository } from '../../services/repository'

Page({
  data: {
    statusBarHeight: 24,
    sessionId: '',
    scanToken: '',
    scanning: true,
    scanError: '',
    browserName: '',
    osName: '',
    deviceLabel: '',
    expiresAt: '',
    trustDevice: false,
    confirming: false,
    confirmError: '',
    confirmed: false,
    cancelling: false,
  },
  onLoad(query: Record<string, string | undefined>) {
    const sessionId = (query.sid || '').trim()
    const scanToken = (query.token || '').trim()
    const statusBarHeight = wx.getWindowInfo().statusBarHeight || 24
    if (!sessionId || !scanToken) {
      this.setData({
        statusBarHeight,
        scanning: false,
        scanError: '二维码参数缺失，请重新扫码。',
      })
      return
    }
    this.setData({ statusBarHeight, sessionId, scanToken })
    this.performScan()
  },
  async performScan() {
    try {
      const result = await repository.qrScan(this.data.sessionId, this.data.scanToken)
      this.setData({
        scanning: false,
        browserName: result.browser_name || '未知浏览器',
        osName: result.os_name || '未知系统',
        deviceLabel: result.device_label || '',
        expiresAt: result.expires_at || '',
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : '扫码失败，请重试。'
      this.setData({ scanning: false, scanError: message })
    }
  },
  toggleTrust() {
    this.setData({ trustDevice: !this.data.trustDevice })
  },
  async confirm() {
    if (this.data.confirming || this.data.confirmed) return
    this.setData({ confirming: true, confirmError: '' })
    try {
      await repository.qrConfirm(this.data.sessionId, this.data.scanToken, this.data.trustDevice)
      this.setData({ confirmed: true, confirming: false })
      wx.showToast({ title: '已确认登录', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 1200)
    } catch (error) {
      const message = error instanceof Error ? error.message : '确认失败，请重试。'
      this.setData({ confirming: false, confirmError: message })
    }
  },
  async cancel() {
    if (this.data.cancelling) return
    this.setData({ cancelling: true })
    await repository.qrCancel(this.data.sessionId, this.data.scanToken)
    this.setData({ cancelling: false })
    wx.navigateBack()
  },
  retryScan() {
    this.setData({ scanning: true, scanError: '' })
    this.performScan()
  },
  back() {
    wx.navigateBack()
  },
})