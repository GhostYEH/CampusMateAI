import { repository } from '../../../services/repository'
import { StudentExam } from '../../../services/types'

interface ExamGroup {
  date: string
  displayDate: string
  day: string
  exams: StudentExam[]
}

Page({
  data: {
    loading: true,
    error: '',
    exams: [] as StudentExam[],
    groups: [] as ExamGroup[],
    nextExam: null as StudentExam | null,
    nextDate: '--',
    nextDay: '--',
  },
  onShow() {
    this.load()
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const exams = await repository.getStudentExamsAsync()
      const grouped = new Map<string, StudentExam[]>()
      exams.forEach((exam) => grouped.set(exam.exam_date, [...(grouped.get(exam.exam_date) || []), exam]))
      const groups = Array.from(grouped.entries()).map(([date, items]) => ({
        date,
        displayDate: date.slice(5),
        day: this.dayLabel(date),
        exams: items,
      }))
      const nextExam = exams[0] || null
      this.setData({
        exams,
        groups,
        nextExam,
        nextDate: nextExam ? nextExam.exam_date.slice(5).replace('-', '月') + '日' : '--',
        nextDay: nextExam ? this.dayLabel(nextExam.exam_date) : '--',
        loading: false,
      })
    } catch (error) {
      this.setData({ loading: false, error: error instanceof Error ? error.message : '考试安排加载失败' })
    }
  },
  dayLabel(value: string) {
    const names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return names[new Date(`${value}T00:00:00`).getDay()]
  },
})
