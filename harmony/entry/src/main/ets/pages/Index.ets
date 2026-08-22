import { AppState } from '../core/AppState';
import { ApiConfig } from '../core/ApiConfig';
import { CampusPalette, darkPalette, lightPalette } from '../ui/Theme';
import { SecondaryHeader } from '../ui/SecondaryHeader';
import { ApiClient, ApiClientAuth, ApiError, ApiErrorCode, SseEvent } from '../data/ApiClient';
import { AuthTokens } from '../data/auth/TokenStore';
import { LoginScreen } from '../features/login/LoginScreen';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { AppDock } from '../ui/AppDock';
import { CoursesPage } from '../features/courses/CoursesPage';
import { TasksPage } from '../features/tasks/TasksPage';
import { CounselorPage } from '../features/counselor/CounselorPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { QrScannerPage } from '../features/profile/QrScannerPage';
import { QrConfirmPage } from '../features/profile/QrConfirmPage';
import { ExamsPage } from '../features/exams/ExamsPage';
import { ClassroomsPage } from '../features/classrooms/ClassroomsPage';
import { V3CorePage } from '../features/v3/V3CorePage';
import { FocusPage } from '../features/focus/FocusPage';
import { LostFoundPage } from '../features/lostfound/LostFoundPage';
import { NotificationsPage } from '../features/notifications/NotificationsPage';
import { PersonalHubPage } from '../features/profile/PersonalHubPage';
import { SettingsPage } from '../features/profile/SettingsPage';
import { AccountPage } from '../features/profile/AccountPage';
import { EduSystemPage } from '../features/profile/EduSystemPage';
import { EduLoginPage } from '../features/edu/EduLoginPage';
import { EduSchedulePage } from '../features/edu/EduSchedulePage';
import { AcademicStatusItem, ActivityItem, ChatMessage, ChatMessageModel, ChatRequest, ClassroomAvailability, ClassroomResponse, CommunityPostItem, CommunityPostPayload, CourseContentBundle, CourseContentPage, CourseContentSummary, CourseItem, ExamItem, FavoriteItem, FocusMode, LocalCapturedNotice, LostFoundItem, LostFoundPayload, MeResponse, NoticeItem, PagedResponse, PersonalFileItem, StudySession, TaskItem, ExtractResult, UniversityItem, UniversitySelectionRequest, UniversitySelectionResponse } from '../data/Models';
import { NotificationIngestService } from '../data/notification/NotificationIngestService';
import { notificationSubscriberManager } from '../data/notification/NotificationSubscriber';
import { StudyRepository } from '../repository/StudyRepository';
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
  @State eduLoginUrl: string = '';
  @State eduLoginConnectionId: string = '';
  // QR 扫码登录
  @State qrSessionId: string = '';
  @State qrScanToken: string = '';
  @State qrBrowserName: string = '';
  @State qrOsName: string = '';
  @State qrDeviceLabel: string = '';
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
  @State universities: UniversityItem[] = [];
  @State selectedUniversityId: string = '';
  @State communityPosts: CommunityPostItem[] = [];
  @State academicStatus: AcademicStatusItem = { status: 'unsupported', provider: 'unsupported' };
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
  @State showLogoutDialog: boolean = false;

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
      this.ingestService = new NotificationIngestService(this.createApiClient(), () => this.appState.getAccessToken());
      notificationSubscriberManager.init(this.ingestService);
    }
    this.loadLocalNotices();
    this.subscriberActive = false;
  }

  createApiClient(): ApiClient {
    const auth: ApiClientAuth = {
      refreshTokenProvider: () => this.appState.getRefreshToken(),
      onTokens: (tokens: AuthTokens) => this.appState.updateTokens(tokens),
      onSessionExpired: () => this.handleSessionExpired()
    };
    return new ApiClient(API_BASE_URL, () => this.appState.getAccessToken(), auth);
  }

  async handleSessionExpired(): Promise<void> {
    await this.appState.clearSession();
    this.signedIn = false;
    this.subscriberActive = false;
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
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

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
      const tokens: AuthTokens = await client.login(this.username.trim(), this.password);
      await this.appState.signIn(tokens);
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
    const client = this.createApiClient();
    try {
      const me = await client.request<MeResponse>(http.RequestMethod.GET, 'auth/me');
      const user = me?.user ?? {};
      this.selectedUniversityId = user.university_id ?? '';
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
      if (error instanceof ApiError && error.code === ApiErrorCode.SESSION_EXPIRED) {
        await this.signOut();
        toastError('登录已过期，请重新登录');
      }
    } finally {
      this.primaryLoading = false;
    }
  }

  async loadCourseContent(courseId: string): Promise<CourseContentBundle> {
    const client = this.createApiClient();
    const summary = await client.request<CourseContentSummary>(http.RequestMethod.GET, `courses/${courseId}/content-summary`);
    const page = await client.request<CourseContentPage>(http.RequestMethod.GET, `courses/${courseId}/content?page=1&page_size=500`);
    return { summary: summary, items: safeArray(page.items) };
  }

  async syncCourseContent(courseId: string): Promise<CourseContentBundle> {
    const client = this.createApiClient();
    await client.requestVoid(http.RequestMethod.POST, `courses/${courseId}/sync`);
    return this.loadCourseContent(courseId);
  }

  async cacheCourseContent(courseId: string, itemId: string): Promise<void> {
    const client = this.createApiClient();
    await client.requestBinary(`courses/${courseId}/resources/${itemId}/download`);
    toastError('资料已按需获取并缓存');
  }

  async toggleTask(task: TaskItem): Promise<void> {
    const client = this.createApiClient();
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
    const client = this.createApiClient();
    try {
      const request: ChatRequest = {
        message: message,
        session_id: 'harmony-session',
        stream: true
      };
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: ''
      };
      this.chatMessages = [...this.chatMessages, assistantMessage];
      let receivedChunk = false;
      let streamError = '';
      let completedAnswer = '';
      await client.streamSse('counselor/chat', request, (event: SseEvent) => {
        try {
          const payload = JSON.parse(event.data) as Record<string, string>;
          if (event.event === 'chunk' && payload.text) {
            receivedChunk = true;
            this.chatMessages = this.chatMessages.map((item: ChatMessage) => {
              return item.id === assistantMessage.id ? new ChatMessageModel(item.id, item.role, item.content + payload.text) : item;
            });
          } else if (event.event === 'done' && payload.answer) {
            completedAnswer = payload.answer;
          } else if (event.event === 'error') {
            streamError = payload.message ?? 'AI 服务生成失败';
          }
        } catch (_) {
          streamError = 'AI 服务返回格式异常';
        }
      });
      if (streamError.length > 0) throw new Error(streamError);
      if (!receivedChunk && completedAnswer.length > 0) {
        this.chatMessages = this.chatMessages.map((item: ChatMessage) => {
          return item.id === assistantMessage.id ? new ChatMessageModel(item.id, item.role, completedAnswer) : item;
        });
      }
      if (!receivedChunk && completedAnswer.length === 0) throw new Error('AI 流式响应为空');
    } catch (error) {
      const latest = this.chatMessages[this.chatMessages.length - 1];
      if (latest !== undefined && latest.role === 'assistant' && latest.content.length === 0) {
        this.chatMessages = this.chatMessages.map((item: ChatMessage) => {
          return item.id === latest.id ? new ChatMessageModel(item.id, item.role, '暂时无法连接校园知识库，请检查网络后重试。') : item;
        });
      } else {
        this.chatMessages = [...this.chatMessages, {
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content: '暂时无法连接校园知识库，请检查网络后重试。'
        }];
      }
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
    this.subscriberActive = false;
    toastError('普通 HarmonyOS 手机应用无系统级第三方通知订阅权限，请使用后端通知、学习通同步或手动粘贴。');
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
    const client = this.createApiClient();
    try {
      if (target === 'exams') {
        this.exams = safeArray<ExamItem>(await client.request<ExamItem[]>(http.RequestMethod.GET, 'student/exams'));
      } else if (target === 'classrooms') {
        const response = await client.request<ClassroomResponse>(http.RequestMethod.GET, 'student/classrooms');
        this.classrooms = safeArray<ClassroomAvailability>(response?.items);
      } else if (target === 'university') {
        const response = await client.request<PagedResponse<UniversityItem>>(http.RequestMethod.GET, 'universities?page=1&page_size=100');
        this.universities = safeArray<UniversityItem>(response.items);
      } else if (target === 'community') {
        const response = await client.request<PagedResponse<CommunityPostItem>>(http.RequestMethod.GET, 'community/posts?page=1&page_size=30');
        this.communityPosts = safeArray<CommunityPostItem>(response.items);
      } else if (target === 'academic') {
        this.academicStatus = await client.request<AcademicStatusItem>(http.RequestMethod.GET, 'academic/status');
      } else if (target === 'lostfound') {
        this.lostFoundItems = safeArray<LostFoundItem>(await client.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found'));
      } else if (target === 'focus') {
        const repository = new StudyRepository(client);
        this.studySessions = safeArray<StudySession>(await repository.listSessions());
        this.activeStudySession = await repository.activeSession();
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
      if (error instanceof ApiError && error.code === ApiErrorCode.SESSION_EXPIRED) {
        await this.signOut();
        toastError('登录已过期，请重新登录');
      }
    } finally {
      this.secondaryLoading = false;
    }
  }

  async selectUniversity(id: string): Promise<void> {
    this.secondarySubmitting = true;
    try {
      const client = this.createApiClient();
      const payload: UniversitySelectionRequest = { university_id: id };
      const response = await client.request<UniversitySelectionResponse>(http.RequestMethod.PUT, 'profile/university', payload);
      this.selectedUniversityId = response.university_id ?? id;
      toastError('大学已切换，校园范围数据已更新');
    } catch (error) {
      toastError('切换大学失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async publishCommunityPost(title: string, content: string, anonymous: boolean): Promise<void> {
    const payload: CommunityPostPayload = { title: title, content: content, category: 'campus', images: [], is_anonymous: anonymous };
    try {
      await this.createApiClient().request<CommunityPostItem>(http.RequestMethod.POST, 'community/posts', payload);
      await this.refreshSecondaryData('community');
      toastError('帖子已发布');
    } catch (_) { toastError('发布失败，请稍后重试'); }
  }

  async likeCommunityPost(id: string): Promise<void> {
    try {
      await this.createApiClient().request<CommunityPostItem>(http.RequestMethod.POST, `community/posts/${id}/like`);
      await this.refreshSecondaryData('community');
    } catch (_) { toastError('点赞失败，请重试'); }
  }

  async publishLostFound(kind: string, title: string, content: string, location: string, contact: string): Promise<void> {
    const payload: LostFoundPayload = { kind: kind, title: title, content: content, location: location, contact: contact };
    this.secondarySubmitting = true;
    try {
      const client = this.createApiClient();
      await client.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', payload);
      await this.refreshSecondaryData('lostfound');
      toastError('发布成功');
    } catch (error) {
      toastError('发布失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async startFocusSession(mode: FocusMode = 'focus'): Promise<void> {
    if (this.activeStudySession !== undefined) return;
    try {
      const repository = new StudyRepository(this.createApiClient());
      const goal: string = mode === 'short_break' ? '短暂休息' : mode === 'long_break' ? '长休息调整' : '完成一段专注学习';
      this.activeStudySession = await repository.start(mode, goal);
    } catch (error) {
      toastError('无法开始专注，请检查网络');
    }
  }

  async updateFocusSession(action: string): Promise<void> {
    if (this.activeStudySession === undefined) return;
    try {
      const repository = new StudyRepository(this.createApiClient());
      if (action === 'finish') {
        await repository.finish(this.activeStudySession.id, '鸿蒙端完成专注');
        this.activeStudySession = undefined;
      } else if (action === 'pause') {
        this.activeStudySession = await repository.pause(this.activeStudySession.id);
      } else {
        this.activeStudySession = await repository.resume(this.activeStudySession.id);
      }
      await this.refreshSecondaryData('focus');
    } catch (error) {
      toastError('操作失败，请重试');
    }
  }

  async saveExam(payload: ExamItem, id?: string): Promise<void> {
    this.secondarySubmitting = true;
    try {
      const client = this.createApiClient();
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
      const client = this.createApiClient();
      await client.requestVoid(http.RequestMethod.DELETE, `student/exams/${id}`);
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
    if (this.route === 'university') return '我的大学';
    if (this.route === 'community') return '校园社区';
    if (this.route === 'academic') return '教务系统';
    if (this.route === 'focus') return '专注自习';
    if (this.route === 'lostfound') return '失物招领';
    if (this.route === 'settings') return '设置';
    if (this.route === 'qr_scanner') return '扫一扫';
    if (this.route === 'qr_confirm') return '确认登录';
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
    } else if (this.route === 'university' || this.route === 'community' || this.route === 'academic') {
      V3CorePage({ route: this.route, darkMode: this.darkMode, loading: this.secondaryLoading, selectedUniversityId: this.selectedUniversityId, universities: this.universities, posts: this.communityPosts, academicStatus: this.academicStatus, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route), onSelectUniversity: (id: string) => this.selectUniversity(id), onPublish: (title: string, content: string, anonymous: boolean) => this.publishCommunityPost(title, content, anonymous), onLike: (id: string) => this.likeCommunityPost(id) })
    } else if (this.route === 'focus') {
      FocusPage({ sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onStart: (mode: FocusMode) => this.startFocusSession(mode), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: () => this.updateFocusSession('finish') })
    } else if (this.route === 'lostfound') {
      LostFoundPage({ items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onFilter: (kind: string) => this.refreshSecondaryData('lostfound'), onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact) })
    } else if (this.route === 'notifications') {
      NotificationsPage({ notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode, localNotices: this.localNotices, subscriberActive: this.subscriberActive, ingestService: this.ingestService, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('notifications'), onToggleSubscriber: () => this.toggleSubscriber(), onTaskSaved: () => this.refreshPrimaryData(), onLocalNoticesChanged: () => this.loadLocalNotices() })
    } else if (this.route === 'files' || this.route === 'activities' || this.route === 'favorites') {
      PersonalHubPage({ section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route) })
    } else if (this.route === 'settings') {
      SettingsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.route = '', onThemeChange: (value: boolean) => { if (value !== this.darkMode) this.toggleTheme(); }, onMotionChange: async (value: boolean) => { await this.appState.setReduceMotion(value); this.reduceMotion = value; }, onNavigate: (target: string) => this.navigateTo(target), onSignOut: () => this.showLogoutDialog = true })
    } else if (this.route === 'qr_scanner') {
      QrScannerPage({
        darkMode: this.darkMode,
        apiClient: this.createApiClient(),
        onBack: () => this.route = '',
        onScanned: (sessionId: string, scanToken: string, browserName: string, osName: string, deviceLabel: string) => {
          this.qrSessionId = sessionId;
          this.qrScanToken = scanToken;
          this.qrBrowserName = browserName;
          this.qrOsName = osName;
          this.qrDeviceLabel = deviceLabel;
          this.route = 'qr_confirm';
        }
      })
    } else if (this.route === 'qr_confirm') {
      QrConfirmPage({
        darkMode: this.darkMode,
        sessionId: this.qrSessionId,
        scanToken: this.qrScanToken,
        browserName: this.qrBrowserName,
        osName: this.qrOsName,
        deviceLabel: this.qrDeviceLabel,
        apiClient: this.createApiClient(),
        onBack: () => { this.route = 'profile'; },
        onSuccess: () => { this.route = 'profile'; }
      })
    } else if (this.route === 'account') {
      AccountPage({ darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.route = '', onSignOut: () => this.signOut() })
    } else if (this.route === 'edu_system') {
      EduSystemPage({
        darkMode: this.darkMode,
        universityId: this.selectedUniversityId,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        onBack: () => this.route = '',
        onNavigateToLogin: (loginUrl: string, connectionId: string) => {
          this.eduLoginUrl = loginUrl;
          this.eduLoginConnectionId = connectionId;
          this.route = 'edu_login';
        },
        onOpenSchedule: () => { this.route = 'edu_schedule'; }
      })
    } else if (this.route === 'edu_login') {
      EduLoginPage({
        darkMode: this.darkMode,
        loginUrl: this.eduLoginUrl,
        connectionId: this.eduLoginConnectionId,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        onBack: () => this.route = 'edu_system',
        onConnected: () => { this.route = 'edu_system'; }
      })
    } else if (this.route === 'edu_schedule') {
      EduSchedulePage({
        darkMode: this.darkMode,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        onBack: () => this.route = 'edu_system'
      })
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
    CoursesPage({
      courses: this.courses,
      loading: this.primaryLoading,
      darkMode: this.darkMode,
      onRefresh: () => this.refreshPrimaryData(),
      onLoadContent: (courseId: string) => this.loadCourseContent(courseId),
      onSyncContent: (courseId: string) => this.syncCourseContent(courseId),
      onCacheContent: (courseId: string, itemId: string) => this.cacheCourseContent(courseId, itemId)
    })
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
          Stack({ alignContent: Alignment.Top }) {
            this.SecondaryPage()
          }
          .width('100%')
          .height('100%')
          .transition(TransitionEffect.OPACITY
            .combine(TransitionEffect.translate({ x: 0, y: '100%' }))
            .animation({ duration: this.reduceMotion ? 0 : 320, curve: Curve.EaseOut }))
        }

        if (this.route.length === 0) {
          this.BottomNavigation()
        }

        if (this.showLogoutDialog) {
          Column() {
            Column() {
              Text('退出登录').fontColor(this.textColor()).fontSize(20).fontWeight(FontWeight.Bold)
              Text('将清除本机会话与登录凭证，并返回登录页。确定退出吗？').fontColor(this.textColor()).fontSize(14).margin({ top: 12 })
              Row() {
                Button('取消').width('48%').height(44).backgroundColor(this.surface()).fontColor(this.textColor()).onClick(() => this.showLogoutDialog = false)
                Button('退出').width('48%').height(44).backgroundColor(this.palette().danger).fontColor('#FFFFFF').onClick(() => {
                  this.showLogoutDialog = false;
                  this.signOut();
                })
              }.width('100%').margin({ top: 24 })
            }.width('85%').padding(24).backgroundColor(this.surface()).borderRadius(20).alignItems(HorizontalAlign.Start)
          }.width('100%').height('100%').backgroundColor('#80000000').justifyContent(FlexAlign.Center).onClick(() => this.showLogoutDialog = false)
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
