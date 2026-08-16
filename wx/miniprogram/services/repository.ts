import { formatApiDate, normalizeDeadline } from './date-utils'
import { defaultCourses, defaultNotices, defaultTasks, demoUsers } from './mock-data'
import {
  AppSettings,
  BackendHealth,
  CampusActivity,
  CampusTask,
  CategoryMeta,
  ChatReply,
  Classroom,
  CommunityComment,
  CommunityPost,
  ConnectionState,
  Course,
  ExtractResult,
  FavoriteItem,
  LostFoundItem,
  Notice,
  PersonalFile,
  ServiceRequest,
  StudentExam,
  University,
  User,
} from './types'

const STORAGE = {
  settings: 'campus.settings',
  session: 'campus.session',
  sessionMode: 'campus.session-mode',
  token: 'campus.token',
  refreshToken: 'campus.refresh-token',
  tasks: 'campus.tasks',
}

const DEFAULT_SETTINGS: AppSettings = {
  mockMode: false,
  reduceMotion: false,
  darkMode: false,
  remindersEnabled: true,
  demoMode: false,
  apiBaseUrl: 'http://192.168.1.17:8000',
}

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
type SessionMode = 'mock' | 'remote'

interface RequestOptions {
  authenticated?: boolean
  retryAfterRefresh?: boolean
}

interface ApiPage<T> {
  items: T[]
  total: number
}

interface ApiUser {
  username: string
  role: string
  name?: string
  display_name?: string
  student_number?: string
  college?: string
  major?: string
  grade?: string
}

interface TokenPair {
  access_token: string
  refresh_token: string
  user?: ApiUser
}

interface ApiTask {
  id: string
  title: string
  deadline?: string
  source_name?: string
  status: string
  priority?: 'low' | 'medium' | 'high'
}

interface ApiCourse {
  id: string
  name: string
  code?: string
  semester?: string
  teacher_name?: string
  provider?: string
  external_id?: string
}

interface ApiNotice {
  id: string
  title: string
  source?: string
  time?: string
  unread?: boolean
}

interface ApiExtractTask {
  title: string
  task: string
  deadline?: string
  source_name?: string
  source_text: string
  confidence: number
  materials?: Array<{ name: string; required: boolean }>
  submission_method?: string
  location?: string
  warnings?: string[]
}

interface MultiExtractResponse {
  tasks: ApiExtractTask[]
}

interface ChatResponse {
  answer?: string
  message?: string
  sources?: Array<{ title: string }>
}

interface StudySessionResponse {
  id: string
  status: string
}

class CampusRepository {
  private refreshPromise: Promise<boolean> | null = null

