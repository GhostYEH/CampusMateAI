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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__courses = new SynchedPropertyObjectOneWayPU(params.courses, this, "courses");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__selectedDay = new ObservedPropertySimplePU(0, this, "selectedDay");
        this.__selectedType = new ObservedPropertySimplePU('全部', this, "selectedType");
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: CoursesPage_Params) {
        if (params.courses === undefined) {
            this.__courses.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.selectedDay !== undefined) {
            this.selectedDay = params.selectedDay;
        }
        if (params.selectedType !== undefined) {
            this.selectedType = params.selectedType;
        }
        if (params.onRefresh !== undefined) {
            this.onRefresh = params.onRefresh;
        }
    }
    updateStateVars(params: CoursesPage_Params) {
        this.__courses.reset(params.courses);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__courses.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__selectedDay.purgeDependencyOnElmtId(rmElmtId);
        this.__selectedType.purgeDependencyOnElmtId(rmElmtId);
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
    set courses(newValue: CourseItem[]) {
        this.__courses.set(newValue);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(newValue: boolean) {
        this.__loading.set(newValue);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __selectedDay: ObservedPropertySimplePU<number>;
    get selectedDay() {
        return this.__selectedDay.get();
    }
    set selectedDay(newValue: number) {
        this.__selectedDay.set(newValue);
    }
    private __selectedType: ObservedPropertySimplePU<string>;
    get selectedType() {
        return this.__selectedType.get();
    }
    set selectedType(newValue: string) {
        this.__selectedType.set(newValue);
    }
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    Header(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Top);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 1 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('课程');
            Text.fontColor(this.palette().text);
            Text.fontSize(26);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('把这周的学习节奏握在手里');
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
    Hero(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.height(164);
            Row.padding({ left: 14, top: 13, right: 10, bottom: 11 });
            Row.linearGradient({ angle: 135, colors: [['#FF5368E8', 0.0], ['#FF7586F5', 1.0]] });
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.layoutWeight(1);
            Column.height('100%');
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 5 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Circle.create();
            Circle.width(6);
            Circle.height(6);
            Circle.fill('#FFFFC35C');
        }, Circle);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('下一节课 · 10:10');
            Text.fontColor('#D1FFFFFF');
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.courses.length > 0 ? this.courses[0].name : '今天没有课程');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(20);
            Text.fontWeight(FontWeight.Bold);
            Text.margin({ top: 5 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 3 });
            Row.margin({ top: 5 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(13);
            SymbolGlyph.fontColor(['#C7FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.courses.length > 0 ? `${this.courses[0].teacher_name ?? '教师待定'} · 教室待定` : '去添加你的课程安排');
            Text.fontColor('#C7FFFFFF');
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 16 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('课程表');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('课程详情');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 3 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E6FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('待办作业');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width(70);
            Column.height('100%');
            Column.alignItems(HorizontalAlign.Center);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(43);
            Stack.height(43);
            Stack.backgroundColor('#2EFFFFFF');
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125833750, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(24);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
    WeekStrip(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.padding({ top: 8, bottom: 8 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(14);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = (_item, index: number) => {
                const day = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Column.create({ space: 3 });
                    Column.layoutWeight(1);
                    Column.onClick(() => this.selectedDay = index);
                }, Column);
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(day);
                    Text.fontColor(this.selectedDay === index ? this.palette().primary : this.palette().muted);
                    Text.fontSize(9);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create((12 + index).toString());
                    Text.fontColor(this.selectedDay === index ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontSize(10);
                    Text.fontWeight(FontWeight.Bold);
                    Text.textAlign(TextAlign.Center);
                    Text.width(25);
                    Text.height(25);
                    Text.backgroundColor(this.selectedDay === index ? this.palette().primary : Color.Transparent);
                    Text.borderRadius(13);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Circle.create();
                    Circle.width(4);
                    Circle.height(4);
                    Circle.fill(index === 2 || index === 4 ? this.palette().accent : this.palette().line);
                }, Circle);
                Column.pop();
            };
            this.forEachUpdateFunction(elmtId, ['一', '二', '三', '四', '五', '六', '日'], forEachItemGenFunction, undefined, true, false);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    Metrics(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
    Metric(value: string, label: string, symbol: Resource, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Center);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.fontSize(15);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(value);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
    }
    Filters(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const label = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(label);
                    Text.fontColor(this.selectedType === label ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontSize(10);
                    Text.fontWeight(this.selectedType === label ? FontWeight.Bold : FontWeight.Normal);
                    Text.padding({ left: 11, right: 11, top: 7, bottom: 7 });
                    Text.backgroundColor(this.selectedType === label ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.selectedType === label ? this.palette().primary : this.palette().line });
                    Text.borderRadius(20);
                    Text.onClick(() => this.selectedType = label);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(elmtId, ['全部', '专业课', '公共课'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    CourseCard(course: CourseItem, index: number, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 9 });
            Row.width('100%');
            Row.padding({ left: 11, right: 11, top: 10, bottom: 10 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(14);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(10);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create((course.code ?? '课').substring(0, Math.min(2, (course.code ?? '课').length)));
            Text.fontColor(this.palette().primary);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(course.name);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${course.teacher_name ?? '教师待定'} · ${course.semester ?? '本学期'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(course.code ?? `COURSE-${index + 1}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('96%');
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 10 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, top: 12, bottom: 10 });
        }, Column);
        this.Header.bind(this)();
        this.Hero.bind(this)();
        this.WeekStrip.bind(this)();
        this.Metrics.bind(this)();
        this.Filters.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 1 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('本学期课程');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('按课程卡片查看上课地点与资料');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${this.courses.length} 门`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading && this.courses.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = (_item, index: number) => {
                            const course = _item;
                            this.CourseCard.bind(this)(course, index);
                        };
                        this.forEachUpdateFunction(elmtId, this.courses, forEachItemGenFunction, (course: CourseItem) => course.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
