import { AppState } from '../core/AppState';
import { darkPalette, lightPalette } from '../ui/Theme';
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
import { ActivityItem, ChatMessage, ChatRequest, ChatResponse, ClassroomAvailability, ClassroomResponse, CourseItem, ExamItem, FavoriteItem, LostFoundItem, LostFoundPayload, MeResponse, NoticeItem, PagedResponse, PersonalFileItem, ServiceRequestItem, ServiceRequestPayload, StudySession, StudySessionCreate, StudySessionFinish, TaskItem } from '../data/Models';
import { http } from '@kit.NetworkKit';

const API_BASE_URL: string = 'http://127.0.0.1:8000/api/v1';

@Entry
@Component
struct Index {
  private appState: AppState = new AppState();
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
  @State personalFiles: PersonalFileItem[] = [];
  @State activities: ActivityItem[] = [];
  @State favorites: FavoriteItem[] = [];
  @State backendOnline: boolean = true;

  aboutToAppear(): void {
    this.appState.restore();
    this.signedIn = this.appState.sessionToken.length > 0;
    this.darkMode = this.appState.darkMode;
    this.reduceMotion = this.appState.reduceMotion;
    if (this.signedIn) {
      this.refreshPrimaryData();
    }
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
      this.appState.signIn(token);
      this.signedIn = true;
      this.loginError = '';
      await this.refreshPrimaryData();
    } catch (error) {
      this.loginError = '暂时无法登录，请检查账号、密码和网络后重试。';
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
      this.displayName = me.user.display_name ?? me.user.name ?? me.user.username ?? '林知夏';
      const detailParts: string[] = [];
      if (me.user.major !== undefined && me.user.major.length > 0) {
        detailParts.push(me.user.major);
      }
      if (me.user.grade !== undefined && me.user.grade.length > 0) {
        detailParts.push(`${me.user.grade}级`);
      }
      if (detailParts.length > 0) {
        this.profileDetail = detailParts.join(' · ');
      }
      const coursePage = await client.request<PagedResponse<CourseItem>>(http.RequestMethod.GET, 'courses?page=1&page_size=100');
      this.courses = coursePage.items;
      const taskPage = await client.request<PagedResponse<TaskItem>>(http.RequestMethod.GET, 'tasks?page=1&page_size=200');
      this.tasks = taskPage.items;
      const noticePage = await client.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=20');
      this.notices = noticePage.items;
      this.backendOnline = true;
    } catch (error) {
      // Keep the Android-equivalent local empty state when the backend becomes unavailable.
      this.backendOnline = false;
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

  signOut(): void {
    this.appState.signOut();
    this.signedIn = false;
    this.route = '';
    this.activeTab = 0;
  }

  toggleTheme(): void {
    this.appState.toggleTheme();
    this.darkMode = this.appState.darkMode;
  }

  navigateTo(target: string): void {
    if (target === 'courses') { this.route = ''; this.activeTab = 1; return; }
    if (target === 'tasks') { this.route = ''; this.activeTab = 2; return; }
    if (target === 'counselor') { this.route = ''; this.activeTab = 3; return; }
    if (target === 'profile') { this.route = ''; this.activeTab = 4; return; }
    this.route = target;
    this.refreshSecondaryData(target);
  }

  async refreshSecondaryData(target: string): Promise<void> {
    if (this.secondaryLoading || this.appState.sessionToken.length === 0) return;
    this.secondaryLoading = true;
    const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
    try {
      if (target === 'exams') {
        this.exams = await client.request<ExamItem[]>(http.RequestMethod.GET, 'student/exams');
      } else if (target === 'classrooms') {
        const response = await client.request<ClassroomResponse>(http.RequestMethod.GET, 'student/classrooms');
        this.classrooms = response.items;
      } else if (target === 'services') {
        this.serviceRequests = await client.request<ServiceRequestItem[]>(http.RequestMethod.GET, 'student/service-requests');
      } else if (target === 'lostfound') {
        this.lostFoundItems = await client.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found');
      } else if (target === 'focus') {
        this.studySessions = await client.request<StudySession[]>(http.RequestMethod.GET, 'study/sessions?page=1&page_size=20');
        this.activeStudySession = await client.request<StudySession | undefined>(http.RequestMethod.GET, 'study/sessions/active');
      } else if (target === 'notifications') {
        const page = await client.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=100');
        this.notices = page.items;
      } else if (target === 'files') {
        this.personalFiles = await client.request<PersonalFileItem[]>(http.RequestMethod.GET, 'personal-hub/files');
      } else if (target === 'activities') {
        const page = await client.request<PagedResponse<ActivityItem>>(http.RequestMethod.GET, 'activities?page=1&page_size=100');
        this.activities = page.items;
      } else if (target === 'favorites') {
        this.favorites = await client.request<FavoriteItem[]>(http.RequestMethod.GET, 'personal-hub/favorites');
      }
    } catch (error) {
      this.backendOnline = false;
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
    } catch (error) {
    } finally { this.secondarySubmitting = false; }
  }

  async publishLostFound(kind: string, title: string, content: string, location: string, contact: string): Promise<void> {
    const payload: LostFoundPayload = { kind: kind, title: title, content: content, location: location, contact: contact };
    this.secondarySubmitting = true;
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      await client.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', payload);
      await this.refreshSecondaryData('lostfound');
    } catch (error) {
    } finally { this.secondarySubmitting = false; }
  }