  bootstrap(): void {
    const stored = wx.getStorageSync(STORAGE.settings) as Partial<AppSettings> | ''
    if (!stored) {
      wx.setStorageSync(STORAGE.settings, DEFAULT_SETTINGS)
    } else if (!stored.apiBaseUrl && stored.mockMode !== false) {
      wx.setStorageSync(STORAGE.settings, {
        ...DEFAULT_SETTINGS,
        ...stored,
        mockMode: false,
        demoMode: false,
        apiBaseUrl: DEFAULT_SETTINGS.apiBaseUrl,
      })
      if (wx.getStorageSync(STORAGE.sessionMode) === 'mock') {
        wx.removeStorageSync(STORAGE.session)
        wx.removeStorageSync(STORAGE.sessionMode)
      }
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

  getConnectionState(): ConnectionState {
    const settings = this.getSettings()
    return {
      mode: settings.mockMode ? 'mock' : 'remote',
      apiBaseUrl: settings.apiBaseUrl.replace(/\/$/, ''),
      authenticated: Boolean(wx.getStorageSync(STORAGE.token)),
    }
  }

  probeRealBackend(): Promise<BackendHealth> {
    return this.request<BackendHealth>('/health', 'GET', undefined, {
      authenticated: false,
      retryAfterRefresh: false,
    })
  }

  getSession(): User | null {
    const session = (wx.getStorageSync(STORAGE.session) as User | '') || null
    if (!session) return null
    const expectedMode: SessionMode = this.getSettings().mockMode ? 'mock' : 'remote'
    return wx.getStorageSync(STORAGE.sessionMode) === expectedMode ? session : null
  }

  async login(username: string, password: string): Promise<User> {
    const settings = this.getSettings()
    if (settings.mockMode) {
      await this.delay(480)
      const user = demoUsers[username]
      if (!user || password !== 'Demo123456') throw new Error('账号或密码不正确')
      this.persistSession(user, 'mock')
      return user
    }

    const login = await this.request<TokenPair>(
      '/auth/login',
      'POST',
      { username, password },
      { authenticated: false, retryAfterRefresh: false },
    )
    this.persistTokens(login)
    const apiUser = login.user || (await this.request<{ user: ApiUser }>('/auth/me', 'GET')).user
    if (apiUser.role !== 'student') {
      this.clearSession()
      throw new Error('当前小程序暂仅支持学生账号')
    }
    const user = this.mapUser(apiUser)
    this.persistSession(user, 'remote')
    return user
  }

  async logout(): Promise<void> {
    const refreshToken = wx.getStorageSync(STORAGE.refreshToken) as string
    if (refreshToken) {
      try {
        await this.request(
          '/auth/logout',
          'POST',
          { refresh_token: refreshToken },
          { authenticated: true, retryAfterRefresh: false },
        )
      } catch {
        const refreshed = await this.refreshAccessToken()
        const latestRefreshToken = wx.getStorageSync(STORAGE.refreshToken) as string
        if (refreshed && latestRefreshToken) {
          try {
            await this.request(
              '/auth/logout',
              'POST',
              { refresh_token: latestRefreshToken },
              { authenticated: true, retryAfterRefresh: false },
            )
          } catch {
            // Local logout must still succeed when the server is unavailable.
          }
        }
      }
    }
    this.clearSession()
  }

  async checkBackendHealth(): Promise<void> {
    await this.probeRealBackend()
  }

  async getTasksAsync(): Promise<CampusTask[]> {
    if (this.getSettings().mockMode) return this.getTasks()
    const response = await this.request<ApiPage<ApiTask>>('/tasks', 'GET')
    return response.items.map((item) => this.mapTask(item))
  }

  getTasks(): CampusTask[] {
    return (wx.getStorageSync(STORAGE.tasks) as CampusTask[] | '') || defaultTasks
  }

  async toggleTask(id: number | string): Promise<CampusTask[]> {
    if (this.getSettings().mockMode) {
      const tasks = this.getTasks().map((task) => (
        task.id === id ? { ...task, done: !task.done } : task
      ))
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }

    const tasks = await this.getTasksAsync()
    const task = tasks.find((item) => item.id === id)
    if (!task) throw new Error('待办不存在或已被删除')
    await this.request(`/tasks/${id}/${task.done ? 'restore' : 'complete'}`, 'POST')
    return this.getTasksAsync()
  }

  async deleteTask(id: number | string): Promise<CampusTask[]> {
    if (this.getSettings().mockMode) {
      const tasks = this.getTasks().filter((task) => task.id !== id)
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }
    await this.request(`/tasks/${id}`, 'DELETE')
    return this.getTasksAsync()
  }

  async addTask(
    title: string,
    due = '待设置',
    course = '个人待办',
    sourceText = '',
  ): Promise<CampusTask[]> {
    if (this.getSettings().mockMode) {
      const tasks = [{ id: Date.now(), title, due, course, done: false }, ...this.getTasks()]
      wx.setStorageSync(STORAGE.tasks, tasks)
      return tasks
    }
    const deadline = normalizeDeadline(due)
    if (due.trim() && due !== '待设置' && due !== '无截止时间' && !deadline) {
      throw new Error('无法识别截止时间，请使用“今天 23:59”“8月20日 18:00”或完整日期')
    }
    await this.request('/tasks', 'POST', {
      title,
      deadline,
      source_name: course,
      source_text: sourceText || null,
    })
    return this.getTasksAsync()
  }

  async getNoticesAsync(): Promise<Notice[]> {
    if (this.getSettings().mockMode) return this.getNotices()
    const response = await this.request<ApiPage<ApiNotice>>('/notices', 'GET')
    return response.items.map((item) => ({
      id: item.id,
      title: item.title,
      source: item.source || '校园通知',
      time: formatApiDate(item.time).replace('无截止时间', '时间未知'),
      unread: Boolean(item.unread),
    }))
  }

  getNotices(): Notice[] {
    return defaultNotices.map((notice) => ({ ...notice }))
  }

  async getCoursesAsync(): Promise<Course[]> {
    if (this.getSettings().mockMode) return this.getCourses()
    const response = await this.request<ApiPage<ApiCourse>>('/courses', 'GET')
    return response.items.map((item) => ({
      id: item.id,
      name: item.name,
      code: item.code || item.external_id || item.id,
      type: item.semester || (item.provider === 'chaoxing' ? '超星课程' : '本学期课程'),
      teacher: item.teacher_name || '教师待同步',
      location: item.provider === 'chaoxing' ? '超星学习通' : '课程平台',
      weekday: '课表待同步',
      time: '时间待确认',
    }))
  }

  getCourses(): Course[] {
    return defaultCourses.map((course) => ({ ...course }))
  }

  async getStudentExamsAsync(): Promise<StudentExam[]> {
    return this.request<StudentExam[]>('/student/exams', 'GET')
  }

  async saveStudentExam(exam: Omit<StudentExam, 'id'>, id?: string): Promise<StudentExam> {
    return this.request<StudentExam>(id ? `/student/exams/${id}` : '/student/exams', id ? 'PATCH' : 'POST', exam)
  }

  async deleteStudentExam(id: string): Promise<void> {
    await this.request(`/student/exams/${id}`, 'DELETE')
  }

  async getClassroomsAsync(date?: string, building?: string): Promise<Classroom[]> {
    const query = [date ? `date=${encodeURIComponent(date)}` : '', building ? `building=${encodeURIComponent(building)}` : '']
      .filter(Boolean)
      .join('&')
    const response = await this.request<ApiPage<Classroom>>(`/student/classrooms${query ? `?${query}` : ''}`, 'GET')
    return response.items
  }

  async getCommunityCategoriesAsync(): Promise<CategoryMeta[]> {
    const response = await this.request<{ items: CategoryMeta[] }>('/community/posts/categories', 'GET')
    return response.items
  }

  async getCommunityPostsAsync(params?: { q?: string; category?: string; sort?: string; page?: number; page_size?: number }): Promise<{ items: CommunityPost[]; total: number }> {
    const query = [
      params?.q ? `q=${encodeURIComponent(params.q)}` : '',
      params?.category ? `category=${encodeURIComponent(params.category)}` : '',
      params?.sort ? `sort=${encodeURIComponent(params.sort)}` : '',
      params?.page ? `page=${params.page}` : '',
      params?.page_size ? `page_size=${params.page_size}` : '',
    ].filter(Boolean).join('&')
    const response = await this.request<{ items: CommunityPost[]; total: number }>(`/community/posts${query ? `?${query}` : ''}`, 'GET')
    return { items: response.items || [], total: response.total || 0 }
  }

  async getCommunityPostAsync(id: string): Promise<CommunityPost> {
    return this.request<CommunityPost>(`/community/posts/${id}`, 'GET')
  }

  async createCommunityPost(payload: { title: string; content: string; category: string; images?: string[]; is_anonymous?: boolean; extra?: Record<string, unknown> | null }): Promise<CommunityPost> {
    return this.request<CommunityPost>('/community/posts', 'POST', {
      title: payload.title,
      content: payload.content,
      category: payload.category,
      images: payload.images || [],
      is_anonymous: payload.is_anonymous || false,
      extra: payload.extra || null,
    })
  }

  async deleteCommunityPost(id: string): Promise<void> {
    await this.request(`/community/posts/${id}`, 'DELETE')
  }

  async likeCommunityPost(id: string): Promise<CommunityPost> {
    return this.request<CommunityPost>(`/community/posts/${id}/like`, 'POST')
  }

  async unlikeCommunityPost(id: string): Promise<CommunityPost> {
    return this.request<CommunityPost>(`/community/posts/${id}/like`, 'DELETE')
  }

  async favoriteCommunityPost(id: string): Promise<CommunityPost> {
    return this.request<CommunityPost>(`/community/posts/${id}/favorite`, 'POST')
  }

  async unfavoriteCommunityPost(id: string): Promise<CommunityPost> {
    return this.request<CommunityPost>(`/community/posts/${id}/favorite`, 'DELETE')
  }

  async getCommunityCommentsAsync(id: string): Promise<CommunityComment[]> {
    const response = await this.request<{ items: CommunityComment[] }>(`/community/posts/${id}/comments`, 'GET')
    return response.items || []
  }

  async createCommunityCommentAsync(id: string, payload: { content: string; parent_comment_id?: string; is_anonymous?: boolean }): Promise<CommunityComment> {
    return this.request<CommunityComment>(`/community/posts/${id}/comments`, 'POST', payload)
  }

  async reportCommunityPostAsync(payload: { target_type: string; target_id: string; reason: string; details?: string }): Promise<void> {
    await this.request('/community/reports', 'POST', payload)
  }

  async uploadCommunityImageAsync(filePath: string): Promise<string> {
    const settings = this.getSettings()
    const baseUrl = settings.apiBaseUrl.replace(/\/$/, '')
    const token = wx.getStorageSync(STORAGE.token) as string
    return new Promise<string>((resolve, reject) => {
      wx.uploadFile({
        url: `${baseUrl}/api/v1/community/upload-image`,
        filePath,
        name: 'image',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (response) => {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            try { const data = JSON.parse(response.data) as { url: string }; resolve(data.url) }
            catch { reject(new Error('上传响应解析失败')) }
            return
          }
          reject(new Error('图片上传失败'))
        },
        fail: () => reject(new Error('图片上传失败，请检查网络')),
      })
    })
  }

  resolveAssetUrl(url: string): string {
    if (!url) return url
    if (url.startsWith('http://') || url.startsWith('https://')) return url
    if (url.startsWith('/static/')) {
      const settings = this.getSettings()
      const baseUrl = settings.apiBaseUrl.replace(/\/$/, '')
      return `${baseUrl}${url}`
    }
    return url
  }

  async getLostFoundAsync(mine = false): Promise<LostFoundItem[]> {
    return this.request<LostFoundItem[]>(`/student/lost-found${mine ? '?mine=true' : ''}`, 'GET')
  }

  async createLostFound(item: Pick<LostFoundItem, 'kind' | 'title' | 'content' | 'location' | 'contact' | 'contact_visibility'>): Promise<LostFoundItem> {
    return this.request<LostFoundItem>('/student/lost-found', 'POST', item)
  }

  async deleteLostFound(id: string): Promise<void> {
    await this.request(`/student/lost-found/${id}`, 'DELETE')
  }

  async getActivitiesAsync(): Promise<CampusActivity[]> {
    const response = await this.request<ApiPage<CampusActivity>>('/activities', 'GET')
    return response.items
  }

  async getPersonalFilesAsync(): Promise<PersonalFile[]> {
    return this.request<PersonalFile[]>('/personal-hub/files', 'GET')
  }

  async getFavoritesAsync(): Promise<FavoriteItem[]> {
    return this.request<FavoriteItem[]>('/personal-hub/favorites', 'GET')
  }

  async getUniversitiesAsync(): Promise<University[]> {
    const response = await this.request<ApiPage<University>>('/universities', 'GET')
    return response.items
  }

  async getServiceRequestsAsync(): Promise<ServiceRequest[]> {
    return this.request<ServiceRequest[]>('/student/service-requests', 'GET')
  }

  async createServiceRequest(kind: string, title: string, content: string): Promise<ServiceRequest> {
    return this.request<ServiceRequest>('/student/service-requests', 'POST', { kind, title, content })
  }

  async extractNotice(text: string): Promise<ExtractResult[]> {
    const content = text.trim()
    if (!content) throw new Error('请先粘贴通知正文')
    if (!this.getSettings().mockMode) {
      const response = await this.request<MultiExtractResponse>(
        '/notices/extract-multi',
        'POST',
        { content, allow_multi_task: true },
      )
      return response.tasks.map((item, index) => this.mapExtractResult(item, index))
    }
    await this.delay(760)
    return [{
      id: 'mock-extract-1',
      title: '2026 年秋季学期选课确认',
      source: '教务处',
      deadline: '本周五 17:00',
      tasks: ['登录教务系统核对课程信息', '如有冲突联系学院教务办公室'],
      confidence: 0.94,
      sourceText: content,
      saved: false,
    }]
  }

  async chat(message: string): Promise<ChatReply> {
    if (!this.getSettings().mockMode) {
      const response = await this.request<ChatResponse>('/counselor/chat', 'POST', {
        message,
        conversation_id: 'wx-session',
        stream: false,
      })
      const sourceTitles = (response.sources || []).map((source) => source.title)
      return {
        answer: response.answer || response.message || '暂无回答',
        citation: sourceTitles.length ? sourceTitles.join('、') : '校园知识库未检索到明确出处',
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

  async startStudySession(): Promise<string | null> {
    if (this.getSettings().mockMode) return null
    const session = await this.request<StudySessionResponse>('/study/sessions', 'POST', {
      mode: 'focus',
    })
    return session.id
  }

  async getActiveStudySession(): Promise<StudySessionResponse | null> {
    if (this.getSettings().mockMode) return null
    return this.request<StudySessionResponse | null>('/study/sessions/active', 'GET')
  }

  async pauseStudySession(sessionId: string): Promise<void> {
    if (this.getSettings().mockMode) return
    await this.request(`/study/sessions/${sessionId}/pause`, 'POST')
  }

  async resumeStudySession(sessionId: string): Promise<void> {
    if (this.getSettings().mockMode) return
    await this.request(`/study/sessions/${sessionId}/resume`, 'POST')
  }

  async finishStudySession(sessionId: string, feeling: string): Promise<void> {
    if (this.getSettings().mockMode) return
    await this.request(`/study/sessions/${sessionId}/finish`, 'POST', {
      self_report: feeling || null,
      self_report_tags: feeling ? [feeling] : [],
    })
  }

  private request<T>(
    path: string,
    method: RequestMethod,
    data?: Record<string, unknown>,
    options: RequestOptions = {},
  ): Promise<T> {
    const settings = this.getSettings()
    const baseUrl = settings.apiBaseUrl.replace(/\/$/, '')
    if (!baseUrl) return Promise.reject(new Error('请先在“我的”中配置后端地址'))
    const authenticated = options.authenticated !== false
    const retryAfterRefresh = options.retryAfterRefresh !== false
    const token = wx.getStorageSync(STORAGE.token) as string

    return new Promise<T>((resolve, reject) => {
      wx.request({
        url: `${baseUrl}/api/v1${path}`,
        method: method as WechatMiniprogram.RequestOption['method'],
        data,
        header: authenticated && token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 15000,
        success: (response) => {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve(response.data as T)
            return
          }
          if (response.statusCode === 401 && authenticated && retryAfterRefresh) {
            this.refreshAccessToken().then((refreshed) => {
              if (!refreshed) {
                this.expireSession()
                reject(new Error('登录已过期，请重新登录'))
                return
              }
              this.request<T>(path, method, data, { authenticated, retryAfterRefresh: false })
                .then(resolve)
                .catch(reject)
            }).catch(reject)
            return
          }
          reject(new Error(this.extractErrorMessage(response.data, response.statusCode)))
        },
        fail: (error) => reject(new Error(error.errMsg.includes('timeout')
          ? '校园服务响应超时，请稍后重试'
          : '暂时无法连接校园服务，请检查网络和后端地址')),
      })
    })
  }

  private refreshAccessToken(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise
    const refreshToken = wx.getStorageSync(STORAGE.refreshToken) as string
    if (!refreshToken) return Promise.resolve(false)
    this.refreshPromise = this.request<TokenPair>(
      '/auth/refresh',
      'POST',
      { refresh_token: refreshToken },
      { authenticated: false, retryAfterRefresh: false },
    ).then((tokens) => {
      this.persistTokens(tokens)
      return true
    }).catch(() => false).finally(() => {
      this.refreshPromise = null
    })
    return this.refreshPromise
  }

  private persistTokens(tokens: TokenPair): void {
    wx.setStorageSync(STORAGE.token, tokens.access_token)
    wx.setStorageSync(STORAGE.refreshToken, tokens.refresh_token)
  }

  private persistSession(user: User, mode: SessionMode): void {
    wx.setStorageSync(STORAGE.session, user)
    wx.setStorageSync(STORAGE.sessionMode, mode)
  }

  private clearSession(): void {
    wx.removeStorageSync(STORAGE.session)
    wx.removeStorageSync(STORAGE.sessionMode)
    wx.removeStorageSync(STORAGE.token)
    wx.removeStorageSync(STORAGE.refreshToken)
  }

  private expireSession(): void {
    this.clearSession()
    setTimeout(() => wx.reLaunch({ url: '/pages/login/login' }), 0)
  }

  private mapUser(user: ApiUser): User {
    const detail = [user.college, user.major, user.grade ? `${user.grade}级` : '']
      .filter(Boolean)
      .join(' · ')
    return {
      name: user.display_name || user.name || user.username,
      role: 'student',
      detail,
      email: '',
      studentId: user.student_number || '',
    }
  }

  private mapTask(item: ApiTask): CampusTask {
    return {
      id: item.id,
      title: item.title,
      deadline: item.deadline,
      due: formatApiDate(item.deadline),
      course: item.source_name || '个人待办',
      done: item.status === 'completed',
      priority: item.priority,
    }
  }

  private mapExtractResult(item: ApiExtractTask, index: number): ExtractResult {
    const steps = [
      item.task,
      ...(item.materials || []).map((material) => `${material.required ? '准备' : '可选'}：${material.name}`),
      item.submission_method ? `提交方式：${item.submission_method}` : '',
      item.location ? `办理地点：${item.location}` : '',
      ...(item.warnings || []).map((warning) => `请确认：${warning}`),
    ].filter(Boolean)
    return {
      id: `extract-${Date.now()}-${index}`,
      title: item.title || item.task,
      source: item.source_name || '校园通知',
      deadline: formatApiDate(item.deadline),
      rawDeadline: item.deadline,
      sourceText: item.source_text,
      tasks: steps,
      confidence: item.confidence,
      saved: false,
    }
  }

  private extractErrorMessage(data: unknown, statusCode: number): string {
    if (data && typeof data === 'object') {
      const payload = data as { message?: unknown; detail?: unknown }
      if (typeof payload.message === 'string' && payload.message) return payload.message
      if (typeof payload.detail === 'string' && payload.detail) return payload.detail
    }
    return `服务请求失败（${statusCode}）`
  }

  private delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, milliseconds))
  }
}

export const repository = new CampusRepository()
