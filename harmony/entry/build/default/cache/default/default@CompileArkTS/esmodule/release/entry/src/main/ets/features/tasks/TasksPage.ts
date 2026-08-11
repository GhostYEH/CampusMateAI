if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface TasksPage_Params {
    tasks?: TaskItem[];
    loading?: boolean;
    darkMode?: boolean;
    filter?: string;
    onRefresh?: () => void;
    onComplete?: (id: string) => void;
}
import type { TaskItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
export class TasksPage extends ViewPU {
    constructor(o17, p17, q17, r17 = -1, s17 = undefined, t17) {
        super(o17, q17, r17, t17);
        if (typeof s17 === "function") {
            this.paramsGenerator_ = s17;
        }
        this.__tasks = new SynchedPropertyObjectOneWayPU(p17.tasks, this, "tasks");
        this.__loading = new SynchedPropertySimpleOneWayPU(p17.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(p17.darkMode, this, "darkMode");
        this.__filter = new ObservedPropertySimplePU('待完成', this, "filter");
        this.onRefresh = () => { };
        this.onComplete = () => { };
        this.setInitiallyProvidedValue(p17);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(n17: TasksPage_Params) {
        if (n17.tasks === undefined) {
            this.__tasks.set([]);
        }
        if (n17.loading === undefined) {
            this.__loading.set(false);
        }
        if (n17.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (n17.filter !== undefined) {
            this.filter = n17.filter;
        }
        if (n17.onRefresh !== undefined) {
            this.onRefresh = n17.onRefresh;
        }
        if (n17.onComplete !== undefined) {
            this.onComplete = n17.onComplete;
        }
    }
    updateStateVars(m17: TasksPage_Params) {
        this.__tasks.reset(m17.tasks);
        this.__loading.reset(m17.loading);
        this.__darkMode.reset(m17.darkMode);
    }
    purgeVariableDependenciesOnElmtId(l17) {
        this.__tasks.purgeDependencyOnElmtId(l17);
        this.__loading.purgeDependencyOnElmtId(l17);
        this.__darkMode.purgeDependencyOnElmtId(l17);
        this.__filter.purgeDependencyOnElmtId(l17);
    }
    aboutToBeDeleted() {
        this.__tasks.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__filter.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __tasks: SynchedPropertySimpleOneWayPU<TaskItem[]>;
    get tasks() {
        return this.__tasks.get();
    }
    set tasks(k17: TaskItem[]) {
        this.__tasks.set(k17);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(j17: boolean) {
        this.__loading.set(j17);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(i17: boolean) {
        this.__darkMode.set(i17);
    }
    private __filter: ObservedPropertySimplePU<string>;
    get filter() {
        return this.__filter.get();
    }
    set filter(h17: string) {
        this.__filter.set(h17);
    }
    private onRefresh: () => void;
    private onComplete: (id: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    pendingCount(): number { return this.tasks.filter((g17: TaskItem) => g17.status !== 'completed').length; }
    Hero(j16 = null) {
        this.observeComponentCreation2((e17, f17) => {
            Row.create();
            Row.width('100%');
            Row.height(164);
            Row.padding(20);
            Row.alignItems(VerticalAlign.Center);
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(24);
        }, Row);
        this.observeComponentCreation2((c17, d17) => {
            Column.create({ space: 7 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((a17, b17) => {
            Text.create('今日进度');
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((y16, z16) => {
            Text.create(this.pendingCount() === 0 ? '都完成啦' : `还有 ${this.pendingCount()} 项`);
            Text.fontColor(this.palette().text);
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((w16, x16) => {
            Text.create('专注当下，不必一次做完所有事');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((u16, v16) => {
            Row.create({ space: 6 });
        }, Row);
        this.observeComponentCreation2((s16, t16) => {
            SymbolGlyph.create({ "id": 125832655, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(16);
            SymbolGlyph.fontColor([this.palette().accent]);
        }, SymbolGlyph);
        this.observeComponentCreation2((q16, r16) => {
            Text.create('优先处理临近截止任务');
            Text.fontColor(this.palette().text);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((o16, p16) => {
            Stack.create({ alignContent: Alignment.Center });
        }, Stack);
        this.observeComponentCreation2((m16, n16) => {
            Progress.create({ value: this.tasks.length === 0 ? 0 : (this.tasks.length - this.pendingCount()) * 100 / this.tasks.length, total: 100, type: ProgressType.Ring });
            Progress.width(72);
            Progress.height(72);
            Progress.color(this.palette().primary);
            Progress.backgroundColor(this.palette().line);
            Progress.style({ strokeWidth: 7 });
        }, Progress);
        this.observeComponentCreation2((k16, l16) => {
            Text.create(this.tasks.length === 0 ? '0%' : `${Math.round((this.tasks.length - this.pendingCount()) * 100 / this.tasks.length)}%`);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Stack.pop();
        Row.pop();
    }
    TaskCard(n15: TaskItem, o15 = null) {
        this.observeComponentCreation2((h16, i16) => {
            Row.create({ space: 10 });
            Row.width('100%');
            Row.padding({ left: 12, right: 12, top: 12, bottom: 12 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(20);
        }, Row);
        this.observeComponentCreation2((f16, g16) => {
            Toggle.create({ type: ToggleType.Checkbox, isOn: n15.status === 'completed' });
            Toggle.selectedColor(this.palette().success);
            Toggle.onChange(() => this.onComplete(n15.id));
        }, Toggle);
        Toggle.pop();
        this.observeComponentCreation2((d16, e16) => {
            Column.create({ space: 5 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((b16, c16) => {
            Text.create(n15.title);
            Text.fontColor(n15.status === 'completed' ? this.palette().muted : this.palette().text);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Medium);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((z15, a16) => {
            Row.create({ space: 7 });
        }, Row);
        this.observeComponentCreation2((x15, y15) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor([this.palette().accent]);
        }, SymbolGlyph);
        this.observeComponentCreation2((v15, w15) => {
            Text.create(n15.deadline ?? n15.due ?? '待设置');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t15, u15) => {
            Text.create('·');
            Text.fontColor(this.palette().muted);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r15, s15) => {
            Text.create(n15.source_name ?? '个人安排');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((p15, q15) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((l15, m15) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((j15, k15) => {
            Column.create({ space: 14 });
            Column.width('100%');
            Column.padding({ left: 16, right: 16, top: 12, bottom: 10 });
        }, Column);
        this.observeComponentCreation2((h15, i15) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((f15, g15) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((d15, e15) => {
            Text.create('待办');
            Text.fontColor(this.palette().text);
            Text.fontSize(26);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((b15, c15) => {
            Text.create('今天先完成最重要的一小步');
            Text.fontColor(this.palette().muted);
            Text.fontSize(13);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((z14, a15) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((x14, y14) => {
            Text.create('REAL');
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.Hero.bind(this)();
        this.observeComponentCreation2((v14, w14) => {
            Row.create({ space: 8 });
        }, Row);
        this.observeComponentCreation2((o14, p14) => {
            ForEach.create();
            const q14 = r14 => {
                const s14 = r14;
                this.observeComponentCreation2((t14, u14) => {
                    Text.create(s14);
                    Text.fontColor(this.filter === s14 ? this.palette().primary : this.palette().muted);
                    Text.fontSize(12);
                    Text.padding({ left: 13, right: 13, top: 8, bottom: 8 });
                    Text.backgroundColor(this.filter === s14 ? this.palette().soft : this.palette().surface);
                    Text.border({ width: 1, color: this.palette().line });
                    Text.borderRadius(12);
                    Text.onClick(() => this.filter = s14);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(o14, ['待完成', '已完成', '全部'], q14);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((m14, n14) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((k14, l14) => {
            Text.create(this.filter);
            Text.fontColor(this.palette().text);
            Text.fontSize(18);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((i14, j14) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((g14, h14) => {
            Text.create(`${this.tasks.length} 项`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((n13, o13) => {
            If.create();
            if (this.loading && this.tasks.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((e14, f14) => {
                        LoadingProgress.create();
                        LoadingProgress.width(36);
                        LoadingProgress.height(36);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 32 });
                    }, LoadingProgress);
                });
            }
            else if (this.tasks.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((c14, d14) => {
                        Column.create({ space: 8 });
                        Column.padding({ top: 48, bottom: 48 });
                        Column.onClick(() => this.onRefresh());
                    }, Column);
                    this.observeComponentCreation2((a14, b14) => {
                        SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(38);
                        SymbolGlyph.fontColor([this.palette().success]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((y13, z13) => {
                        Text.create('待办已清空，做得不错');
                        Text.fontColor(this.palette().text);
                        Text.fontSize(15);
                        Text.fontWeight(FontWeight.Bold);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((w13, x13) => {
                        Text.create('给自己留一点休息时间吧');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                    }, Text);
                    Text.pop();
                    Column.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((p13, q13) => {
                        ForEach.create();
                        const r13 = u13 => {
                            const v13 = u13;
                            this.TaskCard.bind(this)(v13);
                        };
                        this.forEachUpdateFunction(p13, this.tasks.filter((t13: TaskItem) => this.filter === '全部' || (this.filter === '已完成' ? t13.status === 'completed' : t13.status !== 'completed')), r13, (s13: TaskItem) => s13.id, false, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((l13, m13) => {
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
