import { getMiniProgramLayoutMetrics } from '../../utils/layout'

Component({
  properties: {
    title: {
      type: String,
      value: '',
    },
    subtitle: {
      type: String,
      value: '',
    },
    mode: {
      type: String,
      value: '',
    },
    back: {
      type: Boolean,
      value: false,
    },
  },
  data: {
    statusBarHeight: 24,
    headerContentHeight: 82,
    menuSafeRight: 12,
  },
  lifetimes: {
    attached() {
      const metrics = getMiniProgramLayoutMetrics()
      this.setData({
        statusBarHeight: metrics.statusBarHeight,
        headerContentHeight: Math.max(82, metrics.navContentHeight),
        menuSafeRight: metrics.menuSafeRight,
      })
    },
  },
  methods: {
    onBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        wx.navigateBack()
      } else {
        wx.switchTab({ url: '/pages/index/index' })
      }
    },
  },
})
