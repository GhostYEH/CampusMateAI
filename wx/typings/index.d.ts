/// <reference path="./types/index.d.ts" />

interface IAppOption {
  globalData: {
    apiBaseUrl: string
  }
}

declare namespace WechatMiniprogram {
  interface Wx {
    getWindowInfo(): {
      statusBarHeight: number
      pixelRatio: number
    }
  }
}
