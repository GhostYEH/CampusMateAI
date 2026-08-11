if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface CoursesPage_Params {
    courses?: CourseItem[];
    loading?: boolean;
    darkMode?: boolean;
    selectedDay?: number;
    selectedType?: string;
    onRefresh?: () => void;
}
import type { CourseItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
export class CoursesPage extends ViewPU {
    constructor(s9, t9, u9, v9 = -1, w9 = undefined, x9) {
        super(s9, u9, v9, x9);
        if (typeof w9 === "function") {
            this.paramsGenerator_ = w9;
        }
        this.__courses = new SynchedPropertyObjectOneWayPU(t9.courses, this, "courses");
        this.__loading = new SynchedPropertySimpleOneWayPU(t9.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(t9.darkMode, this, "darkMode");
        this.__selectedDay = new ObservedPropertySimplePU(0, this, "selectedDay");
        this.__selectedType = new ObservedPropertySimplePU('全部', this, "selectedType");
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(t9);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(r9: CoursesPage_Params) {
        if (r9.courses === undefined) {
            this.__courses.set([]);
        }
        if (r9.loading === undefined) {
            this.__loading.set(false);
        }
        if (r9.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (r9.selectedDay !== undefined) {
            this.selectedDay = r9.selectedDay;
        }
        if (r9.selectedType !== undefined) {
            this.selectedType = r9.selectedType;
        }
        if (r9.onRefresh !== undefined) {
            this.onRefresh = r9.onRefresh;
        }
    }
    updateStateVars(q9: CoursesPage_Params) {
        this.__courses.reset(q9.courses);
        this.__loading.reset(q9.loading);
        this.__darkMode.reset(q9.darkMode);
    }
    purgeVariableDependenciesOnElmtId(p9) {
        this.__courses.purgeDependencyOnElmtId(p9);
        this.__loading.purgeDependencyOnElmtId(p9);
        this.__darkMode.purgeDependencyOnElmtId(p9);
        this.__selectedDay.purgeDependencyOnElmtId(p9);
        this.__selectedType.purgeDependencyOnElmtId(p9);
    }
    aboutToBeDeleted() {
        this.__courses.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__selectedDay.aboutToBeDeleted();
        this.__selectedType.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __courses: SynchedPropertySimpleOneWayPU<CourseItem[]>;
    get courses() {
        return this.__courses.get();
    }
    set courses(o9: CourseItem[]) {
        this.__courses.set(o9);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(n9: boolean) {
        this.__loading.set(n9);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(m9: boolean) {
        this.__darkMode.set(m9);
    }
    private __selectedDay: ObservedPropertySimplePU<number>;
    get selectedDay() {
        return this.__selectedDay.get();
    }
    set selectedDay(l9: number) {
        this.__selectedDay.set(l9);
    }
    private __selectedType: ObservedPropertySimplePU<string>;
    get selectedType() {
        return this.__selectedType.get();
    }
    set selectedType(k9: string) {
        this.__selectedType.set(k9);
    }
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    Header(x8 = null) {
        this.observeComponentCreation2((i9, j9) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Top);
        }, Row);
        this.observeComponentCreation2((g9, h9) => {
            Column.create({ space: 1 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((e9, f9) => {
            Text.create('课程');
            Text.fontColor(this.palette().text);
            Text.fontSize(26);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((c9, d9) => {
            Text.create('把这周的学习节奏握在手里');
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((a9, b9) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((y8, z8) => {
            Text.create('REAL');
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
            Text.padding({ left: 8, right: 8, top: 5, bottom: 5 });
            Text.backgroundColor(this.darkMode ? '#273D614A' : '#164E8C6A');
            Text.borderRadius(12);
        }, Text);
        Text.pop();
        Row.pop();
    }
    Hero(y6 = null) {
        this.observeComponentCreation2((v8, w8) => {
            Row.create();
            Row.width('100%');
            Row.height(164);
            Row.padding({ left: 14, top: 13, right: 10, bottom: 11 });
            Row.linearGradient({ angle: 135, colors: [['#FF5368E8', 0.0], ['#FF7586F5', 1.0]] });
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((t8, u8) => {
            Column.create();
            Column.layoutWeight(1);
            Column.height('100%');
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((r8, s8) => {
            Row.create({ space: 5 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((p8, q8) => {
            Circle.create();
            Circle.width(6);
            Circle.height(6);
            Circle.fill('#FFFFC35C');
        }, Circle);
        this.observeComponentCreation2((n8, o8) => {
            Text.create('下一节课 · 10:10');
            Text.fontColor('#D1FFFFFF');
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((l8, m8) => {
            Text.create(this.courses.length > 0 ? this.courses[0].name : '今天没有课程');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(20);
            Text.fontWeight(FontWeight.Bold);
            Text.margin({ top: 5 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j8, k8) => {
            Row.create({ space: 3 });
            Row.margin({ top: 5 });
        }, Row);
        this.observeComponentCreation2((h8, i8) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(13);
            SymbolGlyph.fontColor(['#C7FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((f8, g8) => {
            Text.create(this.courses.length > 0 ? `${this.courses[0].teacher_name ?? '教师待定'} · 教室待定` : '去添加你的课程安排');
            Text.fontColor('#C7FFFFFF');
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((d8, e8) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((b8, c8) => {
            Row.create({ space: 16 });
        }, Row);
        this.observeComponentCreation2((z7, a8) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((x7, y7) => {
            SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((v7, w7) => {
            Text.create('课程表');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((t7, u7) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((r7, s7) => {
            SymbolGlyph.create({ "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((p7, q7) => {
            Text.create('课程详情');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((n7, o7) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((l7, m7) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((j7, k7) => {
            Text.create('待办作业');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((h7, i7) => {
            Column.create();
            Column.width(70);
            Column.height('100%');
            Column.alignItems(HorizontalAlign.Center);
        }, Column);
        this.observeComponentCreation2((f7, g7) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(43);
            Stack.height(43);
            Stack.backgroundColor('#2EFFFFFF');
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((d7, e7) => {
            SymbolGlyph.create({ "id": 125833750, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(24);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((b7, c7) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((z6, a7) => {
            Text.create('去查看 →');
            Text.fontColor('#FF5368E8');
            Text.fontSize(10);
            Text.fontWeight(FontWeight.Bold);
            Text.padding({ left: 10, right: 10, top: 6, bottom: 6 });
            Text.backgroundColor('#E6FFFFFF');
            Text.borderRadius(14);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    WeekStrip(h6 = null) {
        this.observeComponentCreation2((w6, x6) => {
            Row.create();
            Row.width('100%');
            Row.padding({ top: 8, bottom: 8 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(14);
        }, Row);
        this.observeComponentCreation2((i6, j6) => {
            ForEach.create();
            const k6 = (l6, m6: number) => {
                const n6 = l6;
                this.observeComponentCreation2((u6, v6) => {
                    Column.create({ space: 3 });
                    Column.layoutWeight(1);
                    Column.onClick(() => this.selectedDay = m6);
                }, Column);
                this.observeComponentCreation2((s6, t6) => {
                    Text.create(n6);
                    Text.fontColor(this.selectedDay === m6 ? this.palette().primary : this.palette().muted);
                    Text.fontSize(9);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((q6, r6) => {
                    Text.create((12 + m6).toString());
                    Text.fontColor(this.selectedDay === m6 ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontSize(10);
                    Text.fontWeight(FontWeight.Bold);
                    Text.textAlign(TextAlign.Center);
                    Text.width(25);
                    Text.height(25);
                    Text.backgroundColor(this.selectedDay === m6 ? this.palette().primary : Color.Transparent);
                    Text.borderRadius(13);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((o6, p6) => {
                    Circle.create();
                    Circle.width(4);
                    Circle.height(4);
                    Circle.fill(m6 === 2 || m6 === 4 ? this.palette().accent : this.palette().line);
                }, Circle);
                Column.pop();
            };
            this.forEachUpdateFunction(i6, ['一', '二', '三', '四', '五', '六', '日'], k6, undefined, true, false);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    Metrics(e6 = null) {
        this.observeComponentCreation2((f6, g6) => {
            Row.create();
            Row.width('100%');
            Row.padding({ top: 10, bottom: 10 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(14);
        }, Row);
        this.Metric.bind(this)(this.courses.length.toString(), '门课程', { "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        this.Metric.bind(this)('18', '本周学时', { "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        this.Metric.bind(this)('26.5', '已修学分', { "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        this.Metric.bind(this)('96%', '出勤率', { "id": 125832315, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
        Row.pop();
    }
    Metric(q5: string, r5: string, s5: Resource, t5 = null) {
        this.observeComponentCreation2((c6, d6) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Center);
        }, Column);
        this.observeComponentCreation2((a6, b6) => {
            Row.create({ space: 4 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((y5, z5) => {
            SymbolGlyph.create(s5);
            SymbolGlyph.fontSize(15);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((w5, x5) => {
            Text.create(q5);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((u5, v5) => {
            Text.create(r5);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
    }
    Filters(g5 = null) {
        this.observeComponentCreation2((o5, p5) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((h5, i5) => {
            ForEach.create();
            const j5 = k5 => {
                const l5 = k5;
                this.observeComponentCreation2((m5, n5) => {
                    Text.create(l5);
                    Text.fontColor(this.selectedType === l5 ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontSize(10);
                    Text.fontWeight(this.selectedType === l5 ? FontWeight.Bold : FontWeight.Normal);
                    Text.padding({ left: 11, right: 11, top: 7, bottom: 7 });
                    Text.backgroundColor(this.selectedType === l5 ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.selectedType === l5 ? this.palette().primary : this.palette().line });
                    Text.borderRadius(20);
                    Text.onClick(() => this.selectedType = l5);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(h5, ['全部', '专业课', '公共课'], j5);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    CourseCard(l4: CourseItem, m4: number, n4 = null) {
        this.observeComponentCreation2((e5, f5) => {
            Row.create({ space: 9 });
            Row.width('100%');
            Row.padding({ left: 11, right: 11, top: 10, bottom: 10 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(14);
        }, Row);
        this.observeComponentCreation2((c5, d5) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(10);
        }, Stack);
        this.observeComponentCreation2((a5, b5) => {
            Text.create((l4.code ?? '课').substring(0, Math.min(2, (l4.code ?? '课').length)));
            Text.fontColor(this.palette().primary);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Stack.pop();
        this.observeComponentCreation2((y4, z4) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((w4, x4) => {
            Text.create(l4.name);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((u4, v4) => {
            Text.create(`${l4.teacher_name ?? '教师待定'} · ${l4.semester ?? '本学期'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((s4, t4) => {
            Text.create(l4.code ?? `COURSE-${m4 + 1}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((q4, r4) => {
            Text.create('96%');
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((o4, p4) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((j4, k4) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((h4, i4) => {
            Column.create({ space: 10 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, top: 12, bottom: 10 });
        }, Column);
        this.Header.bind(this)();
        this.Hero.bind(this)();
        this.WeekStrip.bind(this)();
        this.Metrics.bind(this)();
        this.Filters.bind(this)();
        this.observeComponentCreation2((f4, g4) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((d4, e4) => {
            Column.create({ space: 1 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((b4, c4) => {
            Text.create('本学期课程');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((z3, a4) => {
            Text.create('按课程卡片查看上课地点与资料');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((x3, y3) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((v3, w3) => {
            Text.create(`${this.courses.length} 门`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((i3, j3) => {
            If.create();
            if (this.loading && this.courses.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((t3, u3) => {
                        LoadingProgress.create();
                        LoadingProgress.width(36);
                        LoadingProgress.height(36);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 40 });
                    }, LoadingProgress);
                });
            }
            else if (this.courses.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((r3, s3) => {
                        Text.create('暂时没有课程，点击刷新重试');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(13);
                        Text.padding(32);
                        Text.onClick(() => this.onRefresh());
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((k3, l3) => {
                        ForEach.create();
                        const m3 = (o3, p3: number) => {
                            const q3 = o3;
                            this.CourseCard.bind(this)(q3, p3);
                        };
                        this.forEachUpdateFunction(k3, this.courses, m3, (n3: CourseItem) => n3.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((g3, h3) => {
            Blank.create();
            Blank.height(98);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}
