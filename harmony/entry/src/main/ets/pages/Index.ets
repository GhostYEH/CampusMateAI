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
import { CourseDetailPage } from '../features/courses/CourseDetailPage';
import { TasksPage } from '../features/tasks/TasksPage';
import { TaskDetailPage } from '../features/tasks/TaskDetailPage';
import { ExamDetailPage } from '../features/exams/ExamDetailPage';
import { ExamFormPage } from '../features/exams/ExamFormPage';
import { CounselorPage } from '../features/counselor/CounselorPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { QrScannerPage } from '../features/profile/QrScannerPage';
import { QrConfirmPage } from '../features/profile/QrConfirmPage';
import { ExamsPage } from '../features/exams/ExamsPage';
import { ClassroomsPage } from '../features/classrooms/ClassroomsPage';
import { V3CorePage } from '../features/v3/V3CorePage';
import { FocusPage, FocusSessionMode } from '../features/focus/FocusPage';
import { FocusSessionPage } from '../features/focus/FocusSessionPage';
import { FocusSummaryPage } from '../features/focus/FocusSummaryPage';
import { FocusPlanPage } from '../features/focus/FocusPlanPage';
import { FocusSessionAction, FocusSessionActionGate } from '../features/focus/FocusPresentationState';
import { LostFoundPage } from '../features/lostfound/LostFoundPage';
import { NotificationsPage } from '../features/notifications/NotificationsPage';
import { NotificationSourceSettingsPage } from '../features/notifications/NotificationSourceSettingsPage';
import { ChaoxingPage } from '../features/notifications/ChaoxingPage';
import { PersonalHubPage } from '../features/profile/PersonalHubPage';
import { SettingsPage } from '../features/profile/SettingsPage';
import { AccountPage } from '../features/profile/AccountPage';
import { EduSystemPage } from '../features/profile/EduSystemPage';
import { EduLoginPage } from '../features/edu/EduLoginPage';
import { EduSchedulePage } from '../features/edu/EduSchedulePage';
import { EduScheduleDetailPage } from '../features/edu/EduScheduleDetailPage';
import { AcademicStatusItem, ChatMessage, ChatMessageModel, ChatRequest, ClassroomAvailability, ClassroomResponse, CommunityComment, CommunityCommentCreatePayload, CommunityPostExtra, CommunityPostItem, CommunityPostPayload, CommunityPostUpdatePayload, CommunityReportCreatePayload, CourseContentBundle, CourseContentPage, CourseContentSummary, CourseItem, ExamItem, FavoriteItem, FocusMode, FocusPlan, HomeBannerFeed, HomeBannerItem, LocalCapturedNotice, LostFoundItem, LostFoundPayload, MeResponse, NoticeItem, PagedResponse, PersonalFileItem, StudyBehaviorSummary, StudySession, TaskItem, ExtractResult, UniversityItem, UniversitySelectionRequest, UniversitySelectionResponse, UploadImageResult } from '../data/Models';
import { NotificationIngestService } from '../data/notification/NotificationIngestService';
import { NotificationSource } from '../data/notification/NotificationSource';
import { ChaoxingAccountStatus, ChaoxingStatusMapper } from '../data/chaoxing/ChaoxingAccount';
import { ChaoxingRepository } from '../data/chaoxing/ChaoxingRepository';
import { StudyRepository } from '../repository/StudyRepository';
import { FocusPlanProgress, FocusPlanRepository } from '../repository/FocusPlanRepository';
import { FocusAiRepository } from '../repository/FocusAiRepository';
import { FocusRealtimeVoiceRepository } from '../repository/FocusRealtimeVoiceRepository';
import { FocusRealtimeVoiceClient } from '../service/FocusRealtimeVoiceClient';
import { FocusVoiceEventReducer, FocusVoiceState } from '../features/focus/FocusVoiceState';
import { http } from '@kit.NetworkKit';
import { promptAction, window } from '@kit.ArkUI';
import picker from '@ohos.file.picker';
import {
  ExpressionCameraActivationPolicy,
  ExpressionRecognitionService
} from '../service/ExpressionRecognitionService';
import { withExpressionSignal } from '../data/ExpressionSignalChatBridge';
import { AppRoute, AppRouteRegistry } from '../navigation/AppRoute';
import { EduScheduleItemDto } from '../data/ApiClient';
import { abilityAccessCtrl, common, PermissionRequestResult } from '@kit.AbilityKit';
import {
  FocusAssistProvider,
  FocusAssistSignal,
  toStudyBehaviorSummary,
  UnavailableFocusAssistProvider
} from '../service/FocusAssistProvider';
import { MindSporeBehaviorProvider } from '../service/MindSporeBehaviorProvider';
import { FocusCameraPipeline } from '../service/FocusCameraPipeline';
import {
  FocusCameraActivationPolicy,
  FocusCameraLifecycleAction,
  FocusCameraLifecycleEvent,
  FocusCameraLifecyclePolicy,
  FocusCameraSignalPresentation,
  FocusSessionModeRecovery
} from '../service/FocusCameraContract';
import { MindSporeExpressionProvider } from '../service/MindSporeExpressionProvider';
import { ExpressionGreetingPolicy } from '../service/ExpressionGreetingPolicy';
import { PreferencesUtil } from '../util/PreferencesUtil';
import { ForegroundRefreshGate } from '../core/ForegroundRefreshGate';
import { AmbientMotionField } from '../ui/AmbientMotionField';

const API_BASE_URL: string = ApiConfig.API_BASE_URL;
const HOME_BANNER_CACHE_KEY: string = 'homeBannersV1';

function toastError(message: string): void {
  try { promptAction.showToast({ message: message, duration: 2200 }); } catch { /* ignore toast failure */ }
}

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function restoredFocusSessionMode(session: StudySession | undefined): FocusSessionMode {
  return FocusSessionModeRecovery.normalize(session?.experience_mode) as FocusSessionMode;
}

@Entry
@Component
struct Index {
  private appState: AppState = new AppState();
  private tabsController: TabsController = new TabsController();
  private pageStack: NavPathStack = new NavPathStack();
  private requestedTab: number = -1;
  private ingestService: NotificationIngestService | null = null;
  private chaoxingRepository: ChaoxingRepository | null = null;
  private expressionService: ExpressionRecognitionService = new ExpressionRecognitionService();
  private focusAssistProvider: FocusAssistProvider = new UnavailableFocusAssistProvider();
  private focusCameraPipeline: FocusCameraPipeline | null = null;
  private focusVoiceClient: FocusRealtimeVoiceClient | null = null;
  private focusVoiceSessionId: string = '';
  private expressionPollingTimer: number = -1;
  private foregroundRefreshGate: ForegroundRefreshGate = new ForegroundRefreshGate(30_000);
  private focusSessionActionGate: FocusSessionActionGate = new FocusSessionActionGate();
  private expressionConsentDialogOpen: boolean = false;
  @State signedIn: boolean = false;
  @State darkMode: boolean = false;
  @State reduceMotion: boolean = false;
  @State activeTab: number = 0;
  @State eduLoginUrl: string = '';
  @State eduLoginConnectionId: string = '';
  @State eduLoginAllowedOrigins: string[] = [];
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
  @State homeBanners: HomeBannerItem[] = [];
  @State chatMessages: ChatMessage[] = [];
  @State chatInput: string = '';
  @State chatSending: boolean = false;
  @State digitalHumanSpeechText: string = '';
  @State digitalHumanSpeechRequestId: number = 0;
  @State displayName: string = '林知夏';
  @State profileDetail: string = '计算机科学与技术 · 大三';
  @State secondaryLoading: boolean = false;
  @State secondarySubmitting: boolean = false;
  @State exams: ExamItem[] = [];
  @State classrooms: ClassroomAvailability[] = [];
  @State universities: UniversityItem[] = [];
  @State selectedUniversityId: string = '';
  @State selectedUniversityName: string = '';
  @State communityPosts: CommunityPostItem[] = [];
  @State communityHotPosts: CommunityPostItem[] = [];
  @State communityDetailPost: CommunityPostItem | null = null;
  @State communityComments: CommunityComment[] = [];
  @State communityDetailLoading: boolean = false;
  @State communityDetailId: string = '';
  @State communityPostImages: string[] = [];
  @State communityEditPost: CommunityPostItem | null = null;
  @State academicStatus: AcademicStatusItem = { status: 'unsupported', provider: 'unsupported' };
  @State lostFoundItems: LostFoundItem[] = [];
  @State studySessions: StudySession[] = [];
  @State activeStudySession?: StudySession = undefined;
  @State notices: NoticeItem[] = [];
  @State localNotices: LocalCapturedNotice[] = [];
  @State chaoxingStatus: ChaoxingAccountStatus = ChaoxingStatusMapper.unavailable();
  @State personalFiles: PersonalFileItem[] = [];
  @State favorites: FavoriteItem[] = [];
  @State backendOnline: boolean = true;
  @State rememberUsername: boolean = false;
  @State statusBarHeight: number = 0;
  @State showLogoutDialog: boolean = false;
  @State expressionAvailable: boolean = false;
  @State expressionDetail: string = '';
  @State expressionGreeting: string = ExpressionGreetingPolicy.greeting(undefined);
  @State courseDetailId: string = '';
  @State taskDetailId: string = '';
  @State examDetailId: string = '';
  @State examFormId: string = '';
  @State lostFoundDetailId: string = '';
  @State notificationDetailId: string = '';
  @State notificationSettingsSource: NotificationSource | null = null;
  @State notificationManualSeed: string = '';
  @State scheduleDetailItem?: EduScheduleItemDto = undefined;
  @State focusAssistDetail: string = '正在准备 V3.4 本地模型';
  @State focusAssistLabel: string = '';
  @State focusAssistConfidence: number = 0;
  @State focusBehaviorReminder: string = '';
  @State focusPlannedSeconds: number = 1500;
  @State focusSessionMode: FocusSessionMode = 'QUIET';
  @State focusStartedAt: number = 0;
  @State focusChatMessages: ChatMessage[] = [];
  @State focusChatInput: string = '';
  @State focusChatSending: boolean = false;
  @State focusSummarySeconds: number = 0;
  @State focusSummaryInteractions: number = 0;
  @State focusSummaryObservation: string = '';
  @State focusPlan?: FocusPlan = undefined;
  @State focusPlanLoading: boolean = false;
  @State focusPlanError: string = '';
  @State focusVoiceState: FocusVoiceState = FocusVoiceEventReducer.initial();

