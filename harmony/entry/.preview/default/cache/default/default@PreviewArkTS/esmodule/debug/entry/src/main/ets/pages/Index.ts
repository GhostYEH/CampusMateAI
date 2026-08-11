if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface Index_Params {
    appState?: AppState;
    signedIn?: boolean;
    darkMode?: boolean;
    reduceMotion?: boolean;
    activeTab?: number;
    route?: string;
    username?: string;
    password?: string;
    loginError?: string;
    loginLoading?: boolean;
    primaryLoading?: boolean;
    courses?: CourseItem[];
    tasks?: TaskItem[];
    chatMessages?: ChatMessage[];
    chatInput?: string;
    chatSending?: boolean;
    displayName?: string;
    profileDetail?: string;
    secondaryLoading?: boolean;
    secondarySubmitting?: boolean;
    exams?: ExamItem[];
    classrooms?: ClassroomAvailability[];
    serviceRequests?: ServiceRequestItem[];
    lostFoundItems?: LostFoundItem[];
    studySessions?: StudySession[];
    activeStudySession?: StudySession;
    notices?: NoticeItem[];
    personalFiles?: PersonalFileItem[];
    activities?: ActivityItem[];
    favorites?: FavoriteItem[];
    backendOnline?: boolean;
}
import { AppState } from "@bundle:com.example.campusmate/entry/ets/core/AppState";
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { ApiClient } from "@bundle:com.example.campusmate/entry/ets/data/ApiClient";
import { LoginScreen } from "@bundle:com.example.campusmate/entry/ets/features/login/LoginScreen";
import { DashboardPage } from "@bundle:com.example.campusmate/entry/ets/features/dashboard/DashboardPage";
import { AppDock } from "@bundle:com.example.campusmate/entry/ets/ui/AppDock";
import { CoursesPage } from "@bundle:com.example.campusmate/entry/ets/features/courses/CoursesPage";
import { TasksPage } from "@bundle:com.example.campusmate/entry/ets/features/tasks/TasksPage";
import { CounselorPage } from "@bundle:com.example.campusmate/entry/ets/features/counselor/CounselorPage";
import { ProfilePage } from "@bundle:com.example.campusmate/entry/ets/features/profile/ProfilePage";
import { ExamsPage } from "@bundle:com.example.campusmate/entry/ets/features/exams/ExamsPage";
import { ClassroomsPage } from "@bundle:com.example.campusmate/entry/ets/features/classrooms/ClassroomsPage";
import { ServicesPage } from "@bundle:com.example.campusmate/entry/ets/features/services/ServicesPage";
import { FocusPage } from "@bundle:com.example.campusmate/entry/ets/features/focus/FocusPage";
import { LostFoundPage } from "@bundle:com.example.campusmate/entry/ets/features/lostfound/LostFoundPage";
import { NotificationsPage } from "@bundle:com.example.campusmate/entry/ets/features/notifications/NotificationsPage";
import { PersonalHubPage } from "@bundle:com.example.campusmate/entry/ets/features/profile/PersonalHubPage";
import { SettingsPage } from "@bundle:com.example.campusmate/entry/ets/features/profile/SettingsPage";
import { AccountPage } from "@bundle:com.example.campusmate/entry/ets/features/profile/AccountPage";
import type { ActivityItem, ChatMessage, ChatRequest, ChatResponse, ClassroomAvailability, ClassroomResponse, CourseItem, ExamItem, FavoriteItem, LostFoundItem, LostFoundPayload, MeResponse, NoticeItem, PagedResponse, PersonalFileItem, ServiceRequestItem, ServiceRequestPayload, StudySession, StudySessionCreate, StudySessionFinish, TaskItem } from '../data/Models';
import http from "@ohos:net.http";
const API_BASE_URL: string = 'http://127.0.0.1:8000/api/v1';
class Index extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.appState = new AppState();
        this.__signedIn = new ObservedPropertySimplePU(false, this, "signedIn");
        this.__darkMode = new ObservedPropertySimplePU(false, this, "darkMode");
        this.__reduceMotion = new ObservedPropertySimplePU(false, this, "reduceMotion");
        this.__activeTab = new ObservedPropertySimplePU(0, this, "activeTab");
        this.__route = new ObservedPropertySimplePU('', this, "route");
        this.__username = new ObservedPropertySimplePU('', this, "username");
        this.__password = new ObservedPropertySimplePU('', this, "password");
        this.__loginError = new ObservedPropertySimplePU('', this, "loginError");
        this.__loginLoading = new ObservedPropertySimplePU(false, this, "loginLoading");
        this.__primaryLoading = new ObservedPropertySimplePU(false, this, "primaryLoading");
        this.__courses = new ObservedPropertyObjectPU([], this, "courses");
        this.__tasks = new ObservedPropertyObjectPU([], this, "tasks");
        this.__chatMessages = new ObservedPropertyObjectPU([], this, "chatMessages");
        this.__chatInput = new ObservedPropertySimplePU('', this, "chatInput");
        this.__chatSending = new ObservedPropertySimplePU(false, this, "chatSending");
        this.__displayName = new ObservedPropertySimplePU('林知夏', this, "displayName");
        this.__profileDetail = new ObservedPropertySimplePU('计算机科学与技术 · 大三', this, "profileDetail");
        this.__secondaryLoading = new ObservedPropertySimplePU(false, this, "secondaryLoading");
        this.__secondarySubmitting = new ObservedPropertySimplePU(false, this, "secondarySubmitting");
        this.__exams = new ObservedPropertyObjectPU([], this, "exams");
        this.__classrooms = new ObservedPropertyObjectPU([], this, "classrooms");
        this.__serviceRequests = new ObservedPropertyObjectPU([], this, "serviceRequests");
        this.__lostFoundItems = new ObservedPropertyObjectPU([], this, "lostFoundItems");
        this.__studySessions = new ObservedPropertyObjectPU([], this, "studySessions");
        this.__activeStudySession = new ObservedPropertyObjectPU(undefined, this, "activeStudySession");
        this.__notices = new ObservedPropertyObjectPU([], this, "notices");
        this.__personalFiles = new ObservedPropertyObjectPU([], this, "personalFiles");
        this.__activities = new ObservedPropertyObjectPU([], this, "activities");
        this.__favorites = new ObservedPropertyObjectPU([], this, "favorites");
        this.__backendOnline = new ObservedPropertySimplePU(true, this, "backendOnline");
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: Index_Params) {
        if (params.appState !== undefined) {
            this.appState = params.appState;
        }
        if (params.signedIn !== undefined) {
            this.signedIn = params.signedIn;
        }
        if (params.darkMode !== undefined) {
            this.darkMode = params.darkMode;
        }
        if (params.reduceMotion !== undefined) {
            this.reduceMotion = params.reduceMotion;
        }
        if (params.activeTab !== undefined) {
            this.activeTab = params.activeTab;
        }
        if (params.route !== undefined) {
            this.route = params.route;
        }
        if (params.username !== undefined) {
            this.username = params.username;
        }
        if (params.password !== undefined) {
            this.password = params.password;
        }
        if (params.loginError !== undefined) {
            this.loginError = params.loginError;
        }
        if (params.loginLoading !== undefined) {
            this.loginLoading = params.loginLoading;
        }
        if (params.primaryLoading !== undefined) {
            this.primaryLoading = params.primaryLoading;
        }
        if (params.courses !== undefined) {
            this.courses = params.courses;
        }
        if (params.tasks !== undefined) {
            this.tasks = params.tasks;
        }
        if (params.chatMessages !== undefined) {
            this.chatMessages = params.chatMessages;
        }
        if (params.chatInput !== undefined) {
            this.chatInput = params.chatInput;
        }
        if (params.chatSending !== undefined) {
            this.chatSending = params.chatSending;
        }
        if (params.displayName !== undefined) {
            this.displayName = params.displayName;
        }
        if (params.profileDetail !== undefined) {
            this.profileDetail = params.profileDetail;
        }
        if (params.secondaryLoading !== undefined) {
            this.secondaryLoading = params.secondaryLoading;
        }
        if (params.secondarySubmitting !== undefined) {
            this.secondarySubmitting = params.secondarySubmitting;
        }
        if (params.exams !== undefined) {
            this.exams = params.exams;
        }
        if (params.classrooms !== undefined) {
            this.classrooms = params.classrooms;
        }
        if (params.serviceRequests !== undefined) {
            this.serviceRequests = params.serviceRequests;
        }
        if (params.lostFoundItems !== undefined) {
            this.lostFoundItems = params.lostFoundItems;
        }
        if (params.studySessions !== undefined) {
            this.studySessions = params.studySessions;
        }
        if (params.activeStudySession !== undefined) {
            this.activeStudySession = params.activeStudySession;
        }
        if (params.notices !== undefined) {
            this.notices = params.notices;
        }
        if (params.personalFiles !== undefined) {
            this.personalFiles = params.personalFiles;
        }
        if (params.activities !== undefined) {
            this.activities = params.activities;
        }
        if (params.favorites !== undefined) {
            this.favorites = params.favorites;
        }
        if (params.backendOnline !== undefined) {
            this.backendOnline = params.backendOnline;
        }
    }
    updateStateVars(params: Index_Params) {
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__signedIn.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__reduceMotion.purgeDependencyOnElmtId(rmElmtId);
        this.__activeTab.purgeDependencyOnElmtId(rmElmtId);
        this.__route.purgeDependencyOnElmtId(rmElmtId);
        this.__username.purgeDependencyOnElmtId(rmElmtId);
        this.__password.purgeDependencyOnElmtId(rmElmtId);
        this.__loginError.purgeDependencyOnElmtId(rmElmtId);
        this.__loginLoading.purgeDependencyOnElmtId(rmElmtId);
        this.__primaryLoading.purgeDependencyOnElmtId(rmElmtId);
        this.__courses.purgeDependencyOnElmtId(rmElmtId);
        this.__tasks.purgeDependencyOnElmtId(rmElmtId);
        this.__chatMessages.purgeDependencyOnElmtId(rmElmtId);
        this.__chatInput.purgeDependencyOnElmtId(rmElmtId);
        this.__chatSending.purgeDependencyOnElmtId(rmElmtId);
        this.__displayName.purgeDependencyOnElmtId(rmElmtId);
        this.__profileDetail.purgeDependencyOnElmtId(rmElmtId);
        this.__secondaryLoading.purgeDependencyOnElmtId(rmElmtId);
        this.__secondarySubmitting.purgeDependencyOnElmtId(rmElmtId);
        this.__exams.purgeDependencyOnElmtId(rmElmtId);
        this.__classrooms.purgeDependencyOnElmtId(rmElmtId);
        this.__serviceRequests.purgeDependencyOnElmtId(rmElmtId);
        this.__lostFoundItems.purgeDependencyOnElmtId(rmElmtId);
        this.__studySessions.purgeDependencyOnElmtId(rmElmtId);
        this.__activeStudySession.purgeDependencyOnElmtId(rmElmtId);
        this.__notices.purgeDependencyOnElmtId(rmElmtId);
        this.__personalFiles.purgeDependencyOnElmtId(rmElmtId);
        this.__activities.purgeDependencyOnElmtId(rmElmtId);
        this.__favorites.purgeDependencyOnElmtId(rmElmtId);
        this.__backendOnline.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__signedIn.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__reduceMotion.aboutToBeDeleted();
        this.__activeTab.aboutToBeDeleted();
        this.__route.aboutToBeDeleted();
        this.__username.aboutToBeDeleted();
        this.__password.aboutToBeDeleted();
        this.__loginError.aboutToBeDeleted();
        this.__loginLoading.aboutToBeDeleted();
        this.__primaryLoading.aboutToBeDeleted();
        this.__courses.aboutToBeDeleted();
        this.__tasks.aboutToBeDeleted();
        this.__chatMessages.aboutToBeDeleted();
        this.__chatInput.aboutToBeDeleted();
        this.__chatSending.aboutToBeDeleted();
        this.__displayName.aboutToBeDeleted();
        this.__profileDetail.aboutToBeDeleted();
        this.__secondaryLoading.aboutToBeDeleted();
        this.__secondarySubmitting.aboutToBeDeleted();
        this.__exams.aboutToBeDeleted();
        this.__classrooms.aboutToBeDeleted();
        this.__serviceRequests.aboutToBeDeleted();
        this.__lostFoundItems.aboutToBeDeleted();
        this.__studySessions.aboutToBeDeleted();
        this.__activeStudySession.aboutToBeDeleted();
        this.__notices.aboutToBeDeleted();
        this.__personalFiles.aboutToBeDeleted();
        this.__activities.aboutToBeDeleted();
        this.__favorites.aboutToBeDeleted();
        this.__backendOnline.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private appState: AppState;
    private __signedIn: ObservedPropertySimplePU<boolean>;
    get signedIn() {
        return this.__signedIn.get();
    }
    set signedIn(newValue: boolean) {
        this.__signedIn.set(newValue);
    }
    private __darkMode: ObservedPropertySimplePU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __reduceMotion: ObservedPropertySimplePU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(newValue: boolean) {
        this.__reduceMotion.set(newValue);
    }
    private __activeTab: ObservedPropertySimplePU<number>;
    get activeTab() {
        return this.__activeTab.get();
    }
    set activeTab(newValue: number) {
        this.__activeTab.set(newValue);
    }
    private __route: ObservedPropertySimplePU<string>;
    get route() {
        return this.__route.get();
    }
    set route(newValue: string) {
        this.__route.set(newValue);
    }
    private __username: ObservedPropertySimplePU<string>;
    get username() {
        return this.__username.get();
    }
    set username(newValue: string) {
        this.__username.set(newValue);
    }
    private __password: ObservedPropertySimplePU<string>;
    get password() {
        return this.__password.get();
    }
    set password(newValue: string) {
        this.__password.set(newValue);
    }
    private __loginError: ObservedPropertySimplePU<string>;
    get loginError() {
        return this.__loginError.get();
    }
    set loginError(newValue: string) {
        this.__loginError.set(newValue);
    }
    private __loginLoading: ObservedPropertySimplePU<boolean>;
    get loginLoading() {
        return this.__loginLoading.get();
    }
    set loginLoading(newValue: boolean) {
        this.__loginLoading.set(newValue);
    }
    private __primaryLoading: ObservedPropertySimplePU<boolean>;
    get primaryLoading() {
        return this.__primaryLoading.get();
    }
    set primaryLoading(newValue: boolean) {
        this.__primaryLoading.set(newValue);
    }
    private __courses: ObservedPropertyObjectPU<CourseItem[]>;
    get courses() {
        return this.__courses.get();
    }
    set courses(newValue: CourseItem[]) {
        this.__courses.set(newValue);
    }
    private __tasks: ObservedPropertyObjectPU<TaskItem[]>;
    get tasks() {
        return this.__tasks.get();
    }
    set tasks(newValue: TaskItem[]) {
        this.__tasks.set(newValue);
    }
    private __chatMessages: ObservedPropertyObjectPU<ChatMessage[]>;
    get chatMessages() {
        return this.__chatMessages.get();
    }
    set chatMessages(newValue: ChatMessage[]) {
        this.__chatMessages.set(newValue);
    }
    private __chatInput: ObservedPropertySimplePU<string>;
    get chatInput() {
        return this.__chatInput.get();
    }
    set chatInput(newValue: string) {
        this.__chatInput.set(newValue);
    }
    private __chatSending: ObservedPropertySimplePU<boolean>;
    get chatSending() {
        return this.__chatSending.get();
    }
    set chatSending(newValue: boolean) {
        this.__chatSending.set(newValue);
    }
    private __displayName: ObservedPropertySimplePU<string>;
    get displayName() {
        return this.__displayName.get();
    }
    set displayName(newValue: string) {
        this.__displayName.set(newValue);
    }
    private __profileDetail: ObservedPropertySimplePU<string>;
    get profileDetail() {
        return this.__profileDetail.get();
    }
    set profileDetail(newValue: string) {
        this.__profileDetail.set(newValue);
    }
    private __secondaryLoading: ObservedPropertySimplePU<boolean>;
    get secondaryLoading() {
        return this.__secondaryLoading.get();
    }
    set secondaryLoading(newValue: boolean) {
        this.__secondaryLoading.set(newValue);
    }
    private __secondarySubmitting: ObservedPropertySimplePU<boolean>;
    get secondarySubmitting() {
        return this.__secondarySubmitting.get();
    }
    set secondarySubmitting(newValue: boolean) {
        this.__secondarySubmitting.set(newValue);
    }
    private __exams: ObservedPropertyObjectPU<ExamItem[]>;
    get exams() {
        return this.__exams.get();
    }
    set exams(newValue: ExamItem[]) {
        this.__exams.set(newValue);
    }
    private __classrooms: ObservedPropertyObjectPU<ClassroomAvailability[]>;
    get classrooms() {
        return this.__classrooms.get();
    }
    set classrooms(newValue: ClassroomAvailability[]) {
        this.__classrooms.set(newValue);
    }
    private __serviceRequests: ObservedPropertyObjectPU<ServiceRequestItem[]>;
    get serviceRequests() {
        return this.__serviceRequests.get();
    }
    set serviceRequests(newValue: ServiceRequestItem[]) {
        this.__serviceRequests.set(newValue);
    }
    private __lostFoundItems: ObservedPropertyObjectPU<LostFoundItem[]>;
    get lostFoundItems() {
        return this.__lostFoundItems.get();
    }
    set lostFoundItems(newValue: LostFoundItem[]) {
        this.__lostFoundItems.set(newValue);
    }
    private __studySessions: ObservedPropertyObjectPU<StudySession[]>;
    get studySessions() {
        return this.__studySessions.get();
    }
    set studySessions(newValue: StudySession[]) {
        this.__studySessions.set(newValue);
    }
    private __activeStudySession?: ObservedPropertyObjectPU<StudySession>;
    get activeStudySession() {
        return this.__activeStudySession.get();
    }
    set activeStudySession(newValue: StudySession) {
        this.__activeStudySession.set(newValue);
    }
    private __notices: ObservedPropertyObjectPU<NoticeItem[]>;
    get notices() {
        return this.__notices.get();
    }
    set notices(newValue: NoticeItem[]) {
        this.__notices.set(newValue);
    }
    private __personalFiles: ObservedPropertyObjectPU<PersonalFileItem[]>;
    get personalFiles() {
        return this.__personalFiles.get();
    }
    set personalFiles(newValue: PersonalFileItem[]) {
        this.__personalFiles.set(newValue);
    }
    private __activities: ObservedPropertyObjectPU<ActivityItem[]>;
    get activities() {
        return this.__activities.get();
    }
    set activities(newValue: ActivityItem[]) {
        this.__activities.set(newValue);
    }
    private __favorites: ObservedPropertyObjectPU<FavoriteItem[]>;
    get favorites() {
        return this.__favorites.get();
    }
    set favorites(newValue: FavoriteItem[]) {
        this.__favorites.set(newValue);
    }
    private __backendOnline: ObservedPropertySimplePU<boolean>;
    get backendOnline() {
        return this.__backendOnline.get();
    }
    set backendOnline(newValue: boolean) {
        this.__backendOnline.set(newValue);
    }
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
        }
        catch (error) {
            this.loginError = '暂时无法登录，请检查账号、密码和网络后重试。';
        }
        finally {
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
        }
        catch (error) {
            // Keep the Android-equivalent local empty state when the backend becomes unavailable.
            this.backendOnline = false;
        }
        finally {
            this.primaryLoading = false;
        }
    }
    async toggleTask(task: TaskItem): Promise<void> {
        const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            await client.request<TaskItem>(http.RequestMethod.POST, task.status === 'completed' ? `tasks/${task.id}/restore` : `tasks/${task.id}/complete`);
            await this.refreshPrimaryData();
        }
        catch (error) {
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
        }
        catch (error) {
            const errorMessage: ChatMessage = {
                id: `assistant-error-${Date.now()}`,
                role: 'assistant',
                content: '暂时无法连接校园知识库，请检查网络后重试。'
            };
            this.chatMessages = [...this.chatMessages, errorMessage];
        }
        finally {
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
        if (target === 'courses') {
            this.route = '';
            this.activeTab = 1;
            return;
        }
        if (target === 'tasks') {
            this.route = '';
            this.activeTab = 2;
            return;
        }
        if (target === 'counselor') {
            this.route = '';
            this.activeTab = 3;
            return;
        }
        if (target === 'profile') {
            this.route = '';
            this.activeTab = 4;
            return;
        }
        this.route = target;
        this.refreshSecondaryData(target);
    }
    async refreshSecondaryData(target: string): Promise<void> {
        if (this.secondaryLoading || this.appState.sessionToken.length === 0)
            return;
        this.secondaryLoading = true;
        const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            if (target === 'exams') {
                this.exams = await client.request<ExamItem[]>(http.RequestMethod.GET, 'student/exams');
            }
            else if (target === 'classrooms') {
                const response = await client.request<ClassroomResponse>(http.RequestMethod.GET, 'student/classrooms');
                this.classrooms = response.items;
            }
            else if (target === 'services') {
                this.serviceRequests = await client.request<ServiceRequestItem[]>(http.RequestMethod.GET, 'student/service-requests');
            }
            else if (target === 'lostfound') {
                this.lostFoundItems = await client.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found');
            }
            else if (target === 'focus') {
                this.studySessions = await client.request<StudySession[]>(http.RequestMethod.GET, 'study/sessions?page=1&page_size=20');
                this.activeStudySession = await client.request<StudySession | undefined>(http.RequestMethod.GET, 'study/sessions/active');
            }
            else if (target === 'notifications') {
                const page = await client.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=100');
                this.notices = page.items;
            }
            else if (target === 'files') {
                this.personalFiles = await client.request<PersonalFileItem[]>(http.RequestMethod.GET, 'personal-hub/files');
            }
            else if (target === 'activities') {
                const page = await client.request<PagedResponse<ActivityItem>>(http.RequestMethod.GET, 'activities?page=1&page_size=100');
                this.activities = page.items;
            }
            else if (target === 'favorites') {
                this.favorites = await client.request<FavoriteItem[]>(http.RequestMethod.GET, 'personal-hub/favorites');
            }
        }
        catch (error) {
            this.backendOnline = false;
        }
        finally {
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
        }
        catch (error) {
        }
        finally {
            this.secondarySubmitting = false;
        }
    }
    async publishLostFound(kind: string, title: string, content: string, location: string, contact: string): Promise<void> {
        const payload: LostFoundPayload = { kind: kind, title: title, content: content, location: location, contact: contact };
        this.secondarySubmitting = true;
        try {
            const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            await client.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', payload);
            await this.refreshSecondaryData('lostfound');
        }
        catch (error) {
        }
        finally {
            this.secondarySubmitting = false;
        }
    }
    async startFocusSession(): Promise<void> {
        if (this.activeStudySession !== undefined)
            return;
        const payload: StudySessionCreate = { goal: '完成一段专注学习' };
        try {
            const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            this.activeStudySession = await client.request<StudySession>(http.RequestMethod.POST, 'study/sessions', payload);
        }
        catch (error) {
        }
    }
    async updateFocusSession(action: string): Promise<void> {
        if (this.activeStudySession === undefined)
            return;
        try {
            const client = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            if (action === 'finish') {
                const body: StudySessionFinish = { self_report: '鸿蒙端完成专注' };
                await client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/finish`, body);
                this.activeStudySession = undefined;
            }
            else {
                this.activeStudySession = await client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/${action}`);
            }
            await this.refreshSecondaryData('focus');
        }
        catch (error) {
        }
    }
    routeTitle(): string {
        if (this.route === 'courses')
            return '我的课程';
        if (this.route === 'exams')
            return '考试安排';
        if (this.route === 'classrooms')
            return '空教室查询';
        if (this.route === 'services')
            return '办事大厅';
        if (this.route === 'focus')
            return '专注自习';
        if (this.route === 'lostfound')
            return '失物招领';
        if (this.route === 'settings')
            return '设置';
        if (this.route === 'profile')
            return '个人资料';
        return '校园服务';
    }
    Header(title: string, subtitle: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/pages/Index.ets(304:5)", "entry");
            Row.width('100%');
            Row.padding({ left: 20, right: 20, top: 18, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 4 });
            Column.debugLine("entry/src/main/ets/pages/Index.ets(305:7)", "entry");
            Column.layoutWeight(1);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(title);
            Text.debugLine("entry/src/main/ets/pages/Index.ets(306:9)", "entry");
            Text.fontSize(25);
            Text.fontWeight(FontWeight.Bold);
            Text.fontColor(this.textColor());
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(subtitle);
            Text.debugLine("entry/src/main/ets/pages/Index.ets(307:9)", "entry");
            Text.fontSize(13);
            Text.fontColor(this.mutedColor());
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.darkMode) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125832513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/pages/Index.ets(310:9)", "entry");
                        SymbolGlyph.fontSize(23);
                        SymbolGlyph.fontColor([this.primaryColor()]);
                        SymbolGlyph.onClick(() => this.toggleTheme());
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831540, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/pages/Index.ets(312:9)", "entry");
                        SymbolGlyph.fontSize(23);
                        SymbolGlyph.fontColor([this.primaryColor()]);
                        SymbolGlyph.onClick(() => this.toggleTheme());
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Row.pop();
    }
    LoginPage(parent = null) {
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new LoginScreen(this, {
                        username: this.__username,
                        password: this.__password,
                        loading: this.loginLoading,
                        error: this.loginError,
                        reduceMotion: this.reduceMotion,
                        onSubmit: () => {
                            this.signInForPreview();
                        },
                        onInputChanged: () => {
                            this.loginError = '';
                        }
                    }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 318, col: 5 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            username: this.username,
                            password: this.password,
                            loading: this.loginLoading,
                            error: this.loginError,
                            reduceMotion: this.reduceMotion,
                            onSubmit: () => {
                                this.signInForPreview();
                            },
                            onInputChanged: () => {
                                this.loginError = '';
                            }
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        loading: this.loginLoading,
                        error: this.loginError,
                        reduceMotion: this.reduceMotion
                    });
                }
            }, { name: "LoginScreen" });
        }
    }
    Tile(label: string, target: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 8 });
            Column.debugLine("entry/src/main/ets/pages/Index.ets(334:5)", "entry");
            Column.alignItems(HorizontalAlign.Center);
            Column.padding(14);
            Column.backgroundColor(this.softColor());
            Column.borderRadius(16);
            Column.width('31%');
            Column.onClick(() => this.route = target);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.debugLine("entry/src/main/ets/pages/Index.ets(335:7)", "entry");
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Medium);
            Text.fontColor(this.textColor());
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('进入功能');
            Text.debugLine("entry/src/main/ets/pages/Index.ets(336:7)", "entry");
            Text.fontSize(12);
            Text.fontColor(this.primaryColor());
        }, Text);
        Text.pop();
        Column.pop();
    }
    HomePage(parent = null) {
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new DashboardPage(this, {
                        darkMode: this.darkMode,
                        userName: this.displayName,
                        courses: this.courses,
                        tasks: this.tasks,
                        notices: this.notices,
                        onNavigate: (target: string) => {
                            this.navigateTo(target);
                        }
                    }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 341, col: 5 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            darkMode: this.darkMode,
                            userName: this.displayName,
                            courses: this.courses,
                            tasks: this.tasks,
                            notices: this.notices,
                            onNavigate: (target: string) => {
                                this.navigateTo(target);
                            }
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        darkMode: this.darkMode,
                        userName: this.displayName,
                        courses: this.courses,
                        tasks: this.tasks,
                        notices: this.notices
                    });
                }
            }, { name: "DashboardPage" });
        }
    }
    ListPage(title: string, subtitle: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/pages/Index.ets(354:5)", "entry");
        }, Column);
        this.Header.bind(this)(title, subtitle);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/pages/Index.ets(356:7)", "entry");
            Scroll.layoutWeight(1);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 10 });
            Column.debugLine("entry/src/main/ets/pages/Index.ets(357:9)", "entry");
            Column.padding(20);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel('查看最新校园数据');
            Button.debugLine("entry/src/main/ets/pages/Index.ets(358:11)", "entry");
            Button.width('100%');
            Button.height(54);
            Button.backgroundColor(this.surface());
            Button.fontColor(this.textColor());
        }, Button);
        Button.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel('刷新');
            Button.debugLine("entry/src/main/ets/pages/Index.ets(359:11)", "entry");
            Button.width('100%');
            Button.backgroundColor(this.primaryColor());
            Button.fontColor('#FFFFFF');
        }, Button);
        Button.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    ProfileTab(parent = null) {
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new ProfilePage(this, {
                        darkMode: this.darkMode,
                        name: this.displayName,
                        detail: this.profileDetail,
                        onNavigate: (target: string) => {
                            if (target === 'counselor') {
                                this.route = '';
                                this.activeTab = 3;
                            }
                            else {
                                this.navigateTo(target);
                            }
                        }
                    }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 366, col: 5 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            darkMode: this.darkMode,
                            name: this.displayName,
                            detail: this.profileDetail,
                            onNavigate: (target: string) => {
                                if (target === 'counselor') {
                                    this.route = '';
                                    this.activeTab = 3;
                                }
                                else {
                                    this.navigateTo(target);
                                }
                            }
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        darkMode: this.darkMode,
                        name: this.displayName,
                        detail: this.profileDetail
                    });
                }
            }, { name: "ProfilePage" });
        }
    }
    SecondaryPage(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.route === 'exams') {
                this.ifElseBranchUpdateFunction(0, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new ExamsPage(this, { exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('exams') }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 383, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        exams: this.exams,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('exams')
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "ExamsPage" });
                    }
                });
            }
            else if (this.route === 'classrooms') {
                this.ifElseBranchUpdateFunction(1, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new ClassroomsPage(this, { classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onQuery: () => this.refreshSecondaryData('classrooms') }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 385, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        classrooms: this.classrooms,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onQuery: () => this.refreshSecondaryData('classrooms')
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "ClassroomsPage" });
                    }
                });
            }
            else if (this.route === 'services') {
                this.ifElseBranchUpdateFunction(2, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new ServicesPage(this, { requests: this.serviceRequests, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('services'), onSubmit: (kind: string, title: string, content: string) => this.createServiceRequest(kind, title, content) }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 387, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        requests: this.serviceRequests,
                                        loading: this.secondaryLoading,
                                        submitting: this.secondarySubmitting,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('services'),
                                        onSubmit: (kind: string, title: string, content: string) => this.createServiceRequest(kind, title, content)
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    requests: this.serviceRequests, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode
                                });
                            }
                        }, { name: "ServicesPage" });
                    }
                });
            }
            else if (this.route === 'focus') {
                this.ifElseBranchUpdateFunction(3, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new FocusPage(this, { sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onStart: () => this.startFocusSession(), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: () => this.updateFocusSession('finish') }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 389, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        sessions: this.studySessions,
                                        activeSession: this.activeStudySession,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onStart: () => this.startFocusSession(),
                                        onPause: () => this.updateFocusSession('pause'),
                                        onResume: () => this.updateFocusSession('resume'),
                                        onFinish: () => this.updateFocusSession('finish')
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "FocusPage" });
                    }
                });
            }
            else if (this.route === 'lostfound') {
                this.ifElseBranchUpdateFunction(4, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new LostFoundPage(this, { items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onFilter: (kind: string) => this.refreshSecondaryData('lostfound'), onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact) }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 391, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        items: this.lostFoundItems,
                                        loading: this.secondaryLoading,
                                        submitting: this.secondarySubmitting,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onFilter: (kind: string) => this.refreshSecondaryData('lostfound'),
                                        onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => this.publishLostFound(kind, title, content, location, contact)
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode
                                });
                            }
                        }, { name: "LostFoundPage" });
                    }
                });
            }
            else if (this.route === 'notifications') {
                this.ifElseBranchUpdateFunction(5, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new NotificationsPage(this, { notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('notifications') }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 393, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        notices: this.notices,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('notifications')
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "NotificationsPage" });
                    }
                });
            }
            else if (this.route === 'files' || this.route === 'activities' || this.route === 'favorites') {
                this.ifElseBranchUpdateFunction(6, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new PersonalHubPage(this, { section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route) }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 395, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        section: this.route,
                                        files: this.personalFiles,
                                        activities: this.activities,
                                        favorites: this.favorites,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData(this.route)
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "PersonalHubPage" });
                    }
                });
            }
            else if (this.route === 'settings') {
                this.ifElseBranchUpdateFunction(7, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new SettingsPage(this, { darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.route = '', onThemeChange: (value: boolean) => { if (value !== this.darkMode)
                                        this.toggleTheme(); }, onMotionChange: (value: boolean) => { this.appState.setReduceMotion(value); this.reduceMotion = value; }, onNavigate: (target: string) => this.navigateTo(target) }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 397, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        darkMode: this.darkMode,
                                        reduceMotion: this.reduceMotion,
                                        backendOnline: this.backendOnline,
                                        onBack: () => this.route = '',
                                        onThemeChange: (value: boolean) => { if (value !== this.darkMode)
                                            this.toggleTheme(); },
                                        onMotionChange: (value: boolean) => { this.appState.setReduceMotion(value); this.reduceMotion = value; },
                                        onNavigate: (target: string) => this.navigateTo(target)
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline
                                });
                            }
                        }, { name: "SettingsPage" });
                    }
                });
            }
            else if (this.route === 'account') {
                this.ifElseBranchUpdateFunction(8, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new AccountPage(this, { darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.route = '', onSignOut: () => this.signOut() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 399, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        darkMode: this.darkMode,
                                        name: this.displayName,
                                        detail: this.profileDetail,
                                        onBack: () => this.route = '',
                                        onSignOut: () => this.signOut()
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail
                                });
                            }
                        }, { name: "AccountPage" });
                    }
                });
            }
            else {
                this.ifElseBranchUpdateFunction(9, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Column.create();
                        Column.debugLine("entry/src/main/ets/pages/Index.ets(401:7)", "entry");
                    }, Column);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Row.create({ space: 12 });
                        Row.debugLine("entry/src/main/ets/pages/Index.ets(402:9)", "entry");
                        Row.padding(20);
                    }, Row);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125832679, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/pages/Index.ets(403:11)", "entry");
                        SymbolGlyph.fontSize(22);
                        SymbolGlyph.fontColor([this.textColor()]);
                        SymbolGlyph.onClick(() => this.route = '');
                    }, SymbolGlyph);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create(this.routeTitle());
                        Text.debugLine("entry/src/main/ets/pages/Index.ets(404:11)", "entry");
                        Text.fontSize(22);
                        Text.fontWeight(FontWeight.Bold);
                        Text.fontColor(this.textColor());
                    }, Text);
                    Text.pop();
                    Row.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Column.create({ space: 12 });
                        Column.debugLine("entry/src/main/ets/pages/Index.ets(406:9)", "entry");
                        Column.width('100%');
                        Column.padding(28);
                    }, Column);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/pages/Index.ets(407:11)", "entry");
                        SymbolGlyph.fontSize(38);
                        SymbolGlyph.fontColor([this.primaryColor()]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('面向大学生的校园事务智能陪伴助手。');
                        Text.debugLine("entry/src/main/ets/pages/Index.ets(408:11)", "entry");
                        Text.fontColor(this.textColor());
                        Text.fontSize(15);
                        Text.textAlign(TextAlign.Center);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。');
                        Text.debugLine("entry/src/main/ets/pages/Index.ets(409:11)", "entry");
                        Text.fontColor(this.mutedColor());
                        Text.fontSize(12);
                        Text.textAlign(TextAlign.Center);
                    }, Text);
                    Text.pop();
                    Column.pop();
                    Column.pop();
                });
            }
        }, If);
        If.pop();
    }
    MainContent(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.route.length > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.SecondaryPage.bind(this)();
                });
            }
            else if (this.activeTab === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.HomePage.bind(this)();
                });
            }
            else if (this.activeTab === 1) {
                this.ifElseBranchUpdateFunction(2, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new CoursesPage(this, { courses: this.courses, loading: this.primaryLoading, darkMode: this.darkMode, onRefresh: () => this.refreshPrimaryData() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 419, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        courses: this.courses,
                                        loading: this.primaryLoading,
                                        darkMode: this.darkMode,
                                        onRefresh: () => this.refreshPrimaryData()
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    courses: this.courses, loading: this.primaryLoading, darkMode: this.darkMode
                                });
                            }
                        }, { name: "CoursesPage" });
                    }
                });
            }
            else if (this.activeTab === 2) {
                this.ifElseBranchUpdateFunction(3, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new TasksPage(this, {
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
                                }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 422, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
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
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    tasks: this.tasks,
                                    loading: this.primaryLoading,
                                    darkMode: this.darkMode
                                });
                            }
                        }, { name: "TasksPage" });
                    }
                });
            }
            else if (this.activeTab === 3) {
                this.ifElseBranchUpdateFunction(4, () => {
                    {
                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                            if (isInitialRender) {
                                let componentCall = new CounselorPage(this, {
                                    messages: this.chatMessages,
                                    sending: this.chatSending,
                                    darkMode: this.darkMode,
                                    input: this.__chatInput,
                                    onSend: () => this.sendChat()
                                }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 436, col: 7 });
                                ViewPU.create(componentCall);
                                let paramsLambda = () => {
                                    return {
                                        messages: this.chatMessages,
                                        sending: this.chatSending,
                                        darkMode: this.darkMode,
                                        input: this.chatInput,
                                        onSend: () => this.sendChat()
                                    };
                                };
                                componentCall.paramsGenerator_ = paramsLambda;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(elmtId, {
                                    messages: this.chatMessages,
                                    sending: this.chatSending,
                                    darkMode: this.darkMode
                                });
                            }
                        }, { name: "CounselorPage" });
                    }
                });
            }
            else {
                this.ifElseBranchUpdateFunction(5, () => {
                    this.ProfileTab.bind(this)();
                });
            }
        }, If);
        If.pop();
    }
    BottomNavigation(parent = null) {
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new AppDock(this, {
                        activeTab: this.activeTab,
                        darkMode: this.darkMode,
                        pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length,
                        onNavigate: (index: number) => {
                            this.route = '';
                            this.activeTab = index;
                        }
                    }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 448, col: 5 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            activeTab: this.activeTab,
                            darkMode: this.darkMode,
                            pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length,
                            onNavigate: (index: number) => {
                                this.route = '';
                                this.activeTab = index;
                            }
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        activeTab: this.activeTab,
                        darkMode: this.darkMode,
                        pendingCount: this.tasks.filter((task: TaskItem) => task.status !== 'completed').length
                    });
                }
            }, { name: "AppDock" });
        }
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.signedIn) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Stack.create({ alignContent: Alignment.Bottom });
                        Stack.debugLine("entry/src/main/ets/pages/Index.ets(461:7)", "entry");
                        Stack.width('100%');
                        Stack.height('100%');
                        Stack.backgroundColor(this.pageBackground());
                    }, Stack);
                    this.MainContent.bind(this)();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        If.create();
                        if (this.route.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.BottomNavigation.bind(this)();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                            });
                        }
                    }, If);
                    If.pop();
                    Stack.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.LoginPage.bind(this)();
                });
            }
        }, If);
        If.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
    static getEntryName(): string {
        return "Index";
    }
}
registerNamedRoute(() => new Index(undefined, {}), "", { bundleName: "com.example.campusmate", moduleName: "entry", pagePath: "pages/Index", pageFullPath: "entry/src/main/ets/pages/Index", integratedHsp: "false", moduleType: "followWithHap" });
