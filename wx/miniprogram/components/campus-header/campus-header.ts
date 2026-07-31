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
  },
  lifetimes: {
    attached() {
      const windowInfo = wx.getWindowInfo()
      this.setData({ statusBarHeight: windowInfo.statusBarHeight || 24 })
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
