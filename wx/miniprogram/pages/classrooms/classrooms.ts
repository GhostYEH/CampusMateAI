import { repository } from '../../services/repository'
import { Classroom } from '../../services/types'

Page({
  data: {
    loading: true,
    queried: false,
    error: '',
    date: '',
    building: '',
    classrooms: [] as Classroom[],
  },
  onLoad() {
    const now = new Date()
    const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    this.setData({ date })
    this.query()
  },
  onDateChange(event: WechatMiniprogram.PickerChange) {
    this.setData({ date: event.detail.value as string })
  },
  onBuildingInput(event: WechatMiniprogram.Input) {
    this.setData({ building: event.detail.value })
  },
  async query() {
    this.setData({ loading: true, error: '', queried: true })
    try {
      const classrooms = await repository.getClassroomsAsync(this.data.date, this.data.building.trim() || undefined)
      this.setData({ classrooms, loading: false })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '空教室查询失败' })
    }
  },
})
