export interface MiniProgramLayoutMetrics {
  statusBarHeight: number
  menuTop: number
  menuBottom: number
  menuHeight: number
  menuSafeRight: number
  navContentHeight: number
  navTotalHeight: number
  contentTop: number
}

export function getMiniProgramLayoutMetrics(): MiniProgramLayoutMetrics {
  const windowInfo = wx.getWindowInfo()
  const statusBarHeight = windowInfo.statusBarHeight || 24
  const windowWidth = (windowInfo as typeof windowInfo & { windowWidth?: number }).windowWidth || 375

  let menuTop = statusBarHeight + 6
  let menuHeight = 32
  let menuLeft = windowWidth - 95

  try {
    const menu = wx.getMenuButtonBoundingClientRect()
    if (menu && menu.height > 0 && menu.width > 0) {
      menuTop = menu.top
      menuHeight = menu.height
      menuLeft = menu.left
    }
  } catch {
    // DevTools and older base-library fallbacks keep the layout usable.
  }

  const menuBottom = menuTop + menuHeight
  const verticalInset = Math.max(4, menuTop - statusBarHeight)
  const navContentHeight = Math.max(44, verticalInset * 2 + menuHeight)
  const navTotalHeight = statusBarHeight + navContentHeight
  const menuSafeRight = Math.max(12, windowWidth - menuLeft + 8)

  return {
    statusBarHeight,
    menuTop,
    menuBottom,
    menuHeight,
    menuSafeRight,
    navContentHeight,
    navTotalHeight,
    contentTop: navTotalHeight,
  }
}
