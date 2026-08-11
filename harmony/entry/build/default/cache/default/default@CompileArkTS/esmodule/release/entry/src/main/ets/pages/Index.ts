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
    constructor(f18, g18, h18, i18 = -1, j18 = undefined, k18) {
        super(f18, h18, i18, k18);
        if (typeof j18 === "function") {
            this.paramsGenerator_ = j18;
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
        this.setInitiallyProvidedValue(g18);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(e18: Index_Params) {
        if (e18.appState !== undefined) {
            this.appState = e18.appState;
        }
        if (e18.signedIn !== undefined) {
            this.signedIn = e18.signedIn;
        }
        if (e18.darkMode !== undefined) {
            this.darkMode = e18.darkMode;
        }
        if (e18.reduceMotion !== undefined) {
            this.reduceMotion = e18.reduceMotion;
        }
        if (e18.activeTab !== undefined) {
            this.activeTab = e18.activeTab;
        }
        if (e18.route !== undefined) {
            this.route = e18.route;
        }
        if (e18.username !== undefined) {
            this.username = e18.username;
        }
        if (e18.password !== undefined) {
            this.password = e18.password;
        }
        if (e18.loginError !== undefined) {
            this.loginError = e18.loginError;
        }
        if (e18.loginLoading !== undefined) {
            this.loginLoading = e18.loginLoading;
        }
        if (e18.primaryLoading !== undefined) {
            this.primaryLoading = e18.primaryLoading;
        }
        if (e18.courses !== undefined) {
            this.courses = e18.courses;
        }
        if (e18.tasks !== undefined) {
            this.tasks = e18.tasks;
        }
        if (e18.chatMessages !== undefined) {
            this.chatMessages = e18.chatMessages;
        }
        if (e18.chatInput !== undefined) {
            this.chatInput = e18.chatInput;
        }
        if (e18.chatSending !== undefined) {
            this.chatSending = e18.chatSending;
        }
        if (e18.displayName !== undefined) {
            this.displayName = e18.displayName;
        }
        if (e18.profileDetail !== undefined) {
            this.profileDetail = e18.profileDetail;
        }
        if (e18.secondaryLoading !== undefined) {
            this.secondaryLoading = e18.secondaryLoading;
        }
        if (e18.secondarySubmitting !== undefined) {
            this.secondarySubmitting = e18.secondarySubmitting;
        }
        if (e18.exams !== undefined) {
            this.exams = e18.exams;
        }
        if (e18.classrooms !== undefined) {
            this.classrooms = e18.classrooms;
        }
        if (e18.serviceRequests !== undefined) {
            this.serviceRequests = e18.serviceRequests;
        }
        if (e18.lostFoundItems !== undefined) {
            this.lostFoundItems = e18.lostFoundItems;
        }
        if (e18.studySessions !== undefined) {
            this.studySessions = e18.studySessions;
        }
        if (e18.activeStudySession !== undefined) {
            this.activeStudySession = e18.activeStudySession;
        }
        if (e18.notices !== undefined) {
            this.notices = e18.notices;
        }
        if (e18.personalFiles !== undefined) {
            this.personalFiles = e18.personalFiles;
        }
        if (e18.activities !== undefined) {
            this.activities = e18.activities;
        }
        if (e18.favorites !== undefined) {
            this.favorites = e18.favorites;
        }
        if (e18.backendOnline !== undefined) {
            this.backendOnline = e18.backendOnline;
        }
    }
    updateStateVars(d18: Index_Params) {
    }
    purgeVariableDependenciesOnElmtId(c18) {
        this.__signedIn.purgeDependencyOnElmtId(c18);
        this.__darkMode.purgeDependencyOnElmtId(c18);
        this.__reduceMotion.purgeDependencyOnElmtId(c18);
        this.__activeTab.purgeDependencyOnElmtId(c18);
        this.__route.purgeDependencyOnElmtId(c18);
        this.__username.purgeDependencyOnElmtId(c18);
        this.__password.purgeDependencyOnElmtId(c18);
        this.__loginError.purgeDependencyOnElmtId(c18);
        this.__loginLoading.purgeDependencyOnElmtId(c18);
        this.__primaryLoading.purgeDependencyOnElmtId(c18);
        this.__courses.purgeDependencyOnElmtId(c18);
        this.__tasks.purgeDependencyOnElmtId(c18);
        this.__chatMessages.purgeDependencyOnElmtId(c18);
        this.__chatInput.purgeDependencyOnElmtId(c18);
        this.__chatSending.purgeDependencyOnElmtId(c18);
        this.__displayName.purgeDependencyOnElmtId(c18);
        this.__profileDetail.purgeDependencyOnElmtId(c18);
        this.__secondaryLoading.purgeDependencyOnElmtId(c18);
        this.__secondarySubmitting.purgeDependencyOnElmtId(c18);
        this.__exams.purgeDependencyOnElmtId(c18);
        this.__classrooms.purgeDependencyOnElmtId(c18);
        this.__serviceRequests.purgeDependencyOnElmtId(c18);
        this.__lostFoundItems.purgeDependencyOnElmtId(c18);
        this.__studySessions.purgeDependencyOnElmtId(c18);
        this.__activeStudySession.purgeDependencyOnElmtId(c18);
        this.__notices.purgeDependencyOnElmtId(c18);
        this.__personalFiles.purgeDependencyOnElmtId(c18);
        this.__activities.purgeDependencyOnElmtId(c18);
        this.__favorites.purgeDependencyOnElmtId(c18);
        this.__backendOnline.purgeDependencyOnElmtId(c18);
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
    set signedIn(b18: boolean) {
        this.__signedIn.set(b18);
    }
    private __darkMode: ObservedPropertySimplePU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(a18: boolean) {
        this.__darkMode.set(a18);
    }
    private __reduceMotion: ObservedPropertySimplePU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(z17: boolean) {
        this.__reduceMotion.set(z17);
    }
    private __activeTab: ObservedPropertySimplePU<number>;
    get activeTab() {
        return this.__activeTab.get();
    }
    set activeTab(y17: number) {
        this.__activeTab.set(y17);
    }
    private __route: ObservedPropertySimplePU<string>;
    get route() {
        return this.__route.get();
    }
    set route(x17: string) {
        this.__route.set(x17);
    }
    private __username: ObservedPropertySimplePU<string>;
    get username() {
        return this.__username.get();
    }
    set username(w17: string) {
        this.__username.set(w17);
    }
    private __password: ObservedPropertySimplePU<string>;
    get password() {
        return this.__password.get();
    }
    set password(v17: string) {
        this.__password.set(v17);
    }
    private __loginError: ObservedPropertySimplePU<string>;
    get loginError() {
        return this.__loginError.get();
    }
    set loginError(u17: string) {
        this.__loginError.set(u17);
    }
    private __loginLoading: ObservedPropertySimplePU<boolean>;
    get loginLoading() {
        return this.__loginLoading.get();
    }
    set loginLoading(t17: boolean) {
        this.__loginLoading.set(t17);
    }
    private __primaryLoading: ObservedPropertySimplePU<boolean>;
    get primaryLoading() {
        return this.__primaryLoading.get();
    }
    set primaryLoading(s17: boolean) {
        this.__primaryLoading.set(s17);
    }
    private __courses: ObservedPropertyObjectPU<CourseItem[]>;
    get courses() {
        return this.__courses.get();
    }
    set courses(r17: CourseItem[]) {
        this.__courses.set(r17);
    }
    private __tasks: ObservedPropertyObjectPU<TaskItem[]>;
    get tasks() {
        return this.__tasks.get();
    }
    set tasks(q17: TaskItem[]) {
        this.__tasks.set(q17);
    }
    private __chatMessages: ObservedPropertyObjectPU<ChatMessage[]>;
    get chatMessages() {
        return this.__chatMessages.get();
    }
    set chatMessages(p17: ChatMessage[]) {
        this.__chatMessages.set(p17);
    }
    private __chatInput: ObservedPropertySimplePU<string>;
    get chatInput() {
        return this.__chatInput.get();
    }
    set chatInput(o17: string) {
        this.__chatInput.set(o17);
    }
    private __chatSending: ObservedPropertySimplePU<boolean>;
    get chatSending() {
        return this.__chatSending.get();
    }
    set chatSending(n17: boolean) {
        this.__chatSending.set(n17);
    }
    private __displayName: ObservedPropertySimplePU<string>;
    get displayName() {
        return this.__displayName.get();
    }
    set displayName(m17: string) {
        this.__displayName.set(m17);
    }
    private __profileDetail: ObservedPropertySimplePU<string>;
    get profileDetail() {
        return this.__profileDetail.get();
    }
    set profileDetail(l17: string) {
        this.__profileDetail.set(l17);
    }
    private __secondaryLoading: ObservedPropertySimplePU<boolean>;
    get secondaryLoading() {
        return this.__secondaryLoading.get();
    }
    set secondaryLoading(k17: boolean) {
        this.__secondaryLoading.set(k17);
    }
    private __secondarySubmitting: ObservedPropertySimplePU<boolean>;
    get secondarySubmitting() {
        return this.__secondarySubmitting.get();
    }
    set secondarySubmitting(j17: boolean) {
        this.__secondarySubmitting.set(j17);
    }
    private __exams: ObservedPropertyObjectPU<ExamItem[]>;
    get exams() {
        return this.__exams.get();
    }
    set exams(i17: ExamItem[]) {
        this.__exams.set(i17);
    }
    private __classrooms: ObservedPropertyObjectPU<ClassroomAvailability[]>;
    get classrooms() {
        return this.__classrooms.get();
    }
    set classrooms(h17: ClassroomAvailability[]) {
        this.__classrooms.set(h17);
    }
    private __serviceRequests: ObservedPropertyObjectPU<ServiceRequestItem[]>;
    get serviceRequests() {
        return this.__serviceRequests.get();
    }
    set serviceRequests(g17: ServiceRequestItem[]) {
        this.__serviceRequests.set(g17);
    }
    private __lostFoundItems: ObservedPropertyObjectPU<LostFoundItem[]>;
    get lostFoundItems() {
        return this.__lostFoundItems.get();
    }
    set lostFoundItems(f17: LostFoundItem[]) {
        this.__lostFoundItems.set(f17);
    }
    private __studySessions: ObservedPropertyObjectPU<StudySession[]>;
    get studySessions() {
        return this.__studySessions.get();
    }
    set studySessions(e17: StudySession[]) {
        this.__studySessions.set(e17);
    }
    private __activeStudySession?: ObservedPropertyObjectPU<StudySession>;
    get activeStudySession() {
        return this.__activeStudySession.get();
    }
    set activeStudySession(d17: StudySession) {
        this.__activeStudySession.set(d17);
    }
    private __notices: ObservedPropertyObjectPU<NoticeItem[]>;
    get notices() {
        return this.__notices.get();
    }
    set notices(c17: NoticeItem[]) {
        this.__notices.set(c17);
    }
    private __personalFiles: ObservedPropertyObjectPU<PersonalFileItem[]>;
    get personalFiles() {
        return this.__personalFiles.get();
    }
    set personalFiles(b17: PersonalFileItem[]) {
        this.__personalFiles.set(b17);
    }
    private __activities: ObservedPropertyObjectPU<ActivityItem[]>;
    get activities() {
        return this.__activities.get();
    }
    set activities(a17: ActivityItem[]) {
        this.__activities.set(a17);
    }
    private __favorites: ObservedPropertyObjectPU<FavoriteItem[]>;
    get favorites() {
        return this.__favorites.get();
    }
    set favorites(z16: FavoriteItem[]) {
        this.__favorites.set(z16);
    }
    private __backendOnline: ObservedPropertySimplePU<boolean>;
    get backendOnline() {
        return this.__backendOnline.get();
    }
    set backendOnline(y16: boolean) {
        this.__backendOnline.set(y16);
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
            const w16 = new ApiClient(API_BASE_URL, () => '');
            const x16 = await w16.login(this.username.trim(), this.password);
            this.appState.signIn(x16);
            this.signedIn = true;
            this.loginError = '';
            await this.refreshPrimaryData();
        }
        catch (v16) {
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
        const o16 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            const q16 = await o16.request<MeResponse>(http.RequestMethod.GET, 'auth/me');
            this.displayName = q16.user.display_name ?? q16.user.name ?? q16.user.username ?? '林知夏';
            const r16: string[] = [];
            if (q16.user.major !== undefined && q16.user.major.length > 0) {
                r16.push(q16.user.major);
            }
            if (q16.user.grade !== undefined && q16.user.grade.length > 0) {
                r16.push(`${q16.user.grade}级`);
            }
            if (r16.length > 0) {
                this.profileDetail = r16.join(' · ');
            }
            const s16 = await o16.request<PagedResponse<CourseItem>>(http.RequestMethod.GET, 'courses?page=1&page_size=100');
            this.courses = s16.items;
            const t16 = await o16.request<PagedResponse<TaskItem>>(http.RequestMethod.GET, 'tasks?page=1&page_size=200');
            this.tasks = t16.items;
            const u16 = await o16.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=20');
            this.notices = u16.items;
            this.backendOnline = true;
        }
        catch (p16) {
            this.backendOnline = false;
        }
        finally {
            this.primaryLoading = false;
        }
    }
    async toggleTask(l16: TaskItem): Promise<void> {
        const m16 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            await m16.request<TaskItem>(http.RequestMethod.POST, l16.status === 'completed' ? `tasks/${l16.id}/restore` : `tasks/${l16.id}/complete`);
            await this.refreshPrimaryData();
        }
        catch (n16) {
        }
    }
    async sendChat(): Promise<void> {
        const d16 = this.chatInput.trim();
        if (d16.length === 0 || this.chatSending) {
            return;
        }
        const e16: ChatMessage = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: d16
        };
        this.chatMessages = [...this.chatMessages, e16];
        this.chatInput = '';
        this.chatSending = true;
        const f16 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            const i16: ChatRequest = {
                message: d16,
                session_id: 'harmony-session',
                stream: false
            };
            const j16 = await f16.request<ChatResponse>(http.RequestMethod.POST, 'counselor/chat', i16);
            const k16: ChatMessage = {
                id: `assistant-${Date.now()}`,
                role: 'assistant',
                content: j16.answer ?? j16.message ?? '暂时没有找到合适的回答，请稍后再试。'
            };
            this.chatMessages = [...this.chatMessages, k16];
        }
        catch (g16) {
            const h16: ChatMessage = {
                id: `assistant-error-${Date.now()}`,
                role: 'assistant',
                content: '暂时无法连接校园知识库，请检查网络后重试。'
            };
            this.chatMessages = [...this.chatMessages, h16];
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
    navigateTo(c16: string): void {
        if (c16 === 'courses') {
            this.route = '';
            this.activeTab = 1;
            return;
        }
        if (c16 === 'tasks') {
            this.route = '';
            this.activeTab = 2;
            return;
        }
        if (c16 === 'counselor') {
            this.route = '';
            this.activeTab = 3;
            return;
        }
        if (c16 === 'profile') {
            this.route = '';
            this.activeTab = 4;
            return;
        }
        this.route = c16;
        this.refreshSecondaryData(c16);
    }
    async refreshSecondaryData(w15: string): Promise<void> {
        if (this.secondaryLoading || this.appState.sessionToken.length === 0)
            return;
        this.secondaryLoading = true;
        const x15 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
        try {
            if (w15 === 'exams') {
                this.exams = await x15.request<ExamItem[]>(http.RequestMethod.GET, 'student/exams');
            }
            else if (w15 === 'classrooms') {
                const b16 = await x15.request<ClassroomResponse>(http.RequestMethod.GET, 'student/classrooms');
                this.classrooms = b16.items;
            }
            else if (w15 === 'services') {
                this.serviceRequests = await x15.request<ServiceRequestItem[]>(http.RequestMethod.GET, 'student/service-requests');
            }
            else if (w15 === 'lostfound') {
                this.lostFoundItems = await x15.request<LostFoundItem[]>(http.RequestMethod.GET, 'student/lost-found');
            }
            else if (w15 === 'focus') {
                this.studySessions = await x15.request<StudySession[]>(http.RequestMethod.GET, 'study/sessions?page=1&page_size=20');
                this.activeStudySession = await x15.request<StudySession | undefined>(http.RequestMethod.GET, 'study/sessions/active');
            }
            else if (w15 === 'notifications') {
                const a16 = await x15.request<PagedResponse<NoticeItem>>(http.RequestMethod.GET, 'notices?page=1&page_size=100');
                this.notices = a16.items;
            }
            else if (w15 === 'files') {
                this.personalFiles = await x15.request<PersonalFileItem[]>(http.RequestMethod.GET, 'personal-hub/files');
            }
            else if (w15 === 'activities') {
                const z15 = await x15.request<PagedResponse<ActivityItem>>(http.RequestMethod.GET, 'activities?page=1&page_size=100');
                this.activities = z15.items;
            }
            else if (w15 === 'favorites') {
                this.favorites = await x15.request<FavoriteItem[]>(http.RequestMethod.GET, 'personal-hub/favorites');
            }
        }
        catch (y15) {
            this.backendOnline = false;
        }
        finally {
            this.secondaryLoading = false;
        }
    }
    async createServiceRequest(q15: string, r15: string, s15: string): Promise<void> {
        const t15: ServiceRequestPayload = { kind: q15, title: r15, content: s15 };
        this.secondarySubmitting = true;
        try {
            const v15 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            await v15.request<ServiceRequestItem>(http.RequestMethod.POST, 'student/service-requests', t15);
            await this.refreshSecondaryData('services');
        }
        catch (u15) {
        }
        finally {
            this.secondarySubmitting = false;
        }
    }
    async publishLostFound(i15: string, j15: string, k15: string, l15: string, m15: string): Promise<void> {
        const n15: LostFoundPayload = { kind: i15, title: j15, content: k15, location: l15, contact: m15 };
        this.secondarySubmitting = true;
        try {
            const p15 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            await p15.request<LostFoundItem>(http.RequestMethod.POST, 'student/lost-found', n15);
            await this.refreshSecondaryData('lostfound');
        }
        catch (o15) {
        }
        finally {
            this.secondarySubmitting = false;
        }
    }
    async startFocusSession(): Promise<void> {
        if (this.activeStudySession !== undefined)
            return;
        const f15: StudySessionCreate = { goal: '完成一段专注学习' };
        try {
            const h15 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            this.activeStudySession = await h15.request<StudySession>(http.RequestMethod.POST, 'study/sessions', f15);
        }
        catch (g15) {
        }
    }
    async updateFocusSession(b15: string): Promise<void> {
        if (this.activeStudySession === undefined)
            return;
        try {
            const d15 = new ApiClient(API_BASE_URL, () => this.appState.sessionToken);
            if (b15 === 'finish') {
                const e15: StudySessionFinish = { self_report: '鸿蒙端完成专注' };
                await d15.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/finish`, e15);
                this.activeStudySession = undefined;
            }
            else {
                this.activeStudySession = await d15.request<StudySession>(http.RequestMethod.POST, `study/sessions/${this.activeStudySession.id}/${b15}`);
            }
            await this.refreshSecondaryData('focus');
        }
        catch (c15) {
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
    Header(k14: string, l14: string, m14 = null) {
        this.observeComponentCreation2((z14, a15) => {
            Row.create();
            Row.width('100%');
            Row.padding({ left: 20, right: 20, top: 18, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((x14, y14) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
        }, Column);
        this.observeComponentCreation2((v14, w14) => {
            Text.create(k14);
            Text.fontSize(25);
            Text.fontWeight(FontWeight.Bold);
            Text.fontColor(this.textColor());
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t14, u14) => {
            Text.create(l14);
            Text.fontSize(13);
            Text.fontColor(this.mutedColor());
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((n14, o14) => {
            If.create();
            if (this.darkMode) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((r14, s14) => {
                        SymbolGlyph.create({ "id": 125832513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(23);
                        SymbolGlyph.fontColor([this.primaryColor()]);
                        SymbolGlyph.onClick(() => this.toggleTheme());
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((p14, q14) => {
                        SymbolGlyph.create({ "id": 125831540, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
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
    LoginPage(f14 = null) {
        {
            this.observeComponentCreation2((g14, h14) => {
                if (h14) {
                    let i14 = new LoginScreen(this, {
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
                    }, undefined, g14, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 318, col: 5 });
                    ViewPU.create(i14);
                    let j14 = () => {
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
                    i14.paramsGenerator_ = j14;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(g14, {
                        loading: this.loginLoading,
                        error: this.loginError,
                        reduceMotion: this.reduceMotion
                    });
                }
            }, { name: "LoginScreen" });
        }
    }
    Tile(w13: string, x13: string, y13 = null) {
        this.observeComponentCreation2((d14, e14) => {
            Column.create({ space: 8 });
            Column.alignItems(HorizontalAlign.Center);
            Column.padding(14);
            Column.backgroundColor(this.softColor());
            Column.borderRadius(16);
            Column.width('31%');
            Column.onClick(() => this.route = x13);
        }, Column);
        this.observeComponentCreation2((b14, c14) => {
            Text.create(w13);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Medium);
            Text.fontColor(this.textColor());
        }, Text);
        Text.pop();
        this.observeComponentCreation2((z13, a14) => {
            Text.create('进入功能');
            Text.fontSize(12);
            Text.fontColor(this.primaryColor());
        }, Text);
        Text.pop();
        Column.pop();
    }
    HomePage(p13 = null) {
        {
            this.observeComponentCreation2((q13, r13) => {
                if (r13) {
                    let s13 = new DashboardPage(this, {
                        darkMode: this.darkMode,
                        userName: this.displayName,
                        courses: this.courses,
                        tasks: this.tasks,
                        notices: this.notices,
                        onNavigate: (v13: string) => {
                            this.navigateTo(v13);
                        }
                    }, undefined, q13, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 341, col: 5 });
                    ViewPU.create(s13);
                    let t13 = () => {
                        return {
                            darkMode: this.darkMode,
                            userName: this.displayName,
                            courses: this.courses,
                            tasks: this.tasks,
                            notices: this.notices,
                            onNavigate: (u13: string) => {
                                this.navigateTo(u13);
                            }
                        };
                    };
                    s13.paramsGenerator_ = t13;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(q13, {
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
    ListPage(c13: string, d13: string, e13 = null) {
        this.observeComponentCreation2((n13, o13) => {
            Column.create();
        }, Column);
        this.Header.bind(this)(c13, d13);
        this.observeComponentCreation2((l13, m13) => {
            Scroll.create();
            Scroll.layoutWeight(1);
        }, Scroll);
        this.observeComponentCreation2((j13, k13) => {
            Column.create({ space: 10 });
            Column.padding(20);
        }, Column);
        this.observeComponentCreation2((h13, i13) => {
            Button.createWithLabel('查看最新校园数据');
            Button.width('100%');
            Button.height(54);
            Button.backgroundColor(this.surface());
            Button.fontColor(this.textColor());
        }, Button);
        Button.pop();
        this.observeComponentCreation2((f13, g13) => {
            Button.createWithLabel('刷新');
            Button.width('100%');
            Button.backgroundColor(this.primaryColor());
            Button.fontColor('#FFFFFF');
        }, Button);
        Button.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    ProfileTab(v12 = null) {
        {
            this.observeComponentCreation2((w12, x12) => {
                if (x12) {
                    let y12 = new ProfilePage(this, {
                        darkMode: this.darkMode,
                        name: this.displayName,
                        detail: this.profileDetail,
                        onNavigate: (b13: string) => {
                            if (b13 === 'counselor') {
                                this.route = '';
                                this.activeTab = 3;
                            }
                            else {
                                this.navigateTo(b13);
                            }
                        }
                    }, undefined, w12, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 366, col: 5 });
                    ViewPU.create(y12);
                    let z12 = () => {
                        return {
                            darkMode: this.darkMode,
                            name: this.displayName,
                            detail: this.profileDetail,
                            onNavigate: (a13: string) => {
                                if (a13 === 'counselor') {
                                    this.route = '';
                                    this.activeTab = 3;
                                }
                                else {
                                    this.navigateTo(a13);
                                }
                            }
                        };
                    };
                    y12.paramsGenerator_ = z12;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(w12, {
                        darkMode: this.darkMode,
                        name: this.displayName,
                        detail: this.profileDetail
                    });
                }
            }, { name: "ProfilePage" });
        }
    }
    SecondaryPage(u9 = null) {
        this.observeComponentCreation2((v9, w9) => {
            If.create();
            if (this.route === 'exams') {
                this.ifElseBranchUpdateFunction(0, () => {
                    {
                        this.observeComponentCreation2((r12, s12) => {
                            if (s12) {
                                let t12 = new ExamsPage(this, { exams: this.exams, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('exams') }, undefined, r12, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 383, col: 7 });
                                ViewPU.create(t12);
                                let u12 = () => {
                                    return {
                                        exams: this.exams,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('exams')
                                    };
                                };
                                t12.paramsGenerator_ = u12;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(r12, {
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
                        this.observeComponentCreation2((n12, o12) => {
                            if (o12) {
                                let p12 = new ClassroomsPage(this, { classrooms: this.classrooms, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onQuery: () => this.refreshSecondaryData('classrooms') }, undefined, n12, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 385, col: 7 });
                                ViewPU.create(p12);
                                let q12 = () => {
                                    return {
                                        classrooms: this.classrooms,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onQuery: () => this.refreshSecondaryData('classrooms')
                                    };
                                };
                                p12.paramsGenerator_ = q12;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(n12, {
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
                        this.observeComponentCreation2((d12, e12) => {
                            if (e12) {
                                let f12 = new ServicesPage(this, { requests: this.serviceRequests, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('services'), onSubmit: (k12: string, l12: string, m12: string) => this.createServiceRequest(k12, l12, m12) }, undefined, d12, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 387, col: 7 });
                                ViewPU.create(f12);
                                let g12 = () => {
                                    return {
                                        requests: this.serviceRequests,
                                        loading: this.secondaryLoading,
                                        submitting: this.secondarySubmitting,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('services'),
                                        onSubmit: (h12: string, i12: string, j12: string) => this.createServiceRequest(h12, i12, j12)
                                    };
                                };
                                f12.paramsGenerator_ = g12;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(d12, {
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
                        this.observeComponentCreation2((z11, a12) => {
                            if (a12) {
                                let b12 = new FocusPage(this, { sessions: this.studySessions, activeSession: this.activeStudySession, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onStart: () => this.startFocusSession(), onPause: () => this.updateFocusSession('pause'), onResume: () => this.updateFocusSession('resume'), onFinish: () => this.updateFocusSession('finish') }, undefined, z11, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 389, col: 7 });
                                ViewPU.create(b12);
                                let c12 = () => {
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
                                b12.paramsGenerator_ = c12;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(z11, {
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
                        this.observeComponentCreation2((j11, k11) => {
                            if (k11) {
                                let l11 = new LostFoundPage(this, { items: this.lostFoundItems, loading: this.secondaryLoading, submitting: this.secondarySubmitting, darkMode: this.darkMode, onBack: () => this.route = '', onFilter: (y11: string) => this.refreshSecondaryData('lostfound'), onSubmit: (t11: string, u11: string, v11: string, w11: string, x11: string) => this.publishLostFound(t11, u11, v11, w11, x11) }, undefined, j11, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 391, col: 7 });
                                ViewPU.create(l11);
                                let m11 = () => {
                                    return {
                                        items: this.lostFoundItems,
                                        loading: this.secondaryLoading,
                                        submitting: this.secondarySubmitting,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onFilter: (s11: string) => this.refreshSecondaryData('lostfound'),
                                        onSubmit: (n11: string, o11: string, p11: string, q11: string, r11: string) => this.publishLostFound(n11, o11, p11, q11, r11)
                                    };
                                };
                                l11.paramsGenerator_ = m11;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(j11, {
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
                        this.observeComponentCreation2((f11, g11) => {
                            if (g11) {
                                let h11 = new NotificationsPage(this, { notices: this.notices, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData('notifications') }, undefined, f11, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 393, col: 7 });
                                ViewPU.create(h11);
                                let i11 = () => {
                                    return {
                                        notices: this.notices,
                                        loading: this.secondaryLoading,
                                        darkMode: this.darkMode,
                                        onBack: () => this.route = '',
                                        onRefresh: () => this.refreshSecondaryData('notifications')
                                    };
                                };
                                h11.paramsGenerator_ = i11;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(f11, {
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
                        this.observeComponentCreation2((b11, c11) => {
                            if (c11) {
                                let d11 = new PersonalHubPage(this, { section: this.route, files: this.personalFiles, activities: this.activities, favorites: this.favorites, loading: this.secondaryLoading, darkMode: this.darkMode, onBack: () => this.route = '', onRefresh: () => this.refreshSecondaryData(this.route) }, undefined, b11, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 395, col: 7 });
                                ViewPU.create(d11);
                                let e11 = () => {
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
                                d11.paramsGenerator_ = e11;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(b11, {
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
                        this.observeComponentCreation2((r10, s10) => {
                            if (s10) {
                                let t10 = new SettingsPage(this, { darkMode: this.darkMode, reduceMotion: this.reduceMotion, backendOnline: this.backendOnline, onBack: () => this.route = '', onThemeChange: (a11: boolean) => {
                                        if (a11 !== this.darkMode)
                                            this.toggleTheme();
                                    }, onMotionChange: (z10: boolean) => { this.appState.setReduceMotion(z10); this.reduceMotion = z10; }, onNavigate: (y10: string) => this.navigateTo(y10) }, undefined, r10, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 397, col: 7 });
                                ViewPU.create(t10);
                                let u10 = () => {
                                    return {
                                        darkMode: this.darkMode,
                                        reduceMotion: this.reduceMotion,
                                        backendOnline: this.backendOnline,
                                        onBack: () => this.route = '',
                                        onThemeChange: (x10: boolean) => {
                                            if (x10 !== this.darkMode)
                                                this.toggleTheme();
                                        },
                                        onMotionChange: (w10: boolean) => { this.appState.setReduceMotion(w10); this.reduceMotion = w10; },
                                        onNavigate: (v10: string) => this.navigateTo(v10)
                                    };
                                };
                                t10.paramsGenerator_ = u10;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(r10, {
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
                        this.observeComponentCreation2((n10, o10) => {
                            if (o10) {
                                let p10 = new AccountPage(this, { darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail, onBack: () => this.route = '', onSignOut: () => this.signOut() }, undefined, n10, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 399, col: 7 });
                                ViewPU.create(p10);
                                let q10 = () => {
                                    return {
                                        darkMode: this.darkMode,
                                        name: this.displayName,
                                        detail: this.profileDetail,
                                        onBack: () => this.route = '',
                                        onSignOut: () => this.signOut()
                                    };
                                };
                                p10.paramsGenerator_ = q10;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(n10, {
                                    darkMode: this.darkMode, name: this.displayName, detail: this.profileDetail
                                });
                            }
                        }, { name: "AccountPage" });
                    }
                });
            }
            else {
                this.ifElseBranchUpdateFunction(9, () => {
                    this.observeComponentCreation2((l10, m10) => {
                        Column.create();
                    }, Column);
                    this.observeComponentCreation2((j10, k10) => {
                        Row.create({ space: 12 });
                        Row.padding(20);
                    }, Row);
                    this.observeComponentCreation2((h10, i10) => {
                        SymbolGlyph.create({ "id": 125832679, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(22);
                        SymbolGlyph.fontColor([this.textColor()]);
                        SymbolGlyph.onClick(() => this.route = '');
                    }, SymbolGlyph);
                    this.observeComponentCreation2((f10, g10) => {
                        Text.create(this.routeTitle());
                        Text.fontSize(22);
                        Text.fontWeight(FontWeight.Bold);
                        Text.fontColor(this.textColor());
                    }, Text);
                    Text.pop();
                    Row.pop();
                    this.observeComponentCreation2((d10, e10) => {
                        Column.create({ space: 12 });
                        Column.width('100%');
                        Column.padding(28);
                    }, Column);
                    this.observeComponentCreation2((b10, c10) => {
                        SymbolGlyph.create({ "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(38);
                        SymbolGlyph.fontColor([this.primaryColor()]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((z9, a10) => {
                        Text.create('面向大学生的校园事务智能陪伴助手。');
                        Text.fontColor(this.textColor());
                        Text.fontSize(15);
                        Text.textAlign(TextAlign.Center);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((x9, y9) => {
                        Text.create('AI 校园助手的回答仅作校园事务辅助，学校正式通知为准。');
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
    MainContent(z8 = null) {
        this.observeComponentCreation2((a9, b9) => {
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
                        this.observeComponentCreation2((q9, r9) => {
                            if (r9) {
                                let s9 = new CoursesPage(this, { courses: this.courses, loading: this.primaryLoading, darkMode: this.darkMode, onRefresh: () => this.refreshPrimaryData() }, undefined, q9, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 419, col: 7 });
                                ViewPU.create(s9);
                                let t9 = () => {
                                    return {
                                        courses: this.courses,
                                        loading: this.primaryLoading,
                                        darkMode: this.darkMode,
                                        onRefresh: () => this.refreshPrimaryData()
                                    };
                                };
                                s9.paramsGenerator_ = t9;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(q9, {
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
                        this.observeComponentCreation2((g9, h9) => {
                            if (h9) {
                                let i9 = new TasksPage(this, {
                                    tasks: this.tasks,
                                    loading: this.primaryLoading,
                                    darkMode: this.darkMode,
                                    onRefresh: () => this.refreshPrimaryData(),
                                    onComplete: (n9: string) => {
                                        const o9 = this.tasks.find((p9: TaskItem) => p9.id === n9);
                                        if (o9 !== undefined) {
                                            this.toggleTask(o9);
                                        }
                                    }
                                }, undefined, g9, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 422, col: 7 });
                                ViewPU.create(i9);
                                let j9 = () => {
                                    return {
                                        tasks: this.tasks,
                                        loading: this.primaryLoading,
                                        darkMode: this.darkMode,
                                        onRefresh: () => this.refreshPrimaryData(),
                                        onComplete: (k9: string) => {
                                            const l9 = this.tasks.find((m9: TaskItem) => m9.id === k9);
                                            if (l9 !== undefined) {
                                                this.toggleTask(l9);
                                            }
                                        }
                                    };
                                };
                                i9.paramsGenerator_ = j9;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(g9, {
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
                        this.observeComponentCreation2((c9, d9) => {
                            if (d9) {
                                let e9 = new CounselorPage(this, {
                                    messages: this.chatMessages,
                                    sending: this.chatSending,
                                    darkMode: this.darkMode,
                                    input: this.__chatInput,
                                    onSend: () => this.sendChat()
                                }, undefined, c9, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 436, col: 7 });
                                ViewPU.create(e9);
                                let f9 = () => {
                                    return {
                                        messages: this.chatMessages,
                                        sending: this.chatSending,
                                        darkMode: this.darkMode,
                                        input: this.chatInput,
                                        onSend: () => this.sendChat()
                                    };
                                };
                                e9.paramsGenerator_ = f9;
                            }
                            else {
                                this.updateStateVarsOfChildByElmtId(c9, {
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
    BottomNavigation(p8 = null) {
        {
            this.observeComponentCreation2((q8, r8) => {
                if (r8) {
                    let t8 = new AppDock(this, {
                        activeTab: this.activeTab,
                        darkMode: this.darkMode,
                        pendingCount: this.tasks.filter((y8: TaskItem) => y8.status !== 'completed').length,
                        onNavigate: (x8: number) => {
                            this.route = '';
                            this.activeTab = x8;
                        }
                    }, undefined, q8, () => { }, { page: "entry/src/main/ets/pages/Index.ets", line: 448, col: 5 });
                    ViewPU.create(t8);
                    let u8 = () => {
                        return {
                            activeTab: this.activeTab,
                            darkMode: this.darkMode,
                            pendingCount: this.tasks.filter((w8: TaskItem) => w8.status !== 'completed').length,
                            onNavigate: (v8: number) => {
                                this.route = '';
                                this.activeTab = v8;
                            }
                        };
                    };
                    t8.paramsGenerator_ = u8;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(q8, {
                        activeTab: this.activeTab,
                        darkMode: this.darkMode,
                        pendingCount: this.tasks.filter((s8: TaskItem) => s8.status !== 'completed').length
                    });
                }
            }, { name: "AppDock" });
        }
    }
    initialRender() {
        this.observeComponentCreation2((j8, k8) => {
            If.create();
            if (this.signedIn) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((n8, o8) => {
                        Stack.create({ alignContent: Alignment.Bottom });
                        Stack.width('100%');
                        Stack.height('100%');
                        Stack.backgroundColor(this.pageBackground());
                    }, Stack);
                    this.MainContent.bind(this)();
                    this.observeComponentCreation2((l8, m8) => {
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
