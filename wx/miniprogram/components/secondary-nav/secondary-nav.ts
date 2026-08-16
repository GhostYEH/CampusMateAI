import { getMiniProgramLayoutMetrics } from '../../utils/layout'

Component({
  properties: {
    title: { type: String, value: '' },
    fallback: { type: String, value: '/pages/index/index' },
  },
  data: {
    statusBarHeight: 24,
    navContentHeight: 44,
    navTotalHeight: 68,
    menuSafeRight: 12,
  },
  lifetimes: {
    attached() {
      const metrics = getMiniProgramLayoutMetrics()
      this.setData({
        statusBarHeight: metrics.statusBarHeight,
        navContentHeight: metrics.navContentHeight,
        navTotalHeight: metrics.navTotalHeight,
        menuSafeRight: metrics.menuSafeRight,
      })
    },
  },
  methods: {
    goBack() {
      this.triggerEvent('back')
      if (getCurrentPages().length > 1) {
        wx.navigateBack()
        return
      }
      wx.reLaunch({ url: this.data.fallback })
    },
  },
})
