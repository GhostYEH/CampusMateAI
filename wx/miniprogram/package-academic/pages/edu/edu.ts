import { repository } from '../../../services/repository'
import { EduConnection, EduProbeResult, EduScheduleItem } from '../../../services/types'

type Phase =
  | 'idle'
  | 'probing'
  | 'probe_ready'
  | 'connecting'
  | 'need_credentials'
  | 'waiting_user_login'
  | 'verifying'
  | 'connected'
  | 'syncing'
  | 'synced'
  | 'error'

interface ScheduleCard {
  id: string
  weekday: number
  start_section: number
  end_section: number
  lane: number
  lane_count: number
  course_name: string
  location: string
  style: string
  raw: EduScheduleItem
}

interface WeekdayHeader {
  label: string
  style: string
}

interface SectionRow {
  label: string
  style: string
  cells: { style: string }[]
}

interface DetailRow {
  label: string
  value: string
}

interface GradeRow {
  course_name: string
  credit: string
  score: string
  grade_point: string
  category: string
}

const WEEKDAY_LABELS = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
const TIME_COLUMN_WIDTH = 48
const DAY_COLUMN_WIDTH = 112
const SECTION_HEIGHT = 72
const HEADER_HEIGHT = 40
const COURSE_COLORS = ['#5B70ED', '#D9792B', '#258C78', '#7952B3', '#C43D5C', '#1976B9', '#438A45', '#873A91']
const COURSE_SOFT_COLORS = ['#EEF0FF', '#FFF1E5', '#E8F7F3', '#F1EBFF', '#FFEBF0', '#E8F4FC', '#ECF8EC', '#F5EAF7']

function courseColor(item: EduScheduleItem): { border: string; background: string } {
  const key = item.course_code || item.course_name || ''
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0
  const index = Math.abs(hash) % COURSE_COLORS.length
  return { border: COURSE_COLORS[index], background: COURSE_SOFT_COLORS[index] }
}

function buildWeekdayHeaders(): WeekdayHeader[] {
  return WEEKDAY_LABELS.slice(1).map((label, index) => ({
    label,
    style: `left:${TIME_COLUMN_WIDTH + index * DAY_COLUMN_WIDTH}px;top:0px;width:${DAY_COLUMN_WIDTH}px;height:${HEADER_HEIGHT}px;`,
  }))
}

function buildSectionRows(maxSection: number): SectionRow[] {
  return Array.from({ length: maxSection }, (_, index) => {
    const section = index + 1
    return {
      label: String(section),
      style: `left:0px;top:${HEADER_HEIGHT + index * SECTION_HEIGHT}px;width:${TIME_COLUMN_WIDTH}px;height:${SECTION_HEIGHT}px;`,
      cells: WEEKDAY_LABELS.slice(1).map((_label, dayIndex) => ({
        style: `left:${TIME_COLUMN_WIDTH + dayIndex * DAY_COLUMN_WIDTH}px;top:${HEADER_HEIGHT + index * SECTION_HEIGHT}px;width:${DAY_COLUMN_WIDTH}px;height:${SECTION_HEIGHT}px;`,
      })),
    }
  })
}

function weeksContains(weeks: string, weekText: string, week: number): boolean {
  const w = (weeks || '').trim()
  if (!w) return true
  if (weekText && weekText.includes('单') && week % 2 === 0) return false
  if (weekText && weekText.includes('双') && week % 2 === 1) return false
  const cleaned = w.replace(/周/g, '').replace(/ /g, '')
  const parts = cleaned.split(/[,，;；]/)
  for (const part of parts) {
    const p = part.trim()
    if (!p) continue
    if (p.endsWith('单') && week % 2 === 0) continue
    if (p.endsWith('双') && week % 2 === 1) continue
    const core = p.replace(/单$/, '').replace(/双$/, '')
    if (core.includes('-')) {
      const range = core.split('-').map(Number)
      if (range.length === 2 && range[0] && range[1] && week >= range[0] && week <= range[1]) return true
    } else {
      const n = parseInt(core, 10)
      if (n === week) return true
    }
  }
  return false
}

function formatTeachers(teachers: string[], teacher: string): string {
  if (teachers && teachers.length) {
    const filtered = teachers.filter((t) => t && t.trim())
    if (filtered.length) return filtered.join('、')
  }
  return teacher || ''
}

