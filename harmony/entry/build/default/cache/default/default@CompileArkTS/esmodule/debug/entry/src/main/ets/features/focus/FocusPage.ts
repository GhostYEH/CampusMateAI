if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface FocusPage_Params {
    sessions?: StudySession[];
    activeSession?: StudySession;
    loading?: boolean;
    darkMode?: boolean;
    mode?: string;
    secondsLeft?: number;
    running?: boolean;
    timerId?: number;
    onBack?: () => void;
    onStart?: () => void;
    onPause?: () => void;
    onResume?: () => void;
    onFinish?: () => void;
}
import type { StudySession } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class FocusPage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__sessions = new SynchedPropertyObjectOneWayPU(params.sessions, this, "sessions");
        this.__activeSession = new SynchedPropertyObjectOneWayPU(params.activeSession, this, "activeSession");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__mode = new ObservedPropertySimplePU('专注', this, "mode");
        this.__secondsLeft = new ObservedPropertySimplePU(25 * 60, this, "secondsLeft");
        this.__running = new ObservedPropertySimplePU(false, this, "running");
        this.timerId = -1;
        this.onBack = () => { };
        this.onStart = () => { };
        this.onPause = () => { };
        this.onResume = () => { };
        this.onFinish = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: FocusPage_Params) {
        if (params.sessions === undefined) {
            this.__sessions.set([]);
        }
        if (params.activeSession === undefined) {
            this.__activeSession.set(undefined);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.mode !== undefined) {
            this.mode = params.mode;
        }
        if (params.secondsLeft !== undefined) {
            this.secondsLeft = params.secondsLeft;
        }
        if (params.running !== undefined) {
            this.running = params.running;
        }
        if (params.timerId !== undefined) {
            this.timerId = params.timerId;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onStart !== undefined) {
            this.onStart = params.onStart;
        }
        if (params.onPause !== undefined) {
            this.onPause = params.onPause;
        }
        if (params.onResume !== undefined) {
            this.onResume = params.onResume;
        }
        if (params.onFinish !== undefined) {
            this.onFinish = params.onFinish;
        }
    }
    updateStateVars(params: FocusPage_Params) {
        this.__sessions.reset(params.sessions);
        this.__activeSession.reset(params.activeSession);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__sessions.purgeDependencyOnElmtId(rmElmtId);
        this.__activeSession.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__mode.purgeDependencyOnElmtId(rmElmtId);
        this.__secondsLeft.purgeDependencyOnElmtId(rmElmtId);
        this.__running.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__sessions.aboutToBeDeleted();
        this.__activeSession.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__mode.aboutToBeDeleted();
        this.__secondsLeft.aboutToBeDeleted();
        this.__running.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __sessions: SynchedPropertySimpleOneWayPU<StudySession[]>;
    get sessions() {
        return this.__sessions.get();
    }
    set sessions(newValue: StudySession[]) {
        this.__sessions.set(newValue);
    }
    private __activeSession?: SynchedPropertySimpleOneWayPU<StudySession>;
    get activeSession() {
        return this.__activeSession.get();
    }
    set activeSession(newValue: StudySession) {
        this.__activeSession.set(newValue);
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
    private __mode: ObservedPropertySimplePU<string>;
    get mode() {
        return this.__mode.get();
    }
    set mode(newValue: string) {
        this.__mode.set(newValue);
    }
    private __secondsLeft: ObservedPropertySimplePU<number>;
    get secondsLeft() {
        return this.__secondsLeft.get();
    }
    set secondsLeft(newValue: number) {
        this.__secondsLeft.set(newValue);
    }
    private __running: ObservedPropertySimplePU<boolean>;
    get running() {
        return this.__running.get();
    }
    set running(newValue: boolean) {
        this.__running.set(newValue);
    }
    private timerId: number;
    private onBack: () => void;
    private onStart: () => void;
    private onPause: () => void;
    private onResume: () => void;
    private onFinish: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    aboutToDisappear(): void { this.stopClock(); }
    totalSeconds(): number { return this.mode === '专注' ? 25 * 60 : this.mode === '短休息' ? 5 * 60 : 15 * 60; }
    timeText(): string {
        const minute = Math.floor(this.secondsLeft / 60).toString().padStart(2, '0');
        const second = (this.secondsLeft % 60).toString().padStart(2, '0');
        return `${minute}:${second}`;
    }
    stopClock(): void { if (this.timerId >= 0) {
        clearInterval(this.timerId);
        this.timerId = -1;
    } }
    startClock(): void {
        if (this.running) {
            this.running = false;
            this.stopClock();
            this.onPause();
            return;
        }
        this.running = true;
        if (this.secondsLeft === this.totalSeconds())
            this.onStart();
        else
            this.onResume();
        this.timerId = setInterval(() => {
            if (this.secondsLeft > 0)
                this.secondsLeft -= 1;
            else {
                this.running = false;
                this.stopClock();
                this.onFinish();
            }
        }, 1000);
    }
    resetMode(mode: string): void { this.stopClock(); this.running = false; this.mode = mode; this.secondsLeft = this.totalSeconds(); }
    ModeTabs(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(item);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(11);
                    Text.padding({ top: 8, bottom: 8 });
                    Text.fontColor(this.mode === item ? '#FFFFFFFF' : this.palette().muted);
                    Text.backgroundColor(this.mode === item ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.mode === item ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.resetMode(item));
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(elmtId, ['专注', '短休息', '长休息'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    TimerCard(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 14 });
            Column.width('100%');
            Column.padding({ top: 20, left: 16, right: 16, bottom: 18 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(22);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(230);
            Stack.height(230);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Progress.create({ value: this.totalSeconds() - this.secondsLeft, total: this.totalSeconds(), type: ProgressType.Ring });
            Progress.width(220);
            Progress.height(220);
            Progress.color(this.palette().primary);
            Progress.backgroundColor(this.palette().soft);
            Progress.style({ strokeWidth: 10 });
        }, Progress);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 6 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832304, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(24);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.timeText());
            Text.fontColor(this.palette().primary);
            Text.fontSize(44);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.running ? '专注进行中' : this.secondsLeft !== this.totalSeconds() ? '已暂停' : '准备开始');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithChild({ type: ButtonType.Capsule });
            Button.layoutWeight(1);
            Button.height(48);
            Button.backgroundColor(this.palette().primary);
            Button.onClick(() => this.startClock());
        }, Button);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.running) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831176, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831825, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.running ? '暂停' : this.secondsLeft !== this.totalSeconds() ? '继续' : '开始专注');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        Button.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel('结束');
            Button.width(92);
            Button.height(48);
            Button.backgroundColor(this.palette().soft);
            Button.fontColor(this.palette().primary);
            Button.onClick(() => { this.stopClock(); this.running = false; this.secondsLeft = this.totalSeconds(); this.onFinish(); });
        }, Button);
        Button.pop();
        Row.pop();
        Column.pop();
    }
    Record(item: StudySession, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 10, bottom: 10 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832305, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(19);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.goal ?? '专注学习'} · ${item.started_at.substring(0, Math.min(10, item.started_at.length))}`);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${Math.max(1, Math.floor(item.duration_seconds / 60))} 分钟 · ${item.status === 'completed' ? '已完成' : '进行中'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: '专注自习', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/focus/FocusPage.ets", line: 95, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: '专注自习',
                            subtitle: '一次只做一件事，让注意力回到当下',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: '专注自习', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 20 });
        }, Column);
        this.ModeTabs.bind(this)();
        this.TimerCard.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('学习状态辅助');
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('鸿蒙端不上传画面，专注记录已真实同步后端');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('专注记录');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.width(32);
                        LoadingProgress.height(32);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin(28);
                    }, LoadingProgress);
                });
            }
            else if (this.sessions.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('还没有专注记录');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding(28);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = (_item, index: number) => {
                            const item = _item;
                            this.Record.bind(this)(item);
                            this.observeComponentCreation2((elmtId, isInitialRender) => {
                                If.create();
                                if (index < this.sessions.length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                                            Divider.create();
                                            Divider.color(this.palette().line);
                                        }, Divider);
                                    });
                                }
                                else {
                                    this.ifElseBranchUpdateFunction(1, () => {
                                    });
                                }
                            }, If);
                            If.pop();
                        };
                        this.forEachUpdateFunction(elmtId, this.sessions, forEachItemGenFunction, (item: StudySession) => item.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.height(18);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}
