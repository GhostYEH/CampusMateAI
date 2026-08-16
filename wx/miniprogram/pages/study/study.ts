import { repository } from '../../services/repository'

interface FocusLog {
  id: number
  minutes: number
  feeling: string
  createdAt: string
}

let timer: number | undefined

Page({
  data: {
    modes: [
      { minutes: 25, label: '专注 25 分钟', icon: '/assets/icons/focus-timer.svg' },
      { minutes: 5, label: '短休息 5 分钟', icon: '/assets/icons/focus-moon.svg' },
      { minutes: 15, label: '长休息 15 分钟', icon: '/assets/icons/focus-moon.svg' },
    ],
    targetMinutes: 25,
    secondsLeft: 25 * 60,
    status: 'idle',
    displayTime: '25:00',
    progress: 100,
    currentMinutes: 0,
    statusText: '准备开始',
    primaryAction: '开始',
    assistanceAvailable: false,
    assistanceEnabled: false,
    feeling: '',
    feelings: ['状态不错', '有点疲惫', '任务偏多'],
    mockMode: false,
    reduceMotion: false,
    darkMode: false,
    remoteSessionId: '',
    todayMinutes: 0,
    recordCount: 0,
    streakDays: 0,
    goalMinutes: 120,
    goalProgress: 0,
    recentLogs: [] as Array<FocusLog & { dateLabel: string; durationLabel: string }>,
  },

  async onShow() {
    const settings = repository.getSettings()
    this.setData({
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    this.refreshSummary()
    if (!settings.mockMode && !this.data.remoteSessionId) {
      try {
        const session = await repository.getActiveStudySession()
        if (session) {
          if (session.status === 'active') await repository.pauseStudySession(session.id)
          this.setData({
            remoteSessionId: session.id,
            status: 'paused',
            statusText: '已暂停',
            primaryAction: '继续',
          })
        }
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '专注会话恢复失败', icon: 'none' })
      }
    }
  },

  onHide() {
    this.clearTimer()
    if (this.data.status === 'running') {
      this.setData({ status: 'paused', statusText: '已暂停', primaryAction: '继续' })
      if (this.data.remoteSessionId) {
        repository.pauseStudySession(this.data.remoteSessionId).catch(() => undefined)
      }
    }
  },

  onUnload() {
    this.clearTimer()
  },

  async chooseDuration(event: WechatMiniprogram.TouchEvent) {
    if (this.data.status === 'running') return
    if (this.data.remoteSessionId) {
      try {
        await repository.finishStudySession(this.data.remoteSessionId, this.data.feeling)
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '旧会话结束失败', icon: 'none' })
        return
      }
    }
    const targetMinutes = Number(event.currentTarget.dataset.minutes)
    this.setData({
      targetMinutes,
      secondsLeft: targetMinutes * 60,
      displayTime: this.formatTime(targetMinutes * 60),
      progress: 100,
      currentMinutes: 0,
      status: 'idle',
      statusText: '准备开始',
      primaryAction: '开始',
      remoteSessionId: '',
    })
  },

  async toggleTimer() {
    if (this.data.status === 'finishError') {
      await this.finish()
      return
    }
    if (this.data.status === 'running') {
      try {
        if (this.data.remoteSessionId) await repository.pauseStudySession(this.data.remoteSessionId)
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '暂停同步失败', icon: 'none' })
        return
      }
      this.clearTimer()
      this.setData({ status: 'paused', statusText: '已暂停', primaryAction: '继续' })
      return
    }
    if (this.data.secondsLeft <= 0) await this.reset()
    try {
      if (this.data.status === 'paused' && this.data.remoteSessionId) {
        await repository.resumeStudySession(this.data.remoteSessionId)
      } else if (!this.data.mockMode && !this.data.remoteSessionId) {
        const remoteSessionId = await repository.startStudySession()
        this.setData({ remoteSessionId: remoteSessionId || '' })
      }
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '专注会话启动失败', icon: 'none' })
      return
    }
    this.setData({ status: 'running', statusText: '专注进行中', primaryAction: '暂停' })
    this.startTimer()
  },

  startTimer() {
    this.clearTimer()
    timer = setInterval(() => {
      const secondsLeft = Math.max(0, this.data.secondsLeft - 1)
      const total = this.data.targetMinutes * 60
      this.setData({
        secondsLeft,
        displayTime: this.formatTime(secondsLeft),
        progress: Math.max(0, Math.round((secondsLeft / total) * 100)),
        currentMinutes: Math.floor((total - secondsLeft) / 60),
      })
      if (secondsLeft === 0) this.finish()
    }, 1000) as unknown as number
  },

  async reset() {
    this.clearTimer()
    if (this.data.remoteSessionId) {
      try {
        await repository.finishStudySession(this.data.remoteSessionId, this.data.feeling)
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '专注会话结束失败', icon: 'none' })
        return
      }
    }
    const secondsLeft = this.data.targetMinutes * 60
    this.setData({
      secondsLeft,
      displayTime: this.formatTime(secondsLeft),
      progress: 100,
      currentMinutes: 0,
      status: 'idle',
      statusText: '准备开始',
      primaryAction: '开始',
      remoteSessionId: '',
    })
  },

  async finish() {
    this.clearTimer()
    const elapsedMinutes = Math.max(1, Math.round((this.data.targetMinutes * 60 - this.data.secondsLeft) / 60))
    try {
      if (this.data.remoteSessionId) await repository.finishStudySession(this.data.remoteSessionId, this.data.feeling)
    } catch (error) {
      this.setData({ status: 'finishError', statusText: '记录同步失败', primaryAction: '重试同步' })
      wx.showToast({ title: error instanceof Error ? error.message : '专注记录同步失败', icon: 'none' })
      return
    }
    const logs = this.getLogs()
    logs.unshift({
      id: Date.now(),
      minutes: elapsedMinutes,
      feeling: this.data.feeling || '未填写',
      createdAt: new Date().toISOString(),
    })
    wx.setStorageSync('campus.study.logs', logs.slice(0, 30))
    this.setData({
      status: 'finished',
      statusText: '本次专注已完成',
      primaryAction: '再来一次',
      remoteSessionId: '',
    })
    this.refreshSummary()
    wx.showToast({ title: '专注记录已保存', icon: 'success' })
  },

  chooseFeeling(event: WechatMiniprogram.TouchEvent) {
    this.setData({ feeling: event.currentTarget.dataset.feeling as string })
  },

  onAssistanceChange(event: WechatMiniprogram.SwitchChange) {
    if (!this.data.assistanceAvailable) {
      this.setData({ assistanceEnabled: false })
      wx.showToast({ title: '当前设备暂不支持本地识别', icon: 'none' })
      return
    }
    this.setData({ assistanceEnabled: event.detail.value })
  },

  editGoal() {
    wx.showModal({
      title: '设置今日目标',
      editable: true,
      placeholderText: '请输入分钟数',
      content: String(this.data.goalMinutes),
      success: (result) => {
        if (!result.confirm) return
        const goalMinutes = Math.min(600, Math.max(15, Number(result.content) || 120))
        wx.setStorageSync('campus.study.goal', goalMinutes)
        this.setData({ goalMinutes, goalProgress: Math.min(100, Math.round((this.data.todayMinutes / goalMinutes) * 100)) })
      },
    })
  },

  refreshSummary() {
    const logs = this.getLogs()
    const todayKey = new Date().toDateString()
    const todayMinutes = logs
      .filter((log) => new Date(log.createdAt).toDateString() === todayKey)
      .reduce((total, log) => total + log.minutes, 0)
    const goalMinutes = Number(wx.getStorageSync('campus.study.goal')) || 120
    const dayKeys = Array.from(new Set(logs.map((log) => new Date(log.createdAt).toDateString())))
    let streakDays = 0
    const cursor = new Date()
    while (dayKeys.includes(cursor.toDateString())) {
      streakDays += 1
      cursor.setDate(cursor.getDate() - 1)
    }
    this.setData({
      todayMinutes,
      recordCount: logs.length,
      streakDays,
      goalMinutes,
      goalProgress: Math.min(100, Math.round((todayMinutes / goalMinutes) * 100)),
      recentLogs: logs.slice(0, 3).map((log) => ({
        ...log,
        dateLabel: this.formatDate(log.createdAt),
        durationLabel: `${log.minutes} 分钟`,
      })),
    })
  },

  getLogs(): FocusLog[] {
    return (wx.getStorageSync('campus.study.logs') as FocusLog[] | '') || []
  },

  clearTimer() {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  },

  formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60).toString().padStart(2, '0')
    const rest = (seconds % 60).toString().padStart(2, '0')
    return `${minutes}:${rest}`
  },

  formatDate(value: string): string {
    const date = new Date(value)
    return `${date.getMonth() + 1} 月 ${date.getDate()} 日`
  },
})