function formatTime(weekday: number, start: number, end: number, startTime: string, endTime: string): string {
  if (weekday == null && start == null) return ''
  let sb = ''
  if (weekday >= 1 && weekday <= 7) sb += WEEKDAY_LABELS[weekday]
  if (start != null) {
    sb += ` 第${start}`
    if (end != null && end !== start) sb += `-${end}`
    sb += '节'
  }
  if (startTime || endTime) sb += `\n${startTime || ''}${endTime ? '-' + endTime : ''}`
  return sb
}

function formatWeeks(weeks: string, weekText: string): string {
  if (weekText) return weeks ? `${weekText}（${weeks}）` : weekText
  return weeks || ''
}

function formatCredit(credit: number): string {
  if (credit == null) return ''
  return credit === Math.floor(credit) ? `${Math.floor(credit)} 学分` : `${credit} 学分`
}

function formatHours(hours: number): string {
  if (hours == null) return ''
  return hours === Math.floor(hours) ? `${Math.floor(hours)}` : `${hours}`
}

function buildDetailRows(item: EduScheduleItem): DetailRow[] {
  const rows: DetailRow[] = []
  const teachers = formatTeachers(item.teachers, item.teacher)
  if (teachers) rows.push({ label: '教师', value: teachers })
  const time = formatTime(item.weekday, item.start_section, item.end_section, item.start_time, item.end_time)
  if (time) rows.push({ label: '上课时间', value: time })
  if (item.location) rows.push({ label: '地点', value: item.location })
  const weeks = formatWeeks(item.weeks, item.week_text)
  if (weeks) rows.push({ label: '周次', value: weeks })
  if (item.credit != null) rows.push({ label: '学分', value: formatCredit(item.credit) })
  if (item.course_nature) rows.push({ label: '课程性质', value: item.course_nature })
  if (item.course_category) rows.push({ label: '课程类别', value: item.course_category })
  if (item.course_type) rows.push({ label: '课程类型', value: item.course_type })
  if (item.teaching_class) rows.push({ label: '教学班', value: item.teaching_class })
  if (item.assessment_method) rows.push({ label: '考核方式', value: item.assessment_method })
  if (item.exam_type) rows.push({ label: '考试类型', value: item.exam_type })
  if (item.college) rows.push({ label: '开课学院', value: item.college })
  if (item.department) rows.push({ label: '开课系', value: item.department })
  if (item.campus) rows.push({ label: '校区', value: item.campus })
  if (item.class_name) rows.push({ label: '班级', value: item.class_name })
  if (item.total_hours != null) rows.push({ label: '总学时', value: formatHours(item.total_hours) })
  if (item.theory_hours != null) rows.push({ label: '理论学时', value: formatHours(item.theory_hours) })
  if (item.practice_hours != null) rows.push({ label: '实践学时', value: formatHours(item.practice_hours) })
  if (item.language) rows.push({ label: '授课语言', value: item.language })
  if (item.semester) rows.push({ label: '学期', value: item.semester })
  if (item.note) rows.push({ label: '备注', value: item.note })
  return rows
}

function buildExtraRows(extraInfo: Record<string, string>): DetailRow[] {
  if (!extraInfo) return []
  const rows: DetailRow[] = []
  for (const key of Object.keys(extraInfo)) {
    const v = extraInfo[key]
    if (v != null && String(v).trim()) rows.push({ label: key, value: String(v) })
  }
  return rows
}

function describeState(state: string): string {
  switch (state) {
    case 'idle': return '待连接'
    case 'auth_required': return '需要账号密码'
    case 'waiting_user_login': return '等待登录'
    case 'connecting': return '正在连接'
    case 'authenticated': return '已认证'
    case 'connected': return '已连接'
    case 'auth_failed': return '登录失败'
    case 'syncing': return '正在同步'
    case 'synced': return '已同步'
    case 'failed': return '连接失败'
    default: return state
  }
}

