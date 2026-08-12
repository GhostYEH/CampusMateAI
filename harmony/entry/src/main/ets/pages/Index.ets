import { AppState } from '../core/AppState';
import { ApiConfig } from '../core/ApiConfig';
import { darkPalette, lightPalette } from '../ui/Theme';
import { SecondaryHeader } from '../ui/SecondaryHeader';
import { ApiClient } from '../data/ApiClient';
import { LoginScreen } from '../features/login/LoginScreen';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { AppDock } from '../ui/AppDock';
import { CoursesPage } from '../features/courses/CoursesPage';
import { TasksPage } from '../features/tasks/TasksPage';
import { CounselorPage } from '../features/counselor/CounselorPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { ExamsPage } from '../features/exams/ExamsPage';
import { ClassroomsPage } from '../features/classrooms/ClassroomsPage';
import { ServicesPage } from '../features/services/ServicesPage';
import { FocusPage } from '../features/focus/FocusPage';
import { LostFoundPage } from '../features/lostfound/LostFoundPage';
import { NotificationsPage } from '../features/notifications/NotificationsPage';
import { PersonalHubPage } from '../features/profile/PersonalHubPage';
import { SettingsPage } from '../features/profile/SettingsPage';
import { AccountPage } from '../features/profile/AccountPage';
import { ActivityItem, ChatMessage, ChatRequest, ChatResponse, ClassroomAvailability, ClassroomResponse, CourseItem, ExamItem, FavoriteItem, LocalCapturedNotice, LostFoundItem, LostFoundPayload, MeResponse, NoticeItem, PagedResponse, PersonalFileItem, ServiceRequestItem, ServiceRequestPayload, StudySession, StudySessionCreate, StudySessionFinish, TaskItem, ExtractResult } from '../data/Models';
import { NotificationIngestService } from '../data/notification/NotificationIngestService';
import { notificationSubscriberManager } from '../data/notification/NotificationSubscriber';
import { http } from '@kit.NetworkKit';
import { promptAction, window } from '@kit.ArkUI';

const API_BASE_URL: string = ApiConfig.API_BASE_URL;

function toastError(message: string): void {
  try { promptAction.showToast({ message: message, duration: 2200 }); } catch { /* ignore toast failure */ }
}

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

@Entry
@Component
struct Index {
  private appState: AppState = new AppState();
  private tabsController: TabsController = new TabsController();
  private requestedTab: number = -1;
  private ingestService: NotificationIngestService | null = null;
  @State signedIn: boolean = false;
  @State darkMode: boolean = false;
  @State reduceMotion: boolean = false;
  @State activeTab: number = 0;
  @State route: string = '';
  @State username: string = '';
  @State password: string = '';
  @State loginError: string = '';
  @State loginLoading: boolean = false;
  @State primaryLoading: boolean = false;
  @State courses: CourseItem[] = [];
  @State tasks: TaskItem[] = [];
  @State chatMessages: ChatMessage[] = [];
  @State chatInput: string = '';
  @State chatSending: boolean = false;
  @State displayName: string = '林知夏';
  @State profileDetail: string = '计算机科学与技术 · 大三';
  @State secondaryLoading: boolean = false;
  @State secondarySubmitting: boolean = false;
  @State exams: ExamItem[] = [];
  @State classrooms: ClassroomAvailability[] = [];
  @State serviceRequests: ServiceRequestItem[] = [];
  @State lostFoundItems: LostFoundItem[] = [];
  @State studySessions: StudySession[] = [];
  @State activeStudySession?: StudySession = undefined;
  @State notices: NoticeItem[] = [];
  @State localNotices: LocalCapturedNotice[] = [];
  @State subscriberActive: boolean = false;
  @State personalFiles: PersonalFileItem[] = [];
  @State activities: ActivityItem[] = [];
  @State favorites: FavoriteItem[] = [];
  @State backendOnline: boolean = true;
  @State rememberUsername: boolean = false;
  @State statusBarHeight: number = 0;

  async aboutToAppear(): Promise<void> {
    await this.appState.restore();
    this.signedIn = this.appState.sessionToken.length > 0;
    this.darkMode = this.appState.darkMode;
    this.reduceMotion = this.appState.reduceMotion;
    this.rememberUsername = this.appState.rememberUsername;
    this.applySystemBarStyle();
    if (this.rememberUsername && this.appState.savedUsername.length > 0) {
      this.username = this.appState.savedUsername;
    }
    if (this.signedIn) {
      this.initNotificationService();
      this.refreshPrimaryData();
    }
  }

