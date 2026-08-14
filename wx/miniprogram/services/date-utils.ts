import { WeekDay } from './types'

const WEEK_LABELS = ['日', '一', '二', '三', '四', '五', '六']

export function buildCurrentWeek(reference = new Date()): WeekDay[] {
  const currentDay = reference.getDay()
  const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay
  const monday = new Date(reference)
  monday.setHours(12, 0, 0, 0)
  monday.setDate(reference.getDate() + mondayOffset)

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + index)
    return {
      label: WEEK_LABELS[date.getDay()],
      date: date.getDate(),
      active: isSameDay(date, reference),
    }
  })
}

export function formatApiDate(value?: string | null): string {
  if (!value) return '无截止时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const now = new Date()
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (isSameDay(date, now)) return `今天 ${time}`
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  if (isSameDay(date, tomorrow)) return `明天 ${time}`
  return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`
}

export function isDueSoon(value?: string): boolean {
  if (!value) return false
  const deadline = new Date(value).getTime()
  if (Number.isNaN(deadline)) return false
  const remaining = deadline - Date.now()
  return remaining >= 0 && remaining <= 48 * 60 * 60 * 1000
}

export function normalizeDeadline(value: string, reference = new Date()): string | null {
  const normalized = value.trim()
  if (!normalized || normalized === '待设置' || normalized === '无截止时间') return null
  const relative = normalized.match(/^(今天|明天)\s*(\d{1,2}):(\d{2})$/)
  if (relative) {
    const date = new Date(reference)
    date.setSeconds(0, 0)
    if (relative[1] === '明天') date.setDate(date.getDate() + 1)
    date.setHours(Number(relative[2]), Number(relative[3]))
    return date.toISOString()
  }
  const monthDay = normalized.match(/^(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?$/)
  if (monthDay) {
    const date = new Date(reference)
    date.setSeconds(0, 0)
    date.setMonth(Number(monthDay[1]) - 1, Number(monthDay[2]))
    date.setHours(Number(monthDay[3] || 23), Number(monthDay[4] || 59))
    return date.toISOString()
  }
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

function isSameDay(left: Date, right: Date): boolean {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}
