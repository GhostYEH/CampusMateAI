import { repository } from '../../services/repository'

let timer: number | undefined
let expressionTimer: number | undefined

Page({
  data: {
    targetMinutes: 25,
    secondsLeft: 25 * 60,
    status: 'idle',
    displayTime: '25:00',
    progress: 0,
    expression: '等待开始学习陪伴',
    expressionConfidence: '',
    feeling: '',
    feelings: ['状态不错', '有点疲惫', '任务偏多'],
    mockMode: true,
    reduceMotion: false,
    darkMode: false,
    remoteSessionId: '',
    weekBars: [
      { label: '一', value: 32 },
      { label: '二', value: 56 },
      { label: '三', value: 45 },
      { label: '四', value: 80 },
      { label: '五', value: 62 },
      { label: '六', value: 90 },
      { label: '日', value: 40 },
    ],
  },
  async onShow() {
    const settings = repository.getSettings()
    this.setData({
      mockMode: settings.mockMode,
      reduceMotion: settings.reduceMotion,
      darkMode: settings.darkMode,
    })
    if (!settings.mockMode && !this.data.remoteSessionId) {
      try {
        const session = await repository.getActiveStudySession()
        if (session) {
          if (session.status === 'active') await repository.pauseStudySession(session.id)
          this.setData({ remoteSessionId: session.id, status: 'paused' })
        }
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '学习会话恢复失败', icon: 'none' })
      }
    }
  },
  onHide() {
    this.clearTimers()
    if (this.data.status === 'running') {
      this.setData({ status: 'paused' })
      if (this.data.remoteSessionId) {
        repository.pauseStudySession(this.data.remoteSessionId).catch(() => undefined)
      }
    }
  },
  onUnload() {
    this.clearTimers()
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
      progress: 0,
      status: 'idle',
      expression: '等待开始学习陪伴',
      expressionConfidence: '',
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
        if (this.data.remoteSessionId) {
          await repository.pauseStudySession(this.data.remoteSessionId)
        }
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '暂停同步失败', icon: 'none' })
        return
      }
      this.clearTimers()
      this.setData({ status: 'paused' })
      return
    }
    if (this.data.secondsLeft <= 0) {
      await this.reset()
    }
    try {
      if (this.data.status === 'paused' && this.data.remoteSessionId) {
        await repository.resumeStudySession(this.data.remoteSessionId)
      } else if (!this.data.mockMode && !this.data.remoteSessionId) {
        const remoteSessionId = await repository.startStudySession()
        this.setData({ remoteSessionId: remoteSessionId || '' })
      }
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '学习会话启动失败', icon: 'none' })
      return
    }
    this.setData({ status: 'running' })
    this.startTimer()
    expressionTimer = setTimeout(() => {
      if (this.data.status !== 'running') return
      this.setData({
        expression: this.data.mockMode
          ? 'Mock 观察：当前表情可能偏中性'
          : '暂时无法稳定判断当前表情',
        expressionConfidence: this.data.mockMode ? '稳定结果 · 置信度 86% · 仅供辅助参考' : '低置信度，不触发陪伴建议',
      })
    }, this.data.reduceMotion ? 0 : 2800) as unknown as number
  },
  startTimer() {
    this.clearTimerOnly()
    timer = setInterval(() => {
      const secondsLeft = Math.max(0, this.data.secondsLeft - 1)
      const total = this.data.targetMinutes * 60
      this.setData({
        secondsLeft,
        displayTime: this.formatTime(secondsLeft),
        progress: Math.round(((total - secondsLeft) / total) * 100),
      })
      if (secondsLeft === 0) {
        this.finish()
      }
    }, 1000) as unknown as number
  },
  async reset() {
    this.clearTimers()
    if (this.data.remoteSessionId) {
      try {
        await repository.finishStudySession(this.data.remoteSessionId, this.data.feeling)
      } catch (error) {
        wx.showToast({ title: error instanceof Error ? error.message : '学习会话结束失败', icon: 'none' })
        return
      }
    }
    const secondsLeft = this.data.targetMinutes * 60
    this.setData({
      secondsLeft,
      displayTime: this.formatTime(secondsLeft),
      progress: 0,
      status: 'idle',
      expression: '等待开始学习陪伴',
      expressionConfidence: '',
      remoteSessionId: '',
    })
  },
  async finish() {
    this.clearTimers()
    const elapsedMinutes = Math.max(
      1,
      Math.round((this.data.targetMinutes * 60 - this.data.secondsLeft) / 60),
    )
    try {
      if (this.data.remoteSessionId) {
        await repository.finishStudySession(this.data.remoteSessionId, this.data.feeling)
      }
    } catch (error) {
      this.setData({
        status: 'finishError',
        expression: '学习已结束，但记录同步失败',
        expressionConfidence: '点击“重试同步”后再离开页面',
      })
      wx.showToast({ title: error instanceof Error ? error.message : '学习记录同步失败', icon: 'none' })
      return
    }
    const logs = (wx.getStorageSync('campus.study.logs') as Array<Record<string, unknown>> | '') || []
    logs.unshift({
      id: Date.now(),
      minutes: elapsedMinutes,
      feeling: this.data.feeling || '未填写',
      createdAt: new Date().toISOString(),
    })
    wx.setStorageSync('campus.study.logs', logs.slice(0, 30))
    this.setData({
      status: 'finished',
      expression: '本次陪伴已结束',
      expressionConfidence: this.data.mockMode ? '学习记录已保存在本机' : '学习记录已同步到校园后端',
      remoteSessionId: '',
    })
    wx.showToast({ title: '本次记录已保存', icon: 'success' })
  },
  chooseFeeling(event: WechatMiniprogram.TouchEvent) {
    this.setData({ feeling: event.currentTarget.dataset.feeling as string })
  },
  clearTimerOnly() {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  },
  clearTimers() {
    this.clearTimerOnly()
    if (expressionTimer !== undefined) {
      clearTimeout(expressionTimer)
      expressionTimer = undefined
    }
  },
  formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60).toString().padStart(2, '0')
    const rest = (seconds % 60).toString().padStart(2, '0')
    return `${minutes}:${rest}`
  },
})
