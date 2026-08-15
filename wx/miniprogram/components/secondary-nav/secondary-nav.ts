Component({
  properties: {
    title: { type: String, value: '' },
    fallback: { type: String, value: '/pages/index/index' },
  },
  data: {
    statusBarHeight: 24,
  },
  lifetimes: {
    attached() {
      this.setData({ statusBarHeight: wx.getWindowInfo().statusBarHeight || 24 })
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