  initNotificationService(): void {
    if (this.ingestService === null) {
      this.ingestService = new NotificationIngestService(API_BASE_URL, () => this.appState.sessionToken);
      notificationSubscriberManager.init(this.ingestService);
    }
    this.loadLocalNotices();
    notificationSubscriberManager.start().then((active: boolean) => {
      this.subscriberActive = active;
    }).catch(() => { this.subscriberActive = false; });
  }

  async loadLocalNotices(): Promise<void> {
    if (this.ingestService !== null) {
      try {
        this.localNotices = await this.ingestService.loadLocalNotices();
      } catch { this.localNotices = []; }
    }
  }

  applySystemBarStyle(): void {
    try {
      window.getLastWindow(getContext(this)).then((win: window.Window) => {
        win.setWindowSystemBarProperties({
          statusBarColor: '#00000000',
          isStatusBarLightIcon: this.darkMode
        }).catch(() => {});
        try {
          const avoidArea = win.getWindowAvoidArea(window.AvoidAreaType.TYPE_SYSTEM);
          this.statusBarHeight = px2vp(avoidArea.topRect.height);
        } catch { /* ignore */ }
      }).catch(() => {});
    } catch { /* ignore */ }
  }

  surface(): string { return this.darkMode ? darkPalette.surface : lightPalette.surface; }
  pageBackground(): string { return this.darkMode ? darkPalette.background : lightPalette.background; }
  textColor(): string { return this.darkMode ? darkPalette.text : lightPalette.text; }
  mutedColor(): string { return this.darkMode ? darkPalette.muted : lightPalette.muted; }
  primaryColor(): string { return this.darkMode ? darkPalette.primary : lightPalette.primary; }
  softColor(): string { return this.darkMode ? darkPalette.soft : lightPalette.soft; }
  lineColor(): string { return this.darkMode ? darkPalette.line : lightPalette.line; }

  async signInForPreview(): Promise<void> {
    if (this.loginLoading) {
      return;
    }
    if (this.username.trim().length === 0 || this.password.length === 0) {
      this.loginError = this.username.trim().length === 0 ? '请输入学号、工号或用户名。' : '请输入密码后继续。';
      return;
    }
    this.loginLoading = true;
    this.loginError = '';
    try {
      const client = new ApiClient(API_BASE_URL, () => '');
      const token = await client.login(this.username.trim(), this.password);
      await this.appState.signIn(token);
      await this.appState.setRememberUsername(this.rememberUsername);
      await this.appState.saveUsername(this.username.trim());
      this.signedIn = true;
      this.loginError = '';
      this.initNotificationService();
      await this.refreshPrimaryData();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '暂时无法登录，请检查账号、密码和网络后重试。';
      this.loginError = errorMessage;
    } finally {
      this.loginLoading = false;
    }
  }

  async refreshPrimaryData(): Promise<void> {
    if (this.appState.sessionToken.length === 0 || this.primaryLoading) {
      return;
    }
    this.primaryLoading = true;
    const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
    try {
      const me = await client.request<MeResponse>(http.RequestMethod.GET, 'auth/me');
      const user = me?.user ?? {};
      this.displayName = user.display_name ?? user.name ?? user.username ?? '林知夏';
      const detailParts: string[] = [];
      if (user.major !== undefined && user.major.length > 0) {
        detailParts.push(user.major);
      }
      if (user.grade !== undefined && user.grade.length > 0) {
        detailParts.push(`${user.grade}级`);
      }
      if (detailParts.length > 0) {
        this.profileDetail = detailParts.join(' · ');
      }
      const coursePage = await client.request<PagedResponse<CourseItem>>(http.RequestMethod.GET, 'courses?page=1&page_size=100');
      this.courses = safeArray<CourseItem>(coursePage?.items);
      const taskPage = await client.request<PagedResponse<TaskItem>>(http.RequestMethod.GET, 'tasks?page=1&page_size=200');
      this.tasks = safeArray<TaskItem>(taskPage?.items);
      const noticePage = await client.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=20');
      this.notices = safeArray<NoticeItem>(noticePage?.items);
      await this.loadLocalNotices();
      this.backendOnline = true;
    } catch (error) {
      this.backendOnline = false;
      if (error instanceof Error && error.message.includes('登录已过期')) {
        await this.signOut();
        toastError('登录已过期，请重新登录');
      }
    } finally {
      this.primaryLoading = false;
    }
  }