  async startFocusSession(): Promise<void> {
    if (this.activeStudySession !== undefined) return;
    const payload: StudySessionCreate = { goal: '完成一段专注学习' };
    try {
      const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
      this.activeStudySession = await client.request<StudySession>(http.RequestMethod.POST, 'study/sessions', payload);
    } catch (error) {
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
      onSubmit: () => {
        this.signInForPreview();
      },
      onInputChanged: () => {
        this.loginError = '';
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

  @Builder SecondaryPage() {
    if (this.route === 'exams') {
      Navigation() {
        ExamsPage({ exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('exams') })
      }
      .title('考试安排')
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_refresh'), '刷新', () => this.refreshSecondaryData('exams'))])
    } else if (this.route === 'classrooms') {
      Navigation() {
        ClassroomsPage({ classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onQuery: () => this.refreshSecondaryData('classrooms') })
      }
      .title('空教室查询')
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_search'), '查询', () => this.refreshSecondaryData('classrooms'))])
    } else if (this.route === 'services') {
      Navigation() {
        ServicesPage({ requests: this.serviceRequests, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('services'), onSubmit: (kind: string, title: string, content: string) => this.createServiceRequest(kind, title, content) })
      }
      .title('办事大厅')
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_refresh'), '刷新', () => this.refreshSecondaryData('services'))])
    } else if (this.route === 'focus') {
      Navigation() {
        FocusPage({ sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onStart: () => this.startFocusSession(), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: () => this.updateFocusSession('finish') })
      }
      .title('专注自习')
      .titleMode(NavigationTitleMode.Mini)
    } else if (this.route === 'lostfound') {
      Navigation() {
        LostFoundPage({ items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onFilter: (kind: string) => this.refreshSecondaryData('lostfound'), onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact) })
      }
      .title('失物招领')
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_refresh'), '刷新', () => this.refreshSecondaryData('lostfound'))])
    } else if (this.route === 'notifications') {
      Navigation() {
        NotificationsPage({ notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('notifications') })
      }
      .title('通知整理')
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_refresh'), '刷新', () => this.refreshSecondaryData('notifications'))])
    } else if (this.route === 'files' || this.route === 'activities' || this.route === 'favorites') {
      Navigation() {
        PersonalHubPage({ section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route) })
      }
      .title(`我的${this.route === 'files' ? '文件' : this.route === 'activities' ? '活动' : '收藏'}`)
      .titleMode(NavigationTitleMode.Mini)
      .toolbarConfiguration([this.ToolbarItem($r('app.media.ic_public_refresh'), '刷新', () => this.refreshSecondaryData(this.route))])
    } else if (this.route === 'settings') {
      Navigation() {
        SettingsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.route = '', onThemeChange: (value: boolean) => { if (value !== this.darkMode) this.toggleTheme(); }, onMotionChange: (value: boolean) => { this.appState.setReduceMotion(value); this.reduceMotion = value; }, onNavigate: (target: string) => this.navigateTo(target) })
      }
      .title('系统设置')
      .titleMode(NavigationTitleMode.Mini)
    } else if (this.route === 'account') {
      Navigation() {
        AccountPage({ darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.route = '', onSignOut: () => this.signOut() })
      }
      .title('账号与隐私')
      .titleMode(NavigationTitleMode.Mini)
    } else {
      Navigation() {
        Column({ space: 12 }) {
          SymbolGlyph($r('sys.symbol.info_circle')).fontSize(38).fontColor([this.primaryColor()])
          Text('面向大学生的校园事务智能陪伴助手。').fontColor(this.textColor()).fontSize(15).textAlign(TextAlign.Center)
          Text('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。').fontColor(this.mutedColor()).fontSize(12).textAlign(TextAlign.Center)
        }.width('100%').padding(28)
      }
      .title('校园服务')
      .titleMode(NavigationTitleMode.Mini)
    }
  }

  @Builder ToolbarItem(icon: Resource, text: string, action: () => void) {
    ToolbarItem() {
      Image(icon).width(24).height(24)
    }
    .activeIcon(icon)
    .actionButton(() => {
      action()
    })
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
      activeTab: this.activeTab,
      darkMode: this.darkMode,
      pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length,
      onNavigate: (index: number) => {
        this.route = '';
        this.activeTab = index;
      }
    })
  }

  build() {
    if (this.signedIn) {
      Stack({ alignContent: Alignment.Bottom }) {
        Tabs({ barPosition: BarPosition.Bottom, index: this.activeTab }) {
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
        .animationDuration(280)
        .scrollable(false)
        .width('100%')
        .height('100%')
        .backgroundColor(this.pageBackground())
        .onChange((index: number) => {
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
      .backgroundColor(this.pageBackground())
      .transition(TransitionEffect.OPACITY)
    } else {
      this.LoginPage()
    }
  }
}