  async aboutToAppear(): Promise<void> {
    this.foregroundRefreshGate.setVisible(true);
    await this.appState.restore();
    this.signedIn = this.appState.sessionToken.length > 0;
    this.darkMode = this.appState.darkMode;
    this.reduceMotion = this.appState.reduceMotion;
    this.rememberUsername = this.appState.rememberUsername;
    this.selectedUniversityId = this.appState.universityId;
    this.selectedUniversityName = this.appState.universityName;
    this.applySystemBarStyle();
    try {
      const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
      this.expressionService = new ExpressionRecognitionService(new MindSporeExpressionProvider(context));
    } catch (_) {
      this.expressionService = new ExpressionRecognitionService();
    }
    this.initializeFocusAssist();
    if (this.rememberUsername && this.appState.savedUsername.length > 0) {
      this.username = this.appState.savedUsername;
    }
    if (this.signedIn) {
      this.initNotificationService();
      await this.loadCachedHomeBanners();
      this.refreshPrimaryData();
    }
  }

  async initializeFocusAssist(): Promise<void> {
    try {
      const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
      this.focusAssistProvider = new MindSporeBehaviorProvider(context.resourceManager);
      this.focusCameraPipeline = new FocusCameraPipeline(context, this.focusAssistProvider,
        () => this.refreshFocusAssistState());
    } catch (_) {
      this.focusAssistProvider = new UnavailableFocusAssistProvider();
      this.focusCameraPipeline = null;
    }
    this.refreshFocusAssistState();
  }

  refreshFocusAssistState(): void {
    const signal: FocusAssistSignal | undefined = this.focusAssistProvider.latestSignal();
    const cameraState: string = this.focusCameraPipeline?.state() ?? '';
    const shouldPresent: boolean = signal !== undefined &&
      FocusCameraSignalPresentation.shouldPresent(signal.isStable, cameraState);
    this.focusAssistDetail = this.focusCameraPipeline?.detail() ?? this.focusAssistProvider.detail();
    this.focusAssistLabel = signal === undefined ? '' :
      FocusCameraSignalPresentation.label(signal.label, shouldPresent);
    this.focusAssistConfidence = signal === undefined ? 0 :
      FocusCameraSignalPresentation.confidence(signal.confidence, shouldPresent);
    this.focusBehaviorReminder = shouldPresent ? this.focusAssistProvider.currentReminder() : '';
  }

  async applyFocusCameraLifecycle(event: string, mode: FocusMode): Promise<void> {
    if (FocusCameraLifecyclePolicy.shouldResetSummary(event, mode)) {
      this.focusAssistProvider.resetSessionSummary();
      this.focusCameraPipeline?.resetSession();
    }
    const action: string = FocusCameraLifecyclePolicy.action(event, mode, this.focusSessionMode);
    if (action === FocusCameraLifecycleAction.START) {
      await this.startFocusCamera(mode);
    } else {
      await this.stopFocusCamera();
    }
  }

  async startFocusCamera(mode: FocusMode): Promise<void> {
    if (!FocusCameraActivationPolicy.shouldRun(mode, this.focusSessionMode)) {
      await this.stopFocusCamera();
      return;
    }
    try {
      await this.focusCameraPipeline?.start();
    } catch (_) {
      // Camera/model failure must not roll back the already-created backend session.
    }
    this.refreshFocusAssistState();
  }

  async stopFocusCamera(): Promise<void> {
    try {
      await this.focusCameraPipeline?.stop();
    } catch (_) {
      // Lifecycle cleanup remains best-effort when a device camera driver fails.
    }
    this.refreshFocusAssistState();
  }