  async toggleTask(task: TaskItem): Promise<void> {
    const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
    try {
      await client.request<TaskItem>(
        http.RequestMethod.POST,
        task.status === 'completed' ? `tasks/${task.id}/restore` : `tasks/${task.id}/complete`
      );
      await this.refreshPrimaryData();
    } catch (error) {
      toastError('更新待办状态失败，请重试');
    }
  }

  async sendChat(): Promise<void> {
    const message = this.chatInput.trim();
    if (message.length === 0 || this.chatSending) {
      return;
    }
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message
    };
    this.chatMessages = [...this.chatMessages, userMessage];
    this.chatInput = '';
    this.chatSending = true;
    const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
    try {
      const request: ChatRequest = {
        message: message,
        session_id: 'harmony-session',
        stream: false
      };
      const response = await client.request<ChatResponse>(http.RequestMethod.POST, 'counselor/chat', request);
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer ?? response.message ?? '暂时没有找到合适的回答，请稍后再试。'
      };
      this.chatMessages = [...this.chatMessages, assistantMessage];
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `assistant-error-${Date.now()}`,
        role: 'assistant',
        content: '暂时无法连接校园知识库，请检查网络后重试。'
      };
      this.chatMessages = [...this.chatMessages, errorMessage];
    } finally {
      this.chatSending = false;
    }
  }

  async signOut(): Promise<void> {
    await notificationSubscriberManager.stop();
    this.subscriberActive = false;
    await this.appState.signOut();
    this.signedIn = false;
    this.route = '';
    this.activeTab = 0;
    this.password = '';
    this.localNotices = [];
    if (!this.rememberUsername) {
      this.username = '';
    }
  }

  async toggleSubscriber(): Promise<void> {
    if (this.subscriberActive) {
      await notificationSubscriberManager.stop();
      this.subscriberActive = false;
      toastError('已关闭通知监听');
    } else {
      if (this.ingestService === null) {
        this.ingestService = new NotificationIngestService(API_BASE_URL, () => this.appState.sessionToken);
        notificationSubscriberManager.init(this.ingestService);
      }
      const ok: boolean = await notificationSubscriberManager.start();
      this.subscriberActive = ok;
      if (ok) { toastError('通知监听已开启'); } else { toastError('监听开启失败，需通知控制权限'); }
    }
  }

  async toggleTheme(): Promise<void> {
    await this.appState.toggleTheme();
    this.darkMode = this.appState.darkMode;
    this.applySystemBarStyle();
  }

  navigateTo(target: string): void {
    if (target === 'courses') { this.selectTab(1); return; }
    if (target === 'tasks') { this.selectTab(2); return; }
    if (target === 'counselor') { this.selectTab(3); return; }
    if (target === 'profile') { this.selectTab(4); return; }
    this.route = target;
    this.refreshSecondaryData(target);
  }

  selectTab(index: number): void {
    this.route = '';
    // Tabs.onChange is delivered after controller navigation on this SDK and
    // can briefly report the previous index. Ignore that stale callback while
    // the controller completes the requested page transition.
    this.requestedTab = index;
    this.activeTab = index;
    this.tabsController.changeIndex(index);
  }

  async refreshSecondaryData(target: string): Promise<void> {
    if (this.secondaryLoading || this.appState.sessionToken.length === 0) return;
    this.secondaryLoading = true;
    const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
    try {
      if (target === 'exams') {
        this.exams = safeArray<ExamItem>(await client.request<ExamItem[]>(http.RequestMethod.GET, 'student/exams'));
      } else if (target === 'classrooms') {
        const response = await client.request<ClassroomResponse>(http.RequestMethod.GET, 'student/classrooms');
        this.classrooms = safeArray<ClassroomAvailability>(response?.items);
      } else if (target === 'services') {
        this.serviceRequests = safeArray<ServiceRequestItem>(await client.request<ServiceRequestItem[]>(http.RequestMethod.GET, 'student/service-requests'));
      } else if (target === 'lostfound') {
        this.lostFoundItems = safeArray<LostFoundItem>(await client.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found'));
      } else if (target === 'focus') {
        this.studySessions = safeArray<StudySession>(await client.request<StudySession[]>(http.RequestMethod.GET, 'study/sessions?page=1&page_size=20'));
        this.activeStudySession = await client.request<StudySession | undefined>(http.RequestMethod.GET, 'study/sessions/active');
      } else if (target === 'notifications') {
        const page = await client.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=100');
        this.notices = safeArray<NoticeItem>(page?.items);
        await this.loadLocalNotices();
      } else if (target === 'files') {
        this.personalFiles = safeArray<PersonalFileItem>(await client.request<PersonalFileItem[]>(http.RequestMethod.GET, 'personal-hub/files'));
      } else if (target === 'activities') {
        const page = await client.request<PagedResponse<ActivityItem>>(http.RequestMethod.GET, 'activities?page=1&page_size=100');
        this.activities = safeArray<ActivityItem>(page?.items);
      } else if (target === 'favorites') {
        this.favorites = safeArray<FavoriteItem>(await client.request<FavoriteItem[]>(http.RequestMethod.GET, 'personal-hub/favorites'));
      }
    } catch (error) {
      this.backendOnline = false;
      if (error instanceof Error && error.message.includes('登录已过期')) {
        await this.signOut();
        toastError('登录已过期，请重新登录');
      }
    } finally {
      this.secondaryLoading = false;
    }
  }

  async createServiceRequest(kind: string, title: string, content: string): Promise<void> {
    const payload: ServiceRequestPayload = { kind: kind, title: title, content: content };
    this.secondarySubmitting = true;
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      await client.request<ServiceRequestItem>(http.RequestMethod.POST, 'student/service-requests', payload);
      await this.refreshSecondaryData('services');
      toastError('申请已提交');
    } catch (error) {
      toastError('提交申请失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async publishLostFound(kind: string, title: string, content: string, location: string, contact: string): Promise<void> {
    const payload: LostFoundPayload = { kind: kind, title: title, content: content, location: location, contact: contact };
    this.secondarySubmitting = true;
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      await client.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', payload);
      await this.refreshSecondaryData('lostfound');
      toastError('发布成功');
    } catch (error) {
      toastError('发布失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async startFocusSession(): Promise<void> {
    if (this.activeStudySession !== undefined) return;
    const payload: StudySessionCreate = { goal: '完成一段专注学习' };
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      this.activeStudySession = await client.request<StudySession>(http.RequestMethod.POST, 'study/sessions', payload);
    } catch (error) {
      toastError('无法开始专注，请检查网络');
    }
  }

  async updateFocusSession(action: string): Promise<void> {
    if (this.activeStudySession === undefined) return;
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      if (action === 'finish') {
        const body: StudySessionFinish = { self_report: '鸿蒙端完成专注' };
        await client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/finish`, body);
        this.activeStudySession = undefined;
      } else {
        this.activeStudySession = await client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/${action}`);
      }
      await this.refreshSecondaryData('focus');
    } catch (error) {
      toastError('操作失败，请重试');
    }
  }

  async saveExam(payload: ExamItem, id?: string): Promise<void> {
    this.secondarySubmitting = true;
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      if (id !== undefined && id.length > 0) {
        await client.patch<ExamItem>(`student/exams/${id}`, payload);
      } else {
        await client.request<ExamItem>(http.RequestMethod.POST, 'student/exams', payload);
      }
      await this.refreshSecondaryData('exams');
      toastError(id !== undefined && id.length > 0 ? '考试已更新' : '考试已添加');
    } catch (error) {
      toastError('保存考试失败，请重试');
    } finally { this.secondarySubmitting = false; }
  }

  async deleteExam(id: string): Promise<void> {
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      await client.request<object>(http.RequestMethod.DELETE, `student/exams/${id}`);
      await this.refreshSecondaryData('exams');
      toastError('考试已删除');
    } catch (error) {
      toastError('删除失败，请重试');
    }
  }

  routeTitle(): string {
    if (this.route === 'courses') return '我的课程';
    if (this.route === 'exams') return '考试安排';
    if (this.route === 'classrooms') return '空教室查询';
    if (this.route === 'services') return '办事大厅';
    if (this.route === 'focus') return '专注自习';
    if (this.route === 'lostfound') return '失物招领';
    if (this.route === 'settings') return '设置';
    if (this.route === 'profile') return '个人资料';
    return '校园服务';
  }

  @Builder Header(title: string, subtitle: string) {
    Row() {
      Column({ space: 4 }) {
        Text(title).fontSize(25).fontWeight(FontWeight.Bold).fontColor(this.textColor())
        Text(subtitle).fontSize(13).fontColor(this.mutedColor())
      }.layoutWeight(1)
      if (this.darkMode) {
        SymbolGlyph($r('sys.symbol.sun')).fontSize(23).fontColor([this.primaryColor()]).onClick(() => this.toggleTheme())
      } else {
        SymbolGlyph($r('sys.symbol.moon')).fontSize(23).fontColor([this.primaryColor()]).onClick(() => this.toggleTheme())
      }
    }.width('100%').padding({ left: 20, right: 20, top: 18, bottom: 12 })
  }

  @Builder LoginPage() {
    LoginScreen({
      username: $username,
      password: $password,
      loading: this.loginLoading,
      error: this.loginError,
      reduceMotion: this.reduceMotion,
      rememberUsername: this.rememberUsername,
      onSubmit: () => {
        this.signInForPreview();
      },
      onInputChanged: () => {
        this.loginError = '';
      },
      onRememberChange: (value: boolean) => {
        this.rememberUsername = value;
        this.appState.setRememberUsername(value);
      }
    })
  }

  @Builder Tile(label: string, target: string) {
    Column({ space: 8 }) {
      Text(label).fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.textColor())
      Text('进入功能').fontSize(12).fontColor(this.primaryColor())
    }.alignItems(HorizontalAlign.Center).padding(14).backgroundColor(this.softColor()).borderRadius(16).width('31%').onClick(() => this.route = target)
  }

  @Builder HomePage() {
    DashboardPage({
      darkMode: this.darkMode,
      userName: this.displayName,
      courses: this.courses,
      tasks: this.tasks,
      notices: this.notices,
      onNavigate: (target: string) => {
        this.navigateTo(target);
      }
    })
  }

  @Builder ListPage(title: string, subtitle: string) {
    Column() {
      this.Header(title, subtitle)
      Scroll() {
        Column({ space: 10 }) {
          Button('查看最新校园数据').width('100%').height(54).backgroundColor(this.surface()).fontColor(this.textColor())
          Button('刷新').width('100%').backgroundColor(this.primaryColor()).fontColor('#FFFFFF')
        }.padding(20)
      }.layoutWeight(1)
    }
  }

  @Builder ProfileTab() {
    ProfilePage({
      darkMode: this.darkMode,
      name: this.displayName,
      detail: this.profileDetail,
      onNavigate: (target: string) => {
        if (target === 'counselor') {
          this.route = '';
          this.activeTab = 3;
        } else {
          this.navigateTo(target);
        }
      }
    })
  }

  @Builder SecondaryContent() {
    if (this.route === 'exams') {
      ExamsPage({ exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('exams'), onSave: (payload: ExamItem, id?: string) => this.saveExam(payload, id), onDelete: (id: string) => this.deleteExam(id) })
    } else if (this.route === 'classrooms') {
      ClassroomsPage({ classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onQuery: () => this.refreshSecondaryData('classrooms') })
    } else if (this.route === 'services') {
      ServicesPage({ requests: this.serviceRequests, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('services'), onSubmit: (kind: string, title: string, content: string) => this.createServiceRequest(kind, title, content) })
    } else if (this.route === 'focus') {
      FocusPage({ sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onStart: () => this.startFocusSession(), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: () => this.updateFocusSession('finish') })
    } else if (this.route === 'lostfound') {
      LostFoundPage({ items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onFilter: (kind: string) => this.refreshSecondaryData('lostfound'), onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact) })
    } else if (this.route === 'notifications') {
      NotificationsPage({ notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode, localNotices: this.localNotices, subscriberActive: this.subscriberActive, ingestService: this.ingestService, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('notifications'), onToggleSubscriber: () => this.toggleSubscriber(), onTaskSaved: () => this.refreshPrimaryData(), onLocalNoticesChanged: () => this.loadLocalNotices() })
    } else if (this.route === 'files' || this.route === 'activities' || this.route === 'favorites') {
      PersonalHubPage({ section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route) })
    } else if (this.route === 'settings') {
      SettingsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.route = '', onThemeChange: (value: boolean) => { if (value !== this.darkMode) this.toggleTheme(); }, onMotionChange: async (value: boolean) => { await this.appState.setReduceMotion(value); this.reduceMotion = value; }, onNavigate: (target: string) => this.navigateTo(target) })
    } else if (this.route === 'account') {
      AccountPage({ darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.route = '', onSignOut: () => this.signOut() })
    } else if (this.route === 'about') {
      Column({ space: 12 }) {
        SecondaryHeader({ title: '关于 CampusMate', subtitle: '校园事务智能陪伴助手', darkMode: this.darkMode, onBack: () => this.route = '' })
        Scroll() {
          Column({ space: 14 }) {
            SymbolGlyph($r('sys.symbol.school')).fontSize(46).fontColor([this.primaryColor()])
            Text('CampusMate AI').fontColor(this.textColor()).fontSize(22).fontWeight(FontWeight.Bold)
            Text('面向大学生的校园事务智能陪伴助手。').fontColor(this.textColor()).fontSize(14).textAlign(TextAlign.Center).lineHeight(22)
            Text('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。').fontColor(this.mutedColor()).fontSize(12).textAlign(TextAlign.Center).lineHeight(20)
          }.width('100%').padding(24).alignItems(HorizontalAlign.Center)
        }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      }.width('100%').height('100%').backgroundColor(this.pageBackground())
    } else {
      Column({ space: 12 }) {
        SecondaryHeader({ title: '校园服务', subtitle: '功能开发中', darkMode: this.darkMode, onBack: () => this.route = '' })
        Column({ space: 12 }) {
          SymbolGlyph($r('sys.symbol.info_circle')).fontSize(38).fontColor([this.primaryColor()])
          Text('面向大学生的校园事务智能陪伴助手。').fontColor(this.textColor()).fontSize(15).textAlign(TextAlign.Center)
          Text('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。').fontColor(this.mutedColor()).fontSize(12).textAlign(TextAlign.Center)
        }.width('100%').padding(28).alignItems(HorizontalAlign.Center)
      }.width('100%').height('100%').backgroundColor(this.pageBackground())
    }
  }

  @Builder SecondaryPage() {
    Stack() {
      this.SecondaryContent()
    }
    .width('100%')
    .height('100%')
    .backgroundColor(this.pageBackground())
  }

  private createToolbarItem(icon: Resource, text: string, action: () => void): ToolbarItem {
    return {
      value: text,
      icon: icon,
      action: action
    };
  }

  @Builder EmptyTabBar() {
    Column() {}.width('100%').height(0)
  }

  @Builder CoursesTabContent() {
    CoursesPage({ courses: this.courses, loading: this.primaryLoading, darkMode: this.darkMode, onRefresh: () => this.refreshPrimaryData() })
  }

  @Builder TasksTabContent() {
    TasksPage({
      tasks: this.tasks,
      loading: this.primaryLoading,
      darkMode: this.darkMode,
      onRefresh: () => this.refreshPrimaryData(),
      onComplete: (id: string) => {
        const selected = this.tasks.find((task: TaskItem) => task.id === id);
        if (selected !== undefined) {
          this.toggleTask(selected);
        }
      }
    })
  }

  @Builder CounselorTabContent() {
    CounselorPage({
      messages: this.chatMessages,
      sending: this.chatSending,
      darkMode: this.darkMode,
      input: $chatInput,
      onSend: () => this.sendChat()
    })
  }

  @Builder BottomNavigation() {
    AppDock({
      activeTab: $activeTab,
      darkMode: this.darkMode,
      pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length,
      onNavigate: (index: number) => {
        this.selectTab(index);
      }
    })
  }

  build() {
    if (this.signedIn) {
      Stack({ alignContent: Alignment.Bottom }) {
        Tabs({ barPosition: BarPosition.Start, index: this.activeTab, controller: this.tabsController }) {
          TabContent() {
            this.HomePage()
          }.tabBar(this.EmptyTabBar)

          TabContent() {
            this.CoursesTabContent()
          }.tabBar(this.EmptyTabBar)

          TabContent() {
            this.TasksTabContent()
          }.tabBar(this.EmptyTabBar)

          TabContent() {
            this.CounselorTabContent()
          }.tabBar(this.EmptyTabBar)

          TabContent() {
            this.ProfileTab()
          }.tabBar(this.EmptyTabBar)
        }
        .barHeight(0)
        .barMode(BarMode.Fixed)
        .animationDuration(this.reduceMotion ? 0 : 260)
        .scrollable(false)
        .width('100%')
        .height('100%')
        .backgroundColor(this.pageBackground())
        .onChange((index: number) => {
          if (this.requestedTab >= 0) {
            if (index !== this.requestedTab) {
              return;
            }
            // Keep the requested tab until the next dock action. This Tabs
            // implementation can emit a trailing callback for the former tab.
          }
          this.route = '';
          this.activeTab = index;
        })

        if (this.route.length > 0) {
          this.SecondaryPage()
        }

        if (this.route.length === 0) {
          this.BottomNavigation()
        }
      }
      .width('100%')
      .height('100%')
      .padding({ top: this.statusBarHeight })
      .backgroundColor(this.pageBackground())
    } else {
      this.LoginPage()
    }
  }
}
