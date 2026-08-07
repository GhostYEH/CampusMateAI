import { defaultCourses, defaultNotices, defaultTasks, demoUsers } from './mock-data'
import {
  AppSettings,
  CampusTask,
  ChatReply,
  Course,
  ExtractResult,
  Notice,
  User,
} from './types'

const STORAGE = {
  settings: 'campus.settings',
  session: 'campus.session',
  token: 'campus.token',
  tasks: 'campus.tasks',
}

const DEFAULT_SETTINGS: AppSettings = {
  mockMode: true,
  reduceMotion: false,
  darkMode: false,
  remindersEnabled: true,
  demoMode: true,
  apiBaseUrl: '',
}

type RequestMethod = 'GET' | 'POST' | 'DELETE'

class CampusRepository {
  bootstrap(): void {
    if (!wx.getStorageSync(STORAGE.settings)) {
      wx.setStorageSync(STORAGE.settings, DEFAULT_SETTINGS)
    }
    if (!wx.getStorageSync(STORAGE.tasks)) {
      wx.setStorageSync(STORAGE.tasks, defaultTasks)
    }
  }

  getSettings(): AppSettings {
    return {
      ...DEFAULT_SETTINGS,
      ...(wx.getStorageSync(STORAGE.settings) as Partial<AppSettings> | ''),
    }
  }

  saveSettings(next: Partial<AppSettings>): AppSettings {
    const settings = { ...this.getSettings(), ...next }
    wx.setStorageSync(STORAGE.settings, settings)
    return settings
  }

  getSession(): User | null {
    return (wx.getStorageSync(STORAGE.session) as User | '') || null
  }

  async login(username: string, password: string): Promise<User> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      await this.delay(480)
      const user = demoUsers[username]
      if (!user || password !== 'Demo123456') {
        throw new Error('账号或密码不正确')
      }
      wx.setStorageSync(STORAGE.session, user)
      return user
    }

    const login = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      'POST',
      { username, password },
    )
    wx.setStorageSync(STORAGE.token, login.access_token)
    const response = await this.request<{ user: Partial<User> }>('/auth/me', 'GET')
    if (response.user.role && response.user.role !== 'student') {
      wx.removeStorageSync(STORAGE.token)
      throw new Error('当前小程序暂仅支持学生账号')
    }
    const user: User = {
      name: response.user.name || username,
      role: response.user.role || 'student',
      detail: response.user.detail || '',
      email: response.user.email || '',
      studentId: response.user.studentId || '',
    }
    wx.setStorageSync(STORAGE.session, user)
    return user
  }

  logout(): void {
    wx.removeStorageSync(STORAGE.session)
    wx.removeStorageSync(STORAGE.token)
  }

  async getTasksAsync(): Promise<CampusTask[]> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      return this.getTasks()
    }
    const response = await this.request<{ items: any[] }>('/personal-tasks/', 'GET')
    return response.items.map((item: any) => ({
      id: item.id,
      title: item.title,
      due: item.deadline || '无截止时间',
      course: item.source_name || '个人待办',
      done: item.status === 'completed',
    }))
  }

  getTasks(): CampusTask[] {
    return (wx.getStorageSync(STORAGE.tasks) as CampusTask[] | '') || defaultTasks
  }

  async toggleTask(id: number | string): Promise<CampusTask[]> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      const tasks = this.getTasks().map((task) => (
        task.id === id ? { ...task, done: !task.done } : task
      ))
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }
    
    // Remote
    const tasks = await this.getTasksAsync()
    const task = tasks.find(t => t.id === id)
    if (task) {
      if (task.done) {
        await this.request(`/personal-tasks/${id}/restore`, 'POST')
      } else {
        await this.request(`/personal-tasks/${id}/complete`, 'POST')
      }
    }
    return this.getTasksAsync()
  }

  async deleteTask(id: number | string): Promise<CampusTask[]> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      const tasks = this.getTasks().filter((task) => task.id !== id)
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }
    
    // Remote
    await this.request(`/personal-tasks/${id}`, 'DELETE')
    return this.getTasksAsync()
  }

  async addTask(title: string, due = '待设置', course = '个人待办'): Promise<CampusTask[]> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      const tasks = [
        { id: Date.now(), title, due, course, done: false },
        ...this.getTasks(),
      ]
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }

    // Remote
    await this.request('/personal-tasks/', 'POST', {
      title,
      deadline: due === '待设置' ? null : due,
      source_name: course
    })
    return this.getTasksAsync()
  }

  getNotices(): Notice[] {
    return defaultNotices.map((notice) => ({ ...notice }))
  }

  getCourses(): Course[] {
    return defaultCourses.map((course) => ({ ...course }))
  }

  async extractNotice(text: string): Promise<ExtractResult> {
    if (!text.trim()) throw new Error('请先粘贴通知正文')
    const settings = this.getSettings()
    if (!settings.mockMode) {
      return this.request<ExtractResult>('/notices/extract-multi', 'POST', { text })
    }
    await this.delay(760)
    return {
      title: '2026 年秋季学期选课确认',
      source: '教务处',
      deadline: '本周五 17:00',
      tasks: ['登录教务系统核对课程信息', '如有冲突联系学院教务办公室'],
      confidence: 0.94,
      saved: false,
    }
  }

  async chat(message: string): Promise<ChatReply> {
    const settings = this.getSettings()
    if (!settings.mockMode) {
      const response = await this.request<{ answer?: string; message?: string }>(
        '/counselor/chat',
        'POST',
        { message, session_id: 'wx-session' },
      )
      return {
        answer: response.answer || response.message || '暂无回答',
        citation: '真实知识库检索结果',
        mock: false,
      }
    }
    await this.delay(680)
    if (message.includes('奖学金')) {
      return {
        answer: '奖学金通常综合考察学业成绩、综合素质与志愿服务。不同奖项条件不同，建议先查看学院本学年评审通知。我可以继续帮你整理申请材料清单。',
        citation: 'Mock 引用：《学生手册（演示知识库）》',
        mock: true,
      }
    }
    return {
      answer: '我已经记录你的问题。当前为 Mock 知识库模式，建议以学校教务处或学院最新通知为准。需要的话，我可以帮你把相关步骤整理成待办。',
      citation: 'Mock 引用：校园办事指南（演示数据）',
      mock: true,
    }
  }

  private request<T>(
    path: string,
    method: RequestMethod,
    data?: Record<string, unknown>,
  ): Promise<T> {
    const settings = this.getSettings()
    const baseUrl = settings.apiBaseUrl.replace(/\/$/, '')
    if (!baseUrl) {
      return Promise.reject(new Error('请先在“我的”中配置后端地址'))
    }
    const token = wx.getStorageSync(STORAGE.token) as string
    return new Promise<T>((resolve, reject) => {
      wx.request({
        url: `${baseUrl}/api/v1${path}`,
        method,
        data,
        header: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 10000,
        success: (response) => {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve(response.data as T)
          } else {
            reject(new Error(`服务请求失败（${response.statusCode}）`))
          }
        },
        fail: () => reject(new Error('暂时无法连接校园服务，请检查网络或切回 Mock 模式')),
      })
    })
  }

  private delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, milliseconds))
  }
}

export const repository = new CampusRepository()
