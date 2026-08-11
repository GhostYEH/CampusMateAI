if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface DashboardPage_Params {
    darkMode?: boolean;
    userName?: string;
    courses?: CourseItem[];
    tasks?: TaskItem[];
    notices?: NoticeItem[];
    onNavigate?: (route: string) => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CourseItem, NoticeItem, TaskItem } from '../../data/Models';
interface DashboardAction {
    title: string;
    route: string;
    symbol: Resource;
    color: string;
}
export class DashboardPage extends ViewPU {
    constructor(d8, e8, f8, g8 = -1, h8 = undefined, i8) {
        super(d8, f8, g8, i8);
        if (typeof h8 === "function") {
            this.paramsGenerator_ = h8;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(e8.darkMode, this, "darkMode");
        this.__userName = new SynchedPropertySimpleOneWayPU(e8.userName, this, "userName");
        this.__courses = new SynchedPropertyObjectOneWayPU(e8.courses, this, "courses");
        this.__tasks = new SynchedPropertyObjectOneWayPU(e8.tasks, this, "tasks");
        this.__notices = new SynchedPropertyObjectOneWayPU(e8.notices, this, "notices");
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(e8);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(c8: DashboardPage_Params) {
        if (c8.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (c8.userName === undefined) {
            this.__userName.set('林知夏');
        }
        if (c8.courses === undefined) {
            this.__courses.set([]);
        }
        if (c8.tasks === undefined) {
            this.__tasks.set([]);
        }
        if (c8.notices === undefined) {
            this.__notices.set([]);
        }
        if (c8.onNavigate !== undefined) {
            this.onNavigate = c8.onNavigate;
        }
    }
    updateStateVars(b8: DashboardPage_Params) {
        this.__darkMode.reset(b8.darkMode);
        this.__userName.reset(b8.userName);
        this.__courses.reset(b8.courses);
        this.__tasks.reset(b8.tasks);
        this.__notices.reset(b8.notices);
    }
    purgeVariableDependenciesOnElmtId(a8) {
        this.__darkMode.purgeDependencyOnElmtId(a8);
        this.__userName.purgeDependencyOnElmtId(a8);
        this.__courses.purgeDependencyOnElmtId(a8);
        this.__tasks.purgeDependencyOnElmtId(a8);
        this.__notices.purgeDependencyOnElmtId(a8);
    }
    aboutToBeDeleted() {
        this.__darkMode.aboutToBeDeleted();
        this.__userName.aboutToBeDeleted();
        this.__courses.aboutToBeDeleted();
        this.__tasks.aboutToBeDeleted();
        this.__notices.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(z7: boolean) {
        this.__darkMode.set(z7);
    }
    private __userName: SynchedPropertySimpleOneWayPU<string>;
    get userName() {
        return this.__userName.get();
    }
    set userName(y7: string) {
        this.__userName.set(y7);
    }
    private __courses: SynchedPropertySimpleOneWayPU<CourseItem[]>;
    get courses() {
        return this.__courses.get();
    }
    set courses(x7: CourseItem[]) {
        this.__courses.set(x7);
    }
    private __tasks: SynchedPropertySimpleOneWayPU<TaskItem[]>;
    get tasks() {
        return this.__tasks.get();
    }
    set tasks(w7: TaskItem[]) {
        this.__tasks.set(w7);
    }
    private __notices: SynchedPropertySimpleOneWayPU<NoticeItem[]>;
    get notices() {
        return this.__notices.get();
    }
    set notices(v7: NoticeItem[]) {
        this.__notices.set(v7);
    }
    private onNavigate: (route: string) => void;
    palette(): CampusPalette {
        return this.darkMode ? darkPalette : lightPalette;
    }
    SectionTitle(f7: string, g7: string, h7: string, i7 = null) {
        this.observeComponentCreation2((t7, u7) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((r7, s7) => {
            Text.create(f7);
            Text.fontColor(this.palette().text);
            Text.fontSize(18);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((p7, q7) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((n7, o7) => {
            Row.create({ space: 2 });
            Row.onClick(() => this.onNavigate(h7));
        }, Row);
        this.observeComponentCreation2((l7, m7) => {
            Text.create(g7);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10.5);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j7, k7) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(16);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
        Row.pop();
    }
    HeaderProfile(u6 = null) {
        this.observeComponentCreation2((d7, e7) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
            Row.onClick(() => this.onNavigate('profile'));
        }, Row);
        this.observeComponentCreation2((b7, c7) => {
            Image.create({ "id": 16777224, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width(42);
            Image.height(42);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(21);
            Image.border({ width: 2, color: this.palette().surface });
        }, Image);
        this.observeComponentCreation2((z6, a7) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 10 });
        }, Column);
        this.observeComponentCreation2((x6, y6) => {
            Text.create(this.userName);
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((v6, w6) => {
            Text.create('点击头像进入个人中心');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    ExamHero(r5 = null) {
        this.observeComponentCreation2((s6, t6) => {
            Stack.create();
            Stack.width('100%');
            Stack.height(188);
            Stack.borderRadius(26);
            Stack.clip(true);
            Stack.onClick(() => this.onNavigate('tasks'));
        }, Stack);
        this.observeComponentCreation2((q6, r6) => {
            Image.create({ "id": 16777222, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height('100%');
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((o6, p6) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.linearGradient({
                angle: 90,
                colors: [
                    ['#FA3449C7', 0.0],
                    ['#D15368E8', 0.55],
                    ['#2E5368E8', 1.0]
                ]
            });
        }, Column);
        Column.pop();
        this.observeComponentCreation2((m6, n6) => {
            Column.create();
            Column.width('72%');
            Column.height('100%');
            Column.justifyContent(FlexAlign.Center);
            Column.alignItems(HorizontalAlign.Start);
            Column.padding({ left: 22, right: 8, top: 20, bottom: 20 });
        }, Column);
        this.observeComponentCreation2((k6, l6) => {
            Text.create('期末考试周进行中');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(23);
            Text.fontWeight(FontWeight.Bold);
            Text.letterSpacing(-0.4);
            Text.lineHeight(28);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((i6, j6) => {
            Text.create('合理规划时间，稳住节奏，我们能赢。');
            Text.fontColor('#FFDCE5FF');
            Text.fontSize(12);
            Text.margin({ top: 7 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((g6, h6) => {
            Row.create({ space: 7 });
            Row.padding({ left: 15, right: 15, top: 9, bottom: 9 });
            Row.border({ width: 1, color: '#B8FFFFFF' });
            Row.borderRadius(18);
            Row.margin({ top: 19 });
        }, Row);
        this.observeComponentCreation2((e6, f6) => {
            Text.create('查看复习计划');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((c6, d6) => {
            SymbolGlyph.create({ "id": 125832680, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(15);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((a6, b6) => {
            Row.create({ space: 6 });
            Row.align(Alignment.Bottom);
            Row.margin({ bottom: 10 });
        }, Row);
        this.observeComponentCreation2((y5, z5) => {
            Circle.create();
            Circle.width(7);
            Circle.height(7);
            Circle.fill('#FFFFFFFF');
        }, Circle);
        this.observeComponentCreation2((w5, x5) => {
            Circle.create();
            Circle.width(6);
            Circle.height(6);
            Circle.fill('#6BFFFFFF');
        }, Circle);
        this.observeComponentCreation2((u5, v5) => {
            Circle.create();
            Circle.width(6);
            Circle.height(6);
            Circle.fill('#6BFFFFFF');
        }, Circle);
        this.observeComponentCreation2((s5, t5) => {
            Circle.create();
            Circle.width(6);
            Circle.height(6);
            Circle.fill('#6BFFFFFF');
        }, Circle);
        Row.pop();
        Stack.pop();
    }
    QuickActions(b5 = null) {
        this.observeComponentCreation2((p5, q5) => {
            Row.create();
            Row.width('100%');
            Row.padding({ left: 8, right: 8, top: 16, bottom: 16 });
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(24);
        }, Row);
        this.observeComponentCreation2((c5, d5) => {
            ForEach.create();
            const e5 = f5 => {
                const g5 = f5;
                this.observeComponentCreation2((n5, o5) => {
                    Column.create({ space: 8 });
                    Column.layoutWeight(1);
                    Column.alignItems(HorizontalAlign.Center);
                    Column.onClick(() => this.onNavigate(g5.route));
                }, Column);
                this.observeComponentCreation2((l5, m5) => {
                    Stack.create({ alignContent: Alignment.Center });
                    Stack.width(44);
                    Stack.height(44);
                    Stack.borderRadius(13);
                    Stack.backgroundColor(g5.color);
                }, Stack);
                this.observeComponentCreation2((j5, k5) => {
                    SymbolGlyph.create(g5.symbol);
                    SymbolGlyph.fontSize(24);
                    SymbolGlyph.fontColor(['#FFFFFFFF']);
                }, SymbolGlyph);
                Stack.pop();
                this.observeComponentCreation2((h5, i5) => {
                    Text.create(g5.title);
                    Text.fontColor(this.palette().text);
                    Text.fontSize(11);
                    Text.maxLines(1);
                }, Text);
                Text.pop();
                Column.pop();
            };
            this.forEachUpdateFunction(c5, [
                { title: '考试安排', route: 'exams', symbol: { "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, color: '#5B68F2' },
                { title: '空教室', route: 'classrooms', symbol: { "id": 125834063, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, color: '#397CEF' },
                { title: '办事大厅', route: 'services', symbol: { "id": 125835010, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, color: '#35B99A' },
                { title: '专注自习', route: 'focus', symbol: { "id": 125832304, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, color: '#FFA43A' },
                { title: '失物招领', route: 'lostfound', symbol: { "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, color: '#7C6BE8' }
            ], e5);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    CourseMeta(s4: Resource, t4: string, u4 = null) {
        this.observeComponentCreation2((z4, a5) => {
            Row.create({ space: 5 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((x4, y4) => {
            SymbolGlyph.create(s4);
            SymbolGlyph.fontSize(15);
            SymbolGlyph.fontColor(['#E0FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((v4, w4) => {
            Text.create(t4);
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
    }
    TimelineRow(b4: string, c4: string, d4: string, e4: boolean, f4 = null) {
        this.observeComponentCreation2((q4, r4) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
            Row.padding({ top: 12, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((o4, p4) => {
            Circle.create();
            Circle.width(9);
            Circle.height(9);
            Circle.fill(e4 ? '#FFFFFFFF' : '#FFFFFFFF');
            Circle.stroke('#FF5368E8');
            Circle.strokeWidth(1.5);
        }, Circle);
        this.observeComponentCreation2((m4, n4) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 9 });
        }, Column);
        this.observeComponentCreation2((k4, l4) => {
            Text.create(b4);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((i4, j4) => {
            Text.create(c4);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9.5);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((g4, h4) => {
            Text.create(d4);
            Text.fontColor(e4 ? '#FF5368E8' : this.palette().muted);
            Text.fontSize(9);
            Text.padding({ left: 7, right: 7, top: 5, bottom: 5 });
            Text.backgroundColor(this.palette().soft);
            Text.borderRadius(12);
        }, Text);
        Text.pop();
        Row.pop();
    }
    TodayCourseCard(i3 = null) {
        this.observeComponentCreation2((z3, a4) => {
            Column.create();
            Column.width('100%');
            Column.padding(16);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(24);
        }, Column);
        this.SectionTitle.bind(this)('今日课程', '查看全部', 'courses');
        this.observeComponentCreation2((x3, y3) => {
            Row.create({ space: 10 });
            Row.width('100%');
            Row.margin({ top: 13 });
        }, Row);
        this.observeComponentCreation2((v3, w3) => {
            Column.create();
            Column.layoutWeight(1.02);
            Column.height(166);
            Column.padding(15);
            Column.alignItems(HorizontalAlign.Start);
            Column.linearGradient({
                angle: 135,
                colors: [['#FF4259E8', 0.0], ['#FF7B78F7', 1.0]]
            });
            Column.borderRadius(18);
            Column.onClick(() => this.onNavigate('courses'));
        }, Column);
        this.observeComponentCreation2((t3, u3) => {
            Text.create('下一节');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(10);
            Text.padding({ left: 9, right: 9, top: 4, bottom: 4 });
            Text.backgroundColor('#29FFFFFF');
            Text.borderRadius(12);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r3, s3) => {
            Text.create(this.courses.length > 0 ? this.courses[0].name : '今日无课');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(22);
            Text.fontWeight(FontWeight.Bold);
            Text.margin({ top: 10 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((p3, q3) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.CourseMeta.bind(this)({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '10:00 · 进行中');
        this.observeComponentCreation2((n3, o3) => {
            Blank.create();
            Blank.height(8);
        }, Blank);
        Blank.pop();
        this.CourseMeta.bind(this)({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, this.courses.length > 0 ? `${this.courses[0].teacher_name ?? '教师待定'} · ${this.courses[0].semester ?? '本学期'}` : '今日可自由安排');
        Column.pop();
        this.observeComponentCreation2((l3, m3) => {
            Column.create();
            Column.layoutWeight(0.98);
            Column.height(166);
            Column.padding({ left: 12, right: 12 });
            Column.justifyContent(FlexAlign.Center);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(18);
        }, Column);
        this.TimelineRow.bind(this)(this.courses.length > 1 ? this.courses[1].name : '高等数学', this.courses.length > 1 ? (this.courses[1].teacher_name ?? '教师待定') : '08:00 · B-301', '已结束', false);
        this.observeComponentCreation2((j3, k3) => {
            Divider.create();
            Divider.color(this.palette().line);
            Divider.strokeWidth(1);
        }, Divider);
        this.TimelineRow.bind(this)(this.courses.length > 2 ? this.courses[2].name : '计算机网络', this.courses.length > 2 ? (this.courses[2].teacher_name ?? '教师待定') : '14:00 · A-105', '未开始', true);
        Column.pop();
        Row.pop();
        Column.pop();
    }
    StudyOverview(h2 = null) {
        this.observeComponentCreation2((g3, h3) => {
            Column.create();
            Column.layoutWeight(0.88);
            Column.height(191);
            Column.padding(15);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(22);
        }, Column);
        this.observeComponentCreation2((e3, f3) => {
            Row.create();
        }, Row);
        this.observeComponentCreation2((c3, d3) => {
            Text.create('学习总览');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((a3, b3) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((y2, z2) => {
            SymbolGlyph.create({ "id": 125832271, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(19);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
        this.observeComponentCreation2((w2, x2) => {
            Row.create();
            Row.width('100%');
            Row.layoutWeight(1);
            Row.padding(12);
            Row.alignItems(VerticalAlign.Center);
            Row.backgroundColor(this.palette().background);
            Row.borderRadius(16);
            Row.margin({ top: 12 });
        }, Row);
        this.observeComponentCreation2((u2, v2) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((s2, t2) => {
            Text.create('本周进度');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((q2, r2) => {
            Text.create('72%');
            Text.fontColor(this.palette().text);
            Text.fontSize(28);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((o2, p2) => {
            Text.create('较上周 ↑12%');
            Text.fontColor(this.palette().success);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((m2, n2) => {
            Stack.create({ alignContent: Alignment.Center });
        }, Stack);
        this.observeComponentCreation2((k2, l2) => {
            Progress.create({ value: 72, total: 100, type: ProgressType.Ring });
            Progress.width(65);
            Progress.height(65);
            Progress.color('#FF5368E8');
            Progress.backgroundColor(this.palette().soft);
            Progress.style({ strokeWidth: 7 });
        }, Progress);
        this.observeComponentCreation2((i2, j2) => {
            SymbolGlyph.create({ "id": 125831267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(22);
            SymbolGlyph.fontColor(['#FF5368E8']);
        }, SymbolGlyph);
        Stack.pop();
        Row.pop();
        Column.pop();
    }
    DeadlineRow(r1: string, s1: string, t1: boolean, u1 = null) {
        this.observeComponentCreation2((f2, g2) => {
            Row.create();
            Row.width('100%');
            Row.padding({ left: 9, right: 9, top: 10, bottom: 10 });
            Row.backgroundColor(this.palette().background);
            Row.borderRadius(12);
        }, Row);
        this.observeComponentCreation2((d2, e2) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(28);
            Stack.height(28);
            Stack.borderRadius(8);
            Stack.backgroundColor(t1 ? this.palette().soft : '#29E08A4E');
        }, Stack);
        this.observeComponentCreation2((b2, c2) => {
            SymbolGlyph.create({ "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([t1 ? this.palette().primary : '#FFFFA43A']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((z1, a2) => {
            Column.create({ space: 1 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 8 });
        }, Column);
        this.observeComponentCreation2((x1, y1) => {
            Text.create(r1);
            Text.fontColor(this.palette().text);
            Text.fontSize(10.5);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((v1, w1) => {
            Text.create(s1);
            Text.fontColor(t1 ? this.palette().danger : '#FFFFA43A');
            Text.fontSize(9.5);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    Deadlines(k1 = null) {
        this.observeComponentCreation2((p1, q1) => {
            Column.create();
            Column.layoutWeight(1.12);
            Column.height(191);
            Column.padding(15);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(22);
        }, Column);
        this.SectionTitle.bind(this)('近期截止', '更多', 'tasks');
        this.observeComponentCreation2((n1, o1) => {
            Blank.create();
            Blank.height(9);
        }, Blank);
        Blank.pop();
        this.DeadlineRow.bind(this)(this.tasks.length > 0 ? this.tasks[0].title : '暂无近期截止', this.tasks.length > 0 ? (this.tasks[0].deadline ?? this.tasks[0].due ?? '待设置') : '可以放松一下', true);
        this.observeComponentCreation2((l1, m1) => {
            Blank.create();
            Blank.height(7);
        }, Blank);
        Blank.pop();
        this.DeadlineRow.bind(this)(this.tasks.length > 1 ? this.tasks[1].title : '下一项待办', this.tasks.length > 1 ? (this.tasks[1].deadline ?? this.tasks[1].due ?? '待设置') : '暂无', false);
        Column.pop();
    }
    CampusUpdate(p: string, q: string, r: string, s: Resource, t = null) {
        this.observeComponentCreation2((i1, j1) => {
            Column.create();
            Column.width(236);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(16);
            Column.clip(true);
        }, Column);
        this.observeComponentCreation2((g1, h1) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width('100%');
            Stack.height(76);
        }, Stack);
        this.observeComponentCreation2((e1, f1) => {
            Image.create({ "id": 16777222, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height('100%');
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((c1, d1) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(r);
        }, Column);
        Column.pop();
        this.observeComponentCreation2((a1, b1) => {
            SymbolGlyph.create(s);
            SymbolGlyph.fontSize(28);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((y, z) => {
            Column.create({ space: 2 });
            Column.width('100%');
            Column.padding(11);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((w, x) => {
            Text.create(p);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((u, v) => {
            Text.create(q);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
        Column.pop();
    }
    CampusUpdates(i = null) {
        this.observeComponentCreation2((n, o) => {
            Column.create();
            Column.width('100%');
            Column.padding(16);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(24);
        }, Column);
        this.SectionTitle.bind(this)('校园动态', '查看更多', 'notifications');
        this.observeComponentCreation2((l, m) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.scrollable(ScrollDirection.Horizontal);
            Scroll.scrollBar(BarState.Off);
            Scroll.margin({ top: 12 });
        }, Scroll);
        this.observeComponentCreation2((j, k) => {
            Row.create({ space: 10 });
        }, Row);
        this.CampusUpdate.bind(this)(this.notices.length > 0 ? this.notices[0].title : '期末考试安排通知', this.notices.length > 0 ? (this.notices[0].content ?? this.notices[0].source ?? '校园通知') : '请及时查看考试时间与考场', '#9E5368E8', { "id": 125834958, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        this.CampusUpdate.bind(this)(this.notices.length > 1 ? this.notices[1].title : '创新创业比赛报名', this.notices.length > 1 ? (this.notices[1].content ?? this.notices[1].source ?? '校园通知') : '报名通道现已开放', '#8CFFA43A', { "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        Row.pop();
        Scroll.pop();
        Column.pop();
    }
    initialRender() {
        this.observeComponentCreation2((g, h) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((e, f) => {
            Column.create({ space: 14 });
            Column.width('100%');
            Column.padding({ left: 16, right: 16, top: 12, bottom: 10 });
        }, Column);
        this.HeaderProfile.bind(this)();
        this.ExamHero.bind(this)();
        this.QuickActions.bind(this)();
        this.TodayCourseCard.bind(this)();
        this.observeComponentCreation2((c, d) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.StudyOverview.bind(this)();
        this.Deadlines.bind(this)();
        Row.pop();
        this.CampusUpdates.bind(this)();
        this.observeComponentCreation2((a, b) => {
            Blank.create();
            Blank.height(92);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}