  async onPageShow(): Promise<void> {
    this.foregroundRefreshGate.setVisible(true);
    if (this.signedIn && this.appState.sessionToken.length > 0) {
      this.refreshUniversityFromServer();
    }
    if (this.activeTab === 3) this.syncExpressionForTab();
    const session: StudySession | undefined = this.activeStudySession;
    if (session !== undefined &&
      FocusCameraLifecyclePolicy.shouldResumeOnForeground(
        session.status, session.mode, this.focusSessionMode)) {
      await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.RESUME, session.mode);
    }
  }

  onPageHide(): void {
    this.foregroundRefreshGate.setVisible(false);
    this.stopExpressionRecognition();
    this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.HIDE,
      this.activeStudySession?.mode ?? 'focus');
  }

  aboutToDisappear(): void {
    this.foregroundRefreshGate.setVisible(false);
    this.stopExpressionRecognition();
    this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.LEAVE,
      this.activeStudySession?.mode ?? 'focus');
  }

  async refreshUniversityFromServer(): Promise<void> {
    if (this.appState.sessionToken.length === 0) return;
    if (!this.foregroundRefreshGate.tryStart(Date.now())) return;
    try {
      const client = this.createApiClient();
      const me = await client.request<MeResponse>(http.RequestMethod.GET, 'auth/me');
      const user = me?.user ?? {};
      const newId: string = user.university_id ?? '';
      const newName: string = user.university_name ?? '';
      if (newId !== this.selectedUniversityId || newName !== this.selectedUniversityName) {
        this.selectedUniversityId = newId;
        this.selectedUniversityName = newName;
        await this.appState.saveUniversity(newId, newName);
        this.communityPosts = [];
        this.communityHotPosts = [];
        this.lostFoundItems = [];
      }
    } catch (_) { /* silent refresh, ignore errors */ }
    finally { this.foregroundRefreshGate.finish(); }
  }

  initNotificationService(): void {
    if (this.ingestService === null) {
      this.ingestService = new NotificationIngestService(this.createApiClient(), () => this.appState.getAccessToken());
    }
    if (this.chaoxingRepository === null) this.chaoxingRepository = new ChaoxingRepository(this.createApiClient());
    this.loadLocalNotices();
  }

  async refreshChaoxingStatus(): Promise<void> {
    if (this.chaoxingRepository === null) return;
    try {
      this.chaoxingStatus = await this.chaoxingRepository.getStatus();
    } catch (_) {
      this.chaoxingStatus = ChaoxingStatusMapper.unavailable();
    }
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
    await this.stopExpressionRecognition();
    await this.stopFocusCamera();
    await this.appState.clearSession();
    this.clearRoutes();
    this.signedIn = false;
    this.chaoxingRepository = null;
    this.chaoxingStatus = ChaoxingStatusMapper.unavailable();
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
          isStatusBarLightIcon: this.darkMode,
          navigationBarColor: '#00000000',
          isNavigationBarLightIcon: this.darkMode,
          enableNavigationBarAnimation: true
        }).catch(() => {});
        try {
          const avoidArea = win.getWindowAvoidArea(window.AvoidAreaType.TYPE_SYSTEM);
          this.statusBarHeight = px2vp(avoidArea.topRect.height);
        } catch { /* ignore */ }
      }).catch(() => {});
    } catch { /* ignore */ }
  }

  surface(): string { return this.palette().glass.surface; }
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
      // ArkTS promises begin immediately, so independent startup requests share
      // one network window while retaining explicit response types.
      const bannerPromise: Promise<void> = this.refreshHomeBanners(client);
      const mePromise: Promise<MeResponse> = client.request<MeResponse>(http.RequestMethod.GET, 'auth/me');
      const coursesPromise: Promise<PagedResponse<CourseItem>> = client.request<PagedResponse<CourseItem>>(
        http.RequestMethod.GET, 'courses?page=1&page_size=100'
      );
      const tasksPromise: Promise<PagedResponse<TaskItem>> = client.request<PagedResponse<TaskItem>>(
        http.RequestMethod.GET, 'tasks?page=1&page_size=200'
      );
      const noticesPromise: Promise<PagedResponse<NoticeItem>> = client.request<PagedResponse<NoticeItem>>(
        http.RequestMethod.GET, 'notices?page=1&page_size=20'
      );

      await bannerPromise;
      const me: MeResponse = await mePromise;
      const user = me?.user ?? {};
      const newUniversityId = user.university_id ?? '';
      const newUniversityName = user.university_name ?? '';
      if (newUniversityId !== this.selectedUniversityId || newUniversityName !== this.selectedUniversityName) {
        this.selectedUniversityId = newUniversityId;
        this.selectedUniversityName = newUniversityName;
        await this.appState.saveUniversity(newUniversityId, newUniversityName);
      }
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
      const coursePage: PagedResponse<CourseItem> = await coursesPromise;
      this.courses = safeArray<CourseItem>(coursePage?.items);
      const taskPage: PagedResponse<TaskItem> = await tasksPromise;
      this.tasks = safeArray<TaskItem>(taskPage?.items);
      const noticePage: PagedResponse<NoticeItem> = await noticesPromise;
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

  async loadCachedHomeBanners(): Promise<void> {
    const raw: string = await PreferencesUtil.getString(HOME_BANNER_CACHE_KEY, '');
    if (raw.length === 0) return;
    try {
      const cached = JSON.parse(raw) as HomeBannerItem[];
      if (Array.isArray(cached)) this.homeBanners = cached;
    } catch (_) { /* ignore stale cache */ }
  }

  resolveBannerUrl(url: string): string {
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const marker: string = '/api/v1';
    const markerIndex: number = API_BASE_URL.indexOf(marker);
    const origin: string = markerIndex >= 0 ? API_BASE_URL.substring(0, markerIndex) : API_BASE_URL.replace(/\/$/, '');
    return url.startsWith('/') ? `${origin}${url}` : `${origin}/${url}`;
  }

  async refreshHomeBanners(client: ApiClient): Promise<void> {
    try {
      const feed = await client.request<HomeBannerFeed>(http.RequestMethod.GET, 'home-banners');
      const items: HomeBannerItem[] = safeArray<HomeBannerItem>(feed?.items).map((item: HomeBannerItem): HomeBannerItem => {
        return {
          id: item.id,
          eyebrow: item.eyebrow,
          title: item.title,
          subtitle: item.subtitle,
          cta_label: item.cta_label,
          image_url: this.resolveBannerUrl(item.image_url),
          action_key: item.action_key,
          theme_key: item.theme_key,
          sort_order: item.sort_order,
          status: item.status,
          starts_at: item.starts_at,
          ends_at: item.ends_at,
          created_at: item.created_at,
          updated_at: item.updated_at
        };
      });
      this.homeBanners = items;
      await PreferencesUtil.putString(HOME_BANNER_CACHE_KEY, JSON.stringify(items));
    } catch (_) { /* retain cached banners */ }
  }

  async loadCourseContent(courseId: string): Promise<CourseContentBundle> {
    const client = this.createApiClient();
    const summaryPromise: Promise<CourseContentSummary> = client.request<CourseContentSummary>(
      http.RequestMethod.GET, `courses/${courseId}/content-summary`
    );
    const pagePromise: Promise<CourseContentPage> = client.request<CourseContentPage>(
      http.RequestMethod.GET, `courses/${courseId}/content?page=1&page_size=500`
    );
    const summary: CourseContentSummary = await summaryPromise;
    const page: CourseContentPage = await pagePromise;
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
      const baseRequest: ChatRequest = {
        message: message,
        session_id: 'harmony-session',
        stream: true
      };
      const request: ChatRequest = withExpressionSignal(baseRequest, this.expressionService.latestStableSignal());
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
      const finalAssistant = this.chatMessages.find((item: ChatMessage) => item.id === assistantMessage.id);
      if (finalAssistant !== undefined && finalAssistant.content.trim().length > 0) {
        this.digitalHumanSpeechText = finalAssistant.content;
        this.digitalHumanSpeechRequestId += 1;
      }
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
    await this.stopExpressionRecognition();
    await this.stopFocusCamera();
    this.chaoxingRepository = null;
    this.chaoxingStatus = ChaoxingStatusMapper.unavailable();
    await this.appState.signOut();
    this.signedIn = false;
    this.clearRoutes();
    this.activeTab = 0;
    this.password = '';
    this.localNotices = [];
    this.foregroundRefreshGate.reset();
    if (!this.rememberUsername) {
      this.username = '';
    }
  }

  async startExpressionRecognition(): Promise<void> {
    try {
      await this.expressionService.start();
      this.expressionAvailable = this.expressionService.available();
      this.expressionDetail = this.expressionService.statusDetail();
    } catch (_) {
      this.expressionAvailable = false;
      this.expressionDetail = '情绪识别初始化失败，聊天不会上传相机画面';
    }
  }

  async stopExpressionRecognition(): Promise<void> {
    if (this.expressionPollingTimer >= 0) {
      clearInterval(this.expressionPollingTimer);
      this.expressionPollingTimer = -1;
    }
    await this.expressionService.stop();
    this.expressionAvailable = false;
    this.expressionDetail = '情绪识别已停止；不会上传或保存相机画面';
    this.expressionGreeting = ExpressionGreetingPolicy.greeting(undefined);
  }

  async requestExpressionPermissionAndStart(): Promise<void> {
    if (!ExpressionCameraActivationPolicy.shouldRun(
      this.appState.emotionAssistanceEnabled, this.signedIn,
      this.foregroundRefreshGate.isVisible(), this.activeTab)) return;
    try {
      const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
      const result: PermissionRequestResult = await abilityAccessCtrl.createAtManager()
        .requestPermissionsFromUser(context, ['ohos.permission.CAMERA']);
      if (result.authResults.length === 0 || result.authResults[0] !== 0) {
        this.expressionAvailable = false;
        this.expressionDetail = '需要相机权限才能在本机识别表情';
        return;
      }
      if (!ExpressionCameraActivationPolicy.shouldRun(
        this.appState.emotionAssistanceEnabled, this.signedIn,
        this.foregroundRefreshGate.isVisible(), this.activeTab)) return;
      await this.startExpressionRecognition();
      if (!ExpressionCameraActivationPolicy.shouldRun(
        this.appState.emotionAssistanceEnabled, this.signedIn,
        this.foregroundRefreshGate.isVisible(), this.activeTab)) {
        await this.stopExpressionRecognition();
        return;
      }
      if (this.expressionPollingTimer < 0) {
        this.expressionPollingTimer = setInterval(() => this.refreshExpressionState(), 1000);
      }
    } catch (_) {
      this.expressionAvailable = false;
      this.expressionDetail = '相机权限或本地模型不可用，聊天不会附带表情信息';
    }
  }

  refreshExpressionState(): void {
    this.expressionAvailable = this.expressionService.available();
    this.expressionDetail = this.expressionService.statusDetail();
    this.expressionGreeting = ExpressionGreetingPolicy.greeting(this.expressionService.latestStableSignal());
  }

  syncExpressionForTab(forceConsent: boolean = false): void {
    if (!this.foregroundRefreshGate.isVisible() || !this.signedIn || this.activeTab !== 3) {
      this.stopExpressionRecognition();
      return;
    }
    if (this.appState.emotionAssistanceEnabled) {
      this.requestExpressionPermissionAndStart();
      return;
    }
    if (this.appState.emotionAssistanceDecisionMade && !forceConsent) {
      this.expressionDetail = '情绪陪伴未启用；聊天不会获取或发送表情信息';
      return;
    }
    if (this.expressionConsentDialogOpen) return;
    this.expressionConsentDialogOpen = true;
    promptAction.showDialog({
      title: '启用本地情绪陪伴？',
      message: '仅在 CPM 页面前台使用相机识别表情。画面只在本机处理，不上传、不保存；只有通过高精度阈值且连续稳定的表情标签会随提问发送给 AI。',
      buttons: [{ text: '暂不启用', color: '#6b7280' }, { text: '同意并启用', color: '#5265E8' }]
    }).then(async (result: promptAction.ShowDialogSuccessResponse) => {
      const enabled: boolean = result.index === 1;
      await this.appState.setEmotionAssistance(enabled);
      if (enabled) await this.requestExpressionPermissionAndStart();
      else this.expressionDetail = '情绪陪伴未启用；聊天不会获取或发送表情信息';
    }).catch(() => {}).finally(() => { this.expressionConsentDialogOpen = false; });
  }

  async toggleTheme(): Promise<void> {
    await this.appState.toggleTheme();
    this.darkMode = this.appState.darkMode;
    this.applySystemBarStyle();
  }

  navigateTo(target: string): void {
    const tabIndex: number = AppRouteRegistry.tabIndex(target);
    if (tabIndex >= 0) {
      this.selectTab(tabIndex);
      return;
    }
    this.pushRoute(target);
  }

  openCourseDetail(course: CourseItem): void {
    this.courseDetailId = course.id;
    this.pushRoute(AppRoute.COURSE_DETAIL);
  }

  openTaskDetail(task: TaskItem): void {
    this.taskDetailId = task.id;
    this.pushRoute(AppRoute.TASK_DETAIL);
  }

  openExamDetail(exam: ExamItem): void {
    this.examDetailId = exam.id;
    this.pushRoute(AppRoute.EXAM_DETAIL);
  }

  openExamForm(exam?: ExamItem): void {
    this.examFormId = exam?.id ?? '';
    this.pushRoute(AppRoute.EXAM_FORM);
  }

  openLostFoundDetail(item: LostFoundItem): void {
    this.lostFoundDetailId = item.id;
    this.pushRoute(AppRoute.LOST_FOUND_DETAIL);
  }

  openNotificationDetail(id: string): void {
    this.notificationDetailId = id;
    this.pushRoute(AppRoute.NOTIFICATION_DETAIL);
  }

  openNotificationSourceSettings(source: NotificationSource): void {
    this.notificationSettingsSource = source;
    this.pushRoute(AppRoute.NOTIFICATION_SOURCE_SETTINGS);
  }

  openScheduleDetail(item: EduScheduleItemDto): void {
    this.scheduleDetailItem = item;
    this.pushRoute(AppRoute.EDU_SCHEDULE_DETAIL);
  }

  selectTab(index: number): void {
    this.clearRoutes();
    // Tabs.onChange is delivered after controller navigation on this SDK and
    // can briefly report the previous index. Ignore that stale callback while
    // the controller completes the requested page transition.
    this.requestedTab = index;
    this.activeTab = index;
    this.tabsController.changeIndex(index);
    this.syncExpressionForTab();
  }

  pushRoute(target: string): void {
    if (!AppRouteRegistry.isSecondary(target)) {
      toastError('该校园服务暂不可用');
      return;
    }
    const parent: string = AppRouteRegistry.parent(target);
    const routeNames: string[] = this.pageStack.getAllPathName();
    const current: string = routeNames.length > 0 ? routeNames[routeNames.length - 1] : '';
    const parentTab: number = AppRouteRegistry.tabIndex(parent);
    if (parentTab >= 0) {
      if (this.activeTab !== parentTab) {
        this.selectTab(parentTab);
      }
    } else if (parent.length > 0 && routeNames.indexOf(parent) < 0) {
      this.pageStack.pushPath({ name: parent }, !this.reduceMotion);
      if (AppRouteRegistry.loadsOnOpen(parent)) {
        this.refreshSecondaryData(parent);
      }
    }
    this.pageStack.pushPath({ name: target }, !this.reduceMotion);
    if (AppRouteRegistry.loadsOnOpen(target)) {
      this.refreshSecondaryData(target);
    }
  }

  popRoute(): void {
    this.pageStack.pop(!this.reduceMotion);
  }

  clearRoutes(): void {
    if (this.pageStack.size() > 0) {
      this.pageStack.clear(!this.reduceMotion);
    }
    this.courseDetailId = '';
    this.taskDetailId = '';
    this.examDetailId = '';
    this.examFormId = '';
    this.lostFoundDetailId = '';
    this.notificationDetailId = '';
    this.notificationSettingsSource = null;
    this.scheduleDetailItem = undefined;
  }

  async refreshSecondaryData(target: string): Promise<void> {
    if (target === AppRoute.NOTIFICATIONS) {
      await this.loadLocalNotices();
      await this.refreshChaoxingStatus();
      return;
    }
    if (target === AppRoute.CHAOXING) {
      await this.refreshChaoxingStatus();
      return;
    }
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
        const all: UniversityItem[] = [];
        let page: number = 1;
        let total: number = 0;
        do {
          const response = await client.request<PagedResponse<UniversityItem>>(http.RequestMethod.GET, `universities?page=${page}&page_size=100`);
          const items: UniversityItem[] = safeArray<UniversityItem>(response.items);
          if (items.length === 0) break;
          all.push(...items);
          total = response.total ?? all.length;
          page++;
        } while (all.length < total);
        this.universities = all;
      } else if (target === 'community') {
        const response = await client.request<PagedResponse<CommunityPostItem>>(http.RequestMethod.GET, 'community/posts?page=1&page_size=30');
        this.communityPosts = safeArray<CommunityPostItem>(response.items);
        try {
          const hot = await client.request<PagedResponse<CommunityPostItem>>(http.RequestMethod.GET, 'community/posts?sort=hot&page=1&page_size=30');
          this.communityHotPosts = safeArray<CommunityPostItem>(hot.items);
        } catch (_) { this.communityHotPosts = []; }
      } else if (target === 'academic') {
        this.academicStatus = await client.request<AcademicStatusItem>(http.RequestMethod.GET, 'academic/status');
      } else if (target === 'lostfound') {
        this.lostFoundItems = safeArray<LostFoundItem>(await client.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found'));
      } else if (target === 'focus') {
        const repository = new StudyRepository(client);
        this.studySessions = safeArray<StudySession>(await repository.listSessions());
        this.activeStudySession = await repository.activeSession();
        this.focusSessionMode = restoredFocusSessionMode(this.activeStudySession);
        if (this.activeStudySession !== undefined) {
          this.focusPlannedSeconds = this.activeStudySession.planned_duration_seconds ?? this.focusPlannedSeconds;
        }
      } else if (target === 'files') {
        this.personalFiles = safeArray<PersonalFileItem>(await client.request<PersonalFileItem[]>(http.RequestMethod.GET, 'personal-hub/files'));
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
      const newId: string = response.university_id ?? id;
      const newName: string = response.university?.name ?? '';
      this.selectedUniversityId = newId;
      this.selectedUniversityName = newName;
      await this.appState.saveUniversity(newId, newName);
      this.communityPosts = [];
      this.communityHotPosts = [];
      this.lostFoundItems = [];
      this.academicStatus = { status: 'unsupported', provider: 'unsupported' };
      toastError('大学已切换，校园范围数据已更新');
    } catch (error) {
      toastError('切换大学失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async publishCommunityPost(title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra): Promise<void> {
    const payload: CommunityPostPayload = { title: title, content: content, category: category, images: this.communityPostImages, is_anonymous: anonymous, extra: extra };
    try {
      await this.createApiClient().request<CommunityPostItem>(http.RequestMethod.POST, 'community/posts', payload);
      this.communityPostImages = [];
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

  async openCommunityDetail(id: string): Promise<void> {
    this.communityDetailId = id;
    this.pushRoute(AppRoute.COMMUNITY_DETAIL);
    this.communityDetailLoading = true;
    try {
      const client = this.createApiClient();
      const post = await client.request<CommunityPostItem>(http.RequestMethod.GET, `community/posts/${id}`);
      this.communityDetailPost = post;
      try {
        const comments = await client.request<PagedResponse<CommunityComment>>(http.RequestMethod.GET, `community/posts/${id}/comments`);
        this.communityComments = safeArray<CommunityComment>(comments.items);
      } catch (_) { this.communityComments = []; }
    } catch (_) { toastError('加载详情失败'); }
    finally { this.communityDetailLoading = false; }
  }

  async likeCommunityDetail(): Promise<void> {
    if (this.communityDetailPost === null) return;
    const id = this.communityDetailPost.id;
    const liked = this.communityDetailPost.liked ?? false;
    try {
      const method = liked ? http.RequestMethod.DELETE : http.RequestMethod.POST;
      this.communityDetailPost = await this.createApiClient().request<CommunityPostItem>(method, `community/posts/${id}/like`);
    } catch (_) { toastError('操作失败'); }
  }

  async favoriteCommunityDetail(): Promise<void> {
    if (this.communityDetailPost === null) return;
    const id = this.communityDetailPost.id;
    const favorited = this.communityDetailPost.favorited ?? false;
    try {
      const method = favorited ? http.RequestMethod.DELETE : http.RequestMethod.POST;
      this.communityDetailPost = await this.createApiClient().request<CommunityPostItem>(method, `community/posts/${id}/favorite`);
    } catch (_) { toastError('操作失败'); }
  }

  deleteCommunityDetail(): void {
    promptAction.showDialog({
      title: '确认删除', message: '确认删除这篇帖子？',
      buttons: [{ text: '取消', color: '#6b7280' }, { text: '删除', color: '#dc2626' }],
    }).then((res: promptAction.ShowDialogSuccessResponse) => {
      if (res.index === 1) this.doDeleteCommunityDetail();
    }).catch(() => {});
  }

  async doDeleteCommunityDetail(): Promise<void> {
    if (this.communityDetailPost === null) return;
    try {
      await this.createApiClient().request<CommunityPostItem>(http.RequestMethod.DELETE, `community/posts/${this.communityDetailPost.id}`);
      toastError('帖子已删除');
      this.popRoute();
      await this.refreshSecondaryData('community');
    } catch (_) { toastError('删除失败'); }
  }

  reportCommunityDetail(): void {
    promptAction.showActionMenu({
      title: '选择举报原因',
      buttons: [
        { text: '垃圾广告', color: '#dc2626' },
        { text: '辱骂攻击', color: '#dc2626' },
        { text: '色情低俗', color: '#dc2626' },
        { text: '违法违规', color: '#dc2626' },
        { text: '隐私泄露', color: '#dc2626' },
        { text: '其它', color: '#666666' }
      ]
    }).then((res: promptAction.ActionMenuSuccessResponse) => {
      const reasons: string[] = ['垃圾广告', '辱骂攻击', '色情低俗', '违法违规', '隐私泄露', '其它'];
      if (res.index >= 0 && res.index < reasons.length) {
        this.doReportCommunityDetail(reasons[res.index]);
      }
    }).catch(() => {});
  }

  async doReportCommunityDetail(reason: string): Promise<void> {
    if (this.communityDetailPost === null) return;
    try {
      const body: CommunityReportCreatePayload = { target_type: 'post', target_id: this.communityDetailPost.id, reason: reason };
      await this.createApiClient().requestVoid(http.RequestMethod.POST, 'community/reports', body);
      toastError('已举报，管理员将审核');
    } catch (_) { toastError('举报失败'); }
  }

  async addCommunityComment(content: string, anonymous: boolean, parentId?: string): Promise<void> {
    if (this.communityDetailId.length === 0) return;
    try {
      const body: CommunityCommentCreatePayload = { content: content, is_anonymous: anonymous, parent_comment_id: parentId ?? '' };
      await this.createApiClient().request<CommunityComment>(http.RequestMethod.POST, `community/posts/${this.communityDetailId}/comments`, body);
      const client = this.createApiClient();
      const comments = await client.request<PagedResponse<CommunityComment>>(http.RequestMethod.GET, `community/posts/${this.communityDetailId}/comments`);
      this.communityComments = safeArray<CommunityComment>(comments.items);
      if (this.communityDetailPost !== null) {
        this.communityDetailPost = { id: this.communityDetailPost.id, title: this.communityDetailPost.title, content: this.communityDetailPost.content, category: this.communityDetailPost.category, author_name: this.communityDetailPost.author_name, is_anonymous: this.communityDetailPost.is_anonymous, like_count: this.communityDetailPost.like_count, comment_count: this.communityDetailPost.comment_count + 1, favorite_count: this.communityDetailPost.favorite_count, created_at: this.communityDetailPost.created_at, images: this.communityDetailPost.images, extra: this.communityDetailPost.extra, liked: this.communityDetailPost.liked, favorited: this.communityDetailPost.favorited, is_owner: this.communityDetailPost.is_owner, view_count: this.communityDetailPost.view_count, status: this.communityDetailPost.status, author_id: this.communityDetailPost.author_id };
      }
    } catch (_) { toastError('评论失败'); }
  }

  async uploadCommunityImage(): Promise<void> {
    if (this.communityPostImages.length >= 9) { toastError('最多上传 9 张图片'); return; }
    try {
      const photoPicker: picker.PhotoViewPicker = new picker.PhotoViewPicker();
      const selectResult: picker.PhotoSelectOptions = new picker.PhotoSelectOptions();
      selectResult.MIMEType = picker.PhotoViewMIMETypes.IMAGE_TYPE;
      selectResult.maxSelectNumber = 9 - this.communityPostImages.length;
      const result = await photoPicker.select(selectResult);
      if (result.photoUris.length === 0) return;
      toastError(`正在上传 ${result.photoUris.length} 张图片…`);
      const client = this.createApiClient();
      const uris: string[] = result.photoUris;
      for (let i = 0; i < uris.length; i++) {
        const uri: string = uris[i];
        const fileName: string = uri.split('/').pop() ?? 'image.jpg';
        const contentType: string = this.guessImageContentType(fileName);
        const res: UploadImageResult = await client.uploadImage(uri, fileName, contentType);
        this.communityPostImages = this.communityPostImages.concat([res.url]);
      }
      toastError(`已添加 ${result.photoUris.length} 张图片`);
    } catch (e) {
      toastError('图片上传失败，请重试');
    }
  }

  guessImageContentType(fileName: string): string {
    const lower: string = fileName.toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.gif')) return 'image/gif';
    return 'image/jpeg';
  }

  removeCommunityImage(url: string): void {
    this.communityPostImages = this.communityPostImages.filter((item: string) => item !== url);
  }

  openCommunityEdit(): void {
    if (this.communityDetailPost === null) return;
    this.communityEditPost = this.communityDetailPost;
    this.communityPostImages = this.communityDetailPost.images ?? [];
    this.pushRoute(AppRoute.COMMUNITY_EDIT);
  }

  async updateCommunityPost(title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra): Promise<void> {
    if (this.communityEditPost === null) return;
    const payload: CommunityPostUpdatePayload = { title: title, content: content, category: category, images: this.communityPostImages, is_anonymous: anonymous, extra: extra };
    try {
      const updated: CommunityPostItem = await this.createApiClient().request<CommunityPostItem>('PUT' as http.RequestMethod, `community/posts/${this.communityEditPost.id}`, payload);
      this.communityDetailPost = updated;
      this.communityEditPost = null;
      this.communityPostImages = [];
      this.popRoute();
      await this.refreshSecondaryData('community');
      toastError('帖子已更新');
    } catch (_) { toastError('更新失败，请稍后重试'); }
  }

  cancelCommunityEdit(): void {
    this.communityEditPost = null;
    this.communityPostImages = [];
    this.popRoute();
  }

  async publishLostFound(kind: string, title: string, content: string, location: string, contact: string): Promise<void> {
    const payload: LostFoundPayload = { kind: kind, title: title, content: content, location: location, contact: contact };
    this.secondarySubmitting = true;
    try {
      const client = this.createApiClient();
      await client.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', payload);
      await this.refreshSecondaryData('lostfound');
      this.popRoute();
      toastError('发布成功');
    } catch (error) {
      toastError('发布失败，请稍后重试');
    } finally { this.secondarySubmitting = false; }
  }

  async startFocusSession(mode: FocusMode = 'focus', plannedSeconds: number = 1500, sessionMode: FocusSessionMode = 'QUIET', relatedTaskId?: string, goal?: string): Promise<void> {
    if (this.activeStudySession !== undefined) return;
    try {
      const repository = new StudyRepository(this.createApiClient());
      const sessionGoal: string = goal ?? (mode === 'short_break' ? '短暂休息' : mode === 'long_break' ? '长休息调整' : '完成一段专注学习');
      this.activeStudySession = await repository.start(
        mode, sessionGoal, relatedTaskId, plannedSeconds, sessionMode);
      this.focusPlannedSeconds = this.activeStudySession.planned_duration_seconds ?? plannedSeconds;
      this.focusSessionMode = restoredFocusSessionMode(this.activeStudySession);
      this.focusStartedAt = Date.now();
      this.focusChatMessages = [];
      this.focusChatInput = '';
      await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.START, mode);
      this.pushRoute(AppRoute.FOCUS_SESSION);
    } catch (error) {
      toastError('无法开始专注，请检查网络');
    }
  }

  async toggleFocusVoice(): Promise<void> {
    if (this.focusVoiceClient !== null && this.focusVoiceState.phase !== 'IDLE') {
      const retryAfterError: boolean = this.focusVoiceState.phase === 'ERROR';
      await this.stopFocusVoice();
      if (!retryAfterError) return;
    }
    try {
      const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
      const permission: PermissionRequestResult = await abilityAccessCtrl.createAtManager()
        .requestPermissionsFromUser(context, ['ohos.permission.MICROPHONE']);
      if (permission.authResults.length !== 1 || permission.authResults[0] !== 0) {
        this.focusVoiceState = {
          phase: 'ERROR', message: '需要麦克风权限才能开启实时语音', transcript: '', answer: ''
        };
        return;
      }
      const repository = new FocusRealtimeVoiceRepository(this.createApiClient(), () => this.appState.getAccessToken());
      const session = await repository.createSession();
      this.focusVoiceSessionId = session.session_id;
      const client = new FocusRealtimeVoiceClient(
        (state: FocusVoiceState): void => { this.focusVoiceState = state; },
        (): void => { this.focusVoiceState = FocusVoiceEventReducer.initial(); });
      this.focusVoiceClient = client;
      await client.connect(repository.websocketUrl(session.websocket_path));
    } catch (_) {
      this.focusVoiceState = {
        phase: 'ERROR', message: '实时语音暂时不可用，请稍后重试', transcript: '', answer: ''
      };
      await this.stopFocusVoice();
    }
  }

  async stopFocusVoice(): Promise<void> {
    const client = this.focusVoiceClient;
    const sessionId: string = this.focusVoiceSessionId;
    this.focusVoiceClient = null;
    this.focusVoiceSessionId = '';
    if (client !== null) await client.stop();
    this.focusVoiceState = FocusVoiceEventReducer.initial();
    if (sessionId.length > 0) {
      try { await new FocusRealtimeVoiceRepository(this.createApiClient(), () => this.appState.getAccessToken()).stopSession(sessionId); } catch (_) {}
    }
  }

  async updateFocusSession(action: FocusSessionAction,
    completePlanStep: boolean = true): Promise<boolean> {
    const session: StudySession | undefined = this.activeStudySession;
    if (session === undefined || !this.focusSessionActionGate.tryStart()) return false;
    const behaviorSummary: StudyBehaviorSummary | undefined = action === 'finish' &&
      session.mode === 'focus' && this.focusSessionMode === 'SMART_GUARD' ?
      toStudyBehaviorSummary(this.focusAssistProvider.sessionSummary()) : undefined;
    if (action === 'pause' || action === 'finish') {
      await this.applyFocusCameraLifecycle(
        action === 'pause' ? FocusCameraLifecycleEvent.PAUSE : FocusCameraLifecycleEvent.FINISH,
        session?.mode ?? 'focus');
    }
    try {
      const repository = new StudyRepository(this.createApiClient());
      if (action === 'finish') {
        const finishedSession: StudySession = await repository.finish(
          session.id, '鸿蒙端完成专注', behaviorSummary);
        this.focusSummarySeconds = Math.max(0, finishedSession.duration_seconds);
        this.focusSummaryInteractions = this.focusChatMessages.filter((message: ChatMessage) => message.role === 'assistant').length;
        this.focusSummaryObservation = behaviorSummary === undefined ? '本次未开启学习状态辅助。' :
          `本地聚合：专注 ${behaviorSummary.study_seconds} 秒，缺席 ${behaviorSummary.absent_count} 次，` +
          `手机交互 ${behaviorSummary.phone_interaction_count} 次。`;
        this.activeStudySession = undefined;
        try {
          await this.stopFocusVoice();
        } catch (_) {
          // Backend finish is committed; device-resource cleanup must not roll it back.
        }
        try {
          if (completePlanStep && session.related_task_id !== undefined && this.focusPlan?.taskId === session.related_task_id) {
            const plans = new FocusPlanRepository(new StudyRepository(this.createApiClient()), () => this.appState.getAccessToken());
            this.focusPlan = await plans.completeCurrentStep(session.related_task_id);
            if (this.focusPlan !== undefined && FocusPlanProgress.isComplete(this.focusPlan)) {
              const relatedTask = this.tasks.find((task: TaskItem): boolean => task.id === session.related_task_id);
              if (relatedTask !== undefined && relatedTask.status !== 'completed') await this.toggleTask(relatedTask);
            }
          }
        } catch (_) {
          // Backend finish is the commit boundary; local plan synchronization is best-effort.
        }
      } else if (action === 'pause') {
        this.activeStudySession = await repository.pause(session.id);
        this.focusSessionMode = restoredFocusSessionMode(this.activeStudySession);
      } else {
        this.activeStudySession = await repository.resume(session.id);
        this.focusSessionMode = restoredFocusSessionMode(this.activeStudySession);
        await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.RESUME,
          this.activeStudySession.mode);
      }
      await this.refreshSecondaryData('focus');
      if (action === 'finish') {
        this.pageStack.popToName(AppRoute.FOCUS, false);
        this.pushRoute(AppRoute.FOCUS_SUMMARY);
      }
      return true;
    } catch (error) {
      if ((action === 'pause' || action === 'finish') && session.status === 'active') {
        await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.RESUME, session.mode);
      }
      toastError('操作失败，请重试');
      return false;
    } finally {
      this.focusSessionActionGate.complete();
    }
  }

  openFocusPlan(): void {
    this.focusPlanError = '';
    this.pushRoute(AppRoute.FOCUS_PLAN);
  }

  async generateFocusPlan(task: TaskItem): Promise<void> {
    this.focusPlanLoading = true;
    this.focusPlanError = '';
    try {
      const repository = new FocusPlanRepository(new StudyRepository(this.createApiClient()), () => this.appState.getAccessToken());
      this.focusPlan = await repository.ensurePlan(task.id, task.title, task.description ?? task.title);
    } catch (error) {
      this.focusPlanError = error instanceof Error ? error.message : '暂时无法生成任务规划';
    } finally { this.focusPlanLoading = false; }
  }

  startCurrentPlanStep(): void {
    const plan: FocusPlan | undefined = this.focusPlan;
    if (plan === undefined) return;
    const current = FocusPlanProgress.currentStep(plan);
    const seconds: number = Math.max(5 * 60, Math.min(240 * 60, (current?.estimatedMinutes ?? 25) * 60));
    this.startFocusSession('focus', seconds, 'AI_COMPANION', plan.taskId, current?.title ?? plan.goal);
  }

  async reopenFocusSession(): Promise<void> {
    const session: StudySession | undefined = this.activeStudySession;
    if (session === undefined || (session.status !== 'active' && session.status !== 'paused')) return;
    this.focusSessionMode = restoredFocusSessionMode(session);
    this.focusPlannedSeconds = session.planned_duration_seconds ?? this.focusPlannedSeconds;
    if (session.status === 'paused') {
      if (!await this.updateFocusSession('resume')) return;
    } else {
      await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.RESUME, session.mode);
    }
    this.pushRoute(AppRoute.FOCUS_SESSION);
  }

  async leaveFocusSession(): Promise<void> {
    const session: StudySession | undefined = this.activeStudySession;
    if (session?.status === 'active') {
      if (!await this.updateFocusSession('pause')) return;
    } else {
      await this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.LEAVE, session?.mode ?? 'focus');
    }
    await this.stopFocusVoice();
    this.popRoute();
  }

  async sendFocusCompanionMessage(): Promise<void> {
    const text: string = this.focusChatInput.trim();
    if (text.length === 0 || this.focusChatSending) return;
    this.focusChatMessages = [...this.focusChatMessages, new ChatMessageModel(`focus-user-${Date.now()}`, 'user', text)];
    this.focusChatInput = '';
    this.focusChatSending = true;
    try {
      const answer: string = await new FocusAiRepository(this.createApiClient()).ask(text);
      this.focusChatMessages = [...this.focusChatMessages, new ChatMessageModel(`focus-ai-${Date.now()}`, 'assistant', answer)];
    } catch (_) {
      this.focusChatMessages = [...this.focusChatMessages, new ChatMessageModel(`focus-ai-${Date.now()}`, 'assistant', '我暂时无法回复，但可以先从两分钟的下一步开始。')];
    } finally { this.focusChatSending = false; }
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
      this.popRoute();
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
      this.popRoute();
      toastError('考试已删除');
    } catch (error) {
      toastError('删除失败，请重试');
    }
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
    }.alignItems(HorizontalAlign.Center).padding(14).backgroundColor(this.softColor()).borderRadius(16).width('31%').onClick(() => this.navigateTo(target))
  }

  @Builder HomePage() {
    DashboardPage({
      darkMode: this.darkMode,
      userName: this.displayName,
      courses: this.courses,
      tasks: this.tasks,
      notices: this.notices,
      banners: this.homeBanners,
      reduceMotion: this.reduceMotion,
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
          this.selectTab(3);
        } else {
          this.navigateTo(target);
        }
      }
    })
  }

  courseDetailItem(): CourseItem | undefined {
    return this.courses.find((item: CourseItem) => item.id === this.courseDetailId);
  }

  taskDetailItem(): TaskItem | undefined {
    return this.tasks.find((item: TaskItem) => item.id === this.taskDetailId);
  }

  examDetailItem(): ExamItem | undefined {
    return this.exams.find((item: ExamItem) => item.id === this.examDetailId);
  }

  examFormItem(): ExamItem {
    return this.exams.find((item: ExamItem) => item.id === this.examFormId) ?? { id: '', course_name: '', exam_date: '' };
  }

  lostFoundView(route: string): string {
    if (route === AppRoute.LOST_FOUND_DETAIL) return 'detail';
    if (route === AppRoute.LOST_FOUND_PUBLISH) return 'publish';
    if (route === AppRoute.LOST_FOUND_MINE) return 'mine';
    return 'list';
  }

  @Builder SecondaryContent(route: string) {
    if (route === AppRoute.COURSE_DETAIL) {
      if (this.courseDetailItem() !== undefined) {
        CourseDetailPage({ course: this.courseDetailItem()!, darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.popRoute(), onLoadContent: (courseId: string) => this.loadCourseContent(courseId), onSyncContent: (courseId: string) => this.syncCourseContent(courseId), onCacheContent: (courseId: string, itemId: string) => this.cacheCourseContent(courseId, itemId) })
      }
    } else if (route === AppRoute.TASK_DETAIL) {
      if (this.taskDetailItem() !== undefined) {
        TaskDetailPage({ task: this.taskDetailItem()!, darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.popRoute(), onComplete: (id: string) => { const selected = this.tasks.find((item: TaskItem) => item.id === id); if (selected !== undefined) this.toggleTask(selected); } })
      }
    } else if (route === AppRoute.EXAMS) {
      ExamsPage({ exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.popRoute(), onRefresh: () => this.refreshSecondaryData(AppRoute.EXAMS), onOpenDetail: (exam: ExamItem) => this.openExamDetail(exam), onOpenForm: () => this.openExamForm() })
    } else if (route === AppRoute.EXAM_DETAIL) {
      if (this.examDetailItem() !== undefined) {
        ExamDetailPage({ exam: this.examDetailItem()!, darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.popRoute(), onEdit: () => this.openExamForm(this.examDetailItem()), onDelete: (id: string) => this.deleteExam(id) })
      }
    } else if (route === AppRoute.EXAM_FORM) {
      ExamFormPage({ exam: this.examFormItem(), isEditing: this.examFormId.length > 0, darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.popRoute(), onSave: (payload: ExamItem, id?: string) => this.saveExam(payload, id) })
    } else if (route === AppRoute.CLASSROOMS) {
      ClassroomsPage({ classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.popRoute(), onQuery: () => this.refreshSecondaryData(AppRoute.CLASSROOMS) })
    } else if (route === AppRoute.UNIVERSITY || route === AppRoute.COMMUNITY || route === AppRoute.COMMUNITY_HOT || route === AppRoute.COMMUNITY_PUBLISH || route === AppRoute.COMMUNITY_DETAIL || route === AppRoute.COMMUNITY_EDIT || route === AppRoute.ACADEMIC) {
      V3CorePage({ route: route, darkMode: this.darkMode, loading: this.secondaryLoading, selectedUniversityId: this.selectedUniversityId, selectedUniversityName: this.selectedUniversityName, universities: this.universities, posts: this.communityPosts, hotPosts: this.communityHotPosts, academicStatus: this.academicStatus, detailLoading: this.communityDetailLoading, detailPost: this.communityDetailPost, detailComments: this.communityComments, postImages: this.communityPostImages, editPost: this.communityEditPost, apiBaseUrl: API_BASE_URL, onBack: () => { if (route === AppRoute.COMMUNITY_EDIT) { this.communityEditPost = null; this.communityPostImages = []; } this.popRoute(); }, onRefresh: () => this.refreshSecondaryData(route), onSelectUniversity: (id: string) => this.selectUniversity(id), onPublish: (title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra) => this.publishCommunityPost(title, content, anonymous, category, extra), onLike: (id: string) => this.likeCommunityPost(id), onOpenHot: () => { this.pushRoute(AppRoute.COMMUNITY_HOT); if (this.communityHotPosts.length === 0) { this.refreshSecondaryData(AppRoute.COMMUNITY); } }, onOpenPublish: () => { this.communityPostImages = []; this.pushRoute(AppRoute.COMMUNITY_PUBLISH); }, onOpenDetail: (id: string) => this.openCommunityDetail(id), onDetailLike: () => this.likeCommunityDetail(), onDetailFavorite: () => this.favoriteCommunityDetail(), onDetailDelete: () => this.deleteCommunityDetail(), onDetailReport: () => this.reportCommunityDetail(), onDetailEdit: () => this.openCommunityEdit(), onAddComment: (content: string, anonymous: boolean, parentId?: string) => this.addCommunityComment(content, anonymous, parentId), onChooseImage: () => this.uploadCommunityImage(), onRemoveImage: (url: string) => this.removeCommunityImage(url), onEdit: (title: string, content: string, anonymous: boolean, category: string, extra?: CommunityPostExtra) => this.updateCommunityPost(title, content, anonymous, category, extra), onCancelEdit: () => this.cancelCommunityEdit() })
    } else if (route === AppRoute.FOCUS) {
      FocusPage({ sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, reduceMotion: this.reduceMotion, focusAssistDetail: this.focusAssistDetail, focusAssistLabel: this.focusAssistLabel, focusAssistConfidence: this.focusAssistConfidence, behaviorReminder: this.focusBehaviorReminder, plan: this.focusPlan, onBack: () => { this.applyFocusCameraLifecycle(FocusCameraLifecycleEvent.LEAVE, this.activeStudySession?.mode ?? 'focus'); this.popRoute(); }, onStart: (mode: FocusMode, durationSeconds: number, sessionMode: FocusSessionMode) => this.startFocusSession(mode, durationSeconds, sessionMode), onResumeActive: () => this.reopenFocusSession(), onOpenPlan: () => this.openFocusPlan() })
    } else if (route === AppRoute.FOCUS_PLAN) {
      FocusPlanPage({ tasks: this.tasks, plan: this.focusPlan, loading: this.focusPlanLoading, error: this.focusPlanError, darkMode: this.darkMode, onBack: () => this.popRoute(), onGenerate: (task: TaskItem) => this.generateFocusPlan(task), onStartCurrent: () => this.startCurrentPlanStep() })
    } else if (route === AppRoute.FOCUS_SESSION) {
      FocusSessionPage({ session: this.activeStudySession, plannedSeconds: this.focusPlannedSeconds, sessionMode: this.focusSessionMode, darkMode: this.darkMode, reduceMotion: this.reduceMotion, assistDetail: this.focusAssistDetail, assistLabel: this.focusAssistLabel, assistConfidence: this.focusAssistConfidence, messages: this.focusChatMessages, sending: this.focusChatSending, input: $focusChatInput, voiceState: this.focusVoiceState, hasPlanStep: this.focusPlan !== undefined && FocusPlanProgress.currentStep(this.focusPlan) !== undefined, onBack: () => this.leaveFocusSession(), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: (completePlanStep: boolean) => this.updateFocusSession('finish', completePlanStep), onVoiceToggle: () => this.toggleFocusVoice(), onVoiceInterrupt: async () => { await this.focusVoiceClient?.interrupt(); }, onSend: () => this.sendFocusCompanionMessage() })
    } else if (route === AppRoute.FOCUS_SUMMARY) {
      FocusSummaryPage({ actualSeconds: this.focusSummarySeconds, interactionCount: this.focusSummaryInteractions, observation: this.focusSummaryObservation, darkMode: this.darkMode, onReturnHome: () => { this.pageStack.popToName(AppRoute.FOCUS, !this.reduceMotion); }, onStartNext: () => { this.pageStack.popToName(AppRoute.FOCUS, !this.reduceMotion); } })
    } else if (route === AppRoute.LOST_FOUND || route === AppRoute.LOST_FOUND_DETAIL || route === AppRoute.LOST_FOUND_PUBLISH || route === AppRoute.LOST_FOUND_MINE) {
      LostFoundPage({ items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, reduceMotion: this.reduceMotion, view: this.lostFoundView(route), selectedItemId: this.lostFoundDetailId, onBack: () => this.popRoute(), onFilter: (_kind: string) => this.refreshSecondaryData(AppRoute.LOST_FOUND), onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact), onOpenDetail: (item: LostFoundItem) => this.openLostFoundDetail(item), onOpenPublish: () => this.pushRoute(AppRoute.LOST_FOUND_PUBLISH), onOpenMine: () => this.pushRoute(AppRoute.LOST_FOUND_MINE) })
    } else if (route === AppRoute.NOTIFICATIONS || route === AppRoute.NOTIFICATION_DETAIL) {
      NotificationsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, localNotices: this.localNotices, chaoxingStatus: this.chaoxingStatus, ingestService: this.ingestService, view: route === AppRoute.NOTIFICATION_DETAIL ? 'detail' : 'main', selectedLocalId: this.notificationDetailId, manualSeed: this.notificationManualSeed, onBack: () => this.popRoute(), onTaskSaved: () => this.refreshPrimaryData(), onLocalNoticesChanged: () => this.loadLocalNotices(), onOpenDetail: (id: string) => this.openNotificationDetail(id), onOpenSourceSettings: (source: NotificationSource) => this.openNotificationSourceSettings(source), onOpenChaoxing: () => this.pushRoute(AppRoute.CHAOXING), onPrepareManualExtract: (content: string) => { this.notificationManualSeed = content; } })
    } else if (route === AppRoute.NOTIFICATION_SOURCE_SETTINGS) {
      NotificationSourceSettingsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, source: this.notificationSettingsSource ?? NotificationSource.WECHAT, ingestService: this.ingestService, onBack: () => this.popRoute() })
    } else if (route === AppRoute.CHAOXING) {
      ChaoxingPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, repository: this.chaoxingRepository, onBack: () => this.popRoute(), onStatusChanged: (status: ChaoxingAccountStatus) => { this.chaoxingStatus = status; }, onSynced: () => { this.refreshPrimaryData(); this.loadLocalNotices(); } })
    } else if (route === AppRoute.FILES || route === AppRoute.FAVORITES) {
      PersonalHubPage({ section: route, files: this.personalFiles, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.popRoute(), onRefresh: () => this.refreshSecondaryData(route) })
    } else if (route === AppRoute.SETTINGS) {
      SettingsPage({ darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.popRoute(), onThemeChange: (value: boolean) => { if (value !== this.darkMode) this.toggleTheme(); }, onMotionChange: async (value: boolean) => { await this.appState.setReduceMotion(value); this.reduceMotion = value; }, onNavigate: (target: string) => this.navigateTo(target), onSignOut: () => this.showLogoutDialog = true })
    } else if (route === AppRoute.QR_SCANNER) {
      QrScannerPage({
        darkMode: this.darkMode,
        apiClient: this.createApiClient(),
        onBack: () => this.popRoute(),
        onScanned: (sessionId: string, scanToken: string, browserName: string, osName: string, deviceLabel: string) => {
          this.qrSessionId = sessionId;
          this.qrScanToken = scanToken;
          this.qrBrowserName = browserName;
          this.qrOsName = osName;
          this.qrDeviceLabel = deviceLabel;
          this.pushRoute(AppRoute.QR_CONFIRM);
        }
      })
    } else if (route === AppRoute.QR_CONFIRM) {
      QrConfirmPage({
        darkMode: this.darkMode,
        sessionId: this.qrSessionId,
        scanToken: this.qrScanToken,
        browserName: this.qrBrowserName,
        osName: this.qrOsName,
        deviceLabel: this.qrDeviceLabel,
        apiClient: this.createApiClient(),
        onBack: () => this.popRoute(),
        onSuccess: () => this.clearRoutes()
      })
    } else if (route === AppRoute.ACCOUNT) {
      AccountPage({ darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.popRoute(), onSignOut: () => this.signOut() })
    } else if (route === AppRoute.EDU_SYSTEM) {
      EduSystemPage({
        darkMode: this.darkMode,
        universityId: this.selectedUniversityId,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        apiClient: this.createApiClient(),
        onBack: () => this.popRoute(),
        onNavigateToLogin: (loginUrl: string, connectionId: string, allowedOrigins: string[]) => {
          this.eduLoginUrl = loginUrl;
          this.eduLoginConnectionId = connectionId;
          this.eduLoginAllowedOrigins = allowedOrigins;
          this.pushRoute(AppRoute.EDU_LOGIN);
        },
        onOpenSchedule: () => this.pushRoute(AppRoute.EDU_SCHEDULE)
      })
    } else if (route === AppRoute.EDU_LOGIN) {
      EduLoginPage({
        darkMode: this.darkMode,
        loginUrl: this.eduLoginUrl,
        connectionId: this.eduLoginConnectionId,
        backendAllowedOrigins: this.eduLoginAllowedOrigins,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        onBack: () => this.popRoute(),
        onConnected: () => this.popRoute()
      })
    } else if (route === AppRoute.EDU_SCHEDULE) {
      EduSchedulePage({
        darkMode: this.darkMode,
        apiBaseUrl: API_BASE_URL,
        authToken: this.appState.getAccessToken(),
        onBack: () => this.popRoute(),
        onOpenDetail: (item: EduScheduleItemDto) => this.openScheduleDetail(item)
      })
    } else if (route === AppRoute.EDU_SCHEDULE_DETAIL && this.scheduleDetailItem !== undefined) {
      EduScheduleDetailPage({ item: this.scheduleDetailItem, darkMode: this.darkMode, onBack: () => this.popRoute() })
    } else if (route === AppRoute.ABOUT) {
      Column({ space: 12 }) {
        SecondaryHeader({ title: '关于 CampusMate', subtitle: '校园事务智能陪伴助手', darkMode: this.darkMode, onBack: () => this.popRoute() })
        Scroll() {
          Column({ space: 14 }) {
            SymbolGlyph($r('sys.symbol.school')).fontSize(46).fontColor([this.primaryColor()])
            Text('CampusMate AI').fontColor(this.textColor()).fontSize(22).fontWeight(FontWeight.Bold)
            Text('面向大学生的校园事务智能陪伴助手。').fontColor(this.textColor()).fontSize(14).textAlign(TextAlign.Center).lineHeight(22)
            Text('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。').fontColor(this.mutedColor()).fontSize(12).textAlign(TextAlign.Center).lineHeight(20)
          }.width('100%').padding(24).alignItems(HorizontalAlign.Center)
        }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
      }.width('100%').height('100%').backgroundColor(this.pageBackground())
    } else {
      Column({ space: 12 }) {
        SecondaryHeader({ title: AppRouteRegistry.title(route), subtitle: '功能开发中', darkMode: this.darkMode, onBack: () => this.popRoute() })
        Column({ space: 12 }) {
          SymbolGlyph($r('sys.symbol.info_circle')).fontSize(38).fontColor([this.primaryColor()])
          Text('面向大学生的校园事务智能陪伴助手。').fontColor(this.textColor()).fontSize(15).textAlign(TextAlign.Center)
          Text('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。').fontColor(this.mutedColor()).fontSize(12).textAlign(TextAlign.Center)
        }.width('100%').padding(28).alignItems(HorizontalAlign.Center)
      }.width('100%').height('100%').backgroundColor(this.pageBackground())
    }
  }

  @Builder AppDestination(name: string) {
    NavDestination() {
      this.SecondaryContent(name)
    }
    .hideTitleBar(true)
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
      onOpenDetail: (course: CourseItem) => this.openCourseDetail(course)
    })
  }

  @Builder TasksTabContent() {
    TasksPage({
      tasks: this.tasks,
      loading: this.primaryLoading,
      darkMode: this.darkMode,
      onRefresh: () => this.refreshPrimaryData(),
      onOpenDetail: (task: TaskItem) => this.openTaskDetail(task),
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
      expressionAvailable: this.expressionAvailable,
      expressionDetail: this.expressionDetail,
      expressionGreeting: this.expressionGreeting,
      apiBaseUrl: API_BASE_URL,
      authToken: this.appState.getAccessToken(),
      speechText: this.digitalHumanSpeechText,
      speechRequestId: this.digitalHumanSpeechRequestId,
      input: $chatInput,
      onSend: () => this.sendChat(),
      onEnableExpression: () => this.syncExpressionForTab(true)
    })
  }

  @Builder BottomNavigation() {
    AppDock({
      activeTab: $activeTab,
      darkMode: this.darkMode,
      reduceMotion: this.reduceMotion,
      pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length,
      onNavigate: (index: number) => {
        this.selectTab(index);
      }
    })
  }

  @Builder AuthenticatedShell() {
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
        if (this.requestedTab >= 0 && index !== this.requestedTab) {
          return;
        }
        this.activeTab = index;
        this.syncExpressionForTab();
      })

      AmbientMotionField({ darkMode: this.darkMode, reduceMotion: this.reduceMotion })

      this.BottomNavigation()
    }
    .width('100%')
    .height('100%')
    .backgroundColor(this.pageBackground())
  }

  build() {
    if (this.signedIn) {
      Stack() {
        Navigation(this.pageStack) {
          this.AuthenticatedShell()
        }
        .mode(NavigationMode.Stack)
        .hideTitleBar(true)
        .navDestination(this.AppDestination)
        .width('100%')
        .height('100%')
        .backgroundColor(this.pageBackground())

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
            }.width('85%').padding(24).backgroundColor(this.surface()).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.border }).borderRadius(20).shadow({ radius: 20, color: this.palette().glass.shadow, offsetY: 6 }).alignItems(HorizontalAlign.Start)
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
