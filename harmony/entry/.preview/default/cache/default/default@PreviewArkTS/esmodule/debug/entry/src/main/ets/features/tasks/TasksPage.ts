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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__tasks = new SynchedPropertyObjectOneWayPU(params.tasks, this, "tasks");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__filter = new ObservedPropertySimplePU('待完成', this, "filter");
        this.onRefresh = () => { };
        this.onComplete = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: TasksPage_Params) {
        if (params.tasks === undefined) {
            this.__tasks.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.filter !== undefined) {
            this.filter = params.filter;
        }
        if (params.onRefresh !== undefined) {
            this.onRefresh = params.onRefresh;
        }
        if (params.onComplete !== undefined) {
            this.onComplete = params.onComplete;
        }
    }
    updateStateVars(params: TasksPage_Params) {
        this.__tasks.reset(params.tasks);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__tasks.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__filter.purgeDependencyOnElmtId(rmElmtId);
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
    set tasks(newValue: TaskItem[]) {
        this.__tasks.set(newValue);
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
    private __filter: ObservedPropertySimplePU<string>;
    get filter() {
        return this.__filter.get();
    }
    set filter(newValue: string) {
        this.__filter.set(newValue);
    }
    private onRefresh: () => void;
    private onComplete: (id: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    pendingCount(): number { return this.tasks.filter((task: TaskItem) => task.status !== 'completed').length; }
    Hero(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(17:5)", "entry");
            Row.width('100%');
            Row.height(164);
            Row.padding(20);
            Row.alignItems(VerticalAlign.Center);
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(24);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 7 });
            Column.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(18:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('今日进度');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(19:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.pendingCount() === 0 ? '都完成啦' : `还有 ${this.pendingCount()} 项`);
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(20:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('专注当下，不必一次做完所有事');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(22:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 6 });
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(23:9)", "entry");
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832655, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(24:11)", "entry");
            SymbolGlyph.fontSize(16);
            SymbolGlyph.fontColor([this.palette().accent]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('优先处理临近截止任务');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(25:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(28:7)", "entry");
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Progress.create({ value: this.tasks.length === 0 ? 0 : (this.tasks.length - this.pendingCount()) * 100 / this.tasks.length, total: 100, type: ProgressType.Ring });
            Progress.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(29:9)", "entry");
            Progress.width(72);
            Progress.height(72);
            Progress.color(this.palette().primary);
            Progress.backgroundColor(this.palette().line);
            Progress.style({ strokeWidth: 7 });
        }, Progress);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.tasks.length === 0 ? '0%' : `${Math.round((this.tasks.length - this.pendingCount()) * 100 / this.tasks.length)}%`);
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(31:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Stack.pop();
        Row.pop();
    }
    TaskCard(task: TaskItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 10 });
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(39:5)", "entry");
            Row.width('100%');
            Row.padding({ left: 12, right: 12, top: 12, bottom: 12 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(20);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Toggle.create({ type: ToggleType.Checkbox, isOn: task.status === 'completed' });
            Toggle.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(40:7)", "entry");
            Toggle.selectedColor(this.palette().success);
            Toggle.onChange(() => this.onComplete(task.id));
        }, Toggle);
        Toggle.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 5 });
            Column.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(42:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(task.title);
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(43:9)", "entry");
            Text.fontColor(task.status === 'completed' ? this.palette().muted : this.palette().text);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Medium);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(45:9)", "entry");
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(46:11)", "entry");
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor([this.palette().accent]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(task.deadline ?? task.due ?? '待设置');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(47:11)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('·');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(48:11)", "entry");
            Text.fontColor(this.palette().muted);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(task.source_name ?? '个人安排');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(49:11)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(52:7)", "entry");
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(58:5)", "entry");
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 14 });
            Column.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(59:7)", "entry");
            Column.width('100%');
            Column.padding({ left: 16, right: 16, top: 12, bottom: 10 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(60:9)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(61:11)", "entry");
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('待办');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(62:13)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(26);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('今天先完成最重要的一小步');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(63:13)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(13);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(65:11)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('REAL');
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(65:20)", "entry");
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.Hero.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(68:9)", "entry");
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(item);
                    Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(70:13)", "entry");
                    Text.fontColor(this.filter === item ? this.palette().primary : this.palette().muted);
                    Text.fontSize(12);
                    Text.padding({ left: 13, right: 13, top: 8, bottom: 8 });
                    Text.backgroundColor(this.filter === item ? this.palette().soft : this.palette().surface);
                    Text.border({ width: 1, color: this.palette().line });
                    Text.borderRadius(12);
                    Text.onClick(() => this.filter = item);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(elmtId, ['待完成', '已完成', '全部'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(76:9)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.filter);
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(76:17)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(18);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(76:108)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${this.tasks.length} 项`);
            Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(76:117)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading && this.tasks.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(78:11)", "entry");
                        LoadingProgress.width(36);
                        LoadingProgress.height(36);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 32 });
                    }, LoadingProgress);
                });
            }
            else if (this.tasks.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Column.create({ space: 8 });
                        Column.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(80:11)", "entry");
                        Column.padding({ top: 48, bottom: 48 });
                        Column.onClick(() => this.onRefresh());
                    }, Column);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(81:13)", "entry");
                        SymbolGlyph.fontSize(38);
                        SymbolGlyph.fontColor([this.palette().success]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('待办已清空，做得不错');
                        Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(82:13)", "entry");
                        Text.fontColor(this.palette().text);
                        Text.fontSize(15);
                        Text.fontWeight(FontWeight.Bold);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('给自己留一点休息时间吧');
                        Text.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(83:13)", "entry");
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                    }, Text);
                    Text.pop();
                    Column.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = _item => {
                            const task = _item;
                            this.TaskCard.bind(this)(task);
                        };
                        this.forEachUpdateFunction(elmtId, this.tasks.filter((task: TaskItem) => this.filter === '全部' || (this.filter === '已完成' ? task.status === 'completed' : task.status !== 'completed')), forEachItemGenFunction, (task: TaskItem) => task.id, false, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/tasks/TasksPage.ets(89:9)", "entry");
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