Page({
  data: {
    phase: 'idle' as Phase,
    portalUrl: '',
    probe: null as EduProbeResult | null,
    connection: null as EduConnection | null,
    username: '',
    password: '',
    captcha: '',
    busy: false,
    errorMessage: '',
    allScheduleItems: [] as EduScheduleItem[],
    weekdayHeaders: buildWeekdayHeaders() as WeekdayHeader[],
    sectionRows: buildSectionRows(12) as SectionRow[],
    scheduleCards: [] as ScheduleCard[],
    gridHeight: HEADER_HEIGHT + 12 * SECTION_HEIGHT,
    currentWeek: 1,
    scheduleEmpty: false,
    detailVisible: false,
    detailCourseName: '',
    detailCourseCode: '',
    detailRows: [] as DetailRow[],
    detailExtraRows: [] as DetailRow[],
    gradeRows: [] as GradeRow[],
    activeTab: 'schedule' as 'schedule' | 'grade',
    scheduleSemesters: [] as string[],
    gradeSemesters: [] as string[],
    selectedScheduleSemester: '',
    selectedGradeSemester: '',
    pollTimer: 0 as number,
  },
  onUnload() {
    this.stopPolling()
  },
  onHide() {
    this.stopPolling()
  },
  onPortalInput(event: WechatMiniprogram.Input) {
    this.setData({ portalUrl: event.detail.value })
  },
  onUsernameInput(event: WechatMiniprogram.Input) {
    this.setData({ username: event.detail.value })
  },
  onPasswordInput(event: WechatMiniprogram.Input) {
    this.setData({ password: event.detail.value })
  },
  onCaptchaInput(event: WechatMiniprogram.Input) {
    this.setData({ captcha: event.detail.value })
  },
  async probeAndConnect() {
    const portalUrl = this.data.portalUrl.trim()
    if (!portalUrl) {
      wx.showToast({ title: '请输入教务系统地址', icon: 'none' })
      return
    }
    if (!/^https?:\/\//.test(portalUrl)) {
      wx.showToast({ title: '请输入 http(s) 地址', icon: 'none' })
      return
    }
    this.setData({ phase: 'probing', busy: true, errorMessage: '' })
    try {
      const probe = await repository.eduProbe(portalUrl)
      if (!probe.reachable) {
        this.setData({
          phase: 'error',
          busy: false,
          errorMessage: probe.error || '无法访问该地址，请确认教务系统链接是否正确',
        })
        return
      }
      this.setData({ phase: 'connecting', probe })
      const connection = await repository.eduCreateConnectionFromUrl(portalUrl)
      this.applyConnection(connection)
    } catch (error) {
      this.setData({
        phase: 'error',
        busy: false,
        errorMessage: error instanceof Error ? error.message : '探测失败，请检查地址或网络',
      })
    }
  },
  applyConnection(connection: EduConnection) {
    const state = connection.state
    const mode = connection.login_execution_mode
    let phase: Phase = 'connecting'
    if (state === 'connected' || state === 'synced') {
      phase = 'connected'
    } else if (state === 'auth_required' || (state === 'idle' && mode === 'server_credentials')) {
      phase = 'need_credentials'
    } else if (state === 'waiting_user_login' || (state === 'idle' && mode === 'client_webview')) {
      phase = 'waiting_user_login'
    } else if (state === 'connecting' || state === 'authenticated') {
      phase = 'verifying'
    } else if (state === 'auth_failed' || state === 'failed') {
      phase = 'error'
      this.setData({ errorMessage: connection.error_message || '登录失败，请重试' })
    }
    this.setData({ connection, phase, busy: false })
    if (phase === 'connected') {
      this.autoSync()
    } else if (phase === 'verifying') {
      this.startPolling()
    }
  },
  async submitCredentials() {
    const connection = this.data.connection
    if (!connection) return
    const username = this.data.username.trim()
    const password = this.data.password
    if (!username || !password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' })
      return
    }
    this.setData({ phase: 'verifying', busy: true, errorMessage: '' })
    try {
      const next = await repository.eduContinueConnection(connection.id, {
        username,
        password,
        captcha: this.data.captcha.trim() || undefined,
      })
      this.applyConnection(next)
    } catch (error) {
      this.setData({
        phase: 'need_credentials',
        busy: false,
        errorMessage: error instanceof Error ? error.message : '登录失败，请重试',
      })
    }
  },
  copyLoginUrl() {
    const url = this.data.probe?.final_url || this.data.portalUrl
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '链接已复制', icon: 'success' }),
    })
  },
  startPolling() {
    this.stopPolling()
    const timer = setInterval(() => this.pollOnce(), 2500) as unknown as number
    this.setData({ pollTimer: timer })
  },
  stopPolling() {
    if (this.data.pollTimer) {
      clearInterval(this.data.pollTimer)
      this.setData({ pollTimer: 0 })
    }
  },
  async pollOnce() {
    const connection = this.data.connection
    if (!connection) return
    try {
      const next = await repository.eduPollConnection(connection.id)
      this.applyConnection(next)
    } catch {
      // 轮询失败时静默，下次再试
    }
  },
  async refreshConnection() {
    const connection = this.data.connection
    if (!connection) return
    try {
      const next = await repository.eduGetConnection(connection.id)
      this.applyConnection(next)
    } catch (error) {
      wx.showToast({ title: error instanceof Error ? error.message : '刷新失败', icon: 'none' })
    }
  },
  async autoSync() {
    if (this.data.phase !== 'connected') return
    this.setData({ phase: 'syncing', busy: true })
    try {
      await repository.eduSyncSchedule()
      await repository.eduSyncGrade()
      await this.loadSemesters()
      await this.loadItems()
      this.setData({ phase: 'synced', busy: false })
    } catch (error) {
      this.setData({
        phase: 'connected',
        busy: false,
        errorMessage: error instanceof Error ? error.message : '同步失败，可稍后手动重试',
      })
    }
  },
  async manualSync() {
    if (this.data.phase !== 'connected' && this.data.phase !== 'synced') return
    this.setData({ phase: 'syncing', busy: true, errorMessage: '' })
    try {
      await repository.eduSyncSchedule()
      await repository.eduSyncGrade()
      await this.loadSemesters()
      await this.loadItems()
      this.setData({ phase: 'synced', busy: false })
      wx.showToast({ title: '同步完成', icon: 'success' })
    } catch (error) {
      this.setData({
        phase: 'connected',
        busy: false,
        errorMessage: error instanceof Error ? error.message : '同步失败',
      })
    }
  },
  async loadSemesters() {
    try {
      const [scheduleSemesters, gradeSemesters] = await Promise.all([
        repository.eduScheduleSemesters().catch(() => [] as string[]),
        repository.eduGradeSemesters().catch(() => [] as string[]),
      ])
      this.setData({
        scheduleSemesters,
        gradeSemesters,
        selectedScheduleSemester: scheduleSemesters[0] || '',
        selectedGradeSemester: gradeSemesters[0] || '',
      })
    } catch {
      // 学期列表加载失败不阻塞
    }
  },
  async loadItems() {
    try {
      const [scheduleResp, gradeResp] = await Promise.all([
        repository.eduScheduleItems(this.data.selectedScheduleSemester || undefined).catch(() => null),
        repository.eduGradeItems(this.data.selectedGradeSemester || undefined).catch(() => null),
      ])
      const allScheduleItems: EduScheduleItem[] = (scheduleResp?.items || []).filter((it) => !it.is_stale)
      const gradeRows: GradeRow[] = (gradeResp?.items || []).map((item) => ({
        course_name: item.course_name,
        credit: String(item.credit || ''),
        score: String(item.score || ''),
        grade_point: String(item.grade_point || ''),
        category: item.category || '',
      }))
      this.setData({ allScheduleItems, gradeRows }, () => this.buildScheduleGrid())
    } catch {
      // 条目加载失败不阻塞
    }
  },
  buildScheduleGrid() {
    const week = this.data.currentWeek
    const filtered = this.data.allScheduleItems.filter((it) => {
      const start = Number(it.start_section)
      const end = Number(it.end_section || start)
      return weeksContains(it.weeks, it.week_text, week)
        && Number.isInteger(it.weekday) && it.weekday >= 1 && it.weekday <= 7
        && Number.isInteger(start) && start >= 1 && Number.isInteger(end) && end >= start
    })
    const maxSection = Math.max(12, ...filtered.map((it) => Number(it.end_section || it.start_section)), 0)
    const cards: ScheduleCard[] = []
    for (let wd = 1; wd <= 7; wd++) {
      const dayItems = filtered
        .filter((it) => it.weekday === wd)
        .sort((a, b) => (a.start_section - b.start_section) || (a.end_section - b.end_section))
      const lanes: EduScheduleItem[][] = []
      const laneIndexes: number[] = []
      dayItems.forEach((item) => {
        const start = Number(item.start_section)
        const end = Number(item.end_section || start)
        let lane = -1
        for (let candidate = 0; candidate < lanes.length; candidate++) {
          const available = lanes[candidate].every((other) => {
            const otherStart = Number(other.start_section)
            const otherEnd = Number(other.end_section || otherStart)
            return otherEnd < start || end < otherStart
          })
          if (available) {
            lane = candidate
            break
          }
        }
        if (lane < 0) {
          lane = lanes.length
          lanes.push([])
        }
        lanes[lane].push(item)
        laneIndexes.push(lane)
      })
      dayItems.forEach((item, index) => {
        const start = Number(item.start_section)
        const end = Number(item.end_section || start)
        const overlapCount = dayItems.filter((other) => {
          const otherStart = Number(other.start_section)
          const otherEnd = Number(other.end_section || otherStart)
          return otherStart <= end && start <= otherEnd
        }).length
        const laneCount = Math.max(1, Math.min(lanes.length, overlapCount))
        const laneWidth = DAY_COLUMN_WIDTH / laneCount
        const color = courseColor(item)
        cards.push({
          id: item.id || `${wd}_${item.course_code}_${start}_${item.location}_${item.weeks}`,
          weekday: wd,
          start_section: start,
          end_section: end,
          lane: laneIndexes[index],
          lane_count: laneCount,
          course_name: item.course_name || '未命名课程',
          location: item.location || '',
          style: `left:${TIME_COLUMN_WIDTH + (wd - 1) * DAY_COLUMN_WIDTH + laneIndexes[index] * laneWidth + 2}px;top:${HEADER_HEIGHT + (start - 1) * SECTION_HEIGHT + 2}px;width:${Math.max(44, laneWidth - 4)}px;height:${Math.max(44, (end - start + 1) * SECTION_HEIGHT - 4)}px;border-color:${color.border};background-color:${color.background};`,
          raw: item,
        })
      })
    }
    this.setData({
      scheduleCards: cards,
      sectionRows: buildSectionRows(maxSection),
      gridHeight: HEADER_HEIGHT + maxSection * SECTION_HEIGHT,
      scheduleEmpty: this.data.allScheduleItems.length === 0,
    })
  },
  onWeekPrev() {
    if (this.data.currentWeek > 1) {
      this.setData({ currentWeek: this.data.currentWeek - 1 }, () => this.buildScheduleGrid())
    }
  },
  onWeekNext() {
    if (this.data.currentWeek < 25) {
      this.setData({ currentWeek: this.data.currentWeek + 1 }, () => this.buildScheduleGrid())
    }
  },
  onCourseTap(event: WechatMiniprogram.TouchEvent) {
    const itemIdx = event.currentTarget.dataset.index as number
    const card = this.data.scheduleCards[itemIdx]
    if (!card) return
    const item = card.raw
    this.setData({
      detailVisible: true,
      detailCourseName: item.course_name || '未命名课程',
      detailCourseCode: item.course_code || '',
      detailRows: buildDetailRows(item),
      detailExtraRows: buildExtraRows(item.extra_info),
    })
  },
  onCloseDetail() {
    this.setData({ detailVisible: false })
  },
  onTabChange(event: WechatMiniprogram.TouchEvent) {
    const tab = event.currentTarget.dataset.tab as 'schedule' | 'grade'
    this.setData({ activeTab: tab })
  },
  onScheduleSemesterChange(event: WechatMiniprogram.PickerChange) {
    this.setData({ selectedScheduleSemester: event.detail.value as string }, () => this.loadItems())
  },
  onGradeSemesterChange(event: WechatMiniprogram.PickerChange) {
    this.setData({ selectedGradeSemester: event.detail.value as string }, () => this.loadItems())
  },
  async reconnect() {
    const connection = this.data.connection
    if (!connection) return
    wx.showModal({
      title: '重新登录？',
      content: '将清除当前登录状态，重新进入登录流程。',
      confirmText: '重新登录',
      success: async (result) => {
        if (!result.confirm) return
        this.setData({
          phase: 'connecting',
          username: '',
          password: '',
          captcha: '',
          errorMessage: '',
        })
        try {
          const next = await repository.eduContinueConnection(connection.id, { action: 'CANCEL' })
          const fresh = await repository.eduCreateConnectionFromUrl(this.data.portalUrl)
          this.applyConnection(fresh || next)
        } catch (error) {
          this.setData({
            phase: 'error',
            errorMessage: error instanceof Error ? error.message : '重新登录失败',
          })
        }
      },
    })
  },
  async disconnect() {
    const connection = this.data.connection
    if (!connection) return
    wx.showModal({
      title: '断开教务系统？',
      content: '将清除已同步的课表与成绩数据。',
      confirmText: '断开连接',
      confirmColor: '#ED6E52',
      success: async (result) => {
        if (!result.confirm) return
        this.stopPolling()
        this.setData({ busy: true })
        try {
          await repository.eduCancelConnection(connection.id)
          await repository.eduUnbind().catch(() => undefined)
          this.setData({
            phase: 'idle',
            busy: false,
            connection: null,
            probe: null,
            allScheduleItems: [],
            scheduleCards: [],
            sectionRows: buildSectionRows(12),
            gridHeight: HEADER_HEIGHT + 12 * SECTION_HEIGHT,
            gradeRows: [],
            errorMessage: '',
          })
          wx.showToast({ title: '已断开连接', icon: 'success' })
        } catch (error) {
          this.setData({
            busy: false,
            errorMessage: error instanceof Error ? error.message : '断开失败',
          })
        }
      },
    })
  },
  stateLabel(): string {
    return this.data.connection ? describeState(this.data.connection.state) : ''
  },
})
